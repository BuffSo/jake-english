import json
from pathlib import Path

from je_server.models import Roleplay, ScriptLine

CONTRACT = Path(__file__).resolve().parents[2] / "contract"


def test_roleplay_example_matches_model():
    raw = json.loads((CONTRACT / "roleplay.json").read_text(encoding="utf-8"))
    assert Roleplay.model_validate(raw).model_dump(mode="json") == raw


def test_user_line_example_matches_model():
    raw = json.loads((CONTRACT / "line-user.json").read_text(encoding="utf-8"))
    assert ScriptLine.model_validate(raw).model_dump(mode="json") == raw


def test_user_line_example_passes_three_line_checks():
    from je_server.threeline import check

    line = ScriptLine.model_validate_json((CONTRACT / "line-user.json").read_text(encoding="utf-8"))
    assert check(line.text, line.three) == []


def test_summary_example_has_the_engine_shape():
    raw = json.loads((CONTRACT / "summary.json").read_text(encoding="utf-8"))
    assert set(raw) == {"say", "lines"}
    for l in raw["lines"]:
        assert set(l) == {"line", "tries"} and ScriptLine.model_validate(l["line"]).model_dump(mode="json") == l["line"]
        for t in l["tries"]:
            assert set(t) == {"n", "mode", "heard", "followed", "issues", "point_ko"}
            assert all(set(i) == {"target", "heard", "say_ko"} for i in t["issues"])
