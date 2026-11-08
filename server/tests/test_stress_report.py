"""je_server.stress_report: the stress test's tables from the kept values (spec stress-log 「표 다시 내기」).
Records are made up by hand; the words are made up too."""
from __future__ import annotations

import json

import pytest

from je_server.stress import out_path, write
from je_server.stress_report import auc, load, render, weak_forms, word_rows


def w(word: str, phones: list[str], pick=None, primary=None, secondary=False, mark=None, margin=1.0, score=None,
      content=True) -> dict:
    vowels = [p for p in phones if p[-1].isdigit()]
    return {"w": word, "phones": phones, "syl": [{"p": v} for v in vowels], "pick": pick, "margin": margin,
            "dict": None if primary is None else {"primary": primary, "secondary": secondary}, "mark": mark,
            "score": score, "content": content}


def rec(words: list[dict], followed=True, status="ok", at="2026-11-08T09:00:00") -> dict:
    return {"v": 1, "status": status, "followed": followed, "at": at, "measured": "2026-11-09T04:00:00",
            "words": words}


def two(pick, primary, **kw):
    return w("zebra", ["Z", "IY1", "B", "R", "AH0"], pick=pick, primary=primary, **kw)


def test_auc():
    assert auc([3, 2], [1]) == 1.0
    assert auc([1], [1]) == 0.5
    assert auc([1, 3], [2]) == 0.5
    assert auc([], [1]) is None


def test_word_rows_count_only_words_with_one_dictionary_stress():
    rows = {r[0]: r[1:] for r in word_rows([rec([two(0, [0]), two(1, [0]), two(1, [1]), two(0, [0, 1]),
                                                 two(None, [0])])])}
    n, right, first = rows["dict"]
    assert n == 3 and right == pytest.approx(2 / 3) and first == pytest.approx(2 / 3)


def test_word_rows_without_secondary_and_top_quarter():
    words = [two(0, [0], margin=0.1), two(0, [0], margin=0.2), two(1, [0], margin=0.3, secondary=True),
             two(0, [0], margin=5.0)]
    rows = {r[0]: r[1:] for r in word_rows([rec(words)])}
    assert rows["no_secondary"][0] == 3
    assert rows["top_quarter"] == (1, 1.0, 1.0)


def test_top_quarter_is_not_empty_for_a_small_sample():
    """The default (exclusive) quartile put the cut above the largest of two margins (todo 20261108_41 4)."""
    rows = {r[0]: r[1:] for r in word_rows([rec([two(0, [0], margin=1.0), two(1, [0], margin=2.0)])])}
    assert rows["top_quarter"] == (1, 0.0, 1.0)


def test_top_quarter_of_one_word_is_that_word():
    rows = {r[0]: r[1:] for r in word_rows([rec([two(0, [0], margin=1.0)])])}
    assert rows["top_quarter"] == (1, 1.0, 1.0)


def test_mark_row_needs_the_same_syllable_count():
    words = [two(1, [0], mark={"s": 1, "w": [0], "emph": True, "n": 2}),
             two(0, [0], mark={"s": 0, "w": [], "emph": False, "n": 3}),
             two(0, [0], mark={"s": None, "w": [], "emph": False, "n": 2})]
    assert {r[0]: r[1:] for r in word_rows([rec(words)])}["mark"] == (1, 1.0, 0.0)


def test_empty_rows_have_no_ratio():
    assert {r[0]: r[1:] for r in word_rows([])}["dict"] == (0, None, None)


def test_weak_forms():
    words = [w("for", ["F", "ER0"]), w("for", ["F", "AO1", "R"]), w("the", ["DH", "IY0"]), w("a", ["EY1"])]
    forms = weak_forms([rec(words)])
    assert forms["for"] == (1, 2) and forms["the"] == (1, 1) and forms["a"] == (0, 1) and forms["of"] == (0, 0)


def test_render_prints_numbers_not_words():
    records = [rec([two(0, [0], score=1.0), w("of", ["AH0", "V"], score=-1.0, content=False)]),
               rec([two(1, [0])], followed=False), rec([], status="unaligned")]
    out = render(records)
    assert "zebra" not in out
    assert "녹음: 잼 2, 정렬 실패 1" in out
    assert "### 대사를 따라 말한 것 (녹음 1)" in out and "### 다르게 말한 영어 (녹음 1)" in out
    assert "| 낱말 강세, 사전과 | 1 | 1.00 | 첫 음절 찍기 1.00 |" in out
    assert "AUC 1.00" in out and "| of | 1 | 1 |" in out


def test_load_takes_format_1_since_a_day_and_counts_broken_files(tmp_path):
    write(out_path(tmp_path, "a1a1a1a1a1a1", 1, 1), rec([], at="2026-11-07T09:00:00"))
    write(out_path(tmp_path, "a1a1a1a1a1a1", 2, 1), rec([], at=None))  # measured on 11-09
    write(out_path(tmp_path, "a1a1a1a1a1a1", 3, 1), {**rec([]), "v": 2})
    (tmp_path / "stress" / "a1a1a1a1a1a1" / "4-1.json").write_text("{")
    records, broken = load(tmp_path)
    assert len(records) == 2 and broken == 1
    assert [r["at"] for r in load(tmp_path, since="2026-11-08")[0]] == [None]
    assert json.loads((tmp_path / "stress" / "a1a1a1a1a1a1" / "1-1.json").read_text())["v"] == 1


def test_since_uses_when_the_roleplay_was_made_when_the_try_has_no_time(tmp_path):
    """Tries before 2026-11-07 have no `at`; measuring them again must not bring them in under the new day (todo
    20261108_41 3)."""
    write(out_path(tmp_path, "a1a1a1a1a1a1", 1, 1), {**rec([], at=None), "created": "2026-11-05T09:00:00"})
    assert load(tmp_path, since="2026-11-08")[0] == []
    assert len(load(tmp_path, since="2026-11-05")[0]) == 1


def script_module():
    import importlib.util
    from pathlib import Path

    spec = importlib.util.spec_from_file_location(
        "stress_report_script", Path(__file__).resolve().parent.parent / "scripts" / "stress_report.py")
    script = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(script)
    return script


def test_the_script_stops_on_a_data_folder_without_roleplays(tmp_path, monkeypatch, capsys):
    script = script_module()
    monkeypatch.setattr(script, "env", lambda: {"JE_DATA_DIR": str(tmp_path / "typo")})
    assert script.main([]) == 1
    assert "roleplays" in capsys.readouterr().out


def test_the_script_prints_the_tables_of_the_data_folder(tmp_path, monkeypatch, capsys):
    script = script_module()
    (tmp_path / "roleplays").mkdir()
    write(out_path(tmp_path, "a1a1a1a1a1a1", 1, 1), rec([two(0, [0])]))
    monkeypatch.setattr(script, "env", lambda: {"JE_DATA_DIR": str(tmp_path)})
    assert script.main(["--since", "2026-11-01"]) == 0
    out = capsys.readouterr().out
    assert "녹음: 잼 1" in out and "zebra" not in out and str(tmp_path) not in out
