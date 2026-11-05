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
