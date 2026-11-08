"""Run Jake's suggestion with the real Claude API and count how its endings mix (costs money).

For each topic, starts with nothing turned down and asks `--presses` times, each time adding the last sentence to
the turned-down list, as pressing 「다른 걸로요」 on the situation screen does. The ending is picked by the server's
own `pick_ending` and the sentence comes from the server's own `Claude.recommend`, on the recommend model
(`JE_CLAUDE_RECOMMEND`, or `--model`). The learner's real recent situations are not used: ten made-up ones per topic
go along (`RECENT`), as the server sends the topic's latest ten; a label echo (todo 21) and most odd sentences came
only with them. Each sentence is printed with the ending it was given and whether the model kept it, the server
swapped the ending there for it (`strip_endings`) or neither, and one that opens with the speaker (`odd_start`); the
sentences are the model's own, so printing them is fine. Prints the tally, tokens and cost at the end.

A suggestion costs about $0.003 on Sonnet and $0.00015 on Haiku (21 calls, the default: about $0.065 and $0.003).
Tell the user how many calls and the cost before running (AGENTS.md).

Run in server/: uv run python scripts/check_jake_recommend.py [--presses N] [--model haiku|sonnet]
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

from je_server.claude import JAKE_ENDINGS, QUICKS, Claude, heard_ending, pick_ending  # noqa: E402
from je_server.config import load_settings  # noqa: E402
from je_server.topics import TOPICS  # noqa: E402

# $ per million tokens in/out, for the models the recommendation can pick (claude.QUICKS)
PRICE = {"claude-sonnet-5-5": (2.0, 10.0), "claude-haiku-5-5": (0.10, 0.50)}
# How a suggestion opens when it starts with the speaker instead of the situation (todo 27): in Jake's voice it
# sounds like Jake is the one doing it
ODD_START = ("제가", "저는", "제이크", "잭", "Jake")

# Made up (REVIEW.md), in the shapes the server keeps: an accepted suggestion keeps Jake's ending, a typed one not
RECENT: dict[str, list[str]] = {
    "tourist": ["명동에서 외국인 관광객이 환전소를 묻는 상황을 골라 봤어요.",
                "지하철에서 외국인 관광객이 이 열차가 홍대입구역에 가는지 묻는 상황",
                "인사동에서 외국인 관광객이 전통 찻집을 추천해 달라고 하는 상황을 추천해요.",
                "버스 정류장에서 외국인 관광객이 교통카드 충전하는 법을 묻는 상황으로 연습해 볼까요?",
                "남대문시장에서 외국인 관광객이 값을 깎아도 되는지 묻는 상황",
                "광화문 광장에서 외국인 관광객이 사진을 찍어 달라고 부탁하는 상황을 골라 봤어요.",
                "편의점에서 외국인 관광객이 유심 카드를 어디서 사는지 묻는 상황을 추천해요.",
                "잠실역에서 외국인 관광객이 롯데월드 가는 출구를 묻는 상황",
                "북촌 한옥마을에서 외국인 관광객이 조용히 해야 하는 곳인지 묻는 상황을 골라 봤어요.",
                "공항버스 정류장에서 외국인 관광객이 인천공항 가는 버스를 묻는 상황"],
    "usa": ["샌프란시스코 호텔 프런트에서 체크인하는 상황을 추천해요.", "식당에서 계산서를 나눠 달라고 하는 상황",
            "뉴욕 지하철역에서 메트로카드 충전하는 법을 묻는 상황을 골라 봤어요.",
            "시애틀 카페에서 디카페인으로 바꿔 달라고 주문하는 상황으로 연습해 볼까요?",
            "렌터카 카운터에서 차를 반납하며 기름을 채웠다고 말하는 상황",
            "공항 보안 검색대에서 노트북을 꺼내야 하는지 묻는 상황을 추천해요.",
            "패스트푸드점에서 감자튀김을 큰 것으로 바꾸는 상황", "약국에서 멀미약을 찾는 상황을 골라 봤어요.",
            "호텔 방 와이파이 비밀번호를 묻는 상황", "택시 기사에게 영수증을 달라고 하는 상황을 추천해요."],
    "other": ["외국 거래처에 전화해서 회의 시간을 바꾸는 상황으로 연습해 볼까요?",
              "해외 쇼핑몰 고객센터에 배송이 늦는다고 문의하는 상황을 골라 봤어요.",
              "외국인 동료에게 회의록을 보내 달라고 부탁하는 상황",
              "영어 화상 회의에서 소리가 안 들린다고 말하는 상황을 추천해요.",
              "외국인 이웃에게 택배를 대신 받아 줄 수 있는지 묻는 상황",
              "해외 호텔에 이메일로 늦게 도착한다고 알리는 상황을 골라 봤어요.",
              "외국인 친구에게 생일 선물로 뭐가 좋을지 묻는 상황",
              "해외 항공사에 전화해서 좌석을 창가로 바꾸는 상황을 추천해요.",
              "영어 학원 상담 전화로 수업 시간을 묻는 상황",
              "외국인 집주인에게 보일러가 고장 났다고 알리는 상황으로 연습해 볼까요?"],
}


def make_claude(client, settings, model: str | None) -> Claude:
    """The server's Claude, on `model` for the recommendation if given, else the recommend setting."""
    return Claude(client, recommender=QUICKS[model or settings.claude_recommend])


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


def odd_start(text: str) -> bool:
    """`text` opens with the speaker; the learner inside the situation (「카페에서 제가 시킨 …」) does not count."""
    return text.lstrip().startswith(ODD_START)


def label(raw: str, said: str, ending: str) -> str:
    """How the suggestion came out: the model kept the ending, the server swapped one in, or neither. An ending the
    server does not know is said as the model wrote it, so `raw == said` alone is not a kept ending."""
    if not said.endswith(ending):
        return "MISSED"
    return "model kept" if raw == said else "swapped"


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--presses", type=int, default=7, help="suggestions per topic")
    ap.add_argument("--model", choices=tuple(QUICKS), help="the recommend model (default: JE_CLAUDE_RECOMMEND)")
    args = ap.parse_args()
    s = load_settings()
    counting = Counting(anthropic.AsyncAnthropic(api_key=s.anthropic_api_key))
    claude = make_claude(counting, s, args.model)
    print(f"model {claude.recommender['model']}")
    given: Counter[str] = Counter()
    how: Counter[str] = Counter()
    repeats = odd = 0
    for topic in TOPICS:
        turned_down: list[str] = []
        for _ in range(args.presses):
            ending = pick_ending(turned_down)
            text = await claude.recommend(RECENT[topic.id], turned_down, topic, ending)
            kept = label(counting.raw[-1], text, ending)
            given[ending] += 1
            how[kept] += 1
            heard_before = heard_ending(turned_down[-1]) if turned_down else None
            repeats += heard_before is not None and heard_ending(text) == heard_before
            odd += odd_start(text)
            print(f"{topic.id:8} {ending:16} {kept:10}  {text}" + ("  !! odd start" if odd_start(text) else ""))
            turned_down.append(text)
    total = sum(given.values())
    cost = sum(i * PRICE[m][0] / 1e6 + o * PRICE[m][1] / 1e6 for m, i, o in counting.usage)
    print(f"\nsuggestions {total}: " + ", ".join(f"{k} {how[k]}" for k in ("model kept", "swapped", "MISSED")))
    print(f"same ending heard twice in a row {repeats}, opening with the speaker {odd}")
    for ending, _ in JAKE_ENDINGS:
        print(f"  {ending}: {given[ending]}")
    tokens_in = sum(i for _, i, _ in counting.usage)
    tokens_out = sum(o for _, _, o in counting.usage)
    print(f"calls {len(counting.usage)}, tokens in {tokens_in} out {tokens_out}, ${cost:.4f}")


if __name__ == "__main__":
    asyncio.run(main())
