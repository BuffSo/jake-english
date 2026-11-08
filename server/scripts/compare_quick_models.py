"""Compare the models the quick jobs can pick (claude.QUICKS) on the same made-up inputs (real Claude API, costs money).

The three quick jobs go through the server's own `Claude`: Sohee's interpretation (`interpret`, JE_CLAUDE_QUICK),
Jake's recommendation (`recommend`, JE_CLAUDE_RECOMMEND) and Ryan's feedback on a followed line (`feedback`,
JE_CLAUDE_QUICK). Interpretation and feedback ask each input of every model in turn, the order alternating, so a
slow minute hits both. Recommendations run one model after the other: each model's turned-down list follows its own
answers, so their inputs part after the first press anyway.
- interpret: the made-up lines below, the kinds that go wrong (numbers, directions, idioms, short answers)
- recommend: per topic `--presses` suggestions, each turned down for the next as 「다른 걸로요」 does, with the ending
  from the server's `pick_ending` (same seed for every model) and check_jake_recommend's ten made-up recent situations
- feedback: check_ryan_wording's made-up cases and rule flags, timed to the first text, the first sentence (the voice
  starts there) and the end
Every answer is printed for reading (the inputs are made up, so the answers may be quoted); quality is judged by
reading them, the flags only point at known mistakes. A summary per job and model ends the run: time, flags, cost.
`--out` keeps every row as JSON.

Default run (`--runs 2 --presses 7`): 138 calls, about $0.27 (Sonnet $0.0019 an interpretation, $0.003 a suggestion,
$0.006 a feedback; Haiku about a twentieth). Tell the user how many calls and the cost before running (AGENTS.md).

Run in server/: uv run python scripts/compare_quick_models.py [--only interpret|recommend|feedback] [--runs N]
                [--presses N] [--seed N] [--out results.json]
"""
from __future__ import annotations

import argparse
import asyncio
import json
import random
import re
import statistics
import sys
import time
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS.parent))
sys.path.insert(0, str(SCRIPTS))

import anthropic  # noqa: E402

import check_jake_recommend as cjr  # noqa: E402
import check_ryan_wording as crw  # noqa: E402
from je_server.claude import QUICKS, Claude, ClaudeUnavailable, heard_ending, pick_ending, strip_endings  # noqa: E402
from je_server.config import load_settings  # noqa: E402
from je_server.models import Frame  # noqa: E402
from je_server.topics import TOPICS  # noqa: E402

# $ per million tokens in/out, for every model a quick job can pick: check_jake_recommend's table (one place to fix)
PRICE = cjr.PRICE


class Counting:
    """Wraps the client: usage and the model's own text for each call, created or streamed."""

    def __init__(self, inner, log: list | None = None):
        self.inner, self.messages = inner, self
        self.log = log if log is not None else []

    def with_options(self, **kw):
        return Counting(self.inner.with_options(**kw), self.log)

    async def create(self, **kw):
        resp = await self.inner.messages.create(**kw)
        self.log.append({"model": kw["model"], "in": resp.usage.input_tokens, "out": resp.usage.output_tokens,
                         "raw": next((b.text for b in resp.content if b.type == "text"), "")})
        return resp

    def stream(self, **kw):
        manager, log = self.inner.messages.stream(**kw), self.log

        class Recorded:
            async def __aenter__(self):
                self.s = await manager.__aenter__()
                return self.s

            async def __aexit__(self, *exc):
                if exc[0] is None:
                    m = await self.s.get_final_message()
                    log.append({"model": kw["model"], "in": m.usage.input_tokens, "out": m.usage.output_tokens,
                                "raw": "".join(b.text for b in m.content if b.type == "text")})
                return await manager.__aexit__(*exc)

        return Recorded()


def cost(entries: list[dict]) -> float:
    return sum(e["in"] * PRICE[e["model"]][0] / 1e6 + e["out"] * PRICE[e["model"]][1] / 1e6 for e in entries)


def _frame(title: str, user: str, ryan: str, place: str, goal: str) -> Frame:
    return Frame(title_ko=title, user_role_ko=user, ryan_role_ko=ryan, place_ko=place, goal_ko=goal)


CAFE = _frame("카페에서 주문하기", "손님", "바리스타", "시애틀의 카페", "음료 주문하고 계산하기")
TOURIST = _frame("길을 묻는 관광객 돕기", "길을 아는 한국 사람", "외국인 관광객", "서울 시내 거리", "관광객에게 길 알려 주기")
HOTEL = _frame("호텔 체크인", "손님", "호텔 직원", "보스턴의 호텔 프런트", "방 열쇠 받기")
OFFICE = _frame("동료와 점심 먹기", "회사 동료", "회사 동료", "회사 근처 식당", "점심 먹으며 이야기하기")
TRAIN = _frame("기차표 사기", "여행객", "역무원", "뉴욕 기차역 매표소", "보스턴 가는 기차표 사기")
SHOP = _frame("운동화 사이즈 묻기", "손님", "신발 가게 점원", "로스앤젤레스의 신발 가게", "맞는 사이즈 찾기")
PARK = _frame("공원에서 사진 부탁받기", "공원에 놀러 온 사람", "외국인 관광객", "한강 공원", "관광객 사진 찍어 주기")
RIDE = _frame("차량 호출 기사 만나기", "승객", "차량 호출 기사", "공항 픽업 구역", "예약한 차 타기")

# made up (REVIEW.md): (name, frame, line, line before, line after)
INTERPRET = [
    ("number price", CAFE, ("ryan", "That'll be twelve fifty. Cash or card?"),
     ("user", "Can I get two iced lattes to go?"), ("user", "Card, please.")),
    ("directions", TOURIST, ("user", "Go straight two blocks, then take the second left after the bank."),
     ("ryan", "Excuse me, how do I get to the art museum?"), ("ryan", "Second left after the bank. Got it.")),
    ("can't miss it", TOURIST, ("user", "It's right across from the subway exit. You can't miss it."),
     ("ryan", "Is the market far from here?"), ("ryan", "Great, thanks a lot!")),
    ("number floor time", HOTEL,
     ("ryan", "You're in room fourteen-oh-two, on the fourteenth floor. Checkout's at eleven."),
     ("user", "Hi, I have a reservation under Kim."), ("user", "Great. Is breakfast included?")),
    ("idiom on me", OFFICE, ("ryan", "Put your wallet away. It's on me today."),
     ("user", "How much do I owe you?"), ("user", "Thanks, I'll get the next one.")),
    ("not at all", PARK, ("ryan", "Not at all. Go ahead."),
     ("user", "Do you mind if I sit here for a minute?"), ("user", "Thanks.")),
    ("you bet", PARK, ("user", "You bet. Say cheese!"),
     ("ryan", "Could you take a picture of us with the bridge behind?"), ("ryan", "Perfect, thank you so much!")),
    ("all ears", OFFICE, ("ryan", "Sure, I'm all ears. What's on your mind?"),
     ("user", "Can I ask you something about the new project?"), None),
    ("track and time", TRAIN, ("ryan", "The next one to Boston leaves at four forty-five from track nine."),
     ("user", "When's the next train to Boston?"), ("user", "Okay. One ticket, please.")),
    ("hold on", SHOP, ("ryan", "Hold on a sec. Let me check in the back if we have a ten and a half."),
     ("user", "Do you have these in a size ten and a half?"), ("user", "Sure, take your time.")),
    ("yep that's me", RIDE, ("user", "Yep, that's me. Can I put my bag in the trunk?"),
     ("ryan", "Hi, are you Minsu?"), ("ryan", "Sure, I'll pop it open for you.")),
    ("worth it", SHOP, ("ryan", "They're a little pricey, but trust me, they're totally worth it."),
     ("user", "How much are these?"), ("user", "Hmm, I'll think about it.")),
]

# words that mean the model said what it was given rather than suggested: the message's labels and lists
LEAKS = ("끝말", "학습자", "learner", "주제:", "예:", "목록", "최근", "다른 상황", "거절")
ODD_START = ("제가", "저는", "제이크", "잭", "Jake")


def _situation(text: str) -> str:
    """`text` without its ending and a 상황 at its end, letters only: what a repeat is told by. A recent situation
    keeps the ending it was said with, or none when the learner typed it (todo 28 1: 「…상황을 골라 봤어요.」 said
    again as 「…상황을 추천해요.」 slipped through)."""
    stem = strip_endings(text)
    return re.sub(r"\W", "", stem if stem is not None else text).removesuffix("상황")


def rec_flags(raw: str, said: str, ending: str, seen: list[str]) -> list[str]:
    """Known mistakes in a recommendation: `raw` as the model wrote it, `said` as the server says it, `seen` the
    situations it was told to avoid."""
    out = []
    if not said.endswith(ending):
        out.append("MISSED ending")
    elif raw != said:
        out.append("swapped")
    out += [f"says {w!r}" for w in LEAKS if w in raw]
    if raw.startswith(ODD_START):
        out.append("odd start")
    if strip_endings(raw) is not None and strip_endings(raw[: raw.rfind("상황")]) is not None:
        out.append("doubled ending")
    if any((stem := _situation(s)) and stem in _situation(said) for s in seen):
        out.append("repeats a listed situation")
    if said.count(".") + said.count("?") > 1:
        out.append("more than one sentence")
    return out


def _request_ko(raw: str) -> str:
    try:
        return str(json.loads(raw).get("request_ko", ""))
    except (json.JSONDecodeError, AttributeError):
        return ""


def _order(models: dict, i: int) -> list:
    items = list(models.items())
    return items if i % 2 == 0 else items[::-1]


async def run_interpret(models: dict, runs: int) -> list[dict]:
    rows = []
    for i, (name, frame, line, before, after) in enumerate(INTERPRET):
        for r in range(runs):
            for key, (claude, counting) in _order(models, i + r):
                n0, t0 = len(counting.log), time.perf_counter()
                try:
                    ko = await claude.interpret(frame, line, before, after)
                except ClaudeUnavailable as e:
                    ko = f"!! {e}"
                secs = time.perf_counter() - t0
                rows.append({"job": "interpret", "case": name, "model": key, "ko": ko, "secs": secs,
                             "calls": len(counting.log) - n0, "cost": cost(counting.log[n0:])})
                print(f"{name:18} {key:6} {secs:4.1f}s  {line[1]}\n{'':26}{ko}")
    return rows


async def run_recommend(models: dict, presses: int, seed: int) -> list[dict]:
    rows = []
    for key, (claude, counting) in models.items():
        for t_i, topic in enumerate(TOPICS):
            rng, turned_down, recent = random.Random(seed + t_i), [], cjr.RECENT[topic.id]
            for p in range(presses):
                ending = pick_ending(turned_down, rng)
                n0, t0 = len(counting.log), time.perf_counter()
                try:
                    said = await claude.recommend(recent, turned_down, topic, ending)
                except ClaudeUnavailable as e:
                    said = f"!! {e}"
                secs = time.perf_counter() - t0
                raw = _request_ko(counting.log[-1]["raw"]) if len(counting.log) > n0 else ""
                flags = rec_flags(raw, said, ending, recent + turned_down + [pk.title_ko for pk in topic.picks])
                before = heard_ending(turned_down[-1]) if turned_down else None
                rows.append({"job": "recommend", "case": f"{topic.id}#{p}", "model": key, "ending": ending,
                             "raw": raw, "said": said, "flags": flags, "secs": secs, "cost": cost(counting.log[n0:]),
                             "repeat_ending": before is not None and heard_ending(said) == before})
                shown = f"  !! {', '.join(flags)}" if flags else ""
                print(f"{key:6} {topic.id:8} {secs:4.1f}s {ending:14} {said}{shown}")
                turned_down.append(said)
    return rows


async def run_feedback(models: dict, runs: int) -> list[dict]:
    rows = []
    for i, case in enumerate(crw.FEEDBACK):
        for r in range(runs):
            for key, (claude, counting) in _order(models, i + r):
                n0, t0 = len(counting.log), time.perf_counter()
                first = sentence = None
                parts: list[str] = []
                try:
                    async for piece in claude.feedback(case.line, case.heard, case.praise, case.issues, case.last):
                        now = time.perf_counter() - t0
                        first = first or now
                        parts.append(piece)
                        if sentence is None and re.search(r"[.?!]", "".join(parts)):
                            sentence = now
                    text = "".join(parts)
                except ClaudeUnavailable as e:
                    text = f"!! {e}"
                raw = counting.log[-1]["raw"] if len(counting.log) > n0 else ""
                flags = crw.flags(case, text, False, raw)
                rows.append({"job": "feedback", "case": case.name, "model": key, "text": text, "flags": flags,
                             "first": first or 0.0, "sentence": sentence or 0.0, "total": time.perf_counter() - t0,
                             "chars": len(text), "cost": cost(counting.log[n0:])})
                print(f"{case.name:15} {key:6} first {first or 0:.2f}s sentence {sentence or 0:.2f}s\n   {text}"
                      + (f"\n   !! {', '.join(flags)}" if flags else ""))
    return rows


def summary(rows: list[dict]) -> None:
    def med_max(xs):
        return f"median {statistics.median(xs):.2f}s, max {max(xs):.2f}s"

    for job in ("interpret", "recommend", "feedback"):
        for key in sorted({r["model"] for r in rows if r["job"] == job}):
            ms = [r for r in rows if r["job"] == job and r["model"] == key]
            c = sum(r["cost"] for r in ms)
            line = f"{job:9} {key:6} n={len(ms)} ${c:.4f} (${c / len(ms):.5f} each)"
            if job == "interpret":
                line += f" | {med_max([r['secs'] for r in ms])} | retried {sum(r['calls'] > 1 for r in ms)}"
            elif job == "recommend":
                line += (f" | {med_max([r['secs'] for r in ms])}"
                         f" | flagged {sum(any(f != 'swapped' for f in r['flags']) for r in ms)}"
                         f", swapped {sum('swapped' in r['flags'] for r in ms)}"
                         f", same ending twice {sum(r['repeat_ending'] for r in ms)}")
            else:
                line += (f" | first text {med_max([r['first'] for r in ms])}"
                         f" | first sentence {med_max([r['sentence'] for r in ms])}"
                         f" | end {med_max([r['total'] for r in ms])}"
                         f" | broke a rule {sum(bool(r['flags']) for r in ms)}")
            print(line)


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", choices=("interpret", "recommend", "feedback"))
    ap.add_argument("--runs", type=int, default=2, help="asks per interpretation line and feedback case")
    ap.add_argument("--presses", type=int, default=7, help="suggestions per topic")
    ap.add_argument("--seed", type=int, default=100, help="for the endings picked")
    ap.add_argument("--out", default="", help="keep every row in this JSON file")
    args = ap.parse_args()
    s = load_settings()
    client = anthropic.AsyncAnthropic(api_key=s.anthropic_api_key)
    models = {}
    for key, preset in QUICKS.items():
        counting = Counting(client)
        models[key] = (Claude(counting, quick=preset, recommender=preset), counting)
    rows: list[dict] = []
    if args.only in (None, "interpret"):
        rows += await run_interpret(models, args.runs)
    if args.only in (None, "recommend"):
        rows += await run_recommend(models, args.presses, args.seed)
    if args.only in (None, "feedback"):
        rows += await run_feedback(models, args.runs)
    print()
    summary(rows)
    logs = [e for _, c in models.values() for e in c.log]
    print(f"calls {len(logs)}, ${cost(logs):.4f}")
    if args.out:
        Path(args.out).write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    asyncio.run(main())
