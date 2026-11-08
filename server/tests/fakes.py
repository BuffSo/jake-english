"""Test doubles. No network, no audio models."""
from __future__ import annotations

import json
from types import SimpleNamespace

import anthropic
import httpx2

from je_server.asr import WhisperError
from je_server.claude import ClaudeUnavailable
from je_server.models import Frame, Syllable, ThreeLine, Word


def noted(text: str) -> ThreeLine:
    """A note with Korean in it, as a good annotate gives: `plain` has none, and a pick does not reuse that (spec
    fixed-list-scripts 2)."""
    return ThreeLine(words=[Word(syl=[Syllable(en=t, ko="가", m="n")]) for t in text.split()], reading="")


def _response(text: str, stop_reason: str = "end_turn"):
    return SimpleNamespace(
        content=[SimpleNamespace(type="text", text=text)],
        stop_reason=stop_reason,
        usage=SimpleNamespace(input_tokens=10, output_tokens=10),
    )


def refusal_response():
    return SimpleNamespace(content=[], stop_reason="refusal", usage=SimpleNamespace(input_tokens=1, output_tokens=0))


def status_error(code: int):
    req = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    cls = {400: anthropic.BadRequestError, 401: anthropic.AuthenticationError}.get(code, anthropic.APIStatusError)
    return cls("error", response=httpx2.Response(code, request=req), body=None)


def connection_error() -> anthropic.APIConnectionError:
    return anthropic.APIConnectionError(request=httpx2.Request("POST", "https://api.anthropic.com/v1/messages"))


class _Stream:
    def __init__(self, item):
        self.item = item

    async def __aenter__(self):
        if isinstance(self.item, Exception):
            raise self.item
        return self

    async def __aexit__(self, *exc):
        return False

    @property
    def text_stream(self):
        async def gen():
            for piece in self.item:
                if isinstance(piece, Exception):  # the connection fails after the pieces before it
                    raise piece
                yield piece
        return gen()


class _Messages:
    def __init__(self, owner):
        self.owner = owner

    async def create(self, **kw):
        self.owner.requests.append(kw)
        item = self.owner.answers.pop(0)
        if isinstance(item, Exception):
            raise item
        return _response(item) if isinstance(item, str) else item

    def stream(self, **kw):
        self.owner.requests.append(kw)
        return _Stream(self.owner.answers.pop(0))


class FakeAnthropic:
    """Records each request; answers come from a list (str = JSON text, Exception = raised)."""

    def __init__(self, answers):
        self.answers = list(answers)
        self.requests: list[dict] = []
        self.options: list[dict] = []
        self.messages = _Messages(self)

    def with_options(self, **options):
        self.options.append(options)
        return self


FRAME = {"title_ko": "길 묻기", "user_role_ko": "동네 사람", "ryan_role_ko": "여행자",
         "place_ko": "지하철역 앞", "goal_ko": "역 가는 길 알려 주기"}

DRAFT_USER = ["It's right over there.", "Go straight and turn left.", "About five minutes.", "You're welcome!",
              "Have a nice trip.", "Sure, no problem."]
DRAFT_RYAN = ["Excuse me, where is the subway station?", "How do I get there?", "How long does it take?",
              "Thanks a lot!", "Bye!", "Great.", "Thanks for your help!"]


def script_lines(user_turns: int, first: str = "ryan", last: str = "ryan") -> list[dict]:
    """Alternating lines with `user_turns` learner lines; either speaker may start or end (spec situation-topics 5)."""
    lines = [{"speaker": "ryan", "text": DRAFT_RYAN[0]}] if first == "ryan" else []
    for i in range(user_turns):
        lines.append({"speaker": "user", "text": DRAFT_USER[i % len(DRAFT_USER)]})
        if i < user_turns - 1 or last == "ryan":
            lines.append({"speaker": "ryan", "text": DRAFT_RYAN[(i + 1) % len(DRAFT_RYAN)]})
    return lines


def script_json(user_turns: int, first: str = "ryan", last: str = "ryan") -> str:
    return json.dumps({"frame": FRAME, "lines": script_lines(user_turns, first, last)})


def three_json(text: str = "I like coffee.", stress_first: bool = True) -> str:
    m1, m2 = ("s", "w") if stress_first else ("w", "s")
    words = [
        {"syl": [{"en": "I", "ko": "아이", "m": "n", "hi": ""}], "emph": False, "link": False},
        {"syl": [{"en": "like", "ko": "라익", "m": "n", "hi": ""}], "emph": False, "link": False},
        {"syl": [{"en": "cof", "ko": "카", "m": m1, "hi": "카" if m1 == "s" else ""},
                 {"en": "fee.", "ko": "피", "m": m2, "hi": "피" if m2 == "s" else ""}], "emph": False, "link": False},
    ]
    return json.dumps({"words": words, "reading": "coffee는 앞을 세게, [[카-피]]."})


def three_json_with_wrong_stress(text: str = "I like coffee.") -> str:
    return three_json(text, stress_first=False)


class FakeClaude:
    """Same methods as je_server.claude.Claude with fixed answers."""

    feedback_pieces = ["끝까지 자신 있게 ", "말했어요. 다음 대사로 ", "넘어가요."]

    def __init__(self):
        self.fail_next = False
        self.calls: list[tuple[str, tuple]] = []
        self.feedback_calls: list[dict] = []
        self.annotate_gate = None  # an asyncio.Event to hold annotate until set
        self.interpret_calls: list[dict] = []
        self.interpret_gate = None  # an asyncio.Event to hold interpret until set
        self.script_last = "ryan"  # who ends the scripts make_script gives
        self.aside_calls: list[dict] = []
        self.aside_pieces = ["괜찮아요, 말이 꼬일 수 있어요. ", "다시 해 볼까요?"]
        # pieces given before aside() fails; 0 fails at once. Not fail_next: background notes may take that first.
        self.aside_fail_after: int | None = None
        self.endings: list[str] = []  # the ending recommend() was given, in order

    def _maybe_fail(self):
        if self.fail_next:
            self.fail_next = False
            raise ClaudeUnavailable("fake")

    async def make_script(self, situation, topic, first=None):
        self.calls.append(("make_script", (situation, topic.id, first)))
        self._maybe_fail()
        draft = [(l["speaker"], l["text"]) for l in script_lines(3, first=first or topic.first or "ryan",
                                                                 last=self.script_last)]
        return Frame(**FRAME), draft

    async def annotate(self, text, context):
        self.calls.append(("annotate", (text, context)))
        if self.annotate_gate is not None:
            await self.annotate_gate.wait()
        self._maybe_fail()
        return noted(text)

    async def interpret(self, frame, line, before, after):
        self.interpret_calls.append({"frame": frame.model_dump(), "line": line, "before": before, "after": after})
        if self.interpret_gate is not None:
            await self.interpret_gate.wait()
        self._maybe_fail()
        return "소희: " + line[1]

    async def recommend(self, recent, turned_down, topic, ending):
        self.calls.append(("recommend", (recent, list(turned_down), topic.id)))
        self.endings.append(ending)
        self._maybe_fail()
        return f"카페에서 커피를 주문하는 {ending}"

    async def feedback(self, line, heard, praise, issues, last=False):
        self.feedback_calls.append({"line": line, "heard": heard, "praise": praise,
                                    "issues": [i.model_dump() for i in issues], "last": last})
        self._maybe_fail()
        for piece in self.feedback_pieces:
            yield piece

    async def aside(self, frame, history, line, heard, heard_ko, issues, earlier):
        self.aside_calls.append({"frame": frame.model_dump(), "history": history, "line": line, "heard": heard,
                                 "heard_ko": heard_ko, "issues": [i.model_dump() for i in issues],
                                 "earlier": list(earlier)})
        self._maybe_fail()
        for n, piece in enumerate(self.aside_pieces):
            if self.aside_fail_after is not None and n >= self.aside_fail_after:
                raise ClaudeUnavailable("fake")
            yield piece


class FakeVoice:
    """Returns sound keys without making sound; writes a small placeholder so file routes work."""

    def __init__(self, audio_dir):
        from pathlib import Path

        self.audio_dir = Path(audio_dir)
        self.calls: list[tuple[str, str, str, bool]] = []
        self.checked: list[str] = []  # texts asked to be heard back (check=True)
        self.ranks: list[int] = []  # each call's rank, beside `calls`
        self.fail_text: str | None = None
        # the worker's reference fingerprints by its voice name and language (`tts.Voice.refs`); none by default
        self.refs: dict[str, dict[str, str]] = {}

    async def start(self):
        self.audio_dir.mkdir(parents=True, exist_ok=True)

    async def stop(self):
        pass

    def path(self, key):
        return self.audio_dir / f"{key}.m4a"

    def key(self, voice, lang, text):
        from je_server.tts import WORKER_VOICE, audio_key

        return audio_key(voice, lang, text, self.refs.get(WORKER_VOICE.get(voice, voice), {}).get(lang, ""))

    async def say(self, text, voice, lang, urgent, rank=0, check=False):
        from je_server.tts import VoiceError

        self.calls.append((text, voice, lang, urgent))
        self.ranks.append(rank)
        if check:
            self.checked.append(text)
        if text == self.fail_text:
            raise VoiceError("fake")
        key = self.key(voice, lang, text)
        self.audio_dir.mkdir(parents=True, exist_ok=True)
        self.path(key).write_bytes(b"fake")
        return key

    async def rate_file(self, key, rate):
        return self.path(key)


class FakeWhisper:
    def __init__(self, text: str = "It's right over there."):
        self.text = text
        self.calls = 0
        self.langs: list[str] = []
        self.auto_text: str | None = None  # what auto-detection hears; None: the same as `text`
        self.auto_lang = "english"
        self.auto_fail = False  # transcribe_auto raises WhisperError, as when whisper-server cannot answer

    async def start(self):
        pass

    async def stop(self):
        pass

    async def transcribe(self, wav, lang):
        self.calls += 1
        self.langs.append(lang)
        return self.text

    async def transcribe_auto(self, wav):
        self.calls += 1
        self.langs.append("auto")
        if self.auto_fail:
            raise WhisperError("fake")
        return (self.auto_text if self.auto_text is not None else self.text), self.auto_lang
