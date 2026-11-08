"""Situation topics and their prepared lists (spec situation-topics 1, 3)."""
import pytest

from je_server.topics import TOPICS, get, pick, public


def test_three_topics_in_order():
    # 2026-11-07 the user named them; 「돕기」 was turned down, then the long name was cut short
    assert [t.id for t in TOPICS] == ["tourist", "usa", "other"]
    assert [t.name_ko for t in TOPICS] == ["외국인 관광객", "미국 여행", "그 밖의 상황"]


def test_tourist_starts_with_ryan_and_is_strangers():
    # the user: the foreigner asks first; people the learner knows (a coworker) are left out
    t = get("tourist")
    assert t.first == "ryan" and "stranger" in t.roles_en.lower()
    assert get("usa").first is None and get("other").first is None


def test_starting_lists():
    # three per topic to try it first (user), none yet for 「그 밖의 상황」
    assert [len(get(t).picks) for t in ("tourist", "usa", "other")] == [3, 3, 0]
    assert [p.first for p in get("usa").picks] == ["ryan", "user", "user"]
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


def test_script_has_no_hangul_or_braces():
    import re

    assert not any(re.search(r"[가-힣{}]", t) for p in ALL for _, t in p.script)


def test_tmoney_does_not_send_a_cashless_tourist_to_a_store():
    # final review 2026-11-08: "no cash on me" then "try a convenience store" says the store takes cards, a payment
    # fact the description does not have (spec fixed-list-scripts 1); the store is only another place to top up
    said = " ".join(t for _, t in pick("tourist", "t-tmoney").script).lower()
    assert "cash" not in said.replace("only takes cash", "")
