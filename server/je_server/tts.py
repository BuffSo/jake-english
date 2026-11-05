"""Ryan and Jake voices through a worker process on the Mac's existing TTS setup (ADR-0009).

One worker, one queue: urgent jobs (Ryan's live feedback) go before prepared ones (model audio for
later lines). Sounds are cached by sha256(voice|lang|text), so the same line is made once.
"""
from __future__ import annotations

import asyncio
import hashlib
import itertools
import json
import os
from pathlib import Path
from typing import Literal

from .audio import with_rate

WORKER = Path(__file__).with_name("tts_worker.py")
RATES = (0.6, 0.8, 1.0)
# Speaking rate baked into each sound, kept in pitch. Ryan's Korean (greeting, feedback) at 1x sounded drawn
# out on the phone (2026-11-05); the reply reader plays Korean at 1.3x since the user found 1x too slow
# (2026-11-03). English model lines stay at 1x: they are what the learner copies.
SPEAK_RATE = {"korean": 1.3, "english": 1.0}


class VoiceError(Exception):
    pass


def audio_key(voice: str, lang: str, text: str) -> str:
    return hashlib.sha256(f"{voice}|{lang}|{SPEAK_RATE[lang]}|{text}".encode()).hexdigest()


class Voice:
    def __init__(self, python: str, module: str, audio_dir: Path, worker: Path = WORKER):
        self.python, self.module, self.worker = python, module, worker
        self.audio_dir = audio_dir
        self.tmp_dir = audio_dir / ".tmp"
        self.proc: asyncio.subprocess.Process | None = None
        self.queue: asyncio.PriorityQueue = asyncio.PriorityQueue()
        self.inflight: dict[str, asyncio.Future] = {}
        self.seq = itertools.count()
        self.ids = itertools.count(1)
        self.consumer: asyncio.Task | None = None

    def path(self, key: str) -> Path:
        return self.audio_dir / f"{key}.m4a"

    async def start(self) -> None:
        self.audio_dir.mkdir(parents=True, exist_ok=True)
        self.tmp_dir.mkdir(exist_ok=True)
        await self._spawn()
        self.consumer = asyncio.create_task(self._consume())

    async def _spawn(self) -> None:
        self.proc = await asyncio.create_subprocess_exec(
            self.python, "-I", str(self.worker), self.module,
            stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL,
            limit=1 << 20)
        line = await asyncio.wait_for(self.proc.stdout.readline(), timeout=300)
        if not line or not json.loads(line).get("ready"):
            raise VoiceError("voice worker did not start")

    async def say(self, text: str, voice: Literal["ryan", "jake"], lang: Literal["english", "korean"],
                  urgent: bool, rank: int = 0) -> str:
        """rank orders prepared jobs (the line number), so the next line's sound is not stuck behind later lines."""
        key = audio_key(voice, lang, text)
        if self.path(key).exists():
            return key
        fut = self.inflight.get(key)
        if fut is None:
            fut = asyncio.get_running_loop().create_future()
            self.inflight[key] = fut
        # an urgent ask for a queued prepared job queues it again in front; the consumer skips duplicates
        self.queue.put_nowait((0 if urgent else 1, 0 if urgent else rank, next(self.seq), key, text, voice, lang))
        await asyncio.shield(fut)
        return key

    async def _consume(self) -> None:
        while True:
            _, _, _, key, text, voice, lang = await self.queue.get()
            fut = self.inflight.get(key)
            if fut is None or fut.done():
                continue
            try:
                await self._make(key, text, voice, lang)
                fut.set_result(key)
            except Exception as e:  # noqa: BLE001 - every failure reaches the waiting caller
                fut.set_exception(e if isinstance(e, VoiceError) else VoiceError(type(e).__name__))
            finally:
                self.inflight.pop(key, None)

    async def _make(self, key: str, text: str, voice: str, lang: str) -> None:
        if self.proc is None or self.proc.returncode is not None:
            await self._spawn()
        tmp = self.tmp_dir / f"{key}.m4a"
        req = {"id": next(self.ids), "text": text, "voice": voice, "lang": lang, "rate": SPEAK_RATE[lang],
               "out": str(tmp)}
        self.proc.stdin.write((json.dumps(req, ensure_ascii=False) + "\n").encode())
        await self.proc.stdin.drain()
        line = await self.proc.stdout.readline()
        if not line:
            await self.proc.wait()
            self.proc = None
            raise VoiceError("voice worker died")
        resp = json.loads(line)
        if not resp.get("ok"):
            raise VoiceError(resp.get("error", "voice worker failed"))
        os.replace(tmp, self.path(key))

    async def rate_file(self, key: str, rate: float) -> Path:
        if rate not in RATES:
            raise ValueError("rate")
        if rate == 1.0:
            return self.path(key)
        out = self.audio_dir / f"{key}@{rate}.m4a"
        if not out.exists():
            tmp = self.tmp_dir / out.name
            await with_rate(self.path(key), rate, tmp)
            os.replace(tmp, out)
        return out

    async def stop(self) -> None:
        if self.consumer:
            self.consumer.cancel()
        if self.proc and self.proc.returncode is None:
            self.proc.stdin.close()
            try:
                await asyncio.wait_for(self.proc.wait(), timeout=5)
            except asyncio.TimeoutError:
                self.proc.kill()
