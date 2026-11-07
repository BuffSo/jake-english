"""Transcription with whisper.cpp's whisper-server, kept running on 127.0.0.1.

Each request names its language: turn recordings are English first (no script hint, spec 「평가」), then
auto-detected when they do not follow the line, so Korean is heard too (spec offscript-aside 2); when that second
one fails, the English one stands. Situation input is auto-detected. Transcripts are never logged.
"""
from __future__ import annotations

import asyncio
import re
from pathlib import Path
from typing import Literal

import httpx

from . import audio

BRACKETS = re.compile(r"\[[^\]]*\]|\([^)]*\)")


class WhisperError(Exception):
    """whisper-server did not answer: down, an HTTP error, or a body that is not JSON."""


def _clean(text: str) -> str:
    return " ".join(BRACKETS.sub(" ", text).split())


class Whisper:
    def __init__(self, exe: str, model: str, port: int):
        self.exe, self.model, self.port = exe, model, port
        self.proc: asyncio.subprocess.Process | None = None
        self.client = httpx.AsyncClient(base_url=f"http://127.0.0.1:{port}", timeout=60)

    async def start(self) -> None:
        self.proc = await asyncio.create_subprocess_exec(
            self.exe, "-m", self.model, "--host", "127.0.0.1", "--port", str(self.port), "-nt",
            stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
        for _ in range(240):
            if self.proc.returncode is not None:
                raise RuntimeError("whisper-server exited")
            try:
                if (await self.client.get("/")).status_code == 200:
                    return
            except httpx.TransportError:
                pass
            await asyncio.sleep(0.25)
        raise RuntimeError("whisper-server did not start")

    async def hear(self, sound: Path, lang: Literal["en", "ko"]) -> str:
        """Transcribes a sound the voice just made (its end check). The WAV for whisper is deleted after."""
        wav = sound.with_name(f"{sound.stem}-hear.wav")
        try:
            await audio.to_wav16k(sound, wav)
            return await self.transcribe(wav, lang)
        finally:
            wav.unlink(missing_ok=True)

    async def transcribe(self, wav: Path, lang: Literal["en", "ko", "auto"]) -> str:
        return _clean((await self._infer(wav, lang, "json")).get("text", ""))

    async def transcribe_auto(self, wav: Path) -> tuple[str, str]:
        """The text and the language whisper detected ("korean", "english"; "" when it does not say). Forced to
        English, whisper translates Korean speech or leaves it in Hangul (2026-11-07)."""
        j = await self._infer(wav, "auto", "verbose_json")
        return _clean(j.get("text", "")), str(j.get("language") or "").lower()

    async def _infer(self, wav: Path, lang: str, fmt: str) -> dict:
        try:
            r = await self.client.post(
                "/inference",
                files={"file": ("audio.wav", wav.read_bytes(), "audio/wav")},
                data={"language": lang, "response_format": fmt},
            )
            r.raise_for_status()
            return r.json()
        except (httpx.HTTPError, ValueError) as e:  # ValueError: a body that is not JSON
            raise WhisperError(type(e).__name__) from e

    async def stop(self) -> None:
        if self.proc and self.proc.returncode is None:
            self.proc.terminate()
            await self.proc.wait()
        await self.client.aclose()
