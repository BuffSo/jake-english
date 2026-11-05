"""Make test sounds with ffmpeg in a temp folder (never committed)."""
from __future__ import annotations

import subprocess
from pathlib import Path


def lavfi(tmp: Path, src: str, seconds: float, name: str) -> Path:
    out = tmp / name
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", src, "-t", str(seconds), str(out)],
                   check=True)
    return out


def make_wav(tmp: Path, src: str, seconds: float) -> Path:
    return lavfi(tmp, src, seconds, f"t{abs(hash((src, seconds)))}.wav")


def make_m4a(tmp: Path, src: str, seconds: float) -> Path:
    return lavfi(tmp, src, seconds, f"t{abs(hash((src, seconds)))}.m4a")


def duration(path: Path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                         check=True, capture_output=True, text=True).stdout
    return float(out.strip())
