"""Claude calls (ADR-0004). Only text goes out: lines, transcripts, the Mac's findings, the situation."""
from __future__ import annotations

import json
import logging
import random
import re
import time
from collections.abc import AsyncIterator, Sequence
from typing import Any

import anthropic
import httpx2  # the HTTP client the anthropic SDK uses
from pydantic import ValidationError

from . import prompts
from .models import Draft, Frame, Issue, Speaker, ThreeLine
from .threeline import Problem, check, degrade, plain, tidy
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
QUICK_SONNET: dict[str, Any] = {"model": "claude-sonnet-5-5", "thinking": {"type": "between_tools"}}
QUICKS: dict[str, dict[str, Any]] = {
    "haiku": HAIKU,
    "sonnet": QUICK_SONNET,
}
# Jake's recommendation picks from QUICKS too (JE_CLAUDE_RECOMMEND), default Sonnet: 2026-11-08 the user chose it
# after the three quick jobs were compared on made-up inputs. Haiku wrote odd recommendation sentences 12 times in
# 63 (the message's 「끝말:」 copied, two endings, 「제가 …」), Sonnet twice; Sohee's interpretation and Ryan's
# feedback came out about the same and Sonnet was slower there, so they stay on the quick model.

log = logging.getLogger("je_server")
USER_TURNS = (3, 3)  # 2026-11-05 the user tried 5 on the phone, found it too many, chose 3
USER_MAX_WORDS = 14
ANNOTATE_TRIES = 3
INTERPRET_TRIES = 2
HANGUL = re.compile(r"[가-힣]")
QUOTES = "\"'“”‘’「」『』"
# Ryan's live answers never show double quotes (phone test 2026-11-08: Haiku quoted the transcript in them). 「」 stay:
# teacher Ryan puts meanings in them. Single quotes stay too: they are apostrophes in English words (I'll).
DOUBLE_QUOTES = str.maketrans("", "", "\"“”")


# Calls made while the learner waits in a turn (feedback, teacher Ryan's answer). The app gives up after 30s without a
# stream event, so these must fail sooner and let Ryan say "지금은 대답할 수 없어요" (final review, 2026-11-05).
LIVE_OPTIONS: dict[str, Any] = {"timeout": 12.0, "max_retries": 1}


# How Jake's suggestion ends, with weights (2026-11-08 the user heard five endings in Jake's voice and chose these three
# to mix, in place of the one 「…상황으로 연습해 보면 어때요?」). 「볼까요」 is Ryan's ending too, so it comes least
# (AI recommendation, the user agreed). The server picks one and Claude keeps it: asked to choose among them itself,
# a model leans on one and cannot keep the weights.
JAKE_ENDINGS: tuple[tuple[str, int], ...] = (
    ("상황을 골라 봤어요.", 2),
    ("상황을 추천해요.", 2),
    ("상황으로 연습해 볼까요?", 1),
)


def pick_ending(turned_down: Sequence[str], rng: random.Random | None = None) -> str:
    """One of JAKE_ENDINGS by weight, but not the one heard at the end of the last suggestion just turned down (the
    app sends the latest last), so 「다른 걸로요」 again and again does not hear the same ending twice in a row."""
    heard = heard_ending(turned_down[-1]) if turned_down else None
    left = [(e, w) for e, w in JAKE_ENDINGS if e != heard]
    return (rng or random).choices([e for e, _ in left], weights=[w for _, w in left])[0]


# How long the tail after the last 상황 may be and still be an ending, in letters without spaces and end marks: the
# longest ending the server has known, the old 「으로 연습해 보면 어때요」, is 10. 「…상황에서 주문하는 연습을 해 볼까요?」
# (13) has 상황 near the front only, and its tail is the situation itself.
ENDING_TAIL_MAX = 10
END_MARKS = ".?!~…"
SITUATION = "상황"


def _letters(tail: str) -> str:
    return "".join(c for c in tail if not c.isspace() and c not in END_MARKS)


def _ending_start(text: str) -> int | None:
    """Where the ending at the end of `text` starts: its last 상황, when what follows is short and ends in 요. Not only
    Jake's three: after the merge (2026-11-08) Haiku mixed two into 「…상황을 연습해 볼까요?」, and real runs have lost
    a space or the end mark."""
    at = text.rfind(SITUATION)
    if at < 0:
        return None
    letters = _letters(text[at + len(SITUATION):])
    return at if letters.endswith("요") and len(letters) <= ENDING_TAIL_MAX else None


def strip_endings(text: str) -> str | None:
    """The situation before the ending at the end of `text`, with every ending there taken off (Haiku has doubled
    them) and a 상황 left at its end too (「…묻는 상황 상황을 골라 봤어요.」). None when `text` does not end in an
    ending, empty when nothing comes before it. The clause before 상황 fits every ending, so the server can put the
    given one on."""
    at = _ending_start(text)
    if at is None:
        return None
    stem = text[:at]
    while (at := _ending_start(stem)) is not None:
        stem = stem[:at]
    return re.sub(rf"(?:[\s,]*{SITUATION})*[\s,]*$", "", stem).strip()


# The labels of the lines in Jake's recommendation message (`Claude.recommend`). A model sometimes says one back
# (todo 21: 「…상황을 골라 봤어요. 끝말: 상황을 골라 봤어요.」, read out in Jake's voice). Only a label word
# standing alone before a colon goes, also right after an end mark (「…봤어요.끝말:」, Haiku drops spaces): 「예약:」
# or 「주제곡」 stay.
MESSAGE_LABELS = ("주제", "예", "끝말")
_LABEL = re.compile(rf"(?<![가-힣A-Za-z0-9])(?:{'|'.join(MESSAGE_LABELS)})\s*:\s*")


def drop_labels(text: str) -> str:
    """`text` without the message's line labels said back, spaces tidied where one was taken out."""
    return " ".join(_LABEL.sub(" ", text).split()) if _LABEL.search(text) else text


def heard_ending(text: str) -> str | None:
    """The one of JAKE_ENDINGS a learner hears at the end of `text`: the one whose last word ends the ending there,
    spaces and end marks aside, so a mixed 「…상황을 연습해 볼까요?」 is heard as 「…상황으로 연습해 볼까요?」. None for
    any other ending (the old 「…어때요?」)."""
    at = _ending_start(text)
    if at is None:
        return None
    letters = _letters(text[at:])
    return next((e for e, _ in JAKE_ENDINGS if letters.endswith(_letters(e.split()[-1]))), None)


class ClaudeUnavailable(Exception):
    """No answer right now: no internet, rate limit, server error, timeout or refusal."""


def _problems_text(problems: list[str]) -> str:
    return "\n".join(f"- {p}" for p in problems)


def _spoken(text: str) -> str:
    """A line as it is shown and read out. Braces are JSON slipping into the text (phone test, 2026-11-07: Ryan's
    reply ended in "for you.}"); no line says them."""
    return text.replace("{", "").replace("}", "").strip()


class Claude:
    def __init__(self, client: Any, writer: dict[str, Any] = SONNET, quick: dict[str, Any] = HAIKU,
                 recommender: dict[str, Any] = QUICK_SONNET):
        self.client = client
        self.writer = writer
        self.quick = quick
        self.recommender = recommender

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
        """The frame and script for a situation in a topic. `first` overrides the topic's own (외국인 관광객: Ryan);
        with neither the situation decides (spec situation-topics 5). List picks no longer come here: their scripts
        are in `topics.py` (spec fixed-list-scripts)."""
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
                three = tidy(ThreeLine.model_validate(data))
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

    async def recommend(self, recent: list[str], turned_down: Sequence[str], topic: Topic, ending: str) -> str:
        """Jake's suggestion inside the topic, unlike its recent ones, its prepared list and those just turned down,
        ending in `ending` (one of JAKE_ENDINGS, picked by the server; spec situation-topics 4)."""
        listed = "\n".join(f"- {r}" for r in recent) or "- 없음"
        message = f"주제: {topic.scenes_en}\n예: {topic.example_ko}\n끝말: {ending}\n\n최근 상황:\n{listed}"
        if topic.picks:  # Jake fills in what the short list does not cover (user, 2026-11-07)
            message += "\n\n목록에 있는 상황:\n" + "\n".join(f"- {p.title_ko}" for p in topic.picks)
        if turned_down:  # suggested on the situation screen and turned down with 「다른 걸로요」 (2026-11-06)
            message += "\n\n방금 거절한 상황:\n" + "\n".join(f"- {t}" for t in turned_down)
        data = await self._json(self.recommender, prompts.RECOMMEND_SYSTEM, message, prompts.RECOMMEND_SCHEMA, 300)
        text = (data or {}).get("request_ko", "").strip() if isinstance(data, dict) else ""
        if (dropped := drop_labels(text)) != text:
            log.info("recommendation label dropped")
            text = dropped
        if not text:
            raise ClaudeUnavailable("empty recommendation")
        # no second call: put the given ending on in place of the one there, say anything else as it came
        stem = strip_endings(text)
        if stem is None:
            log.warning("recommendation did not keep the given ending")
        elif not stem:
            log.warning("recommendation has no situation before its ending")
        elif (swapped := f"{stem} {ending}") != text:
            log.info("recommendation ending swapped")
            text = swapped
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
        async for text in self._stream(self._request(self.writer, {}), prompts.ASIDE_SYSTEM, body, 600,
                                       whole=True):
            yield text

    async def _stream(self, kw: dict[str, Any], system: str, body: dict, max_tokens: int,
                      whole: bool = False) -> AsyncIterator[str]:
        """A live call streamed as text, without double quotes; an empty output_config is left out. `whole`: a stream
        that ends at the token limit or as a refusal, after some text and without an error, is unavailable too, so
        teacher Ryan's cut answer ends with the fixed phrase (todo teacher-answer-cut 1). The writer model may think,
        and thinking uses the same tokens. Feedback leaves it off: it is short and keeps what came."""
        if not kw.get("output_config", True):
            kw = {k: v for k, v in kw.items() if k != "output_config"}
        try:
            async with self._client(live=True).messages.stream(
                **kw, max_tokens=max_tokens, system=system,
                messages=[{"role": "user", "content": json.dumps(body, ensure_ascii=False)}],
            ) as stream:
                async for text in stream.text_stream:
                    if text := text.translate(DOUBLE_QUOTES):
                        yield text
                if whole and (why := (await stream.get_final_message()).stop_reason) in ("max_tokens", "refusal"):
                    log.info("claude stream ended: %s", why)
                    raise ClaudeUnavailable(why)
        except (anthropic.APIConnectionError, httpx2.TransportError) as e:
            # the SDK raises a transport error met while reading the stream (a dropped connection, a read timeout
            # between pieces) as it is, not as APIConnectionError (final review, 2026-11-07)
            raise ClaudeUnavailable("connection") from e
        except anthropic.APIStatusError as e:
            log.info("claude api status %d", e.status_code)
            raise ClaudeUnavailable(f"status {e.status_code}") from e


def _points(issues: list[Issue]) -> list[dict[str, str]]:
    """The Mac's points as the prompts name them."""
    return [{"대사 낱말": i.target, "들린 낱말": i.heard, "소리 내는 법": i.explain} for i in issues]
