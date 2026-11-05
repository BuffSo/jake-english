"""Roleplay flow: create a script, prepare lines in the background, answer the app's requests."""
from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from collections.abc import AsyncIterator
from datetime import datetime
from pathlib import Path

from . import audio
from .claude import ClaudeUnavailable
from . import sounds
from .compare import FOLLOW_MIN, find_issues, praise_candidates, similarity, sound_pairs, words
from .models import Attempt, Draft, Issue, Mode, Roleplay, Said, ScriptLine, ThreeLine
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
        self.left: dict[str, int] = {}  # learner lines the running rebuild is writing

    # --- fixed phrases ------------------------------------------------------------------------

    def said(self, name: str) -> Said:
        text = PHRASES[name]
        return Said(text=text, audio=audio_key("ryan", "korean", text))

    async def warm(self) -> None:
        for text in PHRASES.values():  # made once and played many times, so heard back (check)
            await self.voice.say(text, "ryan", "korean", urgent=False, check=True)

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

    async def copy(self, rp_id: str) -> Roleplay:
        """The same script as a new roleplay, to play it again from the start (spec roleplay-practice 6). Notes and
        sounds are reused, so it starts at once; the old record and its tries stay as they are."""
        task = self.continuing.get(rp_id)
        if task is not None and not task.done():
            await asyncio.wait_for(asyncio.shield(task), LINE_WAIT)
        old = self.load(rp_id)
        rp = Roleplay(id=self.store.new_id(), created=datetime.now().isoformat(timespec="seconds"),
                      situation=old.situation, frame=old.frame, lines=[l.model_copy(deep=True) for l in old.lines])
        self.store.save(rp)
        for line in rp.lines:
            if not self.ready(line):
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
        try:
            await asyncio.wait_for(asyncio.shield(self.schedule(rp_id, idx)), LINE_WAIT)
        except VoiceError:
            # the line comes without its sound rather than as an error: the roleplay moves on after a pause and
            # shadow practice can still record it (final review); the next request tries the sound again
            log.info("line sound failed: %s/%d", rp_id, idx)
        return self.get_line(rp_id, idx)[1]

    def recording(self, rp_id: str, idx: int, n: int) -> Path:
        """The learner's recording of one try, for replay on the end screen. The phone plays it, never keeps it."""
        path = self.store.find_rec(rp_id, idx, n)
        if path is None:
            raise NotFound(f"{rp_id}/{idx}/{n}")
        return path

    def progress(self, rp_id: str, idx: int) -> dict[str, int]:
        """「내 대사 no/total」 for the roleplay header. On Ryan's line it is the learner's next line. A rebuild that
        failed ends with Ryan's goodbye and fewer learner lines, so no is kept within total."""
        rp = self.load(rp_id)
        total = sum(1 for l in rp.lines if l.speaker == "user")
        before = sum(1 for l in rp.lines if l.speaker == "user" and l.idx < idx)
        return {"no": min(before + 1, total), "total": total}

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
        # heard back: its last sound was once swallowed (2026-11-05, 「…연습하고 싶~」)
        return Said(text=text, audio=await self.voice.say(text, "jake", "korean", urgent=True, check=True))

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

    def target_line(self, rp_id: str, idx: int, mode: Mode) -> ScriptLine:
        """The line a recording is said against: Ryan's for shadow practice, the learner's for the rest."""
        _, line = self.get_line(rp_id, idx)
        if line.speaker != ("ryan" if mode == "shadow" else "user"):
            raise NotFound(f"{rp_id}/{idx}")
        return line

    def error(self, code: str, phrase: str | None = None) -> dict:
        return {"type": "error", "code": code, "say": self.said(phrase or code).model_dump()}

    async def attempt(self, rp_id: str, idx: int, body: bytes, mode: Mode) -> AsyncIterator[dict]:
        """Only a roleplay turn said differently gets Ryan's reply and a new rest of the script; the other modes
        ask to follow the line and leave the script and the position alone."""
        t0 = time.perf_counter()
        timings: dict[str, float] = {}
        line = self.target_line(rp_id, idx, mode)
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
        elif mode != "turn":
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
            # start rebuilding the rest first, so it runs while Ryan's reply is made and played (spec 「역할극의
            # 한 차례」 5: 라이언이 대답하는 동안 다음 사용자 대사를 먼저 만든다)
            await self.add_reply(rp_id, idx, heard, reply)
            try:
                reply.audio = await self.voice.say(reply.text, "ryan", "english", urgent=True)
                await self.update_line(rp_id, reply.idx, reply.text, audio=reply.audio)
            except VoiceError:
                log.info("reply voice failed")
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
        """Puts Ryan's reply after the line, drops the old rest of the script and rebuilds it in the background.

        If a rebuild for an earlier reply on this line is still running (the app gave up and the learner was
        off-script again), it is cancelled and its count of learner lines is reused (PR #12 review)."""
        async with self.lock(rp_id):
            rp = self.store.load(rp_id)
            running = self.continuing.get(rp_id)
            if running is not None and not running.done():
                running.cancel()
                left = self.left.get(rp_id, 0)
            else:
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
            self.left[rp_id] = left

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
        """The end screen: every line with the learner's tries made inside the roleplay (spec roleplay-practice 3).
        Practice after the roleplay is left out: 「주고받은 말」 is what was said, and Ryan's reply to a line said
        differently answers that try. The closing words go by the same tries."""
        rp = self.load(rp_id)
        lines, issues_left = [], False
        for l in rp.lines:
            tries = [a for a in rp.attempts.get(l.idx, []) if a.mode in ("turn", "retry")] if l.speaker == "user" else []
            issues_left = issues_left or bool(tries and tries[-1].issues)
            lines.append({"line": l.model_dump(mode="json"), "tries": [
                {"n": a.n, "mode": a.mode, "heard": a.heard, "followed": a.followed,
                 "issues": [{"target": i.target, "heard": i.heard} for i in a.issues],
                 # Ryan's one point for a roleplay turn said differently; a retry said differently only asked
                 # to follow the line, which is not a point (final review)
                 "point_ko": a.say_ko if a.mode == "turn" and not a.followed else ""} for a in tries]})
        return {"say": self.said("closing_retry" if issues_left else "closing_clean").model_dump(), "lines": lines}

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
