"""Situation topics and their prepared lists (spec situation-topics 1, 3).

A topic sets who Ryan and the learner are, and goes to Claude with the script and Jake's suggestion. Each topic may
have a list of situations written beforehand, with real places, shops and menus. To add a topic or a situation, add
a line here; the app shows whatever /home lists.

The facts in the lists were checked on the web on 2026-11-07 (Gyeongbokgung station exit 5 goes straight into the
palace, closed on some evenings; the station top-up machines take cash only and convenience stores top up too;
Giovanni's Shrimp Truck serves shrimp scampi, hot & spicy and lemon butter, each plate with two scoops of rice).
Do not change a fact without checking it again: a wrong route or menu is learned as if it were true.

Each list line also has its script and frame, written here and reviewed in the PR: a pick starts from it without
asking Claude (spec fixed-list-scripts, ADR-0013). A script keeps only the facts of its description. When a fact
changes, change the description, the script and `tests/test_topics.py` together.
"""
from __future__ import annotations

from dataclasses import dataclass

from .models import Frame, Speaker

OTHER = "other"


@dataclass(frozen=True)
class Pick:
    id: str
    title_ko: str  # the card on the list screen, and the frame's title
    situation: str  # the facts the script keeps; kept on the record for Jake to avoid recent situations
    first: Speaker
    frame: Frame
    script: tuple[tuple[Speaker, str], ...]  # (speaker, English line) in order


def _pick(id: str, title_ko: str, situation: str, first: Speaker, roles: tuple[str, str, str, str],
          script: tuple[tuple[Speaker, str], ...]) -> Pick:
    """roles: the learner, Ryan, the place, the goal, in Korean (the rest of the frame)."""
    user, ryan, place, goal = roles
    frame = Frame(title_ko=title_ko, user_role_ko=user, ryan_role_ko=ryan, place_ko=place, goal_ko=goal)
    return Pick(id, title_ko, situation, first, frame, script)


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
            _pick("t-gyeongbokgung", "명동역에서 경복궁 가는 길",
                  "명동역 근처에서 외국인 관광객이 경복궁 가는 법을 묻는다. 4호선을 타고 한 정거장 가서 충무로역에서 "
                  "3호선으로 갈아타고, 경복궁역 5번 출구로 나가면 궁으로 바로 이어진다.", "ryan",
                  ("길을 알려 주는 서울 사람", "경복궁에 가려는 외국인 관광객", "명동역 근처",
                   "관광객에게 경복궁 가는 길을 알려 주기"),
                  (("ryan", "Excuse me, do you speak English? I'm trying to get to Gyeongbokgung Palace."),
                   ("user", "Sure. Take Line 4 from here, just one stop to Chungmuro."),
                   ("ryan", "Chungmuro, got it. And then what?"),
                   ("user", "Transfer to Line 3 and get off at Gyeongbokgung Station."),
                   ("ryan", "Great. Which exit should I use?"),
                   ("user", "Take Exit 5. It goes straight into the palace."),
                   ("ryan", "Perfect. Thank you so much!"))),
            _pick("t-tmoney", "지하철역에서 교통카드 충전",
                  "서울 지하철역에서 외국인 관광객이 교통카드(티머니)를 충전하는 법을 묻는다. 역의 교통카드 충전기에서 "
                  "현금으로만 충전한다. 편의점에서도 충전할 수 있다.", "ryan",
                  ("충전하는 법을 알려 주는 서울 사람", "교통카드를 충전하려는 외국인 관광객", "서울의 지하철역",
                   "관광객에게 교통카드 충전하는 법을 알려 주기"),
                  (("ryan", "Hi, sorry to bother you. How do I add money to my T-money card?"),
                   ("user", "You can use the card machine right over there."),
                   ("ryan", "Oh, nice. Can I pay with a credit card?"),
                   ("user", "No, I'm afraid the machine only takes cash."),
                   ("ryan", "Got it. Is this the only place I can do that?"),
                   ("user", "No, a convenience store can top it up too."),
                   ("ryan", "Good to know. Thanks for your help!"))),
            _pick("t-samgyeopsal", "홍대에서 삼겹살집 추천",
                  "홍대입구역 근처에서 외국인 관광객이 한국식 고기구이를 먹을 만한 곳을 묻는다. 삼겹살을 권하고, 보통 "
                  "2인분부터 주문한다고 알려 준다.", "ryan",
                  ("먹을 곳을 알려 주는 서울 사람", "한국식 고기구이를 먹어 보고 싶은 외국인 관광객", "홍대입구역 근처",
                   "관광객에게 삼겹살을 권하고 주문하는 법을 알려 주기"),
                  (("ryan", "Excuse me. I want to try Korean barbecue. Any ideas around here?"),
                   ("user", "You should try samgyeopsal. It's grilled pork belly."),
                   ("ryan", "Sounds great! Is there a good place nearby?"),
                   ("user", "Yeah, there are lots of places around this station."),
                   ("ryan", "Awesome. Anything I should know before I order?"),
                   ("user", "Most places want you to order at least two servings."),
                   ("ryan", "Good to know. Thanks a lot!"))),
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
            _pick("u-shrimp-truck", "하와이 새우 트럭에서 갈릭 쉬림프",
                  "하와이 오아후 노스쇼어 카후쿠의 지오반니 새우 트럭(Giovanni's Shrimp Truck)에서 마늘 새우 접시(Shrimp "
                  "Scampi)를 주문한다. 메뉴는 쉬림프 스캠피, 핫 앤 스파이시, 레몬 버터이고, 접시에는 새우와 밥 두 스쿱이 "
                  "나온다.", "ryan",
                  ("하와이에 여행 온 한국 사람", "새우 트럭 직원", "하와이 오아후 노스쇼어 카후쿠의 지오반니 새우 트럭",
                   "마늘 새우 접시를 주문하기"),
                  (("ryan", "Aloha! Welcome to Giovanni's. What can I get for you?"),
                   ("user", "Hi! It's my first time here. What do you have?"),
                   ("ryan", "We've got shrimp scampi, hot and spicy, and lemon butter."),
                   ("user", "I'll have the shrimp scampi plate, please."),
                   ("ryan", "You got it. It comes with two scoops of rice."),
                   ("user", "Great. I heard it's really garlicky."),
                   ("ryan", "Oh, it is. Lots of garlic. Enjoy!"))),
            # the name on the booking and the checkout time are small made-up values: the hotel has no name
            _pick("u-hotel-checkin", "뉴욕 호텔 체크인",
                  "뉴욕 맨해튼의 호텔 프런트에서 예약한 방에 체크인한다. 예약한 이름을 말하고 여권과 카드를 내고, "
                  "체크아웃 시간과 와이파이를 묻는다.", "user",
                  ("뉴욕에 여행 온 한국 사람", "호텔 프런트 직원", "뉴욕 맨해튼의 호텔 프런트",
                   "예약한 방에 체크인하고 체크아웃 시간과 와이파이를 묻기"),
                  (("user", "Hi, I'd like to check in. The reservation is under Kim."),
                   ("ryan", "Welcome! May I see your passport and a credit card, please?"),
                   ("user", "Sure, here you go. What time is checkout?"),
                   ("ryan", "Checkout is at 11 a.m. Here are your room keys."),
                   ("user", "Thanks. And how do I get on the Wi-Fi?"),
                   ("ryan", "Just pick the hotel network. The password is on your key card sleeve. Enjoy your stay!"))),
            _pick("u-sneaker-size", "알라모아나 센터에서 운동화 사이즈",
                  "하와이 호놀룰루 알라모아나 센터의 신발 가게에서 점원에게 운동화를 다른 사이즈로 신어 볼 수 있는지 "
                  "묻는다. 한국 사이즈 270은 미국 남자 사이즈 9다.", "user",
                  ("하와이에 여행 온 한국 사람", "신발 가게 점원", "하와이 호놀룰루 알라모아나 센터의 신발 가게",
                   "운동화를 다른 사이즈로 신어 보기"),
                  (("user", "Excuse me, can I try these on in a different size?"),
                   ("ryan", "Sure! What size do you need?"),
                   ("user", "I'm a 270 in Korea. I think that's a men's 9."),
                   ("ryan", "That's right, a men's 9. Let me grab a pair from the back."),
                   ("user", "Great, thank you. I'll wait here."))),
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
