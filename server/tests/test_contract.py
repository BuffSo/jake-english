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
        assert set(l) == {"line", "tries", "first"} and ScriptLine.model_validate(l["line"]).model_dump(mode="json") == l["line"]
        for t in l["tries"]:
            assert set(t) == {"n", "mode", "heard", "followed", "issues", "point_ko"}
            assert all(set(i) == {"target", "heard", "say_ko"} for i in t["issues"])


def test_past_example_has_the_engine_shape():
    raw = json.loads((CONTRACT / "past.json").read_text(encoding="utf-8"))
    assert set(raw) == {"items"} and all(set(i) == {"group", "title_ko", "first", "latest"} for i in raw["items"])


def test_saved_example_has_the_engine_shape():
    raw = json.loads((CONTRACT / "saved.json").read_text(encoding="utf-8"))
    assert set(raw) == {"items"}
    assert all(set(i) == {"key", "rp_id", "idx", "speaker", "text", "title_ko", "at"} for i in raw["items"])


def test_home_topics_example_has_the_engine_shape():
    # situation-topics final review: the app draws the topic and list buttons from /home's `topics`
    from je_server.topics import public

    raw = json.loads((CONTRACT / "home-topics.json").read_text(encoding="utf-8"))
    [real, *_] = [t for t in public() if t["picks"]]
    assert set(raw) == {"topics"}
    for t in raw["topics"]:
        assert set(t) == set(real) and all(set(p) == set(real["picks"][0]) for p in t["picks"])


def test_resume_example_has_the_engine_shape():
    raw = json.loads((CONTRACT / "resume.json").read_text(encoding="utf-8"))["resume"]
    assert set(raw) == {"roleplay", "at", "progress", "said"} and set(raw["progress"]) == {"no", "total"}
    assert Roleplay.model_validate(raw["roleplay"]).model_dump(mode="json") == raw["roleplay"]
    assert raw["said"] and all(set(s) == {"idx", "heard", "n"} for s in raw["said"])
