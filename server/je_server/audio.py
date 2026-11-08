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


# The play copy of a recording (spec play-button-feedback 4): from just before the first speech to just after the
# last, so a replay is not silence first. Gentler than SPEECH_MIN_DBFS: on 19 recordings (2026-11-08) -35 dBFS started
# two of them 0.75-1.1 s late, cutting a soft first word; at -45 dBFS they matched the rest within 0.1 s.
PLAY_MIN_DBFS = -45.0
PLAY_LEAD = 0.2  # kept before the first speech
PLAY_TAIL = 0.4  # kept after the last; a recording ended by an 8 s pause would otherwise keep its 8 s


def speech_span(wav: Path) -> tuple[float, float] | None:
    """Start of the first and end of the last 50 ms window at or over PLAY_MIN_DBFS, in seconds; None if none."""
    windows, _ = _window_dbfs(wav)
    loud = [i for i, d in enumerate(windows) if d >= PLAY_MIN_DBFS]
    if not loud:
        return None
    return loud[0] * WINDOW, (loud[-1] + 1) * WINDOW


async def play_cut(src: Path, span: tuple[float, float] | None, seconds: float, dst: Path) -> None:
    """Copies `src` to `dst` cut to `span` with its lead and tail, without re-encoding, moov first so the phone can
    start playing before it has the whole file. No span keeps it whole."""
    args = ["-i", str(src), "-c", "copy", "-movflags", "+faststart", str(dst)]
    if span is not None:
        start, end = max(0.0, span[0] - PLAY_LEAD), min(seconds, span[1] + PLAY_TAIL)
        args = ["-ss", f"{start:.3f}", "-to", f"{end:.3f}", *args]
    await _ffmpeg(*args)


async def with_rate(src: Path, rate: float, dst: Path) -> None:
    """Changes speed, keeps pitch (ffmpeg atempo)."""
    await _ffmpeg("-i", str(src), "-filter:a", f"atempo={rate}", "-c:a", "aac", "-b:a", "96k", str(dst))
