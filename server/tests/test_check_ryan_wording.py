"""scripts/check_ryan_wording.py: the live wording check's own bookkeeping (PR #32 review)."""
import importlib.util
import sys
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "check_ryan_wording", Path(__file__).resolve().parent.parent / "scripts" / "check_ryan_wording.py")
cw = importlib.util.module_from_spec(_spec)
sys.modules["check_ryan_wording"] = cw  # dataclasses look the module up while the script loads
_spec.loader.exec_module(cw)


def test_every_model_the_server_can_pick_has_a_price():
    # with JE_CLAUDE_WRITER=opus the run made every paid call and then died on the cost sum (KeyError)
    from je_server.claude import QUICKS, WRITERS

    assert {m["model"] for m in (*WRITERS.values(), *QUICKS.values())} <= set(cw.PRICE)


def test_double_quotes_are_checked_on_the_model_answer():
    # the server drops double quotes from what the learner sees, so the check looks at the model's own text
    case = cw.Case("q", "Can I get a room?", "Can I get a loom?", [cw.issue("room", "loom")], [cw.REST])
    shown = "나머지 낱말은 다 알아들었어요. 그런데 room이 loom처럼 들렸어요. 한 번 더 해 볼까요?"
    said = shown.replace("room이 loom", '"room"이 "loom"')
    assert "double quotes" in cw.flags(case, shown, aside=False, raw=said)
    assert cw.flags(case, shown, aside=False, raw=shown) == []


def test_aside_flags_the_sorting_and_a_missing_retry():
    # phone test 2026-11-08: teacher Ryan told the learner how the server had sorted the recording, and stopped there
    case = next(c for c in cw.ASIDE if c.name == "off app wish")
    bad = "대사와 상관없는 말로 들려서 따로 짚을 곳이 없어요."
    assert {"names '짚을'", "names '상관없는'", "does not ask to try again"} <= set(cw.flags(case, bad, aside=True))
    # the prompt before this fix, live: the sort's own words, which the check first missed
    assert "names '혼잣말'" in cw.flags(case, "대사와 상관없는 혼잣말로 들렸어요. 한 번 더 해 볼까요?", aside=True)
    good = "그렇군요, 그런 게 있으면 편하겠어요. 다시 해 볼까요?"
    assert cw.flags(case, good, aside=True) == []
    # spec record-cancel-skip 6: a line can be skipped now, so the old example's 「대사를 말해야 넘어가요」 is wrong
    old = "그렇군요, 그런 게 있으면 편하겠어요. 지금은 대사를 말해야 다음으로 넘어가요. 다시 해 볼까요?"
    assert cw.flags(case, old, aside=True) == ["says '말해야'"]


def test_aside_flags_a_skip_wish_without_the_skip_button():
    # spec record-cancel-skip 6: wanting to move past the line gets 「건너뛰기」 named
    case = next(c for c in cw.ASIDE if c.name == "off skip wish")
    assert cw.flags(case, "괜찮아요. 다시 해 볼까요?", aside=True) == ["does not say '건너뛰기'"]
    good = "「건너뛰기」를 누르면 녹음하지 않고 다음으로 넘어가요. 아니면 한 번 더 해 볼까요?"
    assert cw.flags(case, good, aside=True) == []
