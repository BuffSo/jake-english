"""Run Ryan's live wording on made-up lines with the real Claude API and flag broken rules (costs money).

Feedback after a followed line (`Claude.feedback`, the quick model) and teacher Ryan's answer (`Claude.aside`, the
writer model) are asked for each case below, `--runs` times, through the server's own `Claude` class. Each answer
is printed with the rules it broke:
- a given sound tip left out, or the materials named ("짚을 것", "설명", that there is no tip), or how the recording
  was sorted ("상관없는 말"); teacher Ryan not ending with a try at the same line
- the practice called 「역할극」 instead of 「대화」, double quotes (in the model's own answer: the server drops them)
- a particle after an English word that does not fit how the word ends in Hangul (room이, where가)
- a pointed word missing, the whole transcript quoted, or the wrong ending (next line / conversation done)
The lines are made up (REVIEW.md), so printing them is fine. Prints tokens and cost at the end.

Feedback costs about $0.0003 a call on Haiku and $0.007 on Sonnet; teacher Ryan about $0.007 on Sonnet. Tell the
user how many runs and the cost before running (AGENTS.md).

Run in server/: uv run python scripts/check_ryan_wording.py [--runs N] [--only feedback|aside] [--quick haiku|sonnet] [--case NAME]
"""
from __future__ import annotations

import argparse
import asyncio
import re
import statistics
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import anthropic  # noqa: E402

from je_server.claude import QUICKS, WRITERS, Claude  # noqa: E402
from je_server.config import load_settings  # noqa: E402
from je_server.models import Frame, Issue  # noqa: E402

# $ per million tokens in/out, for every model server/.env can pick (claude.WRITERS, claude.QUICKS)
PRICE = {"claude-opus-5-5": (4.0, 20.0), "claude-sonnet-5-5": (2.0, 10.0), "claude-haiku-5-5": (0.10, 0.50)}
RL = "L은 혀끝이 윗잇몸에 닿지만, R은 혀가 어디에도 닿지 않게 하고 입술을 살짝 동그랗게 모아요."
FP = "P는 두 입술을 붙였다가 터뜨리지만, F는 윗니를 아랫입술에 살짝 대고 그 틈으로 바람을 길게 내보내요."
TIP_MARK = {RL: "닿", FP: "아랫입술"}  # a word the reworded tip keeps

# Does the word, written in Hangul, end in a final consonant (받침)? line 라인, room 룸: yes; seventy 세븐티, red 레드: no
BATCHIM = {"line": True, "lime": True, "market": True, "marker": False, "room": True, "loom": True, "station": True, "then": True, "on": True,
           "tent": False, "tenth": False, "red": False, "led": False, "rice": False, "lice": False, "fried": False,
           "flied": False, "stage": False, "and": False, "seventy": False, "seventeen": True, "coffee": False,
           "coffees": False, "copies": False, "copy": False, "right": False, "light": False, "ah": False,
           "please": False, "menu": False, "goes": False, "go": False, "where": False, "well": True,
           "far": False, "fall": True, "in": True, "chicken": True, "check": True}
PARTICLE = re.compile(r"([A-Za-z][A-Za-z']*)(이|가|은|는|을|를|과|와)(?![가-힣])")
WITH_BATCHIM, WITHOUT = set("이은을과"), set("가는를와")
# 「짚을」 and 「상관없는 말」: teacher Ryan said how the server sorted a Korean wish about the app (phone, 2026-11-08)
NAMES = ("짚을", "후보", "소리 내는 법", "설명", "자료", "받은", "역할극", "따로 말", "말하지 않을게",
         "라고 말했", "라고 하셨", "말했는데", "상관없는 말", "대사와 다른 말")
QUOTES = "\"“”"


@dataclass
class Case:
    name: str
    line: str
    heard: str
    issues: list[Issue] = field(default_factory=list)
    praise: list[str] = field(default_factory=list)
    last: bool = False
    heard_ko: str | None = None


def issue(target: str, heard: str, explain: str = "") -> Issue:
    return Issue(target=target, heard=heard, sound=("R", "L") if explain else None, explain=explain)


REST = "나머지 낱말은 다 알아들었어요"
CLEAN = "대사를 빠짐없이 알아듣게 말했어요"
FEEDBACK = [
    Case("tip", "Can I get a room with a view?", "Can I get a loom with a view?",
         [issue("room", "loom", RL)], [REST]),
    Case("tip second", "Is the bus on the red line?", "Is the bus the led line?",
         [issue("on", ""), issue("red", "led", RL)], [REST]),
    Case("same tip twice", "Do you have fried rice?", "Do you have flied lice?",
         [issue("fried", "flied", RL), issue("rice", "lice", RL)], [REST]),
    Case("hidden R", "Where are you from?", "Well are you from?", [issue("where", "well", RL)], [REST]),
    Case("hidden R 2", "Is it far from here?", "Is it fall from here?", [issue("far", "fall", RL)], [REST]),
    Case("no tip", "Is this the right station?", "Is this the right stage?", [issue("station", "stage")], [REST]),
    Case("particles", "Take line one to the market.", "Take lime one to the marker.",
         [issue("line", "lime"), issue("market", "marker")], [REST]),
    Case("span", "My seat is twenty eight.", "My seat is plenty.", [issue("twenty eight", "plenty")], [REST]),
    Case("added word", "Could I see the menu, please?", "Could I see the menu ah please?",
         [issue("", "ah")], [REST]),
    Case("improved", "I'll sit on the right.", "I'll sit the right.",
         [issue("on", "")], ["이번에는 right의 R 소리가 제대로 났어요", REST]),
    Case("clean", "Thanks for waiting.", "Thanks for waiting.", [], [CLEAN]),
    Case("clean last", "Thanks, you too!", "Thanks, you too!", [], [CLEAN], last=True),
]
FRAME = Frame(title_ko="호텔 체크인", user_role_ko="손님", ryan_role_ko="호텔 직원", place_ko="호텔 프런트",
              goal_ko="방 열쇠 받기")
ASIDE = [
    Case("near miss tip", "The room is on the tenth floor.", "The loom is on the tent floor.",
         [issue("room", "loom", RL), issue("tenth", "tent")]),
    Case("near miss F", "I'd like two coffees, please.", "I'd like to copies, please.",
         [Issue(target="coffees", heard="copies", sound=("F", "P"), explain=FP)]),
    Case("near miss number", "That's seventy dollars.", "That's seventeen dollars.", [issue("seventy", "seventeen")]),
    Case("near miss span", "My seat is twenty eight.", "My seat is plenty.", [issue("twenty eight", "plenty")]),
    Case("near miss span 2", "Can I check in now?", "Can I chicken now?", [issue("check in", "chicken")]),
    Case("korean question", "Here is your key card.", "What does key card mean?", [], heard_ko="키 카드가 무슨 뜻이에요?"),
    # made up, not what the learner said: a wish about the app and a remark to oneself, both in Korean
    Case("off app wish", "Here is your key card.", "I wish the app showed the meaning first.", [],
         heard_ko="앱이 뜻을 먼저 보여 주면 좋겠어요."),
    Case("off chat", "Here is your key card.", "Oh, I'm so sleepy today.", [], heard_ko="아 오늘 너무 졸리다."),
]


def flags(case: Case, text: str, aside: bool, raw: str = "") -> list[str]:
    """The rules `text` (what the learner sees) breaks. Double quotes are looked for in `raw`, the model's own answer:
    the server drops them from `text`, so a prompt that stops keeping them out would not show there."""
    text = " ".join(text.split())
    out = []
    for i in case.issues:
        if i.explain and TIP_MARK[i.explain] not in text:
            out.append(f"tip dropped ({i.target})")
        if i.target and i.target not in text:
            out.append(f"word not pointed ({i.target})")
        if i.heard and i.heard not in text:
            out.append(f"heard word not said ({i.heard})")
    out += [f"names {n!r}" for n in NAMES if n in text]
    if any(q in raw for q in QUOTES):
        out.append("double quotes")
    if re.sub(r"\W", "", case.heard.lower()) in re.sub(r"\W", "", text.lower()) and case.issues:
        out.append("quotes the whole transcript")
    for word, p in PARTICLE.findall(text):
        want = BATCHIM.get(word.lower())
        if want is not None and p in (WITHOUT if want else WITH_BATCHIM):
            out.append(f"particle {word}{p}")
    if aside and "다시" not in text and "한 번 더" not in text:
        out.append("does not ask to try again")  # teacher Ryan always ends asking for the same line again
    if not aside:
        if case.last and "다음 대사" in text:
            out.append("offers a next line after the last")
        if not case.issues and not case.last and "다음" not in text:
            out.append("does not move on")
        if case.issues and "한 번 더" not in text and "다시" not in text:
            out.append("does not ask to try again")
    return out


class Counting:
    """Wraps the client to add up usage per streamed call and keep each answer as the model wrote it."""

    def __init__(self, inner, usage: list | None = None, raw: list | None = None):
        self.inner, self.messages = inner, self
        self.usage = usage if usage is not None else []
        self.raw: list[str] = raw if raw is not None else []

    def with_options(self, **kw):
        return Counting(self.inner.with_options(**kw), self.usage, self.raw)

    def stream(self, **kw):
        manager, usage, raw = self.inner.messages.stream(**kw), self.usage, self.raw

        class Recorded:
            async def __aenter__(self):
                self.s = await manager.__aenter__()
                return self.s

            async def __aexit__(self, *exc):
                if exc[0] is None:
                    m = await self.s.get_final_message()
                    usage.append((kw["model"], m.usage.input_tokens, m.usage.output_tokens))
                    raw.append("".join(b.text for b in m.content if b.type == "text"))
                return await manager.__aexit__(*exc)

        return Recorded()


async def timed(gen) -> tuple[str, float]:
    t0, first, parts = time.perf_counter(), None, []
    async for d in gen:
        first = first or time.perf_counter() - t0
        parts.append(d)
    return "".join(parts), first or 0.0


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--only", choices=("feedback", "aside"))
    ap.add_argument("--quick", choices=tuple(QUICKS), default="haiku", help="model for the feedback")
    ap.add_argument("--case", default="", help="only the cases whose name has this text")
    args = ap.parse_args()
    s = load_settings()
    counting = Counting(anthropic.AsyncAnthropic(api_key=s.anthropic_api_key))
    claude = Claude(counting, writer=WRITERS[s.claude_writer], quick=QUICKS[args.quick])
    broken = total = 0
    firsts: dict[str, list[float]] = {"feedback": [], "aside": []}
    for kind, cases in (("feedback", FEEDBACK), ("aside", ASIDE)):
        if args.only and args.only != kind:
            continue
        for case in (c for c in cases if args.case in c.name):
            print(f"\n## {kind}: {case.name} | line: {case.line} | heard: {case.heard_ko or case.heard}")
            for _ in range(args.runs):
                if kind == "feedback":
                    gen = claude.feedback(case.line, case.heard, case.praise, case.issues, case.last)
                else:
                    gen = claude.aside(FRAME, [("ryan", "Welcome. Do you have a reservation?")], case.line,
                                       case.heard, case.heard_ko, case.issues, [])
                text, first = await timed(gen)
                firsts[kind].append(first)
                f = flags(case, text, kind == "aside", counting.raw[-1] if counting.raw else "")
                total += 1
                broken += bool(f)
                print(f"- {text}" + (f"\n  !! {', '.join(f)}" if f else ""))
    cost = sum(i * PRICE[m][0] / 1e6 + o * PRICE[m][1] / 1e6 for m, i, o in counting.usage)
    print(f"\nanswers {total}, with a broken rule {broken}; calls {len(counting.usage)}, ${cost:.4f}")
    for kind, ts in firsts.items():
        if ts:
            print(f"{kind}: first text median {statistics.median(ts):.2f}s, max {max(ts):.2f}s")


if __name__ == "__main__":
    asyncio.run(main())
