"""Test doubles. No network, no audio models."""
from __future__ import annotations

import json
from types import SimpleNamespace

import anthropic
import httpx2

from je_server.claude import ClaudeUnavailable
from je_server.models import Frame, ThreeLine
from je_server.threeline import plain


def _response(text: str, stop_reason: str = "end_turn"):
    return SimpleNamespace(
        content=[SimpleNamespace(type="text", text=text)],
        stop_reason=stop_reason,
        usage=SimpleNamespace(input_tokens=10, output_tokens=10),
    )


def refusal_response():
    return SimpleNamespace(content=[], stop_reason="refusal", usage=SimpleNamespace(input_tokens=1, output_tokens=0))


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
        self.messages = _Messages(self)


FRAME = {"title_ko": "길 묻기", "user_role_ko": "동네 사람", "ryan_role_ko": "여행자",
         "place_ko": "지하철역 앞", "goal_ko": "역 가는 길 알려 주기"}

DRAFT_USER = ["It's right over there.", "Go straight and turn left.", "About five minutes.", "You're welcome!",
              "Have a nice trip.", "Sure, no problem."]
DRAFT_RYAN = ["Excuse me, where is the subway station?", "How do I get there?", "How long does it take?",
              "Thanks a lot!", "Bye!", "Great.", "Thanks for your help!"]


def script_lines(user_turns: int) -> list[dict]:
    lines = [{"speaker": "ryan", "text": DRAFT_RYAN[0]}]
    for i in range(user_turns):
        lines.append({"speaker": "user", "text": DRAFT_USER[i % len(DRAFT_USER)]})
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

    def __init__(self):
        self.fail_next = False
        self.calls: list[tuple[str, tuple]] = []

    def _maybe_fail(self):
        if self.fail_next:
            self.fail_next = False
            raise ClaudeUnavailable("fake")

    async def make_script(self, situation):
        self.calls.append(("make_script", (situation,)))
        self._maybe_fail()
        draft = [(l["speaker"], l["text"]) for l in script_lines(4)]
        return Frame(**FRAME), draft

    async def annotate(self, text, context):
        self.calls.append(("annotate", (text, context)))
        self._maybe_fail()
        return plain(text)

    async def recommend(self, recent):
        self.calls.append(("recommend", (recent,)))
        self._maybe_fail()
        return "카페에서 커피를 주문하는 상황으로 연습하고 싶어."
