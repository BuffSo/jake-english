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
    assert cj.label("카페에서 주문하는 상황이에요.", "카페에서 주문하는 상황이에요.", E) == "MISSED"


def test_kept_swapped_and_doubled():
    assert cj.label("카페에서 주문하는 상황을 추천해요.", "카페에서 주문하는 상황을 추천해요.", E) == "model kept"
    assert cj.label("카페에서 주문하는 상황을 골라 봤어요.", "카페에서 주문하는 상황을 추천해요.", E) == "swapped"
    # a doubled ending ends in the given one, but the server took the other off
    assert cj.label("카페에서 주문하는 상황을 골라 봤어요. 상황을 추천해요.", "카페에서 주문하는 상황을 추천해요.", E) == "swapped"


def test_every_quick_model_has_a_price():
    from je_server.claude import QUICKS

    assert {m["model"] for m in QUICKS.values()} <= set(cj.PRICE)
