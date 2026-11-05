"""ffmpeg conversions and a loudness gate. Arguments always go as a list, never through a shell."""
from __future__ import annotations

import asyncio
import math
import wave
from array import array
from pathlib import Path

SPEECH_MIN_SECONDS = 0.4
# 2026-11-05: whisper wrote "you" for 2s of silence and "Okay." for faint noise, so nothing quieter than
# this (loudest 50 ms window) goes to transcription. Tuned against the test recordings in Task 6.
SPEECH_MIN_DBFS = -35.0
# A pocket bump or the tap that ends recording is one loud window; speech is loud for a while. Require this much
# loud time in total (2026-11-05 final review).
SPEECH_MIN_LOUD_SECONDS = 0.2  # a short "Sure." stays in; real lines measured ~0.7 s loud each


class AudioError(Exception):
    pass


async def _ffmpeg(*args: str) -> None:
    proc = await asyncio.create_subprocess_exec(
        "ffmpeg", "-loglevel", "error", "-y", *args,
        stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
    if await proc.wait() != 0:
        raise AudioError("ffmpeg failed")


async def to_wav16k(src: Path, dst: Path) -> float:
    """Converts to 16 kHz mono 16-bit WAV for whisper. Returns the length in seconds."""
    await _ffmpeg("-i", str(src), "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le", str(dst))
    with wave.open(str(dst)) as w:
        return w.getnframes() / w.getframerate()


WINDOW = 0.05


def _window_dbfs(path: Path) -> tuple[list[float], float]:
    """Loudness (dBFS) of each 50 ms window, and the length in seconds."""
    with wave.open(str(path)) as w:
        rate, width, n = w.getframerate(), w.getsampwidth(), w.getnframes()
        if width != 2 or w.getnchannels() != 1:
            raise AudioError("expected 16-bit mono")
        samples = array("h", w.readframes(n))
    win = max(int(rate * WINDOW), 1)
    out = []
    for start in range(0, len(samples) - win + 1, win):
        chunk = samples[start:start + win]
        rms = math.sqrt(sum(x * x for x in chunk) / win) / 32768
        out.append(20 * math.log10(rms) if rms > 0 else -120.0)
    return out, n / rate


def _loudest_dbfs(path: Path) -> tuple[float, float]:
    windows, seconds = _window_dbfs(path)
    return (max(windows) if windows else -120.0), seconds


def _has_speech(wav: Path) -> bool:
    windows, seconds = _window_dbfs(wav)
    loud = sum(1 for d in windows if d >= SPEECH_MIN_DBFS) * WINDOW
    return seconds >= SPEECH_MIN_SECONDS and loud >= SPEECH_MIN_LOUD_SECONDS


async def has_speech(wav: Path) -> bool:
    return await asyncio.to_thread(_has_speech, wav)


async def with_rate(src: Path, rate: float, dst: Path) -> None:
    """Changes speed, keeps pitch (ffmpeg atempo)."""
    await _ffmpeg("-i", str(src), "-filter:a", f"atempo={rate}", "-c:a", "aac", "-b:a", "96k", str(dst))
