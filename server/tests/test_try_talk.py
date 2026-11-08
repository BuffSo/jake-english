"""scripts/try_talk.py: the times and counts of a free-talk turn, from the events and when each came."""
import importlib.util
import sys
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "try_talk", Path(__file__).resolve().parent.parent / "scripts" / "try_talk.py")
tt = importlib.util.module_from_spec(_spec)
sys.modules["try_talk"] = tt
_spec.loader.exec_module(tt)


def test_summarize_times_each_stage():
    events = [
        (1.2, {"type": "heard", "text": "made up", "n": 1, "idx": 1, "korean": False}),
        (2.0, {"type": "text", "delta": "Sounds fun. "}),
        (2.1, {"type": "audio", "key": "k1"}),
        (2.5, {"type": "text", "delta": "What did you eat?"}),
        (2.6, {"type": "audio", "key": "k2"}),
        (3.4, {"type": "done", "idx": 2}),
    ]
    got = tt.summarize(events)
    assert got == {"heard_s": 1.2, "first_text_s": 2.0, "first_audio_s": 2.1, "done_s": 3.4,
                   "korean": False, "reply_words": 6}


def test_summarize_a_korean_turn():
    events = [
        (1.5, {"type": "heard", "text": "made up", "n": 1, "idx": 1, "korean": True}),
        (1.5, {"type": "text", "delta": "Let's try English."}),
        (1.6, {"type": "audio", "key": "k"}),
        (1.7, {"type": "reply", "idx": 2, "kind": "help", "parts": []}),
    ]
    got = tt.summarize(events)
    assert got["korean"] is True
    assert got["first_audio_s"] == 1.6
    assert got["done_s"] is None  # no done event came


def test_summarize_a_turn_that_ended_in_an_error():
    got = tt.summarize([(0.4, {"type": "error", "code": "no_speech", "say": None})])
    assert got == {"heard_s": None, "first_text_s": None, "first_audio_s": None, "done_s": None,
                   "korean": False, "reply_words": 0}


def test_summarize_end_counts_fixes_and_sound_guesses():
    body = {"items": [{"line": {"fix": {"why_ko": "설명이에요."}}},
                      {"line": {"fix": {"why_ko": "light처럼 들렸어요. L은 ..."}}}], "say": None}
    assert tt.summarize_end(body) == {"fixes": 2, "sound_guesses": 1}
    assert tt.summarize_end({"items": [], "say": {"text": "x"}}) == {"fixes": 0, "sound_guesses": 0}
