"""Measure how long script writing and three-line notes take (real Claude API, costs a few cents).

Prints times, tokens and cost only. Lines and notes are not printed.
Run: uv run python scripts/measure_claude.py [runs]
"""
from __future__ import annotations

import asyncio
import statistics
import sys
import time

import anthropic

from je_server.claude import HAIKU, SONNET, Claude
from je_server.config import load_settings
from je_server.threeline import check

SITUATION = "길에서 외국인이 지하철역 가는 길을 묻는 상황"
PRICE = {"claude-sonnet-5-5": (2.0, 10.0), "claude-haiku-5-5": (0.10, 0.50)}  # $ per million tokens in/out


class Counting:
    """Wraps the client to add up usage per call."""

    def __init__(self, client):
        self.inner = client
        self.calls: list[tuple[str, int, int]] = []
        self.messages = self

    async def create(self, **kw):
        resp = await self.inner.messages.create(**kw)
        self.calls.append((kw["model"], resp.usage.input_tokens, resp.usage.output_tokens))
        return resp


def cost(calls) -> float:
    return sum(i * PRICE[m][0] / 1e6 + o * PRICE[m][1] / 1e6 for m, i, o in calls)


async def run(name: str, model: dict, runs: int, client) -> None:
    script_t, note_t, note_calls, failed, turns = [], [], [], 0, []
    for _ in range(runs):
        counting = Counting(client)
        c = Claude(counting, writer=model)
        t = time.perf_counter()
        frame, draft = await c.make_script(SITUATION)
        script_t.append(time.perf_counter() - t)
        turns.append(sum(1 for s, _ in draft if s == "user"))
        script_calls = list(counting.calls)
        first_user = next(text for s, text in draft if s == "user")
        counting.calls.clear()
        t = time.perf_counter()
        three = await c.annotate(first_user, frame.place_ko)
        note_t.append(time.perf_counter() - t)
        note_calls.append(len(counting.calls))
        failed += bool(check(first_user, three)) or any(not s.ko for w in three.words for s in w.syl)
        print(f"  {name}: script {script_t[-1]:.1f}s ({len(script_calls)} call, {cost(script_calls):.4f}$, "
              f"out {sum(o for _, _, o in script_calls)} tok), note {note_t[-1]:.1f}s "
              f"({note_calls[-1]} call, {cost(counting.calls):.4f}$, out {sum(o for _, _, o in counting.calls)} tok)")
    print(f"{name}: script median {statistics.median(script_t):.1f}s, note median {statistics.median(note_t):.1f}s, "
          f"note calls {note_calls}, user turns {turns}, notes degraded {failed}/{runs}")


async def main() -> None:
    runs = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    s = load_settings()
    client = anthropic.AsyncAnthropic(api_key=s.anthropic_api_key, max_retries=2, timeout=120)
    await run("sonnet", SONNET, runs, client)
    await run("haiku", HAIKU, runs, client)


if __name__ == "__main__":
    asyncio.run(main())
