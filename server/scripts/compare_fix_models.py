"""Compare Sonnet and Haiku as the picker of the corrections after a free talk, on made-up conversations (real Claude
API, costs cents).

Each case is a made-up talk (every line below is invented, so the output may be printed and quoted). Both models get
the same input through the server's own `Claude.fixes`, the order swapping by case so a slow minute hits both alike
(docs/guide/PROMPT_일마다_모델_견주기_20261108.md). Every raw item and what `fixes.check` kept is printed, plus the rules a
run broke: more than three items, an item on a turn that must not be fixed (`keep_off`), items the Mac dropped.
Whether a kept correction is wrong (a right sentence "fixed", a recognition slip called a grammar mistake) is judged by
reading the output.

Money: Sonnet about 0.5 cent a call, Haiku a tenth of that; the default 7 cases x 3 runs x 2 models is 42 calls,
about $0.12 (real API credit, outside the subscription). Say so before running (AGENTS.md).

    uv run python scripts/compare_fix_models.py [--runs 3] [--only N]    (PYTHONPATH=. if je_server is not found)
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from dataclasses import dataclass, field
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS.parent))
sys.path.insert(0, str(SCRIPTS))

import anthropic  # noqa: E402

from compare_quick_models import Counting, cost  # noqa: E402
from je_server.claude import WRITERS, Claude, ClaudeUnavailable  # noqa: E402
from je_server.config import load_settings  # noqa: E402
from je_server.fixes import MAX_FIXES, Found, check  # noqa: E402

MODELS = {"sonnet": WRITERS["sonnet"], "haiku": WRITERS["haiku"]}


@dataclass(frozen=True)
class Case:
    name: str
    conversation: list[tuple[str, str]]  # ("ryan" | "user", what was said); the turn number is the position
    keep_off: set[int] = field(default_factory=set)  # my turns that must not be fixed


CASES: list[Case] = [
    Case("right English only", [
        ("ryan", "Hi! What did you do today?"), ("user", "I went to the market and bought some apples."),
        ("ryan", "Nice! What will you make with them?"), ("user", "I'm going to bake a pie for my friends."),
        ("ryan", "Sounds delicious! When are they coming?"), ("user", "They will come to my house on Saturday."),
    ], {1, 3, 5}),
    Case("two grammar mistakes", [
        ("ryan", "What did you do last weekend?"), ("user", "Last weekend I go to the mountain with my brother."),
        ("ryan", "Sounds fun! Was the weather good?"), ("user", "Yes, it was sunny. We eat lunch on the top."),
        ("ryan", "Lovely. Did you take photos?"), ("user", "Yes, I took many photos."),
    ], {5}),
    Case("recognition slip, light for right", [
        ("ryan", "How do I get to the station?"), ("user", "Go straight and turn light at the corner."),
        ("ryan", "Turn right, got it. Is it far?"), ("user", "No, it is about five minutes on foot."),
    ], {3}),
    Case("recognition slip, many sounds", [
        ("ryan", "What did you have for dinner?"),
        ("user", "I had dinner with my family at the Italian rest around near my house."),
        ("ryan", "Nice! What did you order?"), ("user", "We ordered pasta and a big salad."),
    ], {3}),
    Case("asks how to say it", [
        ("ryan", "How was your day?"), ("user", "How do you say I'm hungry in English?"),
        ("ryan", "You can say, I'm starving! Did you skip lunch?"), ("user", "No, I ate lunch but it was small."),
    ], {1, 3}),
    Case("Ryan did not catch it", [
        ("ryan", "What are you doing this weekend?"), ("user", "Yes the uh with my, the go."),
        ("ryan", "Sorry, I didn't catch that. Could you say it again?"),
        ("user", "I am going to visit my grandmother this weekend."),
    ], {1, 3}),
    Case("common short answers", [
        ("ryan", "How was your weekend?"), ("user", "Good."),
        ("ryan", "Nice! Did you see a movie?"), ("user", "Yes, I like it."),
        ("ryan", "Great. Do you want to go again soon?"), ("user", "Maybe next month."),
    ], {1, 3, 5}),
]


def conversation(case: Case) -> tuple[list[dict], dict[int, str]]:
    """The input in the shape `talk.fix_input` makes: every line with its number and speaker, my turns by number."""
    out, turns = [], {}
    for i, (who, text) in enumerate(case.conversation):
        out.append({"차례": i, "말한 사람": "라이언" if who == "ryan" else "학습자", "말": text})
        if who == "user":
            turns[i] = text
    return out, turns


def flags(raw: list[dict], checked: list[Found], case: Case) -> list[str]:
    out = []
    if len(raw) > MAX_FIXES:
        out.append(f"{len(raw)} items")
    out += [f"keep-off turn {i}" for i in sorted({it.get("idx") for it in raw if it.get("idx") in case.keep_off})]
    if (dropped := len(raw) - len(checked)) > 0:
        out.append(f"dropped {dropped}")
    return out


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--only", type=int, help="one case by its number (from 1)")
    ap.add_argument("--models", nargs="+", choices=list(MODELS), default=list(MODELS), help="default: both")
    args = ap.parse_args()
    models = {m: MODELS[m] for m in args.models}
    client = anthropic.AsyncAnthropic(api_key=load_settings().anthropic_api_key, max_retries=2, timeout=60)
    counting = {m: Counting(client) for m in models}
    claude = {m: Claude(counting[m], writer=models[m]) for m in models}
    cases = [CASES[args.only - 1]] if args.only else CASES
    stat = {m: {"n": 0, "flagged": 0, "keep_off": 0, "items": 0, "kept": 0, "failed": 0} for m in models}
    for c, case in enumerate(cases):
        print(f"\n## {case.name}")
        for i, (who, text) in enumerate(case.conversation):
            print(f"   {i} {who:5} {text}" + ("   (keep off)" if i in case.keep_off else ""))
        conv, turns = conversation(case)
        for run in range(args.runs):
            for m in (list(models) if (c + run) % 2 == 0 else list(reversed(models))):
                s = stat[m]
                s["n"] += 1
                try:
                    raw = await claude[m].fixes(conv)
                except ClaudeUnavailable as e:
                    s["failed"] += 1
                    print(f"  {m:6} !! {e}")
                    continue
                kept = check(raw, turns)
                f = flags(raw, kept, case)
                s["items"] += len(raw)
                s["kept"] += len(kept)
                s["flagged"] += bool(f)
                s["keep_off"] += any(x.startswith("keep-off") for x in f)
                print(f"  {m:6} {len(raw)} items, {len(kept)} kept" + (f"   [{', '.join(f)}]" if f else ""))
                for it in raw:
                    sound = it.get("sound") or {}
                    guess = f"  (heard {sound['heard']} / meant {sound['meant']})" if sound.get("heard") else ""
                    print(f"           turn {it.get('idx')}: {it.get('said')!r} -> {it.get('fixed')!r}{guess}")
                    print(f"             {it.get('why_ko')}")
                for x in kept:
                    print(f"         kept turn {x.of}: {x.fixed!r}  {x.why_ko}")
    print("\nmodel: runs, flagged, hit a keep-off turn, items / kept, failed, cost")
    for m, s in stat.items():
        print(f"  {m}: {s['n']}, {s['flagged']}, {s['keep_off']}, {s['items']} / {s['kept']}, {s['failed']}, "
              f"${cost(counting[m].log):.4f}")


if __name__ == "__main__":
    asyncio.run(main())
