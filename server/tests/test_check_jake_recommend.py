"""scripts/check_jake_recommend.py: the real-model ending check's own bookkeeping (final review, 2026-11-08)."""
import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "check_jake_recommend", Path(__file__).resolve().parent.parent / "scripts" / "check_jake_recommend.py")
cj = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cj)

E = "상황을 추천해요."


def test_an_unknown_ending_is_counted_as_missed():
    # the server says an unknown ending as it came, so the model's text and what is said are the same: that is a
    # miss, not a kept ending (it was counted as kept)
    # (「…상황이에요.」 was the example until PR #42 made a short tail after 상황 an ending the server swaps)
    assert cj.label("카페에서 주문하는 연습을 해 봐요.", "카페에서 주문하는 연습을 해 봐요.", E) == "MISSED"


def test_kept_swapped_and_doubled():
    assert cj.label("카페에서 주문하는 상황을 추천해요.", "카페에서 주문하는 상황을 추천해요.", E) == "model kept"
    assert cj.label("카페에서 주문하는 상황을 골라 봤어요.", "카페에서 주문하는 상황을 추천해요.", E) == "swapped"
    # a doubled ending ends in the given one, but the server took the other off
    assert cj.label("카페에서 주문하는 상황을 골라 봤어요. 상황을 추천해요.", "카페에서 주문하는 상황을 추천해요.", E) == "swapped"


def test_every_quick_model_has_a_price():
    from je_server.claude import QUICKS

    assert {m["model"] for m in QUICKS.values()} <= set(cj.PRICE)


def test_every_topic_sends_made_up_recent_situations():
    # todo 21: the label echo came on the real server, which sends the topic's recent situations; the check sends
    # ten made-up ones per topic as the server would (store.recent_situations keeps ten)
    from je_server.topics import TOPICS

    assert all(len(cj.RECENT[t.id]) == 10 for t in TOPICS)


def test_the_model_is_the_recommend_setting_unless_chosen():
    from types import SimpleNamespace

    from je_server.claude import QUICKS

    s = SimpleNamespace(claude_recommend="sonnet")
    assert cj.make_claude(object(), s, None).recommender is QUICKS["sonnet"]
    assert cj.make_claude(object(), s, "haiku").recommender is QUICKS["haiku"]


def test_odd_starts_are_counted_at_the_front_only():
    # todo 27: now and then a suggestion opens with the speaker, so Jake's voice sounds like he is the one doing it
    assert cj.odd_start("제가 카페에서 주문하는 상황을 추천해요.")
    assert cj.odd_start("제이크가 추천하는 상황은 카페에서 주문하는 상황이에요.")
    # the learner inside the situation is not an odd start
    assert not cj.odd_start("카페에서 제가 시킨 음료가 잘못 나와 바꿔 달라는 상황을 추천해요.")
    assert not cj.odd_start("카페에서 주문하는 상황을 추천해요.")
    # a place that starts like a name (final review) is not the speaker
    assert not cj.odd_start("잭슨빌 공항에서 렌터카를 빌리는 상황을 추천해요.")
    assert not cj.odd_start("제이크스 카페에서 주문하는 상황을 추천해요.")
    assert cj.odd_start("잭이 추천해요, 카페에서 주문하는 상황이에요.")
    # known over-count: the learner at the front of a situation reads the same as the speaker, so the count cannot
    # tell them apart; flagged lines are read before acting (the server could not strip it for the same reason)
    assert cj.odd_start("제가 묵는 호텔에서 수건을 더 달라고 하는 상황을 추천해요.")
