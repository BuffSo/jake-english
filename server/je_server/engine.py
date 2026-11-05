"""Roleplay flow: create a script, prepare lines in the background, answer the app's requests."""
from __future__ import annotations

import asyncio
import contextlib
import logging
from datetime import datetime
from pathlib import Path

from . import audio
from .models import Roleplay, Said, ScriptLine, ThreeLine
from .phrases import PHRASES
from .store import Store
from .tts import audio_key

log = logging.getLogger("je_server")
LINE_WAIT = 120
MAX_SECONDS = 60


class NotFound(Exception):
    pass


class TooLong(Exception):
    pass


class Engine:
    def __init__(self, store: Store, claude, voice, whisper):
        self.store, self.claude, self.voice, self.whisper = store, claude, voice, whisper
        self.tasks: dict[tuple[str, int], asyncio.Task] = {}
        self.locks: dict[str, asyncio.Lock] = {}
        self.sem = asyncio.Semaphore(3)

    # --- fixed phrases ------------------------------------------------------------------------

    def said(self, name: str) -> Said:
        text = PHRASES[name]
        return Said(text=text, audio=audio_key("ryan", "korean", text))

    async def warm(self) -> None:
        for text in PHRASES.values():
            await self.voice.say(text, "ryan", "korean", urgent=False)

    # --- helpers ------------------------------------------------------------------------------

    def lock(self, rp_id: str) -> asyncio.Lock:
        return self.locks.setdefault(rp_id, asyncio.Lock())

    def load(self, rp_id: str) -> Roleplay:
        try:
            return self.store.load(rp_id)
        except KeyError:
            raise NotFound(rp_id) from None

    def get_line(self, rp_id: str, idx: int) -> tuple[Roleplay, ScriptLine]:
        rp = self.load(rp_id)
        if not 0 <= idx < len(rp.lines):
            raise NotFound(f"{rp_id}/{idx}")
        return rp, rp.lines[idx]

    @staticmethod
    def context(rp: Roleplay, idx: int) -> str:
        near = [f"{l.speaker}: {l.text}" for l in rp.lines[max(idx - 1, 0): idx + 2] if l.idx != idx]
        return f"장소: {rp.frame.place_ko}. " + " / ".join(near)

    async def update_line(self, rp_id: str, idx: int, text: str, **changes) -> None:
        async with self.lock(rp_id):
            rp = self.store.load(rp_id)
            if idx < len(rp.lines) and rp.lines[idx].text == text:  # the line was not replaced meanwhile
                rp.lines[idx] = rp.lines[idx].model_copy(update=changes)
                self.store.save(rp)

    # --- create and prepare -------------------------------------------------------------------

    async def create(self, situation: str) -> Roleplay:
        frame, draft = await self.claude.make_script(situation)
        rp = Roleplay(id=self.store.new_id(), created=datetime.now().isoformat(timespec="seconds"),
                      situation=situation, frame=frame,
                      lines=[ScriptLine(idx=i, speaker=s, text=t) for i, (s, t) in enumerate(draft)])
        self.store.save(rp)
        for line in rp.lines:
            self.schedule(rp.id, line.idx)
        return rp

    def schedule(self, rp_id: str, idx: int) -> asyncio.Task:
        key = (rp_id, idx)
        task = self.tasks.get(key)
        if task is None or (task.done() and (task.cancelled() or task.exception() is not None)):
            task = asyncio.create_task(self._prepare(rp_id, idx))
            task.add_done_callback(_quiet)
            self.tasks[key] = task
        return task

    @staticmethod
    def ready(line: ScriptLine) -> bool:
        return line.audio is not None and (line.speaker == "ryan" or line.three is not None)

    async def _prepare(self, rp_id: str, idx: int) -> None:
        rp, line = self.get_line(rp_id, idx)
        three, key = line.three, line.audio
        if line.speaker == "user" and three is None:
            async with self.sem:
                three = await self.claude.annotate(line.text, self.context(rp, idx))
            await self.update_line(rp_id, idx, line.text, three=three)
        if key is None:
            key = await self.voice.say(line.text, "ryan", "english", urgent=False)
            await self.update_line(rp_id, idx, line.text, audio=key)

    async def line(self, rp_id: str, idx: int) -> ScriptLine:
        _, line = self.get_line(rp_id, idx)
        if self.ready(line):
            return line
        await asyncio.wait_for(asyncio.shield(self.schedule(rp_id, idx)), LINE_WAIT)
        return self.get_line(rp_id, idx)[1]

    async def three(self, rp_id: str, idx: int) -> ThreeLine:
        rp, line = self.get_line(rp_id, idx)
        if line.three is not None:
            return line.three
        three = await self.claude.annotate(line.text, self.context(rp, idx))
        await self.update_line(rp_id, idx, line.text, three=three)
        return three

    # --- situation input ----------------------------------------------------------------------

    async def recommend(self) -> Said:
        text = await self.claude.recommend(self.store.recent_situations())
        return Said(text=text, audio=await self.voice.say(text, "jake", "korean", urgent=True))

    async def transcribe(self, body: bytes) -> str:
        """Situation input by voice: Korean or English, auto-detected. The recording is deleted after."""
        src = Path(self.store.tmp_dir) / f"situation-{self.store.new_id()}.m4a"
        wav = src.with_suffix(".wav")
        try:
            src.write_bytes(body)
            if await audio.to_wav16k(src, wav) > MAX_SECONDS:
                raise TooLong()
            if not await audio.has_speech(wav):
                return ""
            return await self.whisper.transcribe(wav, "auto")
        finally:
            for p in (src, wav):
                with contextlib.suppress(FileNotFoundError):
                    p.unlink()


def _quiet(task: asyncio.Task) -> None:
    """Background prep may fail (no internet); the next request retries. Do not warn about it."""
    if not task.cancelled() and task.exception() is not None:
        log.info("line prep failed: %s", type(task.exception()).__name__)
