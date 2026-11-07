"""Situation topics and their prepared lists (spec situation-topics 1, 3).

A topic sets who Ryan and the learner are, and goes to Claude with the script and Jake's suggestion. Each topic may
have a list of situations written beforehand, with real places, shops and menus. To add a topic or a situation, add
a line here; the app shows whatever /home lists.

The facts in the lists were checked on the web on 2026-11-07 (Gyeongbokgung station exit 5 goes straight into the
palace, closed on some evenings; the station top-up machines take cash only and convenience stores top up too;
Giovanni's Shrimp Truck serves shrimp scampi, hot & spicy and lemon butter, each plate with two scoops of rice).
Do not change a fact without checking it again: a wrong route or menu is learned as if it were true.
"""
from __future__ import annotations

from dataclasses import dataclass

from .models import Speaker

OTHER = "other"


@dataclass(frozen=True)
class Pick:
    id: str
    title_ko: str  # the card on the list screen
    situation: str  # what Claude writes the script from, with the facts the script must keep
    first: Speaker


@dataclass(frozen=True)
class Topic:
    id: str
    name_ko: str
    roles_en: str  # who Ryan and the learner are, for the script
    scenes_en: str  # what kind of moments, for Jake's suggestion
    example_ko: str  # one suggestion in Jake's words
    placeholder_ko: str  # the example in the input box when the learner describes it
    first: Speaker | None  # who always speaks first in this topic; None: whoever would in the situation
    picks: tuple[Pick, ...] = ()


TOPICS: tuple[Topic, ...] = (
    Topic(
        id="tourist",
        name_ko="외국인 관광객",
        roles_en=("Ryan is a foreign tourist visiting Korea, a stranger to the learner who comes up and asks for help. "
                  "The learner is a Korean local who helps in English. They are strangers, never coworkers or "
                  "friends."),
        scenes_en=("A foreign tourist in Korea, a stranger, asks the learner for help in English: asking the way, "
                   "how to use the subway, where to eat, and so on. Use real places in Korea. Never people the "
                   "learner knows, such as coworkers or friends."),
        example_ko="인사동에서 외국인 관광객이 한복 빌리는 곳을 묻는 상황으로 연습해 보면 어때요?",
        placeholder_ko="예: 외국인이 명동에서 환전소를 묻는 상황",
        first="ryan",
        picks=(
            Pick("t-gyeongbokgung", "명동역에서 경복궁 가는 길",
                 "명동역 근처에서 외국인 관광객이 경복궁 가는 법을 묻는다. 4호선을 타고 한 정거장 가서 충무로역에서 "
                 "3호선으로 갈아타고, 경복궁역 5번 출구로 나가면 궁으로 바로 이어진다.", "ryan"),
            Pick("t-tmoney", "지하철역에서 교통카드 충전",
                 "서울 지하철역에서 외국인 관광객이 교통카드(티머니)를 충전하는 법을 묻는다. 역의 교통카드 충전기에서 "
                 "현금으로만 충전한다. 편의점에서도 충전할 수 있다.", "ryan"),
            Pick("t-samgyeopsal", "홍대에서 삼겹살집 추천",
                 "홍대입구역 근처에서 외국인 관광객이 한국식 고기구이를 먹을 만한 곳을 묻는다. 삼겹살을 권하고, 보통 "
                 "2인분부터 주문한다고 알려 준다.", "ryan"),
        ),
    ),
    Topic(
        id="usa",
        name_ko="미국 여행",
        roles_en=("The learner is a Korean traveler visiting the United States. Ryan is someone there: a shop or "
                  "restaurant worker, hotel staff, or a passerby."),
        scenes_en=("The learner is traveling in the United States: ordering at a cafe or a fast-food place, checking "
                   "in at a hotel, asking the way, shopping at a mall, and so on. Use real places, shops and menus, "
                   "for example in New York or Hawaii."),
        example_ko="뉴욕 지하철역에서 역무원에게 표 사는 법을 묻는 상황으로 연습해 보면 어때요?",
        placeholder_ko="예: 공항에서 짐이 안 나와 직원에게 묻는 상황",
        first=None,
        picks=(
            Pick("u-shrimp-truck", "하와이 새우 트럭에서 갈릭 쉬림프",
                 "하와이 오아후 노스쇼어 카후쿠의 지오반니 새우 트럭(Giovanni's Shrimp Truck)에서 마늘 새우 접시(Shrimp "
                 "Scampi)를 주문한다. 메뉴는 쉬림프 스캠피, 핫 앤 스파이시, 레몬 버터이고, 접시에는 새우와 밥 두 스쿱이 "
                 "나온다.", "ryan"),
            Pick("u-hotel-checkin", "뉴욕 호텔 체크인",
                 "뉴욕 맨해튼의 호텔 프런트에서 예약한 방에 체크인한다. 예약한 이름을 말하고 여권과 카드를 내고, "
                 "체크아웃 시간과 와이파이를 묻는다.", "user"),
            Pick("u-sneaker-size", "알라모아나 센터에서 운동화 사이즈",
                 "하와이 호놀룰루 알라모아나 센터의 신발 가게에서 점원에게 운동화를 다른 사이즈로 신어 볼 수 있는지 "
                 "묻는다. 한국 사이즈 270은 미국 남자 사이즈 9다.", "user"),
        ),
    ),
    Topic(
        id=OTHER,
        name_ko="그 밖의 상황",
        roles_en="Ryan plays the other person in the situation. The learner plays themself.",
        scenes_en=("Any real moment in daily life where the learner must speak English, other than helping a foreign "
                   "tourist in Korea or traveling in the United States."),
        example_ko="외국 회사에 전화해서 주문한 물건이 언제 오는지 묻는 상황으로 연습해 보면 어때요?",
        placeholder_ko="예: 외국 회사에 전화해 주문을 확인하는 상황",
        first=None,
    ),
)

_BY_ID = {t.id: t for t in TOPICS}


def get(topic_id: str) -> Topic:
    return _BY_ID[topic_id]


def pick(topic_id: str, pick_id: str) -> Pick:
    """A line of that topic's list; one of another topic is not found either (KeyError)."""
    for p in get(topic_id).picks:
        if p.id == pick_id:
            return p
    raise KeyError(pick_id)


def public() -> list[dict]:
    """What the app needs to show the topics and their lists: no prompt text."""
    return [{"id": t.id, "name_ko": t.name_ko, "placeholder_ko": t.placeholder_ko,
             "picks": [{"id": p.id, "title_ko": p.title_ko} for p in t.picks]} for t in TOPICS]
