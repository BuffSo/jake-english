"""Compare Haiku and Sonnet as Ryan the free-talk partner on made-up conversations (real Claude API, costs cents).

Each case is asked of both models in turn, the order swapping by case, so a slow minute hits both alike
(docs/guide/PROMPT_일마다_모델_견주기_20261108.md). Prints every reply (all inputs are made up), the rules a reply
broke, and per model the time to the first text and the first sentence, the cost, the recasts on mistake turns and how
often Ryan answered a misheard question back.

    uv run python scripts/compare_talk_models.py [--runs 3] [--only N]
"""
from __future__ import annotations

import argparse
import asyncio
import re
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # the server package, as in try_talk.py

import anthropic  # noqa: E402

from je_server.claude import QUICKS, WRITERS, Claude  # noqa: E402
from je_server.config import load_settings  # noqa: E402
from je_server.prompts import TALK_ECHO, TALK_KOREAN, TALK_START, TALK_SYSTEM  # noqa: E402  (the prompt that ships)
from je_server.sentences import SentenceBuffer  # noqa: E402


# (name, conversation so far: Ryan's opener first, then turns alternating learner / Ryan, ending with the learner)
CASES: list[tuple[str, list[str]]] = [
    ("first answer", ["Hi! What did you do today?", "I went to the park with my dog this morning."]),
    ("one word", ["How was your weekend?", "Good."]),
    ("grammar mistakes", ["What did you do yesterday?", "Yesterday I go to shopping mall and buy two shoes."]),
    ("misheard words", ["What did you have for lunch?",
                        "I eat the lunch with my coworker at the Korean rest around near my office."]),
    ("asks back", ["What do you usually do on weekends?", "I usually cook at home.", "Nice! What do you like to cook?",
                   "Kimchi stew. What about you? Do you like cooking?"]),
    ("how do you say", ["What did you do today?", "How do you say I'm tired in English?"]),
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
    # "and you?" written as a similar-sounding nonsense word: Ryan should take it as the question back and answer
    ("misheard asks back", ["What did you have for lunch today?", "I had kimbap and ramen at my desk. Endu?"]),
]
# cases whose reply should answer for Ryan himself (the learner asked back), counted with `answers_back`
ANSWER_BACK = {"misheard asks back"}
# Ryan telling his own: "I had a sandwich", "I just grabbed a salad", "my lunch was"; not the learner's words back,
# and not "me too", which is also how he agrees
ANSWERED = re.compile(r"\bI('ve| just| also)? (had|ate|grabbed|got|made|tried|went for)\b|\bmy (own )?lunch\b",
                      re.I)
K = TALK_KOREAN
# turns the learner said in Korean (marked as the server marks them); Ryan must answer in English, and answer them
KOREAN_CASES: list[tuple[str, list[str]]] = [
    ("ko: how to say", ["How was work today?", K + "이건 영어로 어떻게 말해요? 회사에서 야근했다고 하고 싶어요."]),
    ("ko: what did you say", ["That sounds tiring. I used to work late a lot too, but now I try to leave by six. "
                              "How do you relax after a long day?", K + "방금 뭐라고 했어요? 잘 못 알아들었어요."]),
    ("ko: ask Ryan", ["Do you have any plans for this weekend?", "Not yet.", "No rush! Something fun will come up.",
                      K + "라이언은 주말에 뭐 했어요?"]),
    ("ko: answer", ["What did you do last weekend?", K + "그냥 집에서 쉬었어요."]),
    ("ko: don't know", ["Are you a morning person or a night person?", K + "모르겠어요."]),
    ("ko: mixed", ["What did you do this morning?", K + "I went to the 시장 시장이 영어로 뭐지?"]),
]
# (name, turns, a regex of the right forms of the learner's own mistaken words). A recast counts only when the reply
# uses such a form; the regexes are anchored to the learner's object ("you went") so that Ryan's own story
# ("I went shopping too") is not counted. Each case is asked twice: with and without the echo mark.
MISTAKES: list[tuple[str, list[str], str]] = [
    ("mistake: go/buy", ["What did you do yesterday?", "Yesterday I go to shopping mall and buy two shoes."],
     r"\byou (went|bought|got)\b|\byou('ve| have) (been|bought)\b"),
    ("mistake: live/have", ["Do you have any family nearby?", "My sister live in Busan and she have two child."],
     r"\b(your sister|she) (lives|has)\b|\byour sister('s| has) (got )?two (children|kids)\b"),
    ("mistake: boring", ["How is your day going?", "I am very boring today, nothing to do."],
     r"\byou('re| are| feel| felt) (so |very |really )?bored\b|\bfeeling bored\b"),
    ("mistake: eat", ["What did you have for lunch?", "I eat bibimbap with my friend at noon."],
     r"\byou (ate|had)\b"),
]
EMOJI = re.compile("[\U0001F300-\U0001FAFF☀-➿]")
CORRECTING = re.compile(r"\b(you should say|correct|instead of|did you mean|by the way, we say|grammar|mistake)\b",
                        re.I)
PRICE = {"claude-sonnet-5-5": (2.0, 10.0), "claude-haiku-5-5": (0.10, 0.50)}  # $ per million tokens in/out
# the two settings the server can give the partner: the writer's (Sonnet, effort low) and the quick one's (Haiku)
MODELS = {"sonnet": WRITERS["sonnet"], "haiku": QUICKS["haiku"]}


def messages(turns: list[str], echo: bool = False) -> list[dict]:
    """As `talk.messages` builds them; `echo` adds TALK_ECHO to the last message, as the server does on every second
    English turn."""
    out = [{"role": "user", "content": TALK_START}]
    for i, t in enumerate(turns):
        out.append({"role": "assistant" if i % 2 == 0 else "user", "content": t})
    if echo:
        out[-1]["content"] += "\n" + TALK_ECHO
    return out


def recasts(text: str, pattern: str | None) -> bool:
    """Whether the reply used a right form of the learner's own mistaken words (`pattern`; None: no mistake)."""
    return bool(pattern) and bool(re.search(pattern, text, re.I))


def answers_back(text: str) -> bool:
    """Whether the reply answers the learner's question back for Ryan himself."""
    return bool(ANSWERED.search(text))


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


async def ask(client, model: dict, turns: list[str], echo: bool = False) -> dict:
    kw = Claude(client)._request(model, {})
    if not kw.get("output_config"):
        kw.pop("output_config", None)
    t0 = time.perf_counter()
    first_text = first_sentence = None
    buf, sentences, text = SentenceBuffer(), [], ""
    async with client.messages.stream(**kw, max_tokens=300, system=TALK_SYSTEM, messages=messages(turns, echo)) as stream:
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


def all_cases() -> list[tuple[str, list[str], bool, str | None]]:
    """(name, turns, echo, recast pattern) in the order they are asked: the plain cases, the Korean turns, then each
    mistake case without and with the echo mark."""
    out = [(n, t, False, None) for n, t in CASES + KOREAN_CASES]
    for n, t, pattern in MISTAKES:
        out += [(n, t, False, pattern), (n + " +echo", t, True, pattern)]
    return out


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--only", type=int, help="one case by its number (from 1)")
    args = ap.parse_args()
    client = anthropic.AsyncAnthropic(api_key=load_settings().anthropic_api_key, max_retries=2, timeout=30)
    cases = all_cases()
    cases = [cases[args.only - 1]] if args.only else cases
    stats = {m: {"first_text": [], "first_sentence": [], "cost": 0.0, "flagged": 0, "korean": 0, "n": 0,
                 "recast": {False: [0, 0], True: [0, 0]},  # recast[echo] = [recasts, mistake runs]
                 "answered": [0, 0]} for m in MODELS}  # [answered, asked-back runs]
    for c, (name, turns, echo, pattern) in enumerate(cases):
        print(f"\n## {name}: ...{turns[-1]}")
        for run in range(args.runs):
            order = list(MODELS) if (c + run) % 2 == 0 else list(reversed(MODELS))
            for m in order:
                r = await ask(client, MODELS[m], turns, echo)
                f = flags(r["text"], r["sentences"])
                s = stats[m]
                s["first_text"].append(r["first_text"])
                s["first_sentence"].append(r["first_sentence"])
                s["cost"] += r["cost"]
                s["n"] += 1
                s["flagged"] += bool(f)
                s["korean"] += "korean" in f
                mark = ""
                if pattern:
                    s["recast"][echo][1] += 1
                    if recasts(r["text"], pattern):
                        s["recast"][echo][0] += 1
                        mark = " <recast>"
                if name in ANSWER_BACK:
                    s["answered"][1] += 1
                    if answers_back(r["text"]):
                        s["answered"][0] += 1
                        mark = " <answered>"
                print(f"  {m:6} {r['first_sentence']:.2f}s  {r['text']}{mark}" + (f"   [{', '.join(f)}]" if f else ""))
    print("\nmodel: first text / first sentence (median), replies flagged, Korean in a reply, cost")
    for m, s in stats.items():
        print(f"  {m}: {statistics.median(s['first_text']):.2f}s / {statistics.median(s['first_sentence']):.2f}s, "
              f"{s['flagged']}/{s['n']}, korean {s['korean']}, ${s['cost']:.4f}")
    print("recasts on mistake turns (without the echo mark / with it)")
    for m, s in stats.items():
        (a, an), (b, bn) = s["recast"][False], s["recast"][True]
        print(f"  {m}: {a}/{an} / {b}/{bn}")
    print("Ryan answered a misheard question back")
    for m, s in stats.items():
        print(f"  {m}: {s['answered'][0]}/{s['answered'][1]}")


if __name__ == "__main__":
    asyncio.run(main())
