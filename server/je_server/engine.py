"""Roleplay flow: create a script, prepare lines in the background, answer the app's requests."""
from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from collections.abc import AsyncIterator
from datetime import datetime
from pathlib import Path
from typing import Literal

from . import audio
from .claude import ClaudeUnavailable
from . import sounds
from .compare import FOLLOW_MIN, find_issues, praise_candidates, similarity, sound_pairs, words
from .models import Attempt, Draft, Issue, Roleplay, Said, ScriptLine, ThreeLine
from .sentences import SentenceBuffer
from .tts import VoiceError
from .phrases import PHRASES
from .store import Store
from .tts import audio_key

log = logging.getLogger("je_server")
LINE_WAIT = 120
MAX_SECONDS = 60
CLOSING_EN = "Thanks for your help! Have a good day."


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
        self.continuing: dict[str, asyncio.Task] = {}

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
        """Notes and model sound are made at the same time; the sound does not need the notes."""
        rp, line = self.get_line(rp_id, idx)

        async def notes():
            if line.speaker == "user" and line.three is None:
                async with self.sem:
                    three = await self.claude.annotate(line.text, self.context(rp, idx))
                await self.update_line(rp_id, idx, line.text, three=three)

        async def sound():
            if line.audio is None:
                key = await self.voice.say(line.text, "ryan", "english", urgent=False, rank=idx)
                await self.update_line(rp_id, idx, line.text, audio=key)

        await asyncio.gather(notes(), sound())

    async def line(self, rp_id: str, idx: int) -> ScriptLine:
        task = self.continuing.get(rp_id)
        if task is not None and not task.done():
            await asyncio.wait_for(asyncio.shield(task), LINE_WAIT)
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


    # --- a turn: the learner's recording ------------------------------------------------------

    def user_line(self, rp_id: str, idx: int) -> ScriptLine:
        _, line = self.get_line(rp_id, idx)
        if line.speaker != "user":
            raise NotFound(f"{rp_id}/{idx}")
        return line

    def error(self, code: str, phrase: str | None = None) -> dict:
        return {"type": "error", "code": code, "say": self.said(phrase or code).model_dump()}

    async def attempt(self, rp_id: str, idx: int, body: bytes,
                      mode: Literal["turn", "retry"]) -> AsyncIterator[dict]:
        t0 = time.perf_counter()
        timings: dict[str, float] = {}
        line = self.user_line(rp_id, idx)
        n, rec = self.store.next_rec(rp_id, idx)
        rec.write_bytes(body)  # kept on the Mac (spec 「녹음과 기록」)
        wav = self.store.tmp_dir / f"{rp_id}-{idx}-{n}.wav"
        try:
            try:
                seconds = await audio.to_wav16k(rec, wav)
            except audio.AudioError:
                yield self.error("no_speech")
                return
            if seconds > MAX_SECONDS:
                yield self.error("too_long")
                return
            if not await audio.has_speech(wav):
                yield self.error("no_speech")
                return
            heard = await self.whisper.transcribe(wav, "en")
        finally:
            with contextlib.suppress(FileNotFoundError):
                wav.unlink()
        timings["transcribed"] = time.perf_counter() - t0
        if not words(heard):
            yield self.error("no_speech")
            return
        followed = similarity(line.text, heard) >= FOLLOW_MIN
        yield {"type": "heard", "text": heard, "followed": followed}

        issues: list[Issue] = []
        said: list[str] = []
        keys: list[str] = []
        failed = False
        reply: ScriptLine | None = None
        if followed:
            issues = find_issues(line.text, heard, limit=2)
            text = self.claude.feedback(line.text, heard, praise_candidates(line.text, heard), issues)
            nxt = idx + 1 if mode == "turn" else idx
        elif mode == "retry":
            text = _one(self.said("retry_offscript").text)
            nxt = idx
        else:
            try:
                out = await self.claude.offscript(self.load(rp_id).frame, self.history(self.load(rp_id), idx),
                                                  line.text, heard)
            except ClaudeUnavailable:
                out = None
            if out is None:
                text, failed = None, True
                yield self.error("claude_unavailable", "claude_down")
            else:
                point, issues = self.point(out)
                text = _one(point) if point else None
                reply = ScriptLine(idx=idx + 1, speaker="ryan", text=out.reply_en.strip(), kind="reply")
            nxt = idx + 2
        if text is not None:
            async for ev in self.speak(text, said, keys, timings, t0):
                if ev["type"] == "error":
                    failed = True
                yield ev
        if reply is not None:
            try:
                reply.audio = await self.voice.say(reply.text, "ryan", "english", urgent=True)
            except VoiceError:
                log.info("reply voice failed")
            await self.add_reply(rp_id, idx, heard, reply)
            yield {"type": "reply", "line": reply.model_dump(mode="json")}
        timings["total"] = time.perf_counter() - t0
        await self.save_attempt(rp_id, idx, Attempt(n=n, mode=mode, heard=heard, followed=followed, issues=issues,
                                                    say_ko="".join(said), audio=keys, timings=timings),
                                pos=nxt if (mode == "turn" and not failed) else None)
        log.info("attempt %s/%d n=%d followed=%s issues=%d transcribed=%.2f first_text=%.2f first_audio=%.2f "
                 "total=%.2f", rp_id, idx, n, followed, len(issues), timings.get("transcribed", 0),
                 timings.get("first_text", 0), timings.get("first_audio", 0), timings["total"])
        if not failed:
            yield {"type": "done", "next": nxt, "issues": len(issues)}

    async def speak(self, text: AsyncIterator[str], said: list[str], keys: list[str],
                    timings: dict[str, float], t0: float) -> AsyncIterator[dict]:
        """Streams text events as they come and an audio event per finished sentence, in order."""
        out: asyncio.Queue = asyncio.Queue()
        sentences: asyncio.Queue = asyncio.Queue()

        async def read_text():
            buf = SentenceBuffer()
            try:
                async for delta in text:
                    timings.setdefault("first_text", time.perf_counter() - t0)
                    said.append(delta)
                    await out.put({"type": "text", "delta": delta})
                    for s in buf.feed(delta):
                        await sentences.put(s)
                for s in buf.flush():
                    await sentences.put(s)
            except ClaudeUnavailable:
                await out.put(self.error("claude_unavailable", "claude_down"))
            finally:
                await sentences.put(None)

        async def make_audio():
            while (s := await sentences.get()) is not None:
                try:
                    key = await self.voice.say(s, "ryan", "korean", urgent=True)
                except VoiceError:
                    log.info("feedback sentence voice failed")
                    continue
                timings.setdefault("first_audio", time.perf_counter() - t0)
                keys.append(key)
                await out.put({"type": "audio", "key": key})
            await out.put(None)

        reader = asyncio.create_task(read_text())
        maker = asyncio.create_task(make_audio())
        try:
            while (ev := await out.get()) is not None:
                yield ev
            # an error from the reader may land after the last audio event
            await reader
            while not out.empty():
                ev = out.get_nowait()
                if ev is not None:
                    yield ev
        finally:
            reader.cancel()
            maker.cancel()

    @staticmethod
    def history(rp: Roleplay, upto: int) -> Draft:
        """The conversation as it went: for a line said differently, what the learner actually said."""
        out: Draft = []
        for l in rp.lines[:upto]:
            text = l.text
            if l.speaker == "user":
                turns = [a for a in rp.attempts.get(l.idx, []) if a.mode == "turn"]
                if turns and not turns[-1].followed:
                    text = turns[-1].heard
            out.append((l.speaker, text))
        return out

    @staticmethod
    def point(out) -> tuple[str, list[Issue]]:
        """One thing to say before the reply. A pronunciation guess counts only for a listed sound, and then the
        list's explanation is used, not Claude's (spec 「평가」 맞댈 문장이 없을 때)."""
        if out.point_kind == "pronunciation":
            for a, b in sound_pairs(out.meant, out.heard_word):
                s = sounds.find(a, b)
                if s:
                    issue = Issue(target=out.meant, heard=out.heard_word, sound=(a, b), explain=s.explain)
                    return f"{out.meant}, {out.heard_word}처럼 들렸어요. {s.explain}", [issue]
            return "", []
        if out.point_kind == "expression" and out.point_ko.strip():
            return out.point_ko.strip(), []
        return "", []

    async def add_reply(self, rp_id: str, idx: int, heard: str, reply: ScriptLine) -> None:
        """Puts Ryan's reply after the line, drops the old rest of the script and rebuilds it in the background."""
        async with self.lock(rp_id):
            rp = self.store.load(rp_id)
            left = sum(1 for l in rp.lines[idx + 1:] if l.speaker == "user")
            rp.lines = rp.lines[:idx + 1] + [reply]
            self.store.save(rp)
        for key in [k for k in self.tasks if k[0] == rp_id and k[1] > idx]:
            self.tasks.pop(key).cancel()
        if left:
            history = self.history(rp, idx) + [("user", heard), ("ryan", reply.text)]
            task = asyncio.create_task(self._continue(rp_id, rp.frame, history, left))
            task.add_done_callback(_quiet)
            self.continuing[rp_id] = task

    async def _continue(self, rp_id: str, frame, history: Draft, user_turns: int) -> None:
        try:
            draft = await self.claude.continue_script(frame, history, user_turns)
        except ClaudeUnavailable:
            draft = [("ryan", CLOSING_EN)]  # cannot rebuild now: close the roleplay instead of hanging
        async with self.lock(rp_id):
            rp = self.store.load(rp_id)
            start = len(rp.lines)
            rp.lines += [ScriptLine(idx=start + i, speaker=sp, text=t) for i, (sp, t) in enumerate(draft)]
            self.store.save(rp)
        for i in range(start, start + len(draft)):
            self.schedule(rp_id, i)

    def summary(self, rp_id: str) -> dict:
        rp = self.load(rp_id)
        retry = [l.idx for l in rp.lines
                 if l.speaker == "user" and rp.attempts.get(l.idx) and rp.attempts[l.idx][-1].issues]
        return {"say": self.said("closing_retry" if retry else "closing_clean").model_dump(), "retry": retry}

    async def save_attempt(self, rp_id: str, idx: int, attempt: Attempt, pos: int | None) -> None:
        async with self.lock(rp_id):
            rp = self.store.load(rp_id)
            rp.attempts.setdefault(idx, []).append(attempt)
            if pos is not None:
                rp.pos = max(rp.pos, pos)
            self.store.save(rp)


async def _one(text: str) -> AsyncIterator[str]:
    yield text


def _quiet(task: asyncio.Task) -> None:
    """Background prep may fail (no internet); the next request retries. Do not warn about it."""
    if not task.cancelled() and task.exception() is not None:
        log.info("line prep failed: %s", type(task.exception()).__name__)
