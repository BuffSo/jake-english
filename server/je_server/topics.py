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
changes, change the description, the script and `tests/test_topics.py` together. When one answer is split over the
learner's turns (a route with a change), its first piece says more is coming ("First, ..."): ending there, it sounds
like the whole answer, and the other person's next question sounds like waiting for the next piece (2026-11-08 user).

Each script line carries Sohee's Korean for it, made once with the quick model and read over by hand (todo 13): a
pick's 「통역」 does not ask Claude. It says what the English says and no more; read it with the lines around it, as
two lines together can say something neither does (PR #34). When a line changes, change its Korean too.
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
    # Sohee's Korean for each line, in the same order: a pick does not ask Claude for it (todo 13). A line without it
    # is interpreted when tapped, like any other script's.
    ko: tuple[str, ...] = ()


def _pick(id: str, title_ko: str, situation: str, first: Speaker, roles: tuple[str, str, str, str],
          lines: tuple[tuple[Speaker, str, str], ...]) -> Pick:
    """roles: the learner, Ryan, the place, the goal, in Korean (the rest of the frame). lines: (speaker, English
    line, Sohee's Korean for it)."""
    user, ryan, place, goal = roles
    frame = Frame(title_ko=title_ko, user_role_ko=user, ryan_role_ko=ryan, place_ko=place, goal_ko=goal)
    return Pick(id, title_ko, situation, first, frame, tuple((s, t) for s, t, _ in lines), tuple(k for *_, k in lines))


@dataclass(frozen=True)
class Topic:
    id: str
    name_ko: str
    roles_en: str  # who Ryan and the learner are, for the script
    scenes_en: str  # what kind of moments, for Jake's suggestion
    example_ko: str  # one situation Jake might suggest, without his ending (the server picks it, claude.pick_ending)
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
        example_ko="인사동에서 외국인 관광객이 한복 빌리는 곳을 묻는 상황",
        placeholder_ko="예: 외국인이 명동에서 환전소를 묻는 상황",
        first="ryan",
        picks=(
            _pick("t-gyeongbokgung", "명동역에서 경복궁 가는 길",
                  "명동역 근처에서 외국인 관광객이 경복궁 가는 법을 묻는다. 4호선을 타고 한 정거장 가서 충무로역에서 "
                  "3호선으로 갈아타고, 경복궁역 5번 출구로 나가면 궁으로 바로 이어진다.", "ryan",
                  ("길을 알려 주는 서울 사람", "경복궁에 가려는 외국인 관광객", "명동역 근처",
                   "관광객에게 경복궁 가는 길을 알려 주기"),
                  (("ryan", "Excuse me, do you speak English? I'm trying to get to Gyeongbokgung Palace.",
                    "실례합니다, 영어 할 줄 아세요? 경복궁에 가려고 하는데요."),
                   ("user", "Sure. First, take Line 4 one stop to Chungmuro.",
                    "그럼요. 먼저 4호선을 타고 충무로까지 한 정거장 가세요."),
                   ("ryan", "Chungmuro, got it. And then what?",
                    "충무로요, 알겠어요. 그다음엔 어떻게 해요?"),
                   ("user", "Change to Line 3 there, and get off at Gyeongbokgung.",
                    "거기서 3호선으로 갈아타고 경복궁역에서 내리세요."),
                   ("ryan", "Great. Which exit should I use?",
                    "좋아요. 몇 번 출구로 나가야 해요?"),
                   ("user", "Take Exit 5. It goes straight into the palace.",
                    "5번 출구로 나가세요. 궁으로 바로 이어져요."),
                   ("ryan", "Perfect. Thank you so much!",
                    "잘 알겠어요. 정말 감사합니다!"))),
            _pick("t-tmoney", "지하철역에서 교통카드 충전",
                  "서울 지하철역에서 외국인 관광객이 교통카드(티머니)를 충전하는 법을 묻는다. 역의 교통카드 충전기에서 "
                  "현금으로만 충전한다. 편의점에서도 충전할 수 있다.", "ryan",
                  ("충전하는 법을 알려 주는 서울 사람", "교통카드를 충전하려는 외국인 관광객", "서울의 지하철역",
                   "관광객에게 교통카드 충전하는 법을 알려 주기"),
                  (("ryan", "Hi, sorry to bother you. How do I add money to my T-money card?",
                    "안녕하세요, 귀찮게 해서 죄송해요. 티머니 카드는 어떻게 충전해요?"),
                   ("user", "You can use the card machine right over there.",
                    "바로 저기 있는 교통카드 충전기를 쓰시면 돼요."),
                   ("ryan", "Oh, nice. Can I pay with a credit card?",
                    "아, 잘됐네요. 신용카드로 결제할 수 있어요?"),
                   ("user", "No, I'm afraid the machine only takes cash.",
                    "아니요, 아쉽지만 저 충전기는 현금만 받아요."),
                   ("ryan", "Got it. Is this the only place I can do that?",
                    "알겠어요. 충전할 수 있는 데가 여기뿐이에요?"),
                   ("user", "No, a convenience store can top it up too.",
                    "아니요, 편의점에서도 충전할 수 있어요."),
                   ("ryan", "Good to know. Thanks for your help!",
                    "그렇군요. 도와주셔서 감사합니다!"))),
            _pick("t-samgyeopsal", "홍대에서 삼겹살집 추천",
                  "홍대입구역 근처에서 외국인 관광객이 한국식 고기구이를 먹을 만한 곳을 묻는다. 삼겹살을 권하고, 보통 "
                  "2인분부터 주문한다고 알려 준다.", "ryan",
                  ("먹을 곳을 알려 주는 서울 사람", "한국식 고기구이를 먹어 보고 싶은 외국인 관광객", "홍대입구역 근처",
                   "관광객에게 삼겹살을 권하고 주문하는 법을 알려 주기"),
                  (("ryan", "Excuse me, I want to try Korean barbecue. Any ideas around here?",
                    "저기요, 한국식 고기구이를 먹어 보고 싶은데요. 이 근처에서 뭘 먹으면 좋을까요?"),
                   ("user", "You should try samgyeopsal. It's grilled pork belly.",
                    "삼겹살 한번 드셔 보세요. 돼지 뱃살을 구워 먹는 거예요."),
                   ("ryan", "Sounds great! Is there a good place nearby?",
                    "좋네요! 이 근처에 잘하는 데 있어요?"),
                   ("user", "Yeah, there are lots of places around this station.",
                    "네, 이 역 근처에 그런 데가 많아요."),
                   ("ryan", "Awesome. Anything I should know before I order?",
                    "잘됐네요. 주문하기 전에 알아 둘 게 있을까요?"),
                   ("user", "Most places want you to order at least two servings.",
                    "대부분 가게에서는 2인분 이상 시켜야 해요."),
                   ("ryan", "Good to know. Thanks a lot!",
                    "그렇군요. 정말 고마워요!"))),
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
        example_ko="뉴욕 지하철역에서 역무원에게 표 사는 법을 묻는 상황",
        placeholder_ko="예: 공항에서 짐이 안 나와 직원에게 묻는 상황",
        first=None,
        picks=(
            _pick("u-shrimp-truck", "하와이 새우 트럭에서 갈릭 쉬림프",
                  "하와이 오아후 노스쇼어 카후쿠의 지오반니 새우 트럭(Giovanni's Shrimp Truck)에서 마늘 새우 접시(Shrimp "
                  "Scampi)를 주문한다. 메뉴는 쉬림프 스캠피, 핫 앤 스파이시, 레몬 버터이고, 접시에는 새우와 밥 두 스쿱이 "
                  "나온다.", "ryan",
                  ("하와이에 여행 온 한국 사람", "새우 트럭 직원", "하와이 오아후 노스쇼어 카후쿠의 지오반니 새우 트럭",
                   "마늘 새우 접시를 주문하기"),
                  (("ryan", "Aloha, welcome to Giovanni's! What can I get for you?",
                    "알로하, 지오반니에 오신 걸 환영합니다! 뭘 드릴까요?"),
                   ("user", "Hi! It's my first time here. What do you have?",
                    "안녕하세요! 여기 처음 왔는데요. 어떤 메뉴가 있어요?"),
                   ("ryan", "We've got shrimp scampi, hot and spicy, and lemon butter.",
                    "새우 스캠피, 매운맛, 레몬 버터 맛이 있어요."),
                   ("user", "I'll have the shrimp scampi plate, please.",
                    "새우 스캠피 한 접시 주세요."),
                   ("ryan", "You got it. It comes with two scoops of rice.",
                    "네, 알겠습니다. 밥 두 스쿱이 같이 나와요."),
                   ("user", "Great. I heard it's really garlicky.",
                    "좋아요. 마늘 맛이 아주 진하다고 들었어요."),
                   ("ryan", "Oh, it is, with lots of garlic. Enjoy!",
                    "그럼요, 마늘이 듬뿍 들어가요. 맛있게 드세요!"))),
            # the name on the booking, the checkout time and the Wi-Fi password on the key card sleeve are small
            # made-up values: the hotel has no name (REVIEW.md 「목록 대본의 사실」)
            _pick("u-hotel-checkin", "뉴욕 호텔 체크인",
                  "뉴욕 맨해튼의 호텔 프런트에서 예약한 방에 체크인한다. 예약한 이름을 말하고 여권과 카드를 내고, "
                  "체크아웃 시간과 와이파이를 묻는다.", "user",
                  ("뉴욕에 여행 온 한국 사람", "호텔 프런트 직원", "뉴욕 맨해튼의 호텔 프런트",
                   "예약한 방에 체크인하고 체크아웃 시간과 와이파이를 묻기"),
                  (("user", "Hi, I'd like to check in. The reservation is under Kim.",
                    "안녕하세요, 체크인하려고요. 김 이름으로 예약했어요."),
                   ("ryan", "Welcome! May I see your passport and a credit card, please?",
                    "어서 오세요! 여권이랑 신용카드 좀 보여 주시겠어요?"),
                   ("user", "Of course, here they are. When is checkout?",
                    "네, 여기 있어요. 체크아웃은 몇 시예요?"),
                   ("ryan", "Checkout is at 11 a.m. Here are your room keys.",
                    "체크아웃은 오전 열한 시입니다. 여기 객실 키입니다."),
                   ("user", "Thanks. And how do I get on the Wi-Fi?",
                    "감사합니다. 그리고 와이파이는 어떻게 연결해요?"),
                   ("ryan", "Just pick the hotel network, and the password is on your key card sleeve. Enjoy your stay!",
                    "호텔 와이파이를 고르시고, 비밀번호는 카드키 봉투에 적혀 있어요. 즐거운 시간 보내세요!"))),
            _pick("u-sneaker-size", "알라모아나 센터에서 운동화 사이즈",
                  "하와이 호놀룰루 알라모아나 센터의 신발 가게에서 점원에게 운동화를 다른 사이즈로 신어 볼 수 있는지 "
                  "묻는다. 한국 사이즈 270은 미국 남자 사이즈 9다.", "user",
                  ("하와이에 여행 온 한국 사람", "신발 가게 점원", "하와이 호놀룰루 알라모아나 센터의 신발 가게",
                   "운동화를 다른 사이즈로 신어 보기"),
                  (("user", "Hi, could I try these on in another size?",
                    "안녕하세요, 이거 다른 사이즈로 신어 봐도 될까요?"),
                   ("ryan", "Sure! What size do you need?",
                    "그럼요! 몇 사이즈 찾으세요?"),
                   ("user", "In Korea I wear a 270. That's a men's 9, right?",
                    "한국에서는 270을 신어요. 그게 남성 9 사이즈 맞죠?"),
                   ("ryan", "That's right, a men's 9. Let me grab a pair from the back.",
                    "맞아요, 남성 9 사이즈예요. 창고에서 한 켤레 가져다 드릴게요."),
                   ("user", "Great, thank you. I'll wait here.",
                    "좋아요, 감사합니다. 여기서 기다릴게요."))),
            # 2026-11-08 the user: most trips are booked ahead, online or by phone (todo 38). Unlike 「뉴욕 호텔
            # 체크인」, the booking itself is talked over. Two nights, the king room and the twelfth floor are small
            # made-up values: the hotel has no name (REVIEW.md 「목록 대본의 사실」)
            _pick("u-hotel-online", "로스앤젤레스 호텔에서 온라인 예약 확인",
                  "로스앤젤레스의 호텔 프런트에서 체크인한다. 온라인으로 예약했다고 말하고 확인 번호를 보여 준다. "
                  "직원이 킹 침대 방 2박 예약을 확인해 주고, 높은 층 방을 부탁한다.", "ryan",
                  ("로스앤젤레스에 여행 온 한국 사람", "호텔 프런트 직원", "로스앤젤레스의 호텔 프런트",
                   "온라인으로 한 예약을 확인하고 체크인하기"),
                  (("ryan", "Hi, welcome! Are you checking in?",
                    "안녕하세요, 어서 오세요! 체크인하시나요?"),
                   ("user", "Yes, I booked online. Here's my confirmation number.",
                    "네, 온라인으로 예약했어요. 여기 확인 번호요."),
                   ("ryan", "Thanks. I have you down for two nights in a king room.",
                    "감사합니다. 킹 침대 방으로 2박 예약되어 있네요."),
                   ("user", "That's right. Could I get a room on a high floor?",
                    "맞아요. 높은 층 방으로 받을 수 있을까요?"),
                   ("ryan", "Sure, you're on the twelfth floor. Here are your keys.",
                    "그럼요, 12층으로 드릴게요. 여기 객실 키입니다."),
                   ("user", "Awesome, the higher the better. Thank you!",
                    "좋네요, 높을수록 좋아요. 감사합니다!"))),
            # the user: walking in without a booking and being asked for one (todo 38). The 30-minute wait and the
            # name on the list are small made-up values: the restaurant has no name, as a real one's wait and bar
            # change by the day. A waitlist takes a first name, so Jake (the user, 2026-11-08); the hotel keeps Kim
            _pick("u-seafood-walkin", "와이키키 해산물 식당에 예약 없이 가기",
                  "하와이 호놀룰루 와이키키의 해산물 식당에 예약 없이 둘이 간다. 직원이 예약했는지 묻고, 자리가 거의 "
                  "차서 테이블은 30분쯤 기다려야 하고 바에는 앉을 수 있다고 한다. 테이블을 기다리기로 하고 대기 명단에 "
                  "이름을 올린다.", "ryan",
                  ("하와이에 여행 온 한국 사람", "식당 입구의 안내 직원", "하와이 호놀룰루 와이키키의 해산물 식당",
                   "예약 없이 간 식당에서 자리를 묻고 대기 명단에 이름 올리기"),
                  (("ryan", "Aloha, welcome in! Do you have a reservation?",
                    "알로하, 어서 오세요! 예약하셨어요?"),
                   ("user", "No, we don't. Do you have a table for two?",
                    "아니요, 안 했어요. 두 명 앉을 자리 있어요?"),
                   ("ryan", "We're pretty full right now. It's about a 30-minute wait, or you can sit at the bar.",
                    "지금은 자리가 거의 찼어요. 30분쯤 기다리셔야 하고, 아니면 바에 앉으셔도 돼요."),
                   ("user", "We'll wait for a table. Can I put my name down?",
                    "테이블 자리를 기다릴게요. 이름 올려 둘 수 있을까요?"),
                   ("ryan", "Sure, what name should I put down?",
                    "그럼요, 어떤 이름으로 올려 드릴까요?"),
                   ("user", "It's Jake. Thank you!",
                    "제이크요. 감사합니다!"),
                   ("ryan", "Great, we'll call you when your table is ready.",
                    "네, 자리가 나면 불러 드릴게요."))),
        ),
    ),
    Topic(
        id=OTHER,
        name_ko="그 밖의 상황",
        roles_en="Ryan plays the other person in the situation. The learner plays themself.",
        scenes_en=("Any real moment in daily life where the learner must speak English, other than helping a foreign "
                   "tourist in Korea or traveling in the United States."),
        example_ko="외국 회사에 전화해서 주문한 물건이 언제 오는지 묻는 상황",
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


def listed(topic_id: str | None, pick_id: str | None) -> Pick | None:
    """The list line a run was picked from, while it is still on its topic's list; None for a run not picked from a
    list or one taken off it. A copy of the run plays this line's script as it is now (spec fixed-list-scripts 4):
    `Engine.copy` and the recording test script both ask here, so they cannot drift apart (PR #49 review)."""
    if topic_id is None or pick_id is None:
        return None
    try:
        return pick(topic_id, pick_id)
    except KeyError:
        return None


def public() -> list[dict]:
    """What the app needs to show the topics and their lists: no prompt text."""
    return [{"id": t.id, "name_ko": t.name_ko, "placeholder_ko": t.placeholder_ko,
             "picks": [{"id": p.id, "title_ko": p.title_ko} for p in t.picks]} for t in TOPICS]
