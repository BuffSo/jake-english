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


# a fragment answer (1), a right short sentence (3) and a misheard question back (5)
SHORT = cf.Case("short", [("ryan", "What did you have for breakfast?"), ("user", "Toast."), ("ryan", "Nice."),
                          ("user", "I'm good."), ("ryan", "And lunch?"), ("user", "Toast again. Endu?")],
                keep_off={3}, complete={1: r"\bI (had|ate)\b.*\btoast\b"}, far={5: {"udon", "toast"}})


def test_completed_counts_a_fragment_made_a_complete_sentence():
    assert cf.completed([found(3), Found(1, "Toast.", "I had toast for breakfast.", "w")], SHORT) == [1]
    # no verb, more than twelve words, or not a fragment turn: not counted
    assert cf.completed([Found(1, "Toast.", "Some toast, please.", "w")], SHORT) == []
    assert cf.completed([Found(1, "Toast.", "I had toast " + "and jam " * 5 + "today.", "w")], SHORT) == []
    assert cf.completed([Found(3, "I'm good.", "I had toast.", "w")], SHORT) == []


def test_changed_counts_a_kept_fix_on_a_right_sentence():
    kept = [Found(3, "I'm good.", "I am good.", "w"), Found(1, "Toast.", "I had toast.", "w")]
    assert cf.changed(kept, SHORT) == [3]
    assert cf.changed(kept[1:], SHORT) == []


def test_far_fills_count_a_misheard_word_filled_with_a_far_sounding_word():
    assert cf.far_fills([Found(5, "Endu?", "And udon?", "w")], SHORT) == [5]
    assert cf.far_fills([Found(5, "Endu?", "How about you?", "w")], SHORT) == []
    # a word of the turn itself is not a fill
    assert cf.far_fills([Found(5, "Toast again.", "I had toast again.", "w")], SHORT) == []
    assert cf.far_fills([Found(1, "Toast.", "I had udon.", "w")], SHORT) == []  # not a misheard turn


def test_flags_name_a_fragment_left_and_a_far_fill():
    done = Found(1, "Toast.", "I had toast for breakfast.", "w")
    assert cf.flags([item(1)], [done], SHORT) == []
    assert "fragment turn 1 left" in cf.flags([], [], SHORT)
    assert "far fill turn 5" in cf.flags([item(1), item(5)], [done, Found(5, "Endu?", "And udon?", "w")], SHORT)


def test_every_case_marks_only_my_turns_and_its_marks_hold():
    import re

    from je_server.compare import words

    for case in cf.CASES:
        mine = {i for i, (who, _) in enumerate(case.conversation) if who == "user"}
        assert set(case.complete) <= mine and set(case.far) <= mine, case.name
        for i, pattern in case.complete.items():
            assert not re.search(pattern, case.conversation[i][1], re.I), case.name  # the fragment has no verb
        for i, far in case.far.items():
            assert not far & set(words(case.conversation[i][1])), case.name


def test_cases_cover_short_answers_and_a_misheard_word():
    import re

    rights = {"food name only": "I had toast and a banana for breakfast.",
              "place name only": "I went to Jeju Island last weekend.",
              "misheard question back": "I had kimbap and ramen. How about you?"}
    for case in cf.CASES:
        for i, pattern in case.complete.items():
            assert re.search(pattern, rights[case.name], re.I), case.name
    assert set(rights) <= {c.name for c in cf.CASES}
    assert any(c.far for c in cf.CASES)
    right = {text for c in cf.CASES for i, (_, text) in enumerate(c.conversation) if i in c.keep_off}
    assert {"Yes, I do.", "I'm good."} <= right
