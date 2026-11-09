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
    assert set(raw) == {"roleplay", "at", "progress", "said", "ended"} and set(raw["progress"]) == {"no", "total"}
    assert Roleplay.model_validate(raw["roleplay"]).model_dump(mode="json") == raw["roleplay"]
    assert raw["said"] and all(set(s) == {"idx", "heard", "n"} for s in raw["said"])


def test_talk_example_matches_model():
    raw = json.loads((CONTRACT / "talk.json").read_text(encoding="utf-8"))
    assert Roleplay.model_validate(raw).model_dump(mode="json") == raw
    assert raw["kind"] == "talk"
    assert [l["kind"] for l in raw["lines"]] == ["reply", "ask", "help", "turn", "reply", "turn", "reply", "fix"]


def test_records_from_before_read_as_roleplays():
    raw = json.loads((CONTRACT / "roleplay.json").read_text(encoding="utf-8"))
    del raw["kind"]
    for l in raw["lines"]:
        for k in ("parts", "heard_upto", "fix", "hint"):
            del l[k]
    rp = Roleplay.model_validate(raw)
    assert rp.kind == "roleplay"
    assert all(l.parts is None and l.heard_upto is None and l.fix is None and l.hint is None for l in rp.lines)


def test_talk_events_example_has_the_engine_types():
    events = [json.loads(l) for l in (CONTRACT / "talk-events.ndjson").read_text(encoding="utf-8").splitlines() if l]
    assert {e["type"] for e in events} == {"heard", "text", "reply", "audio", "error", "done"}
    keys = {"heard": {"type", "text", "n", "idx", "korean"}, "reply": {"type", "idx", "kind", "parts"},
            "done": {"type", "idx"}}
    for e in events:
        if e["type"] in keys:
            assert set(e) == keys[e["type"]]
    assert next(e for e in events if e["type"] == "heard")["korean"] is False
    # inside a free talk Ryan speaks English only: its errors say a fixed English line (spec free-talk-design 3)
    from je_server.phrases import TALK_PHRASES

    error = next(e for e in events if e["type"] == "error")
    assert error["say"]["text"] == TALK_PHRASES[error["code"]]


def test_talk_end_example_has_the_engine_shape():
    raw = json.loads((CONTRACT / "talk-end.json").read_text(encoding="utf-8"))
    assert set(raw) == {"items", "say", "sohee"} and raw["say"] is None and raw["items"]
    assert isinstance(raw["sohee"], int) and raw["sohee"] >= 0  # Sohee chances used (spec free-talk-design 9)
    for item in raw["items"]:
        assert set(item) == {"line", "rec"}
        assert ScriptLine.model_validate(item["line"]).model_dump(mode="json") == item["line"]


def test_a_lines_given_is_in_its_json_only_when_set():
    # only my turns said from Sohee's full sentence have it (spec free-talk-design 9), so the examples' lines, and the
    # app's line keys, stay without it
    line = ScriptLine(idx=1, speaker="user", text="I want home.", kind="turn")
    assert "given" not in line.model_dump(mode="json") and '"given"' not in line.model_dump_json()
    helped = line.model_copy(update={"given": "I went home."})
    assert helped.model_dump(mode="json")["given"] == "I went home."
    assert ScriptLine.model_validate_json(helped.model_dump_json()) == helped


def test_a_lines_dropped_is_in_its_json_only_when_set():
    # only a turn said again and Ryan's reply to it have it (spec talk-resay 3), so the examples' lines stay without it
    line = ScriptLine(idx=1, speaker="user", text="I want home.", kind="turn")
    assert "dropped" not in line.model_dump(mode="json") and '"dropped"' not in line.model_dump_json()
    gone = line.model_copy(update={"dropped": True})
    assert gone.model_dump(mode="json")["dropped"] is True
    assert ScriptLine.model_validate_json(gone.model_dump_json()) == gone
