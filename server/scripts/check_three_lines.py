"""Measure how often three-line notes pass the machine checks and how many calls they take (real Claude API, costs
money).

The lines come from the Mac's records: every line that already has a note, once per text, with the context the
server gives it (`Engine.context`). Each goes through the server's own `Claude.annotate` with the writer model of
server/.env, one line at a time, and its result is read from the server's own log line (「three-line note: N tries」
or 「three-line note degraded after 3 tries …: kinds」). Nothing of a line or its note is printed: only the result,
calls, time and cost per line and a summary.

A note takes 1 to 3 Sonnet calls, about $0.01 each: 20 lines cost about $0.3 to $0.6. Tell the user how many calls and
the cost before running (AGENTS.md). `--budget` stops starting new lines once that many dollars are spent.

Run in server/: uv run python scripts/check_three_lines.py [--lines 20] [--seed 7] [--only FILE] [--budget 0.7]
`--only FILE`: a text file with one line per row; only the records' lines among them are measured. Keep it outside
the repository: the lines are the learner's.
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import random
import re
import statistics
import sys
import time
from collections import Counter
from collections.abc import Iterable
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS.parent))

import anthropic  # noqa: E402

from je_server.claude import WRITERS, Claude, ClaudeUnavailable  # noqa: E402
from je_server.config import load_settings  # noqa: E402
from je_server.engine import Engine  # noqa: E402
from je_server.models import Roleplay  # noqa: E402
from je_server.store import Store  # noqa: E402

# $ per million tokens in/out (claude-api skill, 2026-11-08)
PRICE = {"claude-sonnet-5-5": (2.0, 10.0), "claude-haiku-5-5": (0.10, 0.50)}
PASSED = re.compile(r"^three-line note: (\d+) tries")
DEGRADED = re.compile(r"^three-line note degraded after \d+ tries, [\d.]+s: ([a-z,]+)$")


def noted_lines(records: Iterable[Roleplay]) -> list[tuple[str, str]]:
    """(text, context) of every line that has a note, once per text, the context from the newest record."""
    seen: dict[str, str] = {}
    for rp in sorted(records, key=lambda r: r.created):
        for line in rp.lines:
            if line.three is not None:
                seen[line.text] = Engine.context(rp, line.idx)
    return list(seen.items())


def sample(lines: list[tuple[str, str]], n: int, seed: int) -> list[tuple[str, str]]:
    ordered = sorted(lines)
    return random.Random(seed).sample(ordered, min(n, len(ordered)))


def outcome(message: str) -> str | None:
    """「1」, 「2」, 「3」 (tries to pass) or 「degraded:kinds」 from `Claude.annotate`'s log line; None for other lines."""
    if m := PASSED.match(message):
        return m.group(1)
    if m := DEGRADED.match(message):
        return f"degraded:{m.group(1)}"
    return None


def summary(rows: list[dict]) -> str:
    tries = Counter(r["outcome"] for r in rows)
    degraded = [r["outcome"].split(":", 1)[1] for r in rows if r["outcome"].startswith("degraded:")]
    kinds = Counter(k for d in degraded for k in d.split(","))
    calls = sum(r["calls"] for r in rows)
    other = len(rows) - sum(tries[k] for k in ("1", "2", "3")) - len(degraded)
    return (f"lines {len(rows)}: first try {tries['1']}, two tries {tries['2']}, three tries {tries['3']}, "
            f"degraded {len(degraded)}"
            + (f" ({', '.join(f'{k} {n}' for k, n in sorted(kinds.items()))})" if kinds else "")
            + (f", other {other}" if other else "")
            + f"; calls {calls} ({calls / max(len(rows), 1):.2f} a line); cost ${sum(r['cost'] for r in rows):.3f}; "
            f"median {statistics.median(r['secs'] for r in rows):.1f}s")


class Counting:
    """Wraps the client to add up the calls and tokens of one line."""

    def __init__(self, client):
        self.inner = client
        self.calls: list[tuple[str, int, int]] = []
        self.messages = self

    async def create(self, **kw):
        resp = await self.inner.messages.create(**kw)
        self.calls.append((kw["model"], resp.usage.input_tokens, resp.usage.output_tokens))
        return resp

    def cost(self) -> float:
        return sum(i * PRICE[m][0] / 1e6 + o * PRICE[m][1] / 1e6 for m, i, o in self.calls)


class LastOutcome(logging.Handler):
    def __init__(self):
        super().__init__()
        self.last: str | None = None

    def emit(self, record: logging.LogRecord) -> None:
        got = outcome(record.getMessage())
        if got is not None:
            self.last = got


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lines", type=int, default=20)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--only", type=Path)
    ap.add_argument("--budget", type=float, default=0.7)
    args = ap.parse_args()
    s = load_settings()
    writer = WRITERS[s.claude_writer]
    if writer["model"] not in PRICE:
        sys.exit(f"no price for {writer['model']}: add it to PRICE first")
    lines = noted_lines(Store(s.data_dir).all())
    if args.only:
        wanted = {t.strip() for t in args.only.read_text().splitlines() if t.strip()}
        lines = [l for l in lines if l[0] in wanted]
    picked = sample(lines, args.lines, args.seed)
    handler = LastOutcome()
    logging.getLogger("je_server").addHandler(handler)
    logging.getLogger("je_server").setLevel(logging.INFO)
    client = anthropic.AsyncAnthropic(api_key=s.anthropic_api_key, max_retries=2, timeout=120)
    rows: list[dict] = []
    for n, (text, context) in enumerate(picked, 1):
        if sum(r["cost"] for r in rows) > args.budget:
            print(f"budget ${args.budget} spent: stopped before line {n}")
            break
        counting = Counting(client)
        handler.last = None
        t0 = time.perf_counter()
        try:
            await Claude(counting, writer=writer).annotate(text, context)
            got = handler.last or "?"
        except ClaudeUnavailable as e:
            got = f"unavailable ({e})"
        rows.append({"outcome": got, "calls": len(counting.calls), "secs": time.perf_counter() - t0,
                     "cost": counting.cost()})
        print(f"line {n}/{len(picked)}: {got}, {len(counting.calls)} calls, {rows[-1]['secs']:.1f}s", flush=True)
    if rows:
        print(f"{writer['model']}: {summary(rows)}")


if __name__ == "__main__":
    asyncio.run(main())
