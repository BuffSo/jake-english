"""scripts/measure_stress.py: the hand-run measuring (spec stress-log). MFA and the Praat feature script are faked
here; tests/test_stress_features.py and the end-to-end run in the plan cover the real ones. Sentences are made up."""
from __future__ import annotations

import hashlib
import importlib.util
import os
import json
import sys
from pathlib import Path

import pytest

from audiotools import make_m4a
from je_server.models import Attempt, Frame, Roleplay, ScriptLine
from je_server.store import Store

_spec = importlib.util.spec_from_file_location(
    "measure_stress", Path(__file__).resolve().parent.parent / "scripts" / "measure_stress.py")
mod = importlib.util.module_from_spec(_spec)
sys.modules["measure_stress"] = mod
_spec.loader.exec_module(mod)

RP = "0a1b2c3d4e5f"
ENV = Path("/nowhere/mfa")


def attempt(n: int, heard: str) -> Attempt:
    return Attempt(n=n, mode="turn", heard=heard, followed=True, issues=[], say_ko="", audio=[], timings={})


@pytest.fixture
def data(tmp_path):
    """Two English tries to measure (lines 1 and 3) and a Korean one, with tone recordings."""
    root = tmp_path / "data"
    store = Store(root)
    store.save(Roleplay(id=RP, created="2026-11-08T08:00:00", situation="s",
                        frame=Frame(title_ko="t", user_role_ko="u", ryan_role_ko="r", place_ko="p", goal_ko="g"),
                        lines=[ScriptLine(idx=i, speaker="user", text="x") for i in range(4)],
                        attempts={1: [attempt(1, "I'd like 2 coffees.")], 2: [attempt(1, "커피요")],
                                  3: [attempt(1, "See you soon.")]}))
    tone = make_m4a(tmp_path, "sine=f=220:r=44100", 1).read_bytes()
    for idx in (1, 2, 3):
        store.rec_path(RP, idx, 1).write_bytes(tone)
    return root


ALIGNED = {"words": [{"w": "i'd", "start": 0.0, "end": 0.2, "phones": ["AY1", "D"],
                      "syl": [{"p": "AY1", "start": 0.0, "end": 0.15, "dur": 0.15, "db": 66, "st": 4, "st_med": 4}]}],
           "quality": {"speech_log_likelihood": -50.0, "phone_duration_deviation": 1.2}}


class Fake:
    """MFA and the feature script, faked: align reads the .lab files; features answers for line 1 only."""

    def __init__(self):
        self.labs: dict[str, str] = {}
        self.wavs: list[str] = []
        self.aligned = 0

    def align(self, mfa_env, corpus, out, work):
        self.aligned += 1
        for lab in sorted(corpus.rglob("*.lab")):
            self.labs[lab.stem] = lab.read_text()
        self.wavs += sorted(w.stem for w in corpus.rglob("*.wav"))
        out.mkdir(parents=True)

    def features(self, mfa_env, corpus, out, dest):
        return {"praat": "6.1.38", "files": {f"{RP}_1_1": ALIGNED}}


def run(data, fake=None, **kw):
    fake = fake or Fake()
    return mod.run(data, ENV, now=kw.pop("now", True), align=kw.pop("align", fake.align),
                   features=kw.pop("features", fake.features), version=lambda env: "3.4.3", **kw)


def tmp_left(data):
    return list((data / "tmp").glob("stress-*"))


def test_run_writes_one_record_per_try_and_cleans_tmp(data):
    counts = run(data)
    assert counts == {"measured": 1, "unaligned": 1, "korean_or_empty": 1, "failed": 0, "busy": False}
    assert sorted(p.name for p in (data / "stress" / RP).iterdir()) == ["1-1.json", "3-1.json"]
    rec = json.loads((data / "stress" / RP / "1-1.json").read_text())
    assert rec["status"] == "ok" and rec["tools"] == {"mfa": "3.4.3", "model": "english_us_arpa", "praat": "6.1.38"}
    assert json.loads((data / "stress" / RP / "3-1.json").read_text())["status"] == "unaligned"
    assert not tmp_left(data)


def test_the_lab_holds_the_normalised_heard_words(data):
    fake = Fake()
    run(data, fake)
    assert fake.labs == {f"{RP}_1_1": "i'd like two coffees", f"{RP}_3_1": "see you soon"}
    assert fake.wavs == [f"{RP}_1_1", f"{RP}_3_1"]


def test_a_second_run_measures_nothing(data):
    run(data)
    fake = Fake()
    assert run(data, fake) == {"measured": 0, "unaligned": 0, "korean_or_empty": 1, "failed": 0, "busy": False}
    assert fake.aligned == 0


def test_a_failing_align_leaves_no_records_and_no_tmp(data):
    def boom(*a):
        raise RuntimeError("mfa align failed")

    counts = run(data, align=boom)
    assert counts["failed"] == 2 and counts["measured"] == 0
    assert not (data / "stress").exists() and not tmp_left(data)


def test_a_recording_ffmpeg_cannot_read_is_counted_failed(data):
    Store(data).rec_path(RP, 3, 1).write_bytes(b"not a sound")
    fake = Fake()
    counts = run(data, fake)
    assert (counts["measured"], counts["unaligned"], counts["failed"]) == (1, 0, 1)
    assert fake.wavs == [f"{RP}_1_1"]  # no half-made WAV left for MFA
    assert sorted(p.name for p in (data / "stress" / RP).iterdir()) == ["1-1.json"]


def test_records_are_split_into_chunks(data):
    fake = Fake()
    fake.align = lambda env, corpus, out, work: (fake.labs.update({p.stem: "" for p in corpus.rglob("*.lab")}),
                                                 out.mkdir(parents=True))
    run(data, fake, chunk=1)
    assert len(fake.labs) == 2 and not tmp_left(data)


def tree_hashes(root: Path) -> dict[str, str]:
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob("*")) if p.is_file()}


def test_records_and_recordings_are_unchanged(data):
    before = tree_hashes(data / "roleplays")
    run(data)
    assert tree_hashes(data / "roleplays") == before


def test_busy_stops_unless_now(data):
    assert run(data, now=False)["busy"] is True
    assert not (data / "stress").exists()


def test_main_needs_the_mfa_env(monkeypatch, capsys, data):
    monkeypatch.setattr(mod, "env", lambda: {"JE_DATA_DIR": str(data)})
    assert mod.main([]) == 1
    assert "JE_MFA_ENV" in capsys.readouterr().out


def test_main_prints_counts_only(monkeypatch, capsys, data, tmp_path):
    (tmp_path / "mfa" / "bin").mkdir(parents=True)
    (tmp_path / "mfa" / "bin" / "mfa").write_text("")
    monkeypatch.setattr(mod, "env", lambda: {"JE_DATA_DIR": str(data), "JE_MFA_ENV": str(tmp_path / "mfa")})
    fake = Fake()
    monkeypatch.setattr(mod, "mfa_align", fake.align)
    monkeypatch.setattr(mod, "praat_features", fake.features)
    monkeypatch.setattr(mod, "mfa_version", lambda env: "3.4.3")
    assert mod.main(["--now"]) == 0
    out = capsys.readouterr().out
    assert "measured 1" in out and "coffee" not in out and str(data) not in out


def test_a_wav_the_wave_module_rejects_is_counted_failed(data, monkeypatch):
    """ffmpeg can exit 0 and still leave a WAV that `wave` rejects; that recording fails, the run goes on (PR #61
    review, as engine.py's comment on reading the WAV says)."""
    import wave

    real = mod.audio.to_wav16k

    async def picky(src, dst):
        if src.name == "3-1.m4a":
            dst.write_bytes(b"RIFF")
            raise wave.Error("file does not start with RIFF id")
        return await real(src, dst)

    monkeypatch.setattr(mod.audio, "to_wav16k", picky)
    fake = Fake()
    counts = run(data, fake)
    assert (counts["measured"], counts["failed"]) == (1, 1) and fake.wavs == [f"{RP}_1_1"]
    assert not tmp_left(data)


def dead_pid() -> int:
    import subprocess

    p = subprocess.Popen(["true"])
    p.wait()
    return p.pid


def test_copies_left_by_a_killed_run_are_removed_next_time(data):
    """A run killed with SIGKILL or a power cut never reaches its finally (PR #61 review): the next run removes the
    folders of runs that are no longer alive, even when it then stops because the app is in use."""
    left = data / "tmp" / f"stress-{dead_pid()}-0" / "corpus" / "learner"
    left.mkdir(parents=True)
    (left / "x.wav").write_bytes(b"voice")
    assert run(data, now=False)["busy"] is True
    assert not left.parent.parent.exists()


def test_the_folder_of_a_run_still_going_is_left_alone(data):
    alive = data / "tmp" / f"stress-{os.getppid()}-0"
    alive.mkdir(parents=True)
    run(data)
    assert alive.exists()


def test_hangup_and_term_unwind_so_the_copies_are_deleted():
    """Closing the terminal (SIGHUP) or `kill` (SIGTERM) raise SystemExit, so each chunk's finally deletes its work."""
    import signal
    import time

    old = {s: signal.getsignal(s) for s in (signal.SIGHUP, signal.SIGTERM)}
    try:
        mod.exit_on_signals()
        for s in old:
            with pytest.raises(SystemExit):
                os.kill(os.getpid(), s)
                time.sleep(1)
    finally:
        for s, handler in old.items():
            signal.signal(s, handler)
