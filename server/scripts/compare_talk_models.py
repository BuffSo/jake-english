"""Compare Haiku and Sonnet as Ryan the free-talk partner on made-up conversations (real Claude API, costs cents).

Each case is asked of both models in turn, the order swapping by case, so a slow minute hits both alike
(docs/guide/PROMPT_일마다_모델_견주기_20261108.md). Prints every reply (all inputs are made up), the rules a reply
broke, and per model the time to the first text and the first sentence, and the cost.

    uv run python scripts/compare_talk_models.py [--runs 3] [--only N]
"""
from __future__ import annotations

import argparse
import asyncio
import re
import statistics
import time

import anthropic

from je_server.claude import QUICKS, WRITERS, Claude
from je_server.config import load_settings
from je_server.sentences import SentenceBuffer

# A draft of the partner's instructions; the prompt that ships is in je_server/prompts.py once written.
SYSTEM = """\
You are Ryan, an English conversation partner in a speaking-practice app. The learner is a Korean adult who
understands some English but is not confident speaking it. You chat in English about everyday life.

How you reply:
- Two or three sentences, never more, and under 35 words in all, in plain everyday English a learner can follow.
- Begin with a short reaction of two to five words that fits what they said. It is spoken first, so keep it short.
  Vary it: do not begin with a reaction you already used in this conversation.
- Then, if you like, one short comment or a little about yourself, and end with one easy question, so the learner
  has something to answer.
- Follow what the learner wants to talk about.
- Never correct the learner's English and never comment on mistakes: corrections come after the conversation.
  If you understand what they mean, just answer it.
- The learner's words come from speech recognition and may contain wrong words. Guess the meaning from the
  conversation. If it still does not make sense, do not make up what they meant: say kindly that you did not catch
  it and ask them to say it again.
- If the learner asks you something, answer briefly as Ryan, then ask back.
- Plain text only: no lists, no quotation marks, no emojis, no stage directions.
"""
START = "(The learner opened free talk.)"

# (name, conversation so far: Ryan's opener first, then turns alternating learner / Ryan, ending with the learner)
CASES: list[tuple[str, list[str]]] = [
    ("first answer", ["Hi! What did you do today?", "I went to the park with my dog this morning."]),
    ("one word", ["How was your weekend?", "Good."]),
    ("grammar mistakes", ["What did you do yesterday?", "Yesterday I go to shopping mall and buy two shoes."]),
    ("misheard words", ["What did you have for lunch?",
                        "I eat the lunch with my coworker at the Korean rest around near my office."]),
    ("asks back", ["What do you usually do on weekends?", "I usually cook at home.", "Nice! What do you like to cook?",
                   "Kimchi stew. What about you? Do you like cooking?"]),
    ("stuck", ["Do you have any plans for the holidays?", "Um... I don't know."]),
    ("long turn", ["How is work these days?",
                   "I am thinking about changing my job because my company is too far from my house, it takes one "
                   "hour and half by subway."]),
    ("late in the talk", ["Do you like traveling?", "Yes, I like it very much.", "Me too! Where did you go last?",
                          "I went to Busan last summer.", "Busan is great. Did you go to the beach?",
                          "Yes, Haeundae beach. It was very crowded.", "I bet! What did you eat there?",
                          "I ate raw fish, very fresh.", "Yum. Where do you want to go next?",
                          "I want to go to Japan next month."]),
    ("changes topic", ["What did you do today?", "I worked all day.", "That sounds tiring. Was it busy?",
                       "By the way, it is raining a lot today."]),
    ("cannot understand", ["What did you do this morning?", "Yes the uh with my, the go."]),
]
EMOJI = re.compile("[\U0001F300-\U0001FAFF☀-➿]")
CORRECTING = re.compile(r"\b(you should say|correct|instead of|did you mean|by the way, we say|grammar|mistake)\b",
                        re.I)
PRICE = {"claude-sonnet-5-5": (2.0, 10.0), "claude-haiku-5-5": (0.10, 0.50)}  # $ per million tokens in/out
# the two settings the server can give the partner: the writer's (Sonnet, effort low) and the quick one's (Haiku)
MODELS = {"sonnet": WRITERS["sonnet"], "haiku": QUICKS["haiku"]}


def messages(turns: list[str]) -> list[dict]:
    out = [{"role": "user", "content": START}]
    for i, t in enumerate(turns):
        out.append({"role": "assistant" if i % 2 == 0 else "user", "content": t})
    return out


def flags(text: str, sentences: list[str]) -> list[str]:
    out = []
    if len(sentences) > 3:
        out.append(f"{len(sentences)} sentences")
    if sentences and len(sentences[0].split()) > 6:
        out.append(f"first sentence {len(sentences[0].split())} words")
    if "?" not in text:
        out.append("no question")
    if re.search(r"[\"“”]", text) or EMOJI.search(text) or re.search(r"^\s*[-*\d]+[.)]?\s", text, re.M):
        out.append("format")
    if CORRECTING.search(text):
        out.append("correcting?")
    if re.search(r"[가-힣]", text):
        out.append("korean")
    return out


async def ask(client, model: dict, turns: list[str]) -> dict:
    kw = Claude(client)._request(model, {})
    if not kw.get("output_config"):
        kw.pop("output_config", None)
    t0 = time.perf_counter()
    first_text = first_sentence = None
    buf, sentences, text = SentenceBuffer(), [], ""
    async with client.messages.stream(**kw, max_tokens=300, system=SYSTEM, messages=messages(turns)) as stream:
        async for delta in stream.text_stream:
            first_text = first_text or time.perf_counter() - t0
            text += delta
            got = buf.feed(delta)
            if got and first_sentence is None:
                first_sentence = time.perf_counter() - t0
            sentences += got
        final = await stream.get_final_message()
    whole = time.perf_counter() - t0
    sentences += buf.flush()
    p = PRICE[kw["model"]]
    return {"text": text.strip(), "sentences": sentences, "first_text": first_text or whole,
            "first_sentence": first_sentence or whole,
            "cost": final.usage.input_tokens * p[0] / 1e6 + final.usage.output_tokens * p[1] / 1e6}


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--only", type=int, help="one case by its number (from 1)")
    args = ap.parse_args()
    client = anthropic.AsyncAnthropic(api_key=load_settings().anthropic_api_key, max_retries=2, timeout=30)
    cases = [CASES[args.only - 1]] if args.only else CASES
    stats = {m: {"first_text": [], "first_sentence": [], "cost": 0.0, "flagged": 0, "n": 0} for m in MODELS}
    for c, (name, turns) in enumerate(cases):
        print(f"\n## {name}: …{turns[-1]}")
        for run in range(args.runs):
            order = list(MODELS) if (c + run) % 2 == 0 else list(reversed(MODELS))
            for m in order:
                r = await ask(client, MODELS[m], turns)
                f = flags(r["text"], r["sentences"])
                s = stats[m]
                s["first_text"].append(r["first_text"])
                s["first_sentence"].append(r["first_sentence"])
                s["cost"] += r["cost"]
                s["n"] += 1
                s["flagged"] += bool(f)
                print(f"  {m:6} {r['first_sentence']:.2f}s  {r['text']}" + (f"   [{', '.join(f)}]" if f else ""))
    print("\nmodel: first text / first sentence (median), replies flagged, cost")
    for m, s in stats.items():
        print(f"  {m}: {statistics.median(s['first_text']):.2f}s / {statistics.median(s['first_sentence']):.2f}s, "
              f"{s['flagged']}/{s['n']}, ${s['cost']:.4f}")


if __name__ == "__main__":
    asyncio.run(main())
