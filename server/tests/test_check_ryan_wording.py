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
