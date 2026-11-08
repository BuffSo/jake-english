"""scripts/check_three_lines.py: the three-line measure's own bookkeeping (made-up lines, 2026-11-08)."""
import importlib.util
import sys
from pathlib import Path

from fakes import FRAME, noted
from je_server.engine import Engine
from je_server.models import Frame, Roleplay, ScriptLine

_path = Path(__file__).resolve().parent.parent / "scripts" / "check_three_lines.py"
_spec = importlib.util.spec_from_file_location("check_three_lines", _path)
ct = importlib.util.module_from_spec(_spec)
sys.modules["check_three_lines"] = ct
_spec.loader.exec_module(ct)

ASK = "Excuse me, where is the station?"
ANSWER = "Go straight and turn left."
THANKS = "Thank you so much."


def record(rp_id: str, created: str, place: str, lines: list[tuple[str, str, bool]]) -> Roleplay:
    return Roleplay(id=rp_id, created=created, situation="길 묻기", frame=Frame(**{**FRAME, "place_ko": place}),
                    lines=[ScriptLine(idx=i, speaker=s, text=t, three=noted(t) if has else None)
                           for i, (s, t, has) in enumerate(lines)])


def test_noted_lines_keeps_lines_with_notes_once():
    old = record("a", "2026-11-01T10:00:00", "역 앞", [("user", ASK, True), ("ryan", ANSWER, False),
                                                      ("user", THANKS, True)])
    new = record("b", "2026-11-02T10:00:00", "공원", [("user", ASK, True), ("ryan", ANSWER, False)])
    got = dict(ct.noted_lines([new, old]))  # any order in, newest record's context out
    assert set(got) == {ASK, THANKS}  # Ryan's line has no note here
    assert got[ASK] == Engine.context(new, 0) == f"장소: 공원. ryan: {ANSWER}"
    assert got[THANKS] == Engine.context(old, 2)


def test_sample_is_the_same_for_the_same_seed():
    lines = [(f"line {i}", "") for i in range(10)]
    assert ct.sample(lines, 4, 7) == ct.sample(list(reversed(lines)), 4, 7)
    assert len(ct.sample(lines, 4, 7)) == 4
    assert sorted(ct.sample(lines, 50, 7)) == sorted(lines)


def test_outcome_reads_the_server_log_line():
    assert ct.outcome("three-line note: 1 tries, 2.0s") == "1"
    assert ct.outcome("three-line note: 2 tries, 3.1s") == "2"
    assert ct.outcome("three-line note degraded after 3 tries, 9.0s: hi,ref") == "degraded:hi,ref"
    assert ct.outcome("claude api status 529") is None


def test_summary_counts_without_lines():
    rows = [{"outcome": "1", "calls": 1, "secs": 3.0, "cost": 0.01},
            {"outcome": "2", "calls": 2, "secs": 6.0, "cost": 0.02},
            {"outcome": "degraded:ref,stress", "calls": 3, "secs": 9.0, "cost": 0.03},
            {"outcome": "degraded:ref", "calls": 3, "secs": 9.5, "cost": 0.03}]
    s = ct.summary(rows)
    assert "lines 4" in s and "first try 1" in s and "two tries 1" in s and "three tries 0" in s
    assert "degraded 2 (ref 2, stress 1)" in s
    assert "calls 9 (2.25 a line)" in s and "$0.090" in s and "median 7.5s" in s
    assert ASK not in s


def test_summary_without_degraded_lines():
    s = ct.summary([{"outcome": "1", "calls": 1, "secs": 3.0, "cost": 0.01}])
    assert "degraded 0;" in s and "()" not in s
