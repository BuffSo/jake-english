"""Run Jake's suggestion with the real Claude API and count how its endings mix (costs money).

For each topic, starts with nothing turned down and asks `--presses` times, each time adding the last sentence to
the turned-down list, as pressing 「다른 걸로요」 on the situation screen does. The ending is picked by the server's
own `pick_ending` and the sentence comes from the server's own `Claude.recommend`. The learner's real recent
situations are not used. Each sentence is printed with the ending it was given and whether the model kept it, the
server swapped a known ending for it (`swap_ending`) or neither; the sentences are the model's own, so printing
them is fine. Prints the tally, tokens and cost at the end.

A suggestion costs about $0.0001 on Haiku (21 calls, the default, about $0.003). Tell the user how many calls and
the cost before running (AGENTS.md).

Run in server/: uv run python scripts/check_jake_recommend.py [--presses N]
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import anthropic  # noqa: E402

from je_server.claude import JAKE_ENDINGS, QUICKS, Claude, pick_ending  # noqa: E402
from je_server.config import load_settings  # noqa: E402
from je_server.topics import TOPICS  # noqa: E402

# $ per million tokens in/out, for the quick models server/.env can pick (claude.QUICKS)
PRICE = {"claude-sonnet-5-5": (2.0, 10.0), "claude-haiku-5-5": (0.10, 0.50)}


class Counting:
    """Wraps the client to add up usage per call and keep the sentence as the model wrote it."""

    def __init__(self, inner):
        self.inner, self.messages = inner, self
        self.usage: list[tuple[str, int, int]] = []
        self.raw: list[str] = []

    async def create(self, **kw):
        resp = await self.inner.messages.create(**kw)
        self.usage.append((kw["model"], resp.usage.input_tokens, resp.usage.output_tokens))
        text = next((b.text for b in resp.content if b.type == "text"), "")
        try:
            self.raw.append(str(json.loads(text).get("request_ko", "")).strip())
        except (json.JSONDecodeError, AttributeError):
            self.raw.append("")
        return resp


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--presses", type=int, default=7, help="suggestions per topic")
    args = ap.parse_args()
    s = load_settings()
    counting = Counting(anthropic.AsyncAnthropic(api_key=s.anthropic_api_key))
    claude = Claude(counting, quick=QUICKS[s.claude_quick])
    given: Counter[str] = Counter()
    how: Counter[str] = Counter()
    repeats = 0
    for topic in TOPICS:
        turned_down: list[str] = []
        for _ in range(args.presses):
            ending = pick_ending(turned_down)
            text = await claude.recommend([], turned_down, topic, ending)
            kept = "model kept" if counting.raw[-1] == text else ("swapped" if text.endswith(ending) else "MISSED")
            given[ending] += 1
            how[kept] += 1
            heard_before = next((e for e, _ in JAKE_ENDINGS if turned_down and turned_down[-1].endswith(e)), None)
            repeats += text.endswith(heard_before) if heard_before else 0
            print(f"{topic.id:8} {ending:16} {kept:10}  {text}")
            turned_down.append(text)
    total = sum(given.values())
    cost = sum(i * PRICE[m][0] / 1e6 + o * PRICE[m][1] / 1e6 for m, i, o in counting.usage)
    print(f"\nsuggestions {total}: " + ", ".join(f"{k} {how[k]}" for k in ("model kept", "swapped", "MISSED")))
    print(f"same ending heard twice in a row {repeats}")
    for ending, _ in JAKE_ENDINGS:
        print(f"  {ending}: {given[ending]}")
    tokens_in = sum(i for _, i, _ in counting.usage)
    tokens_out = sum(o for _, _, o in counting.usage)
    print(f"calls {len(counting.usage)}, tokens in {tokens_in} out {tokens_out}, ${cost:.4f}")


if __name__ == "__main__":
    asyncio.run(main())
