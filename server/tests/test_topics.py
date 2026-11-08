"""Situation topics and their prepared lists (spec situation-topics 1, 3)."""
import pytest

from je_server.topics import TOPICS, get, listed, pick, public


def test_three_topics_in_order():
    # 2026-11-07 the user named them; 2026-11-08 the user renamed two and kept the ids, which the records hold
    # (spec korea-english-topic 1)
    assert [t.id for t in TOPICS] == ["tourist", "usa", "other"]
    assert [t.name_ko for t in TOPICS] == ["한국에서 영어 쓰기", "미국 여행하기", "그 밖의 상황"]


def test_korea_topic_is_strangers_and_either_may_start():
    # the user: a foreigner the learner has never met, a tourist or someone living here; asking for help or just
    # greeting and chatting; the learner may speak first (spec korea-english-topic 2, 3). People the learner knows
    # (a coworker) stay out, as before
    t = get("tourist")
    assert t.first is None and get("usa").first is None and get("other").first is None
    for text in (t.roles_en, t.scenes_en):
        low = text.lower()
        assert "never met" in low and "tourist" in low and "lives in korea" in low and "coworkers" in low
    assert all(w in t.scenes_en.lower() for w in ("help", "small talk", "park", "cafe", "market",
                                                  "learner speaks first"))
    assert "learner may speak first" in t.roles_en.lower()


def test_other_leaves_out_the_korea_topic():
    # 「그 밖의 상황」 is what the two topics do not cover; talking in Korea with a foreigner one has never met is now
    # the first topic, chatting included
    s = get("other").scenes_en.lower()
    assert "helping a foreign tourist" not in s and "never met" in s and "united states" in s


def test_starting_lists():
    # three per topic to try it first (user), none yet for 「그 밖의 상황」; 2026-11-08 the user added two reservation
    # scenes to 「미국 여행」, at the end so the first three keep their places (todo 38)
    assert [len(get(t).picks) for t in ("tourist", "usa", "other")] == [3, 5, 0]
    assert [p.id for p in get("usa").picks] == ["u-shrimp-truck", "u-hotel-checkin", "u-sneaker-size",
                                                "u-hotel-online", "u-seafood-walkin"]
    assert [p.first for p in get("usa").picks] == ["ryan", "user", "user", "ryan", "ryan"]
    assert all(p.first == "ryan" for p in get("tourist").picks)
    ids = [p.id for t in TOPICS for p in t.picks]
    assert len(ids) == len(set(ids))


def test_list_facts_checked_on_the_web():
    # spec 3: checked on 2026-11-07; a builder does not change them unchecked
    by_id = {p.id: p.situation for t in TOPICS for p in t.picks}
    assert "5번 출구" in by_id["t-gyeongbokgung"]
    assert "현금" in by_id["t-tmoney"]
    assert "Giovanni's" in by_id["u-shrimp-truck"] and "밥 두 스쿱" in by_id["u-shrimp-truck"]


def test_pick_must_belong_to_the_topic():
    assert pick("usa", "u-hotel-checkin").first == "user"
    with pytest.raises(KeyError):
        pick("usa", "t-tmoney")
    with pytest.raises(KeyError):
        pick("usa", "u-none")
    with pytest.raises(KeyError):
        get("nope")


def test_listed_is_the_pick_still_on_its_list():
    # one place says whether a run copies the list's current script, for Engine.copy and the recording test script
    # (PR #49 review: try_recordings had copied the branch by hand)
    p = get("usa").picks[0]
    assert listed("usa", p.id) is p
    assert listed(None, p.id) is None and listed("usa", None) is None  # not a list pick
    assert listed("usa", "gone-from-the-list") is None
    assert listed("tourist", p.id) is None  # another topic's line


def test_examples_end_at_the_situation_without_an_ending():
    # the server picks Jake's ending (2026-11-08); an example with one would pull every suggestion toward it
    for t in TOPICS:
        assert t.example_ko.endswith("상황") and "어때요" not in t.example_ko


def test_public_leaves_out_prompt_text():
    out = public()
    assert [t["id"] for t in out] == ["tourist", "usa", "other"]
    for t in out:
        assert set(t) == {"id", "name_ko", "placeholder_ko", "picks"}
        assert all(set(p) == {"id", "title_ko"} for p in t["picks"])


# --- fixed scripts (spec fixed-list-scripts 1, ADR-0013) ---------------------------------------------------------

ALL = [p for t in TOPICS for p in t.picks]


def test_every_pick_has_a_script_that_passes_the_script_checks():
    # the same checks as a script Claude writes
    from je_server.claude import Claude

    for p in ALL:
        assert Claude.script_problems(list(p.script), p.first) == [], p.id
        assert all(len(t.split()) <= 12 for s, t in p.script if s == "user"), p.id


def test_script_title_is_the_card_title():
    # the past list shows the frame's title; it must read as the card that was picked
    assert all(p.frame.title_ko == p.title_ko for p in ALL)


def test_script_keeps_the_facts_of_its_description():
    # the facts in each list description, as said in the script; change them only after checking again
    said = {p.id: " ".join(t for _, t in p.script) for p in ALL}
    assert all(w in said["t-gyeongbokgung"] for w in ("Line 4", "one stop", "Chungmuro", "Line 3", "Exit 5"))
    assert "only takes cash" in said["t-tmoney"] and "convenience store" in said["t-tmoney"]
    assert "samgyeopsal" in said["t-samgyeopsal"] and "two servings" in said["t-samgyeopsal"]
    assert all(w in said["u-shrimp-truck"] for w in ("Giovanni's", "shrimp scampi", "hot and spicy",
                                                     "lemon butter", "two scoops of rice"))
    assert all(w in said["u-hotel-checkin"] for w in ("passport", "credit card", "checkout", "Wi-Fi"))
    assert "270" in said["u-sneaker-size"] and "men's 9" in said["u-sneaker-size"]
    assert all(w in said["u-hotel-online"] for w in ("booked online", "confirmation number", "two nights",
                                                     "king room", "high floor"))
    assert all(w in said["u-seafood-walkin"] for w in ("reservation", "table for two", "30-minute wait", "bar",
                                                       "put my name down"))


def test_ryans_list_lines_are_one_or_two_sentences():
    # prompts.SCRIPT_SYSTEM asks Claude for Ryan's lines in one or two sentences; the hand-written list scripts keep the
    # same rule (todo fixed-list-scripts minors 2). a.m. and p.m. do not end a sentence
    import re

    def sentences(text):
        text = re.sub(r"\b([ap])\.m\.", r"\1m", text)
        return [x for x in re.split(r"(?<=[.?!])\s+", text.strip()) if x]

    long = [(p.id, t) for p in ALL for s, t in p.script if s == "ryan" and len(sentences(t)) > 2]
    assert long == []


def test_a_route_split_over_turns_says_more_is_coming():
    # 2026-11-08 the user, after the gyeongbokgung pick on the phone: the first answer sounded like the whole way,
    # so the tourist's 「And then what?」 sounded like it had waited for the next piece
    p = pick("tourist", "t-gyeongbokgung")
    first = next(i for i, (s, _) in enumerate(p.script) if s == "user")
    assert "First," in p.script[first][1] and "먼저" in p.ko[first]


def test_script_has_no_hangul_or_braces():
    import re

    assert not any(re.search(r"[가-힣{}]", t) for p in ALL for _, t in p.script)


def test_tmoney_does_not_send_a_cashless_tourist_to_a_store():
    # final review 2026-11-08: "no cash on me" then "try a convenience store" says the store takes cards, a payment
    # fact the description does not have (spec fixed-list-scripts 1); the store is only another place to top up
    said = " ".join(t for _, t in pick("tourist", "t-tmoney").script).lower()
    assert "cash" not in said.replace("only takes cash", "")


# --- Sohee's Korean for each line (todo 13) -----------------------------------------------------------------------

def test_every_line_has_sohee_korean():
    # read aloud by Sohee: Korean only, one line, nothing a voice would read out as a mark
    import re

    from je_server.claude import QUOTES

    for p in ALL:
        assert len(p.ko) == len(p.script), p.id
        for ko in p.ko:
            assert re.search(r"[가-힣]", ko) and not re.search(r"[A-Za-z{}\n]", ko), (p.id, ko)
            assert not any(q in ko for q in QUOTES), (p.id, ko)


def test_korean_keeps_the_facts():
    # the same facts as the English (test_script_keeps_the_facts_of_its_description), said in Korean
    said = {p.id: " ".join(p.ko) for p in ALL}
    assert all(w in said["t-gyeongbokgung"] for w in ("4호선", "한 정거장", "충무로", "3호선", "5번 출구"))
    assert all(w in said["t-tmoney"] for w in ("현금", "편의점"))
    assert all(w in said["t-samgyeopsal"] for w in ("삼겹살", "2인분"))
    assert all(w in said["u-shrimp-truck"] for w in ("지오반니", "스캠피", "매운", "레몬 버터", "밥 두 스쿱"))
    assert all(w in said["u-hotel-checkin"] for w in ("여권", "신용카드", "체크아웃", "와이파이"))
    assert all(w in said["u-sneaker-size"] for w in ("270", "9 사이즈"))
    assert all(w in said["u-hotel-online"] for w in ("온라인", "확인 번호", "2박", "킹 침대", "높은 층"))
    assert all(w in said["u-seafood-walkin"] for w in ("예약", "두 명", "30분", "바에", "이름"))


def test_tmoney_korean_says_cash_only_of_the_machine():
    # the English test above, in Korean: the store is only another place to top up, not one that takes cards
    ko = pick("tourist", "t-tmoney").ko
    assert [i for i, k in enumerate(ko) if "현금" in k] == [3]
    assert "카드" not in ko[5]


# --- reservation scenes (todo 38, 2026-11-08) ---------------------------------------------------------------------

def test_reserved_hotel_says_how_it_was_booked():
    # the old hotel pick is already booked under a name; this one says how it was booked in the learner's first line
    p = pick("usa", "u-hotel-online")
    first = next(i for i, (s, _) in enumerate(p.script) if s == "user")
    assert "online" in p.script[first][1] and "온라인" in p.ko[first]


def test_walk_in_host_asks_for_a_reservation_first():
    # the user: we walk in without one and the staff ask whether we booked
    p = pick("usa", "u-seafood-walkin")
    assert p.script[0][0] == "ryan" and "reservation" in p.script[0][1] and "예약" in p.ko[0]


def test_reservation_values_are_in_the_description():
    # the made-up values the scripts say are facts of their descriptions too (REVIEW.md 「목록 대본의 사실」)
    hotel, food = pick("usa", "u-hotel-online").situation, pick("usa", "u-seafood-walkin").situation
    assert all(w in hotel for w in ("온라인", "확인 번호", "킹 침대", "2박", "높은 층", "12층"))
    assert all(w in food for w in ("예약 없이", "30분", "바에는", "대기 명단", "제이크"))


def test_walk_in_korean_says_no_more_than_the_english():
    # the bar is only another place to sit: 「바로」(right away) is not in the English
    assert not any("바로" in k for k in pick("usa", "u-seafood-walkin").ko)
