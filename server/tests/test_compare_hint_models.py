"""scripts/compare_hint_models.py: the hint comparison's own bookkeeping (2026-11-09)."""
import importlib.util
import sys
from pathlib import Path

_path = Path(__file__).resolve().parent.parent / "scripts" / "compare_hint_models.py"
_spec = importlib.util.spec_from_file_location("compare_hint_models", _path)
ch = importlib.util.module_from_spec(_spec)
sys.modules["compare_hint_models"] = ch
_spec.loader.exec_module(ch)

GOOD = {"meaning_ko": "주말 계획이 있다고 말하기", "starters": ["I'm going to…", "Not really,…"],
        "full": "I'm going to see a movie."}


def test_good_hint_has_no_flags():
    assert ch.flags(GOOD) == []


def test_no_json_is_flagged():
    assert ch.flags(None) == ["no json"]


def test_full_sentence_not_from_an_opener_is_flagged_apart_from_the_check():
    bad = {**GOOD, "full": "Maybe I will rest at home."}
    f = ch.flags(bad)
    assert "full not from opener" in f
    assert "check" in f  # hints.check drops it too


def test_rule_break_the_check_catches_is_flagged():
    bad = {**GOOD, "starters": ["I'm going to"]}  # one opener, no dots
    assert ch.flags(bad) == ["check"]


def test_check_is_given_ryans_line():
    # an opener that repeats his words, then one left: the server's check drops it (spec 9)
    h = {**GOOD, "starters": ["Plans for this weekend…", "Not really,…"], "full": "Not really. I was busy."}
    assert ch.flags(h) == [] and ch.flags(h, "Any plans for this weekend?") == ["check"]


def test_opener_comma_before_dots_still_starts_the_full_sentence():
    h = {**GOOD, "starters": ["Not really,…", "Yes, I do…"], "full": "Not really. I was busy."}
    assert ch.flags(h) == []


def test_every_case_is_a_ryan_line_last():
    assert len(ch.CASES) == 8
    for name, turns in ch.CASES:
        assert len(turns) % 2 == 1, name  # Ryan speaks first and last
