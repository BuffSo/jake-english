"""Test doubles. No network, no audio models."""
from __future__ import annotations

import json
from types import SimpleNamespace

import anthropic
import httpx2

from je_server.claude import ClaudeUnavailable
from je_server.models import Frame, Offscript, ThreeLine
from je_server.threeline import plain


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


def script_json(user_turns: int) -> str:
    return json.dumps({"frame": FRAME, "lines": script_lines(user_turns)})


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
        self.offscript_calls: list[dict] = []
        self.offscript_out = Offscript(point_kind="expression", point_ko="이럴 때는 I'm not sure처럼 말해도 좋아요.",
                                       meant="", heard_word="", reply_en="Oh, no worries. Thanks anyway!")
        self.fail_continue = False
        self.continue_gate = None  # an asyncio.Event to hold continue_script until set
        self.annotate_gate = None  # an asyncio.Event to hold annotate until set
        self.interpret_calls: list[dict] = []
        self.interpret_gate = None  # an asyncio.Event to hold interpret until set
        self.script_last = "ryan"  # who ends the scripts make_script gives

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
        return plain(text)

    async def interpret(self, frame, line, before, after):
        self.interpret_calls.append({"frame": frame.model_dump(), "line": line, "before": before, "after": after})
        if self.interpret_gate is not None:
            await self.interpret_gate.wait()
        self._maybe_fail()
        return "소희: " + line[1]

    async def recommend(self, recent, turned_down, topic):
        self.calls.append(("recommend", (recent, list(turned_down), topic.id)))
        self._maybe_fail()
        return "카페에서 커피를 주문하는 상황으로 연습해 보면 어때요?"

    async def feedback(self, line, heard, praise, issues, last=False):
        self.feedback_calls.append({"line": line, "heard": heard, "praise": praise,
                                    "issues": [i.model_dump() for i in issues], "last": last})
        self._maybe_fail()
        for piece in self.feedback_pieces:
            yield piece

    async def offscript(self, frame, history, expected, heard):
        self.offscript_calls.append({"frame": frame.model_dump(), "history": history, "expected": expected,
                                     "heard": heard})
        self._maybe_fail()
        return self.offscript_out

    async def continue_script(self, frame, history, user_turns):
        self.calls.append(("continue_script", (user_turns, list(history))))
        if self.continue_gate is not None:
            await self.continue_gate.wait()
        if self.fail_continue:
            raise ClaudeUnavailable("fake")
        draft = []
        for i in range(user_turns):
            draft += [("user", f"Maybe ask at the shop number {i}."), ("ryan", "Good idea." if i < user_turns - 1
                                                                       else "Thanks for your help!")]
        return draft


class FakeVoice:
    """Returns sound keys without making sound; writes a small placeholder so file routes work."""

    def __init__(self, audio_dir):
        from pathlib import Path

        self.audio_dir = Path(audio_dir)
        self.calls: list[tuple[str, str, str, bool]] = []
        self.checked: list[str] = []  # texts asked to be heard back (check=True)
        self.fail_text: str | None = None

    async def start(self):
        self.audio_dir.mkdir(parents=True, exist_ok=True)

    async def stop(self):
        pass

    def path(self, key):
        return self.audio_dir / f"{key}.m4a"

    async def say(self, text, voice, lang, urgent, rank=0, check=False):
        from je_server.tts import VoiceError, audio_key

        self.calls.append((text, voice, lang, urgent))
        if check:
            self.checked.append(text)
        if text == self.fail_text:
            raise VoiceError("fake")
        key = audio_key(voice, lang, text)
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

    async def start(self):
        pass

    async def stop(self):
        pass

    async def transcribe(self, wav, lang):
        self.calls += 1
        self.langs.append(lang)
        return self.text
