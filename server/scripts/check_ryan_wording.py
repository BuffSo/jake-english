"""Run Ryan's live wording on made-up lines with the real Claude API and flag broken rules (costs money).

Feedback after a followed line (`Claude.feedback`, the quick model) and teacher Ryan's answer (`Claude.aside`, the
writer model) are asked for each case below, `--runs` times, through the server's own `Claude` class. Each answer
is printed with the rules it broke:
- a given sound tip left out, said only in half, said in other words or order (「tip reworded」), said twice or with a
  half again (「tip repeated」), a sound named outside it (「sound named」: 「R이 L로 들렸어요」 before the tip), or a tip
  the Mac did not give (「tip made up」: mouth words when no tip came), or the materials named ("짚을 것", "설명", that there is no tip), or how the recording
  was sorted ("상관없는", "혼잣말"); teacher Ryan not ending with a try at the same line
- the practice called 「역할극」 instead of 「대화」, double quotes (in the model's own answer: the server drops them)
- a particle after an English word that does not fit how the word ends in Hangul (room이, where가)
- a pointed word missing, the whole transcript quoted, or the wrong ending (next line / conversation done)
- a word a case requires or forbids (`must`, `never`): a wish to skip names 「건너뛰기」, an app wish never says 「말해야」,
  a question about the try before names its words and never says nothing was pointed out (todo 40 1)
The materials' names are looked for in the model's own answer: the server drops those sentences (`ASIDE_LEAKS`), and a
name it dropped is flagged 「(server dropped)」.
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

from je_server import sounds  # noqa: E402
from je_server.claude import ASIDE_LEAKS, QUICKS, WRITERS, Claude  # noqa: E402
from je_server.config import load_settings  # noqa: E402
from je_server.models import Frame, Issue  # noqa: E402

# $ per million tokens in/out, for every model server/.env can pick (claude.WRITERS, claude.QUICKS)
PRICE = {"claude-opus-5-5": (4.0, 20.0), "claude-sonnet-5-5": (2.0, 10.0), "claude-haiku-5-5": (0.10, 0.50)}


def tip(a: str, b: str) -> str:
    """The list's tip for a sound pair (CMUdict phonemes), as the Mac sends it."""
    return sounds.find(a, b).explain


RL, FP, VB, TH_S, TH_D, Z_J = (tip(*p) for p in (("R", "L"), ("F", "P"), ("V", "B"), ("TH", "S"), ("DH", "D"),
                                                ("Z", "JH")))
# A word from each half of a tip that the other half does not have: a tip said whole keeps both (todo 20: teacher
# Ryan said only the R half, and the old mark 「닿」, in both halves, let it through). A test keeps this in step with
# data/sounds.json.
TIP_HALVES = {RL: ("윗잇몸", "동그랗게"), FP: ("터뜨리", "아랫입술"), VB: ("터뜨리", "아랫입술"),
              TH_S: ("윗잇몸", "내밀고"), TH_D: ("윗잇몸", "내밀고"), Z_J: ("입천장", "벌 소리")}
# Words for the mouth that any tip uses: in an answer with no tip given they are a tip made up (todo 29: a word not
# heard got an F tip the Mac never sent)
MOUTH = ("혀", "입술", "윗니", "아랫니", "잇몸", "입천장", "목을 울", "바람")
SOUND_NAME = re.compile(r"(?<![A-Za-z])[A-Z]{1,2}(?![A-Za-z])")  # R, L, TH in 「R은」, 「TH는」

# Does the word, written in Hangul, end in a final consonant (받침)? line 라인, room 룸: yes; seventy 세븐티, red 레드: no
BATCHIM = {"line": True, "lime": True, "market": True, "marker": False, "room": True, "loom": True, "station": True, "then": True, "on": True,
           "tent": False, "tenth": False, "red": False, "led": False, "rice": False, "lice": False, "fried": False,
           "flied": False, "stage": False, "and": False, "seventy": False, "seventeen": True, "coffee": False,
           "coffees": False, "copies": False, "copy": False, "right": False, "light": False, "ah": False,
           "please": False, "menu": False, "goes": False, "go": False, "where": False, "well": True,
           "far": False, "fall": True, "in": True, "chicken": True, "check": True, "by": False, "fork": False,
           "pork": False, "very": False, "berry": False, "think": False, "sink": False, "there": False,
           "dare": False, "zone": True, "joan": True}
PARTICLE = re.compile(r"([A-Za-z][A-Za-z']*)(이|가|은|는|을|를|과|와)(?![가-힣])")
WITH_BATCHIM, WITHOUT = set("이은을과"), set("가는를와")
# 「짚을」, 「상관없는」, 「혼잣말」: teacher Ryan said how the server sorted a recording, in the words of his prompt
# (phone 2026-11-08: 「대사와 상관없는 말로 들려서 따로 짚을 곳이 없어요」; live: 「…상관없는 혼잣말로 들렸어요」)
# The server's own list (`ASIDE_LEAKS`) too: it drops those sentences, and the model saying them still breaks the rule.
# 「갈라」, 「비어 있」: on a try at the line with no points teacher Ryan read his rules out (todo 40 2, 2026-11-08:
# 「「짚을 것」이 비어 있으니 … 갈라 말하지 않고 …」)
NAMES = tuple(dict.fromkeys(("짚을", "후보", "소리 내는 법", "설명", "자료", "받은", "역할극", "따로 말", "말하지 않을게",
                             "라고 말했", "라고 하셨", "말했는데", "상관없는", "혼잣말", "대사와 다른 말", "갈라", "비어 있",
                             *ASIDE_LEAKS)))
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
    must: tuple[str, ...] = ()  # words the answer has to say (spec record-cancel-skip 6: the skip button)
    never: tuple[str, ...] = ()  # words it must not say
    # teacher Ryan only: the line's tries before this one, oldest first, as (heard, points, Ryan's answer)
    earlier: list[tuple[str, list[Issue], str]] = field(default_factory=list)
    frame: Frame | None = None  # teacher Ryan only; FRAME when None
    before: str = "Welcome. Do you have a reservation?"  # teacher Ryan only: Ryan's line before the learner's


def issue(target: str, heard: str, explain: str = "", sound: tuple[str, str] = ("R", "L")) -> Issue:
    return Issue(target=target, heard=heard, sound=sound if explain else None, explain=explain)


# One made-up line per listed sound but R and L (the cases above have those): the line's word and a word that swaps
# only that sound. A tip changed in data/sounds.json is checked on both Ryans with --case sound.
SOUND_LINES = [
    ("sound F", ("F", "P"), "Is the fork on the table?", "Is the pork on the table?", "fork", "pork"),
    ("sound V", ("V", "B"), "It's a very good view.", "It's a berry good view.", "very", "berry"),
    ("sound TH S", ("TH", "S"), "I think it's open.", "I sink it's open.", "think", "sink"),
    ("sound TH D", ("DH", "D"), "Is there a bus stop near here?", "Is dare a bus stop near here?", "there", "dare"),
    ("sound Z", ("Z", "JH"), "Is this the quiet zone?", "Is this the quiet Joan?", "zone", "Joan"),
]


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
    Case("dropped", "Can I pay by card?", "Can I pay card?", [issue("by", "")], [REST]),
    *(Case(name, line, heard, [issue(t, h, tip(*p), p)], [REST]) for name, p, line, heard, t, h in SOUND_LINES),
    Case("clean", "Thanks for waiting.", "Thanks for waiting.", [], [CLEAN]),
    Case("clean last", "Thanks, you too!", "Thanks, you too!", [], [CLEAN], last=True),
]
FRAME = Frame(title_ko="호텔 체크인", user_role_ko="손님", ryan_role_ko="호텔 직원", place_ko="호텔 프런트",
              goal_ko="방 열쇠 받기")
SUBWAY = Frame(title_ko="지하철 길 알려 주기", user_role_ko="길을 알려 주는 사람", ryan_role_ko="관광객",
               place_ko="지하철역 개찰구 앞", goal_ko="관광객에게 갈아타는 길 알려 주기")
ASIDE = [
    Case("near miss tip", "The room is on the tenth floor.", "The loom is on the tent floor.",
         [issue("room", "loom", RL), issue("tenth", "tent")]),
    # one tip for two words: the feedback prompt needed its own rule for this (todo 29); teacher Ryan gets the same case
    Case("same tip twice", "Do you have fried rice?", "Do you have flied lice?",
         [issue("fried", "flied", RL), issue("rice", "lice", RL)]),
    Case("near miss F", "I'd like two coffees, please.", "I'd like to copies, please.",
         [Issue(target="coffees", heard="copies", sound=("F", "P"), explain=FP)]),
    Case("near miss number", "That's seventy dollars.", "That's seventeen dollars.", [issue("seventy", "seventeen")]),
    Case("near miss span", "My seat is twenty eight.", "My seat is plenty.", [issue("twenty eight", "plenty")]),
    Case("near miss span 2", "Can I check in now?", "Can I chicken now?", [issue("check in", "chicken")]),
    *(Case(name, line, heard, [issue(t, h, tip(*p), p)]) for name, p, line, heard, t, h in SOUND_LINES
      if name != "sound F"),  # F and P: near miss F
    Case("korean question", "Here is your key card.", "What does key card mean?", [], heard_ko="키 카드가 무슨 뜻이에요?"),
    # made up, not what the learner said: a wish about the app and a remark to oneself, both in Korean
    # the line can be skipped now: 「대사를 말해야 넘어가요」 would be wrong (spec record-cancel-skip 6)
    Case("off app wish", "Here is your key card.", "I wish the app showed the meaning first.", [],
         heard_ko="앱이 뜻을 먼저 보여 주면 좋겠어요.", never=("말해야",)),
    Case("off chat", "Here is your key card.", "Oh, I'm so sleepy today.", [], heard_ko="아 오늘 너무 졸리다."),
    # made up: the learner wants to move past the line; Ryan points to 「건너뛰기」 (spec record-cancel-skip 6)
    Case("off skip wish", "Here is your key card.", "I just want to skip this line.", [],
         heard_ko="이 줄은 그냥 넘어가고 싶어요.", must=("건너뛰기",)),
    # made up in the shape of todo 40 1: a Korean question about what the try before pointed out. Ryan answered that
    # he had pointed out nothing: the earlier tries did not go to him
    Case("asks about a point", "Can I get a late checkout?",
         "I don't get why late sounded like lake. Maybe get a was misheard?", [],
         heard_ko="late가 lake처럼 들렸다는 게 이해가 안 돼요. 혹시 get a가 잘못 들린 거 아니에요?",
         earlier=[("Can I get a lake checkout?", [issue("late", "lake")],
                   "나머지 낱말은 다 알아들었어요. 그런데 late가 lake처럼 들렸어요. 한 번 더 해 볼까요?")],
         must=("late", "lake", "get a"),
         never=("짚은 곳은 없", "짚은 곳이 없", "짚은 것은 없", "짚은 것이 없", "짚은 게 없", "짚은 게 아니",
                "짚은 말이 아니", "짚어 드리지 못", "소리가", "또박또박")),
    # made up in the shape of todo 40 2: a try at the line that auto-detection heard as Korean, so no points came.
    # Ryan read out his rules (「짚을 것」, what he would not say) and told the learner to speak slowly
    Case("try heard as korean", "Take Line 2 and get off at Hongdae.", "Take lime too and get of at Hongdae.", [],
         heard_ko="take lime too and get of at 홍대", frame=SUBWAY, never=("천천히", "또박또박", "lime"),
         before="Excuse me, how do I get to Hongdae from here?"),
    Case("try in hangul", "Can I get a late checkout?", "Can I get a rate check out?", [],
         heard_ko="캔 아이 겟 어 레잇 체크아웃", never=("천천히", "또박또박", "rate")),
]


def flags(case: Case, text: str, aside: bool, raw: str = "") -> list[str]:
    """The rules `text` (what the learner sees) breaks. Double quotes are looked for in `raw`, the model's own answer:
    the server drops them from `text`, so a prompt that stops keeping them out would not show there."""
    text = " ".join(text.split())
    out = tip_flags(case, text)
    for i in case.issues:
        if i.target and i.target not in text:
            out.append(f"word not pointed ({i.target})")
        if i.heard and i.heard not in text:
            out.append(f"heard word not said ({i.heard})")
    # the model's own answer: the server drops sentences that name its materials from what the learner sees (todo 40
    # 2), and a name it dropped is still the model breaking the rule
    said = " ".join(raw.split()) if raw else text
    out += [f"names {n!r}" + ("" if n in text else " (server dropped)") for n in NAMES if n in said]
    out += [f"does not say {w!r}" for w in case.must if w not in text]
    out += [f"says {w!r}" for w in case.never if w in text]
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


def _plain(text: str) -> str:
    """Commas, periods and spacing aside: a tip said with a comma left out reads aloud the same."""
    return " ".join(re.sub(r"[,.]", " ", text).split())


def tip_flags(case: Case, text: str) -> list[str]:
    """How `text` says the case's sound tips: each given tip whole and once, nothing named around it, and no tip
    that was not given (todo 29)."""
    text = _plain(text)
    given: dict[str, tuple[str, str]] = {}  # tip -> (the first word it came with, so the flag says which)
    for i in case.issues:
        if i.explain:
            given.setdefault(_plain(i.explain), (i.target, i.explain))
    rest = text
    for t in given:
        rest = rest.replace(t, " ")
    out = []
    for t, (target, raw) in given.items():
        halves = [w in text for w in TIP_HALVES[raw]]
        if t not in text:
            out.append(f"tip {'dropped' if not any(halves) else 'cut' if not all(halves) else 'reworded'} ({target})")
        elif text.count(t) > 1 or any(w in rest for w in TIP_HALVES[raw]):
            out.append(f"tip repeated ({target})")
        elif any(re.search(rf"(?<![A-Za-z]){n}(?![A-Za-z])", rest) for n in set(SOUND_NAME.findall(t))):
            out.append(f"sound named ({target})")
    if not out and any(w in rest for w in MOUTH):
        out.append("tip made up")
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
                    gen = claude.aside(case.frame or FRAME, [("ryan", case.before)],
                                       case.line, case.heard, case.heard_ko, case.issues, case.earlier)
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
