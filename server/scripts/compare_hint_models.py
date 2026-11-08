"""Compare Haiku and Sonnet as the writer of Sohee's answer hint on made-up conversations (real Claude API, costs cents).

Each case is a made-up talk ending on a line of Ryan's (every line below is invented, so the output may be printed and
quoted). Both models get the server's own `HINT_SYSTEM` and `HINT_SCHEMA`, the order swapping by case so a slow minute
hits both alike (docs/guide/PROMPT_일마다_모델_견주기_20261108.md). Every hint is printed with the rules it broke:
`hints.check` dropping it, a full sentence that does not start with an opener. Per model: how many hints the check
dropped, how many full sentences did not start with an opener, the median time, and the cost. Whether a hint is easy
and natural is judged by reading the output.

Money: Haiku a fraction of a cent a call, Sonnet about a cent; the default 8 cases x 2 runs x 2 models is 32 calls,
a few cents (real API credit, outside the subscription). Say so before running (AGENTS.md).

    uv run python scripts/compare_hint_models.py [--runs 2]
"""
from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # the server package, as in try_talk.py

import anthropic  # noqa: E402

from je_server import hints  # noqa: E402
from je_server.claude import QUICKS, Claude  # noqa: E402
from je_server.config import load_settings  # noqa: E402
from je_server.prompts import HINT_SCHEMA, HINT_SYSTEM  # noqa: E402  (the prompt that ships)

# (name, the talk so far: Ryan's line first and last, the learner's between)
CASES: list[tuple[str, list[str]]] = [
    ("plans", ["Do you have any plans for this weekend?"]),
    ("no question", ["What did you have for lunch today?", "I ate kimchi stew with my coworkers.",
                     "Oh, nice and warm! I had a sandwich at my desk today."]),
    ("long", ["How was work today?", "It was so busy. I worked until nine.",
              "That sounds tiring. I used to work late a lot too, but now I try to leave by six. How do you relax "
              "after a long day?"]),
    ("yes/no", ["What did you have for lunch today?", "I ate kimchi stew with my coworkers.",
                "Oh, nice and warm! Do you often eat with your coworkers?"]),
    ("opener", ["Hi! What did you do today?"]),
    ("checks", ["What did you do last weekend?", "I go to the moun… mountain with friend.",
                "Sorry, I didn't quite catch that. Did you go hiking with a friend?"]),
    ("abstract", ["Are you a morning person or a night person?", "Night person, I think.",
                  "Me too! What's your favorite way to spend a quiet night?"]),
    ("either", ["Have you watched anything good recently?", "Yes, a Korean drama.",
                "Nice! Do you watch dramas on your phone or on TV?"]),
]
PRICE = {"claude-sonnet-5-5": (2.0, 10.0), "claude-haiku-5-5": (0.10, 0.50)}  # $ per million tokens in/out
MODELS = {"haiku": QUICKS["haiku"], "sonnet": QUICKS["sonnet"]}


def conversation(turns: list[str]) -> list[dict]:
    """The talk as `hints.conversation` gives it: Ryan's lines and the learner's turns."""
    return [{"말한 사람": "라이언" if i % 2 == 0 else "학습자", "말": t} for i, t in enumerate(turns)]


def flags(data: dict | None) -> list[str]:
    """The rules a hint broke: no JSON, `hints.check` dropping it, a full sentence that starts with none of the
    openers (counted apart from the check, which drops it for other reasons too)."""
    if not isinstance(data, dict):
        return ["no json"]
    out = []
    if hints.check(data) is None:
        out.append("check")
    stems = [str(s).replace("…", "").strip().rstrip(",").strip().lower() for s in data.get("starters", [])]
    full = str(data.get("full", "")).lower()
    if not any(full.startswith(x) for x in stems if x):
        out.append("full not from opener")
    return out


async def ask(client, model: dict, turns: list[str]) -> dict:
    kw = Claude(client)._request(model, {"format": {"type": "json_schema", "schema": HINT_SCHEMA}})
    body = json.dumps({"대화": conversation(turns)}, ensure_ascii=False)
    t0 = time.perf_counter()
    resp = await client.messages.create(**kw, max_tokens=400, system=HINT_SYSTEM,
                                        messages=[{"role": "user", "content": body}])
    took = time.perf_counter() - t0
    text = next((b.text for b in resp.content if b.type == "text"), "")
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        data = None
    p = PRICE[kw["model"]]
    return {"data": data, "text": text, "time": took,
            "cost": resp.usage.input_tokens * p[0] / 1e6 + resp.usage.output_tokens * p[1] / 1e6}


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=2)
    ap.add_argument("--only", type=int, help="one case by its number (from 1)")
    args = ap.parse_args()
    client = anthropic.AsyncAnthropic(api_key=load_settings().anthropic_api_key, max_retries=2, timeout=30)
    cases = [CASES[args.only - 1]] if args.only else CASES
    stats = {m: {"t": [], "cost": 0.0, "check": 0, "unfull": 0, "n": 0} for m in MODELS}
    for c, (name, turns) in enumerate(cases):
        print(f"\n## {name}: ...{turns[-1]}")
        for run in range(args.runs):
            order = list(MODELS) if (c + run) % 2 == 0 else list(reversed(MODELS))
            for m in order:
                r = await ask(client, MODELS[m], turns)
                f = flags(r["data"])
                s = stats[m]
                s["t"].append(r["time"])
                s["cost"] += r["cost"]
                s["n"] += 1
                s["check"] += "check" in f
                s["unfull"] += "full not from opener" in f
                d = r["data"]
                show = (f"{d.get('meaning_ko')} | {' / '.join(map(str, d.get('starters', [])))} || {d.get('full')}"
                        if isinstance(d, dict) else r["text"])
                print(f"  {m:6} {r['time']:.2f}s  {show}" + (f"   [{', '.join(f)}]" if f else ""))
    print("\nmodel: median time, dropped by the check, full sentence not from an opener, cost")
    for m, s in stats.items():
        print(f"  {m}: {statistics.median(s['t']):.2f}s, {s['check']}/{s['n']}, {s['unfull']}/{s['n']}, "
              f"${s['cost']:.4f}")


if __name__ == "__main__":
    asyncio.run(main())
