"""Transcription with whisper.cpp's whisper-server, kept running on 127.0.0.1.

Each request names its language: turn recordings are English (no script hint, spec 「평가」),
situation input is auto-detected. Transcripts are never logged.
"""
from __future__ import annotations

import asyncio
import re
from pathlib import Path
from typing import Literal

import httpx

BRACKETS = re.compile(r"\[[^\]]*\]|\([^)]*\)")


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

    async def transcribe(self, wav: Path, lang: Literal["en", "auto"]) -> str:
        r = await self.client.post(
            "/inference",
            files={"file": ("audio.wav", wav.read_bytes(), "audio/wav")},
            data={"language": lang, "response_format": "json"},
        )
        r.raise_for_status()
        text = BRACKETS.sub(" ", r.json().get("text", ""))
        return " ".join(text.split())

    async def stop(self) -> None:
        if self.proc and self.proc.returncode is None:
            self.proc.terminate()
            await self.proc.wait()
        await self.client.aclose()
