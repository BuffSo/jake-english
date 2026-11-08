"""scripts/compare_fix_models.py: the corrections comparison's own bookkeeping (2026-11-08)."""
import importlib.util
import sys
from pathlib import Path

_path = Path(__file__).resolve().parent.parent / "scripts" / "compare_fix_models.py"
_spec = importlib.util.spec_from_file_location("compare_fix_models", _path)
cf = importlib.util.module_from_spec(_spec)
sys.modules["compare_fix_models"] = cf
_spec.loader.exec_module(cf)

from je_server.fixes import Found  # noqa: E402

CASE = cf.Case("x", [("ryan", "Hi!"), ("user", "Good."), ("ryan", "Nice."), ("user", "I go home.")], {1})


def item(idx):
    return {"idx": idx, "said": "s", "fixed": "f", "why_ko": "w"}


def found(of):
    return Found(of, "s", "f", "w")


def test_flags_count_rule_breaks():
    four = [item(3)] * 4
    assert "4 items" in cf.flags(four, [found(3)] * 3, CASE)
    assert "keep-off turn 1" in cf.flags([item(1)], [found(1)], CASE)
    assert "dropped 1" in cf.flags([item(3), item(3)], [found(3)], CASE)
    assert cf.flags([item(3)], [found(3)], CASE) == []


def test_conversation_numbers_every_line_and_lists_my_turns():
    conv, turns = cf.conversation(CASE)
    assert conv[1] == {"차례": 1, "말한 사람": "학습자", "말": "Good."}
    assert turns == {1: "Good.", 3: "I go home."}


def test_every_case_keeps_off_only_my_turns():
    for case in cf.CASES:
        mine = {i for i, (who, _) in enumerate(case.conversation) if who == "user"}
        assert case.keep_off <= mine, case.name
