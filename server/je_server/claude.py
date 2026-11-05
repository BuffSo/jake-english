"""Claude calls (ADR-0004). Only text goes out: lines, transcripts, the Mac's findings, the situation."""
from __future__ import annotations

import json
import logging
import time
from collections.abc import AsyncIterator
from typing import Any

import anthropic
from pydantic import ValidationError

from . import prompts
from .models import Draft, Frame, Issue, Offscript, ThreeLine
from .threeline import Problem, check, degrade, plain

# Spec 「기다리는 시간과 모델」: Haiku with thinking off for quick wording, Sonnet with thinking off and low
# effort for writing. No temperature/top_p/top_k: API version 2026-10-21 rejects them.
HAIKU: dict[str, Any] = {"model": "claude-haiku-5-5", "thinking": {"type": "disabled"}}
SONNET: dict[str, Any] = {"model": "claude-sonnet-5-5", "thinking": {"type": "between_tools"}, "effort": "low"}

log = logging.getLogger("je_server")
USER_TURNS = (4, 6)
USER_MAX_WORDS = 14
ANNOTATE_TRIES = 3


ERRORS = (anthropic.APIConnectionError, anthropic.RateLimitError)


class ClaudeUnavailable(Exception):
    """No answer right now: no internet, rate limit, server error, timeout or refusal."""


def _problems_text(problems: list[str]) -> str:
    return "\n".join(f"- {p}" for p in problems)


class Claude:
    def __init__(self, client: Any, writer: dict[str, Any] = SONNET, quick: dict[str, Any] = HAIKU):
        self.client = client
        self.writer = writer
        self.quick = quick

    def _request(self, model: dict[str, Any], output_config: dict[str, Any]) -> dict[str, Any]:
        kw = {k: v for k, v in model.items() if k != "effort"}
        if "effort" in model:
            output_config = {**output_config, "effort": model["effort"]}
        kw["output_config"] = output_config
        return kw

    async def _create(self, **kw):
        try:
            resp = await self.client.messages.create(**kw)
        except anthropic.APIConnectionError as e:  # includes timeouts
            raise ClaudeUnavailable("connection") from e
        except anthropic.RateLimitError as e:
            raise ClaudeUnavailable("rate limit") from e
        except anthropic.APIStatusError as e:
            if e.status_code >= 500:
                raise ClaudeUnavailable(f"status {e.status_code}") from e
            raise
        if resp.stop_reason == "refusal":
            raise ClaudeUnavailable("refusal")
        return resp

    async def _json(self, model: dict[str, Any], system: str, user: str, schema: dict, max_tokens: int) -> Any:
        """Returns parsed JSON, or None when the answer is not valid JSON."""
        resp = await self._create(
            **self._request(model, {"format": {"type": "json_schema", "schema": schema}}),
            max_tokens=max_tokens, system=system, messages=[{"role": "user", "content": user}],
        )
        text = next((b.text for b in resp.content if b.type == "text"), "")
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return None

    # --- script -------------------------------------------------------------------------------

    @staticmethod
    def script_problems(draft: Draft) -> list[str]:
        out = []
        if not draft:
            return ["the script is empty"]
        if draft[0][0] != "ryan" or draft[-1][0] != "ryan":
            out.append("Ryan must speak first and last")
        if any(a[0] == b[0] for a, b in zip(draft, draft[1:])):
            out.append("lines must alternate between Ryan and the learner")
        turns = sum(1 for s, _ in draft if s == "user")
        if not USER_TURNS[0] <= turns <= USER_TURNS[1]:
            out.append(f"the learner must have {USER_TURNS[0]} to {USER_TURNS[1]} lines, not {turns}")
        if any(s == "user" and len(t.split()) > USER_MAX_WORDS for s, t in draft):
            out.append(f"learner lines must be at most {USER_MAX_WORDS - 2} words")
        return out

    async def make_script(self, situation: str) -> tuple[Frame, Draft]:
        user = f"상황: {situation}"
        problems: list[str] = []
        for _ in range(2):
            content = user if not problems else f"{user}\n\nThe last script had problems. Fix them:\n{_problems_text(problems)}"
            data = await self._json(self.writer, prompts.SCRIPT_SYSTEM, content, prompts.SCRIPT_SCHEMA, 4000)
            try:
                frame = Frame.model_validate(data["frame"])
                draft: Draft = [(l["speaker"], l["text"].strip()) for l in data["lines"]]
            except (TypeError, KeyError, ValidationError):
                problems = ["the answer did not follow the JSON format"]
                continue
            problems = self.script_problems(draft)
            if not problems:
                return frame, draft
        raise ClaudeUnavailable("could not get a valid script")

    # --- three lines --------------------------------------------------------------------------

    async def annotate(self, text: str, context: str) -> ThreeLine:
        base = f"Line: {text}\nContext: {context or '-'}"
        last: ThreeLine | None = None
        problems: list[Problem] = []
        t0 = time.perf_counter()
        for tries in range(1, ANNOTATE_TRIES + 1):
            content = base if last is None else (
                f"{base}\n\nThe last answer failed these checks. Fix them:\n"
                + _problems_text([f"{p.kind}: {p.detail}" for p in problems]))
            data = await self._json(self.writer, prompts.THREE_SYSTEM, content, prompts.THREE_SCHEMA, 4000)
            try:
                three = ThreeLine.model_validate(data)
            except ValidationError:
                continue
            problems = check(text, three)
            if not problems:
                log.info("three-line note: %d tries, %.1fs", tries, time.perf_counter() - t0)
                return three
            last = three
        log.info("three-line note degraded after %d tries, %.1fs: %s", ANNOTATE_TRIES, time.perf_counter() - t0,
                 ",".join(sorted({p.kind for p in problems})))
        return degrade(text, last, problems) if last is not None else plain(text)

    # --- recommendation -----------------------------------------------------------------------

    async def recommend(self, recent: list[str]) -> str:
        listed = "\n".join(f"- {r}" for r in recent) or "- 없음"
        data = await self._json(self.quick, prompts.RECOMMEND_SYSTEM, f"최근 상황:\n{listed}",
                                prompts.RECOMMEND_SCHEMA, 300)
        text = (data or {}).get("request_ko", "").strip() if isinstance(data, dict) else ""
        if not text:
            raise ClaudeUnavailable("empty recommendation")
        return text

    # --- the learner said something else -------------------------------------------------------

    @staticmethod
    def _talk(frame: Frame, history: Draft) -> dict:
        return {"상황": frame.model_dump(), "지금까지 대화": [{"speaker": s, "text": t} for s, t in history]}

    async def offscript(self, frame: Frame, history: Draft, expected: str, heard: str) -> Offscript:
        body = {**self._talk(frame, history), "대본의 대사": expected, "학습자가 한 말(받아쓴 글)": heard}
        data = await self._json(self.writer, prompts.OFFSCRIPT_SYSTEM, json.dumps(body, ensure_ascii=False),
                                prompts.OFFSCRIPT_SCHEMA, 1000)
        try:
            out = Offscript.model_validate(data)
        except ValidationError as e:
            raise ClaudeUnavailable("bad off-script answer") from e
        if not out.reply_en.strip():
            raise ClaudeUnavailable("empty reply")
        return out

    async def continue_script(self, frame: Frame, history: Draft, user_turns: int) -> Draft:
        body = json.dumps({**self._talk(frame, history), "학습자 대사 수": user_turns}, ensure_ascii=False)
        problems: list[str] = []
        for _ in range(2):
            content = body if not problems else f"{body}\n\nThe last answer had problems. Fix them:\n{_problems_text(problems)}"
            data = await self._json(self.writer, prompts.CONTINUE_SYSTEM, content, prompts.CONTINUE_SCHEMA, 3000)
            try:
                draft: Draft = [(l["speaker"], l["text"].strip()) for l in data["lines"]]
            except (TypeError, KeyError):
                problems = ["the answer did not follow the JSON format"]
                continue
            problems = []
            if not draft or draft[0][0] != "user" or draft[-1][0] != "ryan":
                problems.append("start with the learner and end with Ryan")
            if any(a[0] == b[0] for a, b in zip(draft, draft[1:])):
                problems.append("lines must alternate")
            turns = sum(1 for sp, _ in draft if sp == "user")
            if not max(1, user_turns - 1) <= turns <= user_turns + 1:
                problems.append(f"the learner must have {user_turns} lines, not {turns}")
            if not problems:
                return draft
        raise ClaudeUnavailable("could not continue the script")

    # --- feedback on a followed line ----------------------------------------------------------

    async def feedback(self, line: str, heard: str, praise: list[str], issues: list[Issue]) -> AsyncIterator[str]:
        """Streams Ryan's Korean feedback. Only the line, the transcript and the Mac's findings go out."""
        found = {
            "대사": line,
            "들린 말": heard,
            "잘한 점 후보": praise,
            "짚을 것": [{"대사 낱말": i.target, "들린 낱말": i.heard, "소리 내는 법": i.explain} for i in issues],
        }
        kw = {k: v for k, v in self.quick.items() if k != "effort"}
        try:
            async with self.client.messages.stream(
                **kw, max_tokens=800, system=prompts.FEEDBACK_SYSTEM,
                messages=[{"role": "user", "content": json.dumps(found, ensure_ascii=False)}],
            ) as stream:
                async for text in stream.text_stream:
                    yield text
        except ERRORS as e:
            raise ClaudeUnavailable(type(e).__name__) from e
        except anthropic.APIStatusError as e:
            if e.status_code >= 500:
                raise ClaudeUnavailable(f"status {e.status_code}") from e
            raise
