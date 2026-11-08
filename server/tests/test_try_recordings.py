"""scripts/try_recordings.py: recordings sent the way the app sends them, on a copy deleted after (todo 2026-11-08)."""
import dataclasses
import importlib.util
import json
import sys
from pathlib import Path

import pytest

from je_server import topics

_spec = importlib.util.spec_from_file_location(
    "try_recordings", Path(__file__).resolve().parent.parent / "scripts" / "try_recordings.py")
tr = importlib.util.module_from_spec(_spec)
sys.modules["try_recordings"] = tr  # dataclasses look the module up while the script loads
_spec.loader.exec_module(tr)


class ClientHttp:
    """The script's two HTTP calls, through the test client instead of the network."""

    def __init__(self, client):
        self.c = client

    def json(self, method, path):
        r = self.c.request(method, path)
        r.raise_for_status()
        return r.json()

    def lines(self, path, body):
        r = self.c.post(path, content=body, headers={"Content-Type": "audio/mp4"})
        r.raise_for_status()
        return [json.loads(l) for l in r.text.splitlines() if l.strip()]


@pytest.fixture
def roleplay(client):
    rp = client.post("/roleplays", json={"situation": "길 묻기"}).json()
    client.get(f"/roleplays/{rp['id']}/lines/1")  # line 1 is the learner's
    return rp


def recording(tmp_path, data: bytes, name: str = "a.m4a") -> Path:
    path = tmp_path / name
    path.write_bytes(data)
    return path


def test_tries_go_to_a_copy_that_is_deleted(client, settings, roleplay, speech_bytes, tmp_path):
    tries = tr.run(ClientHttp(client), settings.data_dir, roleplay["id"], 1,
                   [recording(tmp_path, speech_bytes, "a.m4a"), recording(tmp_path, speech_bytes, "b.m4a")], "turn",
                   out=lambda *_: None)
    assert [t.file for t in tries] == ["a.m4a", "b.m4a"]
    t = tries[0]
    assert (t.heard, t.followed, t.error) == ("It's right over there.", True, None)
    assert "다음 대사로" in t.said and t.done == {"next": 2, "issues": 0} and t.audio > 0
    assert t.timings["total"] > 0
    # the copy is gone with its recordings; the learner's own record has no test tries
    assert [d.name for d in (settings.data_dir / "roleplays").iterdir()] == [roleplay["id"]]
    assert client.get(f"/roleplays/{roleplay['id']}").json()["attempts"] == {}


def test_keep_leaves_the_copy(client, settings, roleplay, speech_bytes, tmp_path):
    lines = []
    tr.run(ClientHttp(client), settings.data_dir, roleplay["id"], 1, [recording(tmp_path, speech_bytes)], "turn",
           keep=True, out=lines.append)
    [copy] = [d for d in (settings.data_dir / "roleplays").iterdir() if d.name != roleplay["id"]]
    assert (copy / "rec" / "1-1.m4a").exists()
    assert any(copy.name in l for l in lines)  # the kept copy's id is printed, so it can be deleted by hand


def test_an_error_event_is_reported(client, settings, roleplay, silent_bytes, tmp_path):
    [t] = tr.run(ClientHttp(client), settings.data_dir, roleplay["id"], 1, [recording(tmp_path, silent_bytes)], "turn",
                 out=lambda *_: None)
    assert t.error == "no_speech" and t.said == "" and t.done is None
    assert [d.name for d in (settings.data_dir / "roleplays").iterdir()] == [roleplay["id"]]


def test_a_line_not_for_the_mode_stops_and_leaves_no_copy(client, settings, roleplay, speech_bytes, tmp_path):
    with pytest.raises(tr.Stop, match="Ryan's line"):  # line 0 is Ryan's; a turn is said against the learner's
        tr.run(ClientHttp(client), settings.data_dir, roleplay["id"], 0, [recording(tmp_path, speech_bytes)], "turn")
    with pytest.raises(tr.Stop, match="no line 9"):
        tr.run(ClientHttp(client), settings.data_dir, roleplay["id"], 9, [recording(tmp_path, speech_bytes)], "turn")
    assert [d.name for d in (settings.data_dir / "roleplays").iterdir()] == [roleplay["id"]]


def test_remove_copy_deletes_only_the_copy_it_made(client, settings, roleplay):
    root = settings.data_dir / "roleplays"
    with pytest.raises(tr.Stop):
        tr.remove_copy(settings.data_dir, "../roleplays", roleplay["id"])
    with pytest.raises(tr.Stop):  # the learner's own roleplay is not a copy
        tr.remove_copy(settings.data_dir, roleplay["id"], roleplay["id"])
    other = client.post("/roleplays", json={"situation": "카페 주문"}).json()
    copy_of_other = client.post(f"/roleplays/{other['id']}/copy").json()
    with pytest.raises(tr.Stop):  # a copy, but of another roleplay
        tr.remove_copy(settings.data_dir, copy_of_other["id"], roleplay["id"])
    assert {d.name for d in root.iterdir()} == {roleplay["id"], other["id"], copy_of_other["id"]}
    tr.remove_copy(settings.data_dir, copy_of_other["id"], other["id"])
    assert {d.name for d in root.iterdir()} == {roleplay["id"], other["id"]}


SNEAKER = ("usa", "u-sneaker-size")  # the learner speaks first
CHANGED = "Could I try these on in a bigger size?"  # made up


def change_script(monkeypatch, speaker="user"):
    """The list's script edited after the learner's run: its first line differs (spec fixed-list-scripts 4)."""
    old = topics.pick(*SNEAKER)
    new = dataclasses.replace(old, script=((speaker, CHANGED),) + old.script[1:])
    monkeypatch.setattr(topics, "pick", lambda t, i: new)


@pytest.fixture
def pick_run(client):
    return client.post("/roleplays", json={"topic": SNEAKER[0], "pick": SNEAKER[1]}).json()


def test_the_copy_line_is_checked_and_printed(client, settings, pick_run, speech_bytes, tmp_path, monkeypatch):
    # todo 25: a list pick's copy plays the script as it is now; the line printed was the old run's
    change_script(monkeypatch)
    lines = []
    tr.run(ClientHttp(client), settings.data_dir, pick_run["id"], 0, [recording(tmp_path, speech_bytes)], "turn",
           out=lines.append)
    assert lines[0] == f"line 0: {CHANGED}"
    assert [d.name for d in (settings.data_dir / "roleplays").iterdir()] == [pick_run["id"]]


def test_a_copy_line_not_for_the_mode_stops_and_the_copy_is_deleted(client, settings, pick_run, speech_bytes, tmp_path,
                                                                    monkeypatch):
    change_script(monkeypatch, speaker="ryan")  # the old run's line 0 is the learner's, the copy's is Ryan's
    for keep in (False, True):  # nothing was sent to it, so it goes even with --keep
        with pytest.raises(tr.Stop, match="Ryan's line"):
            tr.run(ClientHttp(client), settings.data_dir, pick_run["id"], 0, [recording(tmp_path, speech_bytes)],
                   "turn", keep=keep, out=lambda *_: None)
        assert [d.name for d in (settings.data_dir / "roleplays").iterdir()] == [pick_run["id"]]


def test_list_shows_the_lines_a_copy_gets(client, settings, pick_run, monkeypatch, capsys):
    change_script(monkeypatch)
    tr.list_roleplays(settings.data_dir)
    out = capsys.readouterr().out
    assert CHANGED in out and "(list: current script)" in out
