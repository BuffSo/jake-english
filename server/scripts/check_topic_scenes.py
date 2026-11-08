"""Count the scenes the 「한국에서 영어 쓰기」 topic gets on the real model (spec korea-english-topic 5; costs money).

Jake's suggestion: `--runs` chains of `--presses` suggestions each, every one added to the turned-down list as
「다른 걸로요」 does, on the server's own `Claude.recommend` and recommend model. Recent situations are the made-up
ones of `check_jake_recommend.RECENT` (`--recent filled`, all asking for help, like the learner's records today) or
none (`--recent empty`). `--example` swaps the topic's example for that run, to compare examples.

With `--scripts`, the server's own `Claude.make_script` on the writing model writes scripts for made-up typed
situations (`TYPED`) and for the first three suggestions of the first chain: who speaks first, the frame, every line.

Each line is flagged where a person should read first: someone the learner knows (`known_people`), a scene outside
Korea (`abroad`) and long words (`hard_words`, the user asked for easy everyday words on 2026-11-08). The flags only
point; the scenes (help or small talk, who should start) are read by hand. Inputs are made up and the model's own
sentences are printed, so printing them is fine (REVIEW.md). Prints calls, tokens and cost at the end.

About $0.003 a suggestion and $0.02 a script on Sonnet. Run in server/:
uv run python scripts/check_topic_scenes.py [--runs 2] [--presses 7] [--recent filled|empty] [--example TEXT] [--scripts]
"""
from __future__ import annotations

import argparse
import asyncio
import dataclasses
import importlib.util
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

_spec = importlib.util.spec_from_file_location("check_jake_recommend",
                                               Path(__file__).resolve().parent / "check_jake_recommend.py")
cj = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cj)

# Made up (REVIEW.md): asking for help, greeting first, small talk, and bare one-word places
TYPED = ("명동에서 외국인이 환전소가 어디냐고 묻는 상황",
         "공원에서 산책하다 처음 보는 외국인에게 먼저 인사하는 상황",
         "동네 빵집에서 옆에 선 외국인과 날씨 이야기를 하는 상황",
         "지하철에서 길을 헤매는 외국인에게 먼저 도와줄지 묻는 상황",
         "헬스장", "고궁")

_KNOWN = re.compile(r"동료|친구|직장|회사 사람|상사|선배|후배|룸메이트|아는 사이|"
                    r"\b(?:co-?workers?|colleagues?|friends?|boss|classmates?|roommates?)\b", re.I)
_ABROAD = re.compile(r"뉴욕|미국|하와이|도쿄|일본|파리|런던|해외|중국|베이징|"
                     r"\b(?:new york|tokyo|hawaii|america|united states|paris|london|abroad|overseas)\b", re.I)
HARD_LEN = 11  # letters; long words to read first, not a verdict


def known_people(text: str) -> bool:
    """Someone the learner already knows: the topic is for people never met (spec korea-english-topic 2)."""
    return bool(_KNOWN.search(text))


def abroad(text: str) -> bool:
    """A scene outside Korea. 외국인 alone is not one."""
    return bool(_ABROAD.search(text))


def hard_words(text: str) -> list[str]:
    """Long words in a line, lowercased, in order."""
    return [w.lower() for w in re.findall(r"[A-Za-z']+", text) if len(w.strip("'")) >= HARD_LEN]


def flags(text: str) -> str:
    out = [name for name, hit in (("KNOWN", known_people(text)), ("ABROAD", abroad(text))) if hit]
    if hard := hard_words(text):
        out.append("hard:" + ",".join(hard))
    return ("  !! " + " ".join(out)) if out else ""


async def main() -> None:
    import anthropic

    from je_server.claude import WRITERS, Claude, pick_ending
    from je_server.config import load_settings
    from je_server.topics import get

    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=2, help="chains of suggestions")
    ap.add_argument("--presses", type=int, default=7, help="suggestions per chain")
    ap.add_argument("--recent", choices=("filled", "empty"), default="filled")
    ap.add_argument("--example", help="the topic's example for this run")
    ap.add_argument("--scripts", action="store_true", help="also write scripts")
    args = ap.parse_args()
    s = load_settings()
    counting = cj.Counting(anthropic.AsyncAnthropic(api_key=s.anthropic_api_key))
    claude = Claude(counting, writer=WRITERS[s.claude_writer], recommender=cj.QUICKS[s.claude_recommend])
    topic = get("tourist")
    if args.example:
        topic = dataclasses.replace(topic, example_ko=args.example)
    recent = cj.RECENT["tourist"] if args.recent == "filled" else []
    print(f"recommend {claude.recommender['model']}, writer {claude.writer['model']}, recent {args.recent}, "
          f"example {topic.example_ko}")
    first_chain: list[str] = []
    for run in range(args.runs):
        turned_down: list[str] = []
        for _ in range(args.presses):
            text = await claude.recommend(recent, turned_down, topic, pick_ending(turned_down))
            print(f"suggest {run}  {text}{flags(text)}")
            turned_down.append(text)
        if run == 0:
            first_chain = turned_down
    if args.scripts:
        for situation in (*TYPED, *first_chain[:3]):
            frame, draft = await claude.make_script(situation, topic)
            print(f"\nscript  {situation}\n  first {draft[0][0]}; {frame.title_ko} / Ryan: {frame.ryan_role_ko} / "
                  f"learner: {frame.user_role_ko}{flags(frame.title_ko + ' ' + frame.ryan_role_ko)}")
            for speaker, line in draft:
                print(f"  {speaker:4} {line}{flags(line)}")
    cost = sum(i * cj.PRICE[m][0] / 1e6 + o * cj.PRICE[m][1] / 1e6 for m, i, o in counting.usage)
    tokens_in = sum(i for _, i, _ in counting.usage)
    tokens_out = sum(o for _, _, o in counting.usage)
    print(f"\ncalls {len(counting.usage)}, tokens in {tokens_in} out {tokens_out}, ${cost:.4f}")


if __name__ == "__main__":
    asyncio.run(main())
