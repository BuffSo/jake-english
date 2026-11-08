"""je_server.stress: stress values kept for each recording (spec stress-log). Sentences here are made up."""
from __future__ import annotations

import json
import os

import pytest

from je_server.models import Attempt, Frame, Roleplay, ScriptLine, Syllable, ThreeLine, Word
from je_server.store import Store
from je_server.stress import (Job, build, dict_stress, in_use, is_vowel, judge, line_marks, out_path, pending,
                              sentence_scores, write)

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


# --- which tries to measure, and the record kept for each ---------------------------------------------------------------

RP = "a1b2c3d4e5f6"


def attempt(n: int, heard: str, mode: str = "turn", followed: bool = True) -> Attempt:
    return Attempt(n=n, mode=mode, heard=heard, followed=followed, issues=[], say_ko="", audio=[], timings={},
                   at="2026-11-08T09:00:00")


@pytest.fixture
def data(tmp_path):
    """One roleplay: a followed English try (to measure), a Korean one and an empty one (skipped and counted), one
    without a recording and one already measured (left out). The words are made up."""
    store = Store(tmp_path)
    line = ScriptLine(idx=1, speaker="user", text="I'd like 2 coffees.",
                      three=three([("I'd", "n")], [("like", "n")], [("two", "n")], [("cof", "s"), ("fees", "w")]))
    rp = Roleplay(id=RP, created="2026-11-08T08:00:00", situation="s",
                  frame=Frame(title_ko="t", user_role_ko="u", ryan_role_ko="r", place_ko="p", goal_ko="g"),
                  lines=[ScriptLine(idx=0, speaker="ryan", text="Hello."), line,
                         ScriptLine(idx=2, speaker="user", text="Thanks a lot.")],
                  attempts={1: [attempt(1, "I'd like 2 coffees.")],
                            2: [attempt(1, "커피 두 잔이요", followed=False), attempt(2, "...", followed=False),
                                attempt(3, "Thanks a lot."), attempt(4, "Thanks a lot.")]})
    store.save(rp)
    for idx, n in [(1, 1), (2, 1), (2, 2), (2, 4)]:  # no recording for 2-3
        store.rec_path(RP, idx, n).write_bytes(b"x")
    write(out_path(tmp_path, RP, 2, 4), {"v": 1})
    return tmp_path


def test_pending_takes_english_tries_with_a_recording_not_yet_measured(data):
    jobs, skipped = pending(data)
    assert [j.key for j in jobs] == [f"{RP}_1_1"] and skipped == 2
    job = jobs[0]
    assert job.words == ["i'd", "like", "two", "coffees"]  # the heard words, numbers read out
    assert job.rec == data / "roleplays" / RP / "rec" / "1-1.m4a"
    assert (job.mode, job.followed, job.aside, job.at) == ("turn", True, False, "2026-11-08T09:00:00")
    assert job.created == "2026-11-08T08:00:00"
    assert job.three is not None and len(job.three.words) == 4


def test_pending_skips_an_unreadable_roleplay(data):
    (data / "roleplays" / "0f0f0f0f0f0f").mkdir()
    (data / "roleplays" / "0f0f0f0f0f0f" / "roleplay.json").write_text("{")
    assert [j.key for j in pending(data)[0]] == [f"{RP}_1_1"]


def test_in_use_looks_at_records_changed_in_the_last_ten_minutes(data):
    t0 = 1_800_000_000
    for f in data.rglob("*"):
        os.utime(f, (t0, t0))
    assert in_use(data, now=t0 + 599) and not in_use(data, now=t0 + 601)
    rec = data / "roleplays" / RP / "rec" / "1-1.m4a"
    os.utime(rec, (t0 + 500, t0 + 500))  # a new recording counts too
    assert in_use(data, now=t0 + 1000)


def syl(p: str, db: float, st: float | None, dur: float, start: float = 0.0) -> dict:
    return {"p": p, "start": start, "end": start + dur, "dur": dur, "db": db, "st": st, "st_med": st}


ALIGNED = {
    "words": [
        {"w": "i'd", "start": 0.0, "end": 0.2, "phones": ["AY1", "D"], "syl": [syl("AY1", 66, 4, 0.15)]},
        {"w": "like", "start": 0.2, "end": 0.5, "phones": ["L", "AY1", "K"], "syl": [syl("AY1", 68, 5, 0.12)]},
        {"w": "two", "start": 0.5, "end": 0.7, "phones": ["T", "UW1"], "syl": [syl("UW1", 70, 6, 0.14)]},
        {"w": "coffees", "start": 0.7, "end": 1.2, "phones": ["K", "AO1", "F", "IY0", "Z"],
         "syl": [syl("AO1", 72, 7, 0.16), syl("IY0", 64, 3, 0.10)]},
    ],
    "quality": {"speech_log_likelihood": -50.0, "phone_duration_deviation": 1.2},
}


def test_build_adds_judgement_and_keeps_the_try(data):
    job = pending(data)[0][0]
    rec = build(job, ALIGNED, tools={"mfa": "3.4.3"}, measured="2026-11-08T10:00:00")
    assert {k: rec[k] for k in ("v", "rp", "idx", "n", "mode", "followed", "aside", "at", "created", "measured",
                                "status")} == {
        "v": 1, "rp": RP, "idx": 1, "n": 1, "mode": "turn", "followed": True, "aside": False,
        "at": "2026-11-08T09:00:00", "created": "2026-11-08T08:00:00", "measured": "2026-11-08T10:00:00",
        "status": "ok"}
    assert rec["tools"] == {"mfa": "3.4.3"} and rec["quality"] == ALIGNED["quality"]
    first, cof = rec["words"][0], rec["words"][3]
    assert first["content"] is False and first["pick"] is None and first["dict"] == {"primary": [0], "secondary": False}
    assert cof["content"] is True and cof["pick"] == 0 and cof["margin"] == pytest.approx(8 / 3 + 2 + 1.5)
    assert cof["mark"] == {"s": 0, "w": [1], "emph": False, "n": 2}
    assert cof["syl"] == ALIGNED["words"][3]["syl"] and cof["phones"] == ["K", "AO1", "F", "IY0", "Z"]
    assert cof["score"] > first["score"]


def test_build_without_alignment_is_a_failure_record(data):
    rec = build(pending(data)[0][0], None, tools={}, measured="t")
    assert rec["status"] == "unaligned" and rec["words"] == [] and rec["quality"] is None


def test_write_keeps_values_apart_from_the_records(data):
    write(out_path(data, RP, 1, 1), {"v": 1})
    assert json.loads((data / "stress" / RP / "1-1.json").read_text()) == {"v": 1}
    assert not (data / "roleplays" / RP / "stress").exists()
    assert sorted(p.name for p in (data / "roleplays" / RP).iterdir()) == ["rec", "roleplay.json"]
