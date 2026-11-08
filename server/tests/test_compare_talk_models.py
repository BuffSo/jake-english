"""scripts/compare_talk_models.py: Korean turns, the echo mark and the recast count (2026-11-09)."""
import importlib.util
import re
import sys
from pathlib import Path

_path = Path(__file__).resolve().parent.parent / "scripts" / "compare_talk_models.py"
_spec = importlib.util.spec_from_file_location("compare_talk_models", _path)
ct = importlib.util.module_from_spec(_spec)
sys.modules["compare_talk_models"] = ct
_spec.loader.exec_module(ct)

from je_server.prompts import TALK_ECHO, TALK_KOREAN, TALK_START  # noqa: E402


def test_messages_without_echo_leave_the_last_turn_alone():
    m = ct.messages(["Hi!", "I go home."])
    assert m == [{"role": "user", "content": TALK_START}, {"role": "assistant", "content": "Hi!"},
                 {"role": "user", "content": "I go home."}]


def test_messages_with_echo_mark_only_the_last_message():
    m = ct.messages(["Hi!", "I go home."], echo=True)
    assert m[-1]["content"] == "I go home.\n" + TALK_ECHO
    assert TALK_ECHO not in m[1]["content"]


def test_recast_counts_the_right_form_only():
    assert ct.recasts("Oh, you went to the mall! What did you buy?", r"\byou (went|bought)\b")
    assert not ct.recasts("I went shopping too! What did you get?", r"\byou (went|bought)\b")
    assert not ct.recasts("anything", None)


def test_every_mistake_regex_ignores_ryans_own_story():
    stories = ["I went shopping too, and I bought a jacket!", "My sister lives far away and has a dog.",
               "I get bored on rainy days too.", "I had a sandwich and ate it at my desk.",
               "I went to the mall too, and I bought two pairs of shoes!", "I have two kids and they live in Seoul.",
               "My sister has two children, so she is busy.", "I got two pairs of socks there."]
    for name, turns, pattern in ct.MISTAKES:
        for s in stories:
            assert not re.search(pattern, s, re.I), (name, s)


def test_every_mistake_regex_catches_a_right_form_of_the_learners_words():
    rights = {"mistake: go/buy": "Oh, you went to the mall and bought shoes!",
              "mistake: live/have": "Your sister lives in Busan? And she has two children!",
              "mistake: boring": "Oh no, you're bored today?",
              "mistake: eat": "You ate bibimbap? Nice!"}
    for name, turns, pattern in ct.MISTAKES:
        assert re.search(pattern, rights[name], re.I), name


def test_korean_cases_are_marked_in_the_last_turn():
    assert len(ct.KOREAN_CASES) == 6
    for name, turns in ct.KOREAN_CASES:
        assert turns[-1].startswith(TALK_KOREAN), name


def test_flags_korean_in_a_reply():
    assert "korean" in ct.flags("좋아요! What next?", ["좋아요!", "What next?"])
