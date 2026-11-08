"""scripts/stress_features.py: vowel values from an MFA TextGrid and its WAV, run in the MFA environment's Python.

Needs that environment (it has parselmouth and praatio, the server's does not): set JE_MFA_ENV to its folder, or the
tests are skipped. The sound is a made-up tone, not a recording.
"""
from __future__ import annotations

import json
import math
import os
import struct
import subprocess
import wave
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "stress_features.py"
ENV = os.environ.get("JE_MFA_ENV", "")
pytestmark = pytest.mark.skipif(not ENV, reason="JE_MFA_ENV (the MFA environment) is not set")

TEXTGRID = """File type = "ooTextFile"
Object class = "TextGrid"

xmin = 0
xmax = 1
tiers? <exists>
size = 2
item []:
    item [1]:
        class = "IntervalTier"
        name = "words"
        xmin = 0
        xmax = 1
        intervals: size = 3
        intervals [1]:
            xmin = 0
            xmax = 0.2
            text = ""
        intervals [2]:
            xmin = 0.2
            xmax = 0.6
            text = "ah"
        intervals [3]:
            xmin = 0.6
            xmax = 1
            text = ""
    item [2]:
        class = "IntervalTier"
        name = "phones"
        xmin = 0
        xmax = 1
        intervals: size = 3
        intervals [1]:
            xmin = 0
            xmax = 0.2
            text = ""
        intervals [2]:
            xmin = 0.2
            xmax = 0.6
            text = "AA1"
        intervals [3]:
            xmin = 0.6
            xmax = 1
            text = ""
"""


def tone(path: Path, hz: float = 200.0, seconds: float = 1.0, rate: int = 16000) -> None:
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"".join(struct.pack("<h", int(12000 * math.sin(2 * math.pi * hz * i / rate)))
                               for i in range(int(seconds * rate))))


def run_features(tmp: Path, csv: str | None = None) -> dict:
    corpus, out = tmp / "corpus" / "learner", tmp / "out" / "learner"
    corpus.mkdir(parents=True, exist_ok=True)
    out.mkdir(parents=True, exist_ok=True)
    tone(corpus / "tone.wav")
    (out / "tone.TextGrid").write_text(TEXTGRID)
    if csv is not None:
        (tmp / "out" / "alignment_analysis.csv").write_text(csv)
    dest = tmp / "features.json"
    subprocess.run([str(Path(ENV) / "bin" / "python"), "-I", str(SCRIPT), str(tmp / "corpus"), str(tmp / "out"),
                    str(dest)], check=True, capture_output=True)
    return json.loads(dest.read_text())


def test_features_of_a_200_hz_tone(tmp_path):
    out = run_features(tmp_path)
    assert out["praat"]
    word = out["files"]["tone"]["words"][0]
    assert (word["w"], word["start"], word["end"], word["phones"]) == ("ah", 0.2, 0.6, ["AA1"])
    syl = word["syl"][0]
    assert syl["p"] == "AA1" and syl["dur"] == pytest.approx(0.4, abs=0.001)
    assert syl["st"] == pytest.approx(12.0, abs=0.2) and syl["st_med"] == pytest.approx(12.0, abs=0.2)
    assert syl["db"] > 40
    assert out["files"]["tone"]["quality"] == {"speech_log_likelihood": None, "phone_duration_deviation": None}


def test_quality_comes_from_the_alignment_analysis(tmp_path):
    csv = ("file,begin,end,speaker,overall_log_likelihood,speech_log_likelihood,phone_duration_deviation\n"
           "tone,0.0,1.0,learner,-55.5,-50.25,1.5\n")
    assert run_features(tmp_path, csv)["files"]["tone"]["quality"] == {
        "speech_log_likelihood": -50.25, "phone_duration_deviation": 1.5}


def test_a_wav_without_a_textgrid_is_left_out(tmp_path):
    (tmp_path / "corpus" / "learner").mkdir(parents=True)
    tone(tmp_path / "corpus" / "learner" / "lost.wav")
    out = run_features(tmp_path)
    assert list(out["files"]) == ["tone"]
