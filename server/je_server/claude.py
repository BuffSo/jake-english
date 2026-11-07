"""Claude calls (ADR-0004). Only text goes out: lines, transcripts, the Mac's findings, the situation."""
from __future__ import annotations

import json
import logging
import re
import time
from collections.abc import AsyncIterator, Sequence
from typing import Any

import anthropic
from pydantic import ValidationError

from . import prompts
from .models import Draft, Frame, Issue, Speaker, ThreeLine
from .threeline import Problem, check, degrade, plain
from .topics import Topic

# Spec 「기다리는 시간과 모델」: Haiku with thinking off for quick wording, Sonnet with thinking off and low
# effort for writing. No temperature/top_p/top_k: API version 2026-10-21 rejects them.
HAIKU: dict[str, Any] = {"model": "claude-haiku-5-5", "thinking": {"type": "disabled"}}
SONNET: dict[str, Any] = {"model": "claude-sonnet-5-5", "thinking": {"type": "between_tools"}, "effort": "low"}

# The models server/.env can pick (JE_CLAUDE_WRITER, JE_CLAUDE_QUICK; defaults Sonnet and Haiku, the spec's). A role
# keeps its settings and only the model changes: writing has thinking off and effort low, quick wording has thinking
# off and no effort (feedback() streams without output_config). Opus 5.5 rejects disabled thinking with a 400 at every
# effort, so it writes with adaptive thinking at effort low. Disabled (Haiku) and between_tools (Sonnet) need effort
# high or below.
WRITERS: dict[str, dict[str, Any]] = {
    "haiku": {**HAIKU, "effort": "low"},
    "sonnet": SONNET,
    "opus": {"model": "claude-opus-5-5", "effort": "low"},
}
QUICKS: dict[str, dict[str, Any]] = {
    "haiku": HAIKU,
    "sonnet": {"model": "claude-sonnet-5-5", "thinking": {"type": "between_tools"}},
}

log = logging.getLogger("je_server")
USER_TURNS = (3, 3)  # 2026-11-05 the user tried 5 on the phone, found it too many, chose 3
USER_MAX_WORDS = 14
ANNOTATE_TRIES = 3
INTERPRET_TRIES = 2
HANGUL = re.compile(r"[가-힣]")
QUOTES = "\"'“”‘’「」『』"


# Calls made while the learner waits in a turn (feedback, off-script reply). The app gives up after 30s without a
# stream event, so these must fail sooner and let Ryan say "지금은 대답할 수 없어요" (final review, 2026-11-05).
LIVE_OPTIONS: dict[str, Any] = {"timeout": 12.0, "max_retries": 1}


class ClaudeUnavailable(Exception):
    """No answer right now: no internet, rate limit, server error, timeout or refusal."""


def _problems_text(problems: list[str]) -> str:
    return "\n".join(f"- {p}" for p in problems)


def _spoken(text: str) -> str:
    """A line as it is shown and read out. Braces are JSON slipping into the text (phone test, 2026-11-07: Ryan's
    reply ended in "for you.}"); no line says them."""
    return text.replace("{", "").replace("}", "").strip()


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

    def _client(self, live: bool):
        return self.client.with_options(**LIVE_OPTIONS) if live else self.client

    async def _create(self, live: bool = False, **kw):
        try:
            resp = await self._client(live).messages.create(**kw)
        except anthropic.APIConnectionError as e:  # includes timeouts
            raise ClaudeUnavailable("connection") from e
        except anthropic.APIStatusError as e:
            # 429 and 5xx, but also 400 (e.g. no credit left) and 401: the learner can only be told "not now"
            log.info("claude api status %d", e.status_code)
            raise ClaudeUnavailable(f"status {e.status_code}") from e
        if resp.stop_reason == "refusal":
            raise ClaudeUnavailable("refusal")
        return resp

    async def _json(self, model: dict[str, Any], system: str, user: str, schema: dict, max_tokens: int,
                    live: bool = False) -> Any:
        """Returns parsed JSON, or None when the answer is not valid JSON."""
        resp = await self._create(
            live,
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
    def script_problems(draft: Draft, first: Speaker | None = None) -> list[str]:
        """What is wrong with a script. Either speaker may start and end (spec situation-topics 5); `first` is who
        must start when the topic or the list says so."""
        out = []
        if not draft:
            return ["the script is empty"]
        if first is not None and draft[0][0] != first:
            out.append("Ryan must speak first" if first == "ryan" else "the learner must speak first")
        if any(a[0] == b[0] for a, b in zip(draft, draft[1:])):
            out.append("lines must alternate between Ryan and the learner")
        turns = sum(1 for s, _ in draft if s == "user")
        if not USER_TURNS[0] <= turns <= USER_TURNS[1]:
            want = str(USER_TURNS[0]) if USER_TURNS[0] == USER_TURNS[1] else f"{USER_TURNS[0]} to {USER_TURNS[1]}"
            out.append(f"the learner must have {want} lines, not {turns}")
        if any(s == "user" and len(t.split()) > USER_MAX_WORDS for s, t in draft):
            out.append(f"learner lines must be at most {USER_MAX_WORDS - 2} words")
        return out

    async def make_script(self, situation: str, topic: Topic, first: Speaker | None = None) -> tuple[Frame, Draft]:
        """The frame and script for a situation in a topic. `first` comes from a list pick; otherwise the topic's
        own (외국인 관광객: Ryan), and with neither the situation decides (spec situation-topics 5)."""
        first = first or topic.first
        starts = {"ryan": "Ryan speaks first.", "user": "The learner speaks first.",
                  None: "Whoever would naturally speak first in this situation speaks first."}[first]
        user = f"상황: {situation}\nRoles: {topic.roles_en}\n{starts}"
        problems: list[str] = []
        for _ in range(2):
            content = user if not problems else f"{user}\n\nThe last script had problems. Fix them:\n{_problems_text(problems)}"
            data = await self._json(self.writer, prompts.SCRIPT_SYSTEM, content, prompts.SCRIPT_SCHEMA, 4000)
            try:
                frame = Frame.model_validate(data["frame"])
                draft: Draft = [(l["speaker"], _spoken(l["text"])) for l in data["lines"]]
            except (TypeError, KeyError, ValidationError):
                problems = ["the answer did not follow the JSON format"]
                continue
            problems = self.script_problems(draft, first)
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

    # --- Sohee's interpretation -----------------------------------------------------------------

    async def interpret(self, frame: Frame, line: tuple[Speaker, str], before: tuple[Speaker, str] | None,
                        after: tuple[Speaker, str] | None) -> str:
        """Sohee's Korean for one line, on the quick model (spec korean-translation 3). The lines around it are
        context, as the conversation went. The learner waits for it, so it fails fast."""
        roles = {"ryan": frame.ryan_role_ko, "user": frame.user_role_ko}

        def said(l: tuple[Speaker, str] | None) -> dict | None:
            return None if l is None else {"말하는 사람": roles[l[0]], "text": l[1]}

        body = json.dumps({"상황": frame.model_dump(), "앞 대사": said(before), "옮길 대사": said(line),
                           "뒤 대사": said(after)}, ensure_ascii=False)
        t0 = time.perf_counter()
        for tries in range(1, INTERPRET_TRIES + 1):
            data = await self._json(self.quick, prompts.INTERPRET_SYSTEM, body, prompts.INTERPRET_SCHEMA, 300,
                                    live=True)
            raw = data.get("ko") if isinstance(data, dict) else None
            ko = " ".join(raw.split()).strip(QUOTES).strip() if isinstance(raw, str) else ""
            if HANGUL.search(ko):
                log.info("interpretation: %d tries, %.1fs", tries, time.perf_counter() - t0)
                return ko
        raise ClaudeUnavailable("bad interpretation")

    # --- recommendation -----------------------------------------------------------------------

    async def recommend(self, recent: list[str], turned_down: Sequence[str], topic: Topic) -> str:
        """Jake's suggestion inside the topic, unlike its recent ones, its prepared list and those just turned down
        (spec situation-topics 4)."""
        listed = "\n".join(f"- {r}" for r in recent) or "- 없음"
        message = f"주제: {topic.scenes_en}\n예: {topic.example_ko}\n\n최근 상황:\n{listed}"
        if topic.picks:  # Jake fills in what the short list does not cover (user, 2026-11-07)
            message += "\n\n목록에 있는 상황:\n" + "\n".join(f"- {p.title_ko}" for p in topic.picks)
        if turned_down:  # suggested on the situation screen and turned down with 「다른 걸로요」 (2026-11-06)
            message += "\n\n방금 거절한 상황:\n" + "\n".join(f"- {t}" for t in turned_down)
        data = await self._json(self.quick, prompts.RECOMMEND_SYSTEM, message, prompts.RECOMMEND_SCHEMA, 300)
        text = (data or {}).get("request_ko", "").strip() if isinstance(data, dict) else ""
        if not text:
            raise ClaudeUnavailable("empty recommendation")
        return text

    # --- the conversation sent along ---------------------------------------------------------

    @staticmethod
    def _talk(frame: Frame, history: Draft) -> dict:
        return {"상황": frame.model_dump(), "지금까지 대화": [{"speaker": s, "text": t} for s, t in history]}

    # --- feedback on a followed line ----------------------------------------------------------

    async def feedback(self, line: str, heard: str, praise: list[str], issues: list[Issue],
                       last: bool = False) -> AsyncIterator[str]:
        """Streams Ryan's Korean feedback. Only the line, the transcript and the Mac's findings go out. `last`: the
        line ends the roleplay, so there is no next line to move on to (a script may end with the learner)."""
        found = {
            "대사": line,
            "들린 말": heard,
            "잘한 점 후보": praise,
            "짚을 것": _points(issues),
            "마지막 대사": last,
        }
        kw = {k: v for k, v in self.quick.items() if k != "effort"}
        async for text in self._stream(kw, prompts.FEEDBACK_SYSTEM, found, 800):
            yield text

    # --- teacher Ryan, when the line was not followed -------------------------------------------

    async def aside(self, frame: Frame, history: Draft, line: str, heard: str, heard_ko: str | None,
                    issues: list[Issue], earlier: list[tuple[str, str]]) -> AsyncIterator[str]:
        """Streams teacher Ryan's Korean answer to a recording that did not follow the line (spec offscript-aside
        3), on the writer model. `heard` is the English transcript, `heard_ko` the Korean one when auto-detection
        heard Korean, `issues` what the Mac found against the line, `earlier` the asides before on this line as
        (heard, Ryan's answer). Only text goes out (ADR-0004)."""
        body = {
            **self._talk(frame, history),
            "대사": line,
            "들린 말(영어 받아쓰기)": heard,
            "들린 말(한국어 받아쓰기)": heard_ko or "",
            "짚을 것": _points(issues),
            "앞서 선생님에게 한 말": [{"들린 말": h, "라이언의 답": a} for h, a in earlier],
        }
        async for text in self._stream(self._request(self.writer, {}), prompts.ASIDE_SYSTEM, body, 600):
            yield text

    async def _stream(self, kw: dict[str, Any], system: str, body: dict, max_tokens: int) -> AsyncIterator[str]:
        """A live call streamed as text; an empty output_config is left out."""
        if not kw.get("output_config", True):
            kw = {k: v for k, v in kw.items() if k != "output_config"}
        try:
            async with self._client(live=True).messages.stream(
                **kw, max_tokens=max_tokens, system=system,
                messages=[{"role": "user", "content": json.dumps(body, ensure_ascii=False)}],
            ) as stream:
                async for text in stream.text_stream:
                    yield text
        except anthropic.APIConnectionError as e:
            raise ClaudeUnavailable("connection") from e
        except anthropic.APIStatusError as e:
            log.info("claude api status %d", e.status_code)
            raise ClaudeUnavailable(f"status {e.status_code}") from e


def _points(issues: list[Issue]) -> list[dict[str, str]]:
    """The Mac's points as the prompts name them."""
    return [{"대사 낱말": i.target, "들린 낱말": i.heard, "소리 내는 법": i.explain} for i in issues]
