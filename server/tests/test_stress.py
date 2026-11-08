"""je_server.stress: stress values kept for each recording (spec stress-log). Sentences here are made up."""
from __future__ import annotations

import pytest

from je_server.models import Syllable, ThreeLine, Word
from je_server.stress import dict_stress, is_vowel, judge, line_marks, sentence_scores

# --- judging one word (guide 「무엇으로 쟀나」: 3 dB, 2 semitones and 40 ms count the same) ---------------------------


def test_is_vowel_is_a_phone_with_a_stress_digit():
    assert is_vowel("AA1") and is_vowel("IY0") and not is_vowel("K") and not is_vowel("spn")


def test_judge_picks_the_strongest_vowel_with_the_guide_weights():
    syl = [{"db": 70, "st": 10, "dur": 0.10}, {"db": 64, "st": 8, "dur": 0.08}]
    pick, margin = judge(syl)
    assert pick == 0 and margin == pytest.approx(2 + 1 + 0.5)


def test_judge_drops_pitch_for_the_whole_word_when_one_vowel_has_none():
    syl = [{"db": 70, "st": None, "dur": 0.10}, {"db": 64, "st": 30, "dur": 0.20}]
    pick, margin = judge(syl)
    assert pick == 1 and margin == pytest.approx(-2 + 2.5)


def test_judge_needs_two_measured_vowels():
    assert judge([{"db": 70, "st": 10, "dur": 0.1}]) == (None, None)
    assert judge([{"db": None, "st": 1, "dur": 0.1}, {"db": 60, "st": 1, "dur": 0.1}]) == (None, None)
    assert judge([]) == (None, None)


# --- the dictionary's stress for the pronunciation MFA chose ----------------------------------------------------------


def test_dict_stress_keeps_the_prons_with_the_same_vowel_count():
    assert dict_stress("coffee", ["K", "AA1", "F", "IY0"]) == {"primary": [0], "secondary": False}


def test_dict_stress_lists_every_place_when_the_prons_differ():
    assert dict_stress("record", ["R", "EH1", "K", "ER0", "D"])["primary"] == [0, 1]  # noun and verb


def test_dict_stress_tells_a_secondary_stress():
    assert dict_stress("understand", ["AH2", "N", "D", "ER0", "S", "T", "AE1", "N", "D"])["secondary"] is True


def test_dict_stress_of_an_unknown_word_or_vowel_count_is_none():
    assert dict_stress("qwzxv", ["K", "AH0"]) is None
    assert dict_stress("coffee", ["K", "AA1", "F"]) is None


# --- the marks of the line's three-line display -----------------------------------------------------------------------


def three(*words: list[tuple[str, str]], emph: tuple[int, ...] = ()) -> ThreeLine:
    return ThreeLine(words=[Word(syl=[Syllable(en=en, ko="가", m=m, hi="가" if m == "s" else "") for en, m in w],
                                 emph=i in emph)
                            for i, w in enumerate(words)], reading="")


def test_line_marks_follow_the_words_heard():
    t = three([("I'd", "n")], [("cof", "s"), ("fee", "w")])
    marks = line_marks(t, ["i'd", "like", "coffee"])
    assert marks == [{"s": None, "w": [], "emph": False, "n": 1}, None, {"s": 0, "w": [1], "emph": False, "n": 2}]


def test_line_marks_carry_a_word_stressed_for_meaning():
    t = three([("I", "n")], [("did", "s")], [("say", "n")], emph=(1,))
    assert line_marks(t, ["i", "did", "say"])[1] == {"s": 0, "w": [], "emph": True, "n": 1}


def test_line_marks_without_a_three_line_display_are_empty():
    assert line_marks(None, ["a", "cup"]) == [None, None]


# --- sentence stress: each word's stressed vowel, standardised within the recording -----------------------------------


def word(db: float, phones: list[str], st: float | None = 5.0, dur: float = 0.1) -> dict:
    vowels = [p for p in phones if is_vowel(p)]
    return {"phones": phones, "syl": [{"p": v, "db": db, "st": st, "dur": dur} for v in vowels]}


def test_sentence_scores_are_standardised_within_the_recording():
    s = sentence_scores([word(70, ["K", "AH1", "P"]), word(60, ["AH0"]), {"phones": ["S"], "syl": []}])
    assert s[0] == pytest.approx(1.0) and s[1] == pytest.approx(-1.0) and s[2] is None


def test_sentence_scores_count_no_pitch_as_average():
    s = sentence_scores([word(70, ["AH1"], st=None), word(70, ["AH1"], st=2), word(70, ["AH1"], st=8)])
    assert s[0] == pytest.approx(0.0) and s[2] > s[1]


def test_a_word_of_several_vowels_without_a_primary_has_no_score():
    assert sentence_scores([word(70, ["AH0", "IH0"]), word(60, ["AH1"])])[0] is None
