"""scripts/compare_quick_models.py: the quick-model comparison's own bookkeeping (2026-11-08)."""
import importlib.util
import sys
from pathlib import Path

_path = Path(__file__).resolve().parent.parent / "scripts" / "compare_quick_models.py"
_spec = importlib.util.spec_from_file_location("compare_quick_models", _path)
cq = importlib.util.module_from_spec(_spec)
sys.modules["compare_quick_models"] = cq
_spec.loader.exec_module(cq)

E = "상황을 추천해요."
KEPT = "카페에서 주문하는 상황을 추천해요."


def test_every_model_a_quick_job_can_pick_has_a_price():
    from je_server.claude import QUICKS

    assert {m["model"] for m in QUICKS.values()} <= set(cq.PRICE)


def test_a_kept_recommendation_has_no_flags():
    assert cq.rec_flags(KEPT, KEPT, E, ["공항에서 짐을 찾는 상황"]) == []


def test_recommendation_flags():
    # what the comparison saw from Haiku (made-up lines of the same shape)
    assert "says '끝말'" in cq.rec_flags("카페에서 주문하는 상황을 추천해요. 끝말: 상황을 추천해요.", KEPT, E, [])
    two = "카페에서 주문하는 상황을 연습해 볼까요? 이 상황을 추천해요."
    assert "more than one sentence" in cq.rec_flags(two, two, E, [])
    odd = "제가 카페에서 주문하는 상황을 추천해요."
    assert "odd start" in cq.rec_flags(odd, odd, E, [])
    assert "repeats a listed situation" in cq.rec_flags(KEPT, KEPT, E, ["카페에서 주문하는 상황"])
    assert "MISSED ending" in cq.rec_flags("카페에서 주문하는 연습을 해 봐요.", "카페에서 주문하는 연습을 해 봐요.", E, [])


def test_a_repeat_with_another_ending_is_flagged():
    # todo 28 1: a listed situation said again with another of Jake's endings slipped through
    seen = ["명동에서 환전소를 묻는 상황을 골라 봤어요."]
    said = "명동에서 환전소를 묻는 상황을 추천해요."
    assert "repeats a listed situation" in cq.rec_flags(said, said, E, seen)
    # a recent situation kept without an ending (typed by the learner) still matches
    assert "repeats a listed situation" in cq.rec_flags(KEPT, KEPT, E, ["카페에서 주문하는 상황"])
    # an ending alone has no situation to repeat
    assert "repeats a listed situation" not in cq.rec_flags(KEPT, KEPT, E, ["상황을 추천해요."])
