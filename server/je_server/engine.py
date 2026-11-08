"""Roleplay flow: create a script, prepare lines in the background, answer the app's requests."""
from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import re
import threading
import time
from collections.abc import AsyncIterator, Sequence
from datetime import date, datetime
from pathlib import Path

from . import audio
from .asr import WhisperError
from .claude import ClaudeUnavailable, pick_ending
from . import topics
from .compare import FOLLOW_MIN, find_issues, issue_ko, praise_candidates, similarity, words
from .models import Attempt, Draft, Issue, Mode, Roleplay, Said, Saved, ScriptLine, ThreeLine
from .sentences import NewSentence, SentenceBuffer
from .threeline import settled
from .tts import VoiceError
from .phrases import PHRASES, TIPS
from .review import (first_try, group_of, kept_tries, latest_run, past_items, resume_start, said_on, sentence_key,
                     to_resume)
from .store import Store

log = logging.getLogger("je_server")
LINE_WAIT = 120
MAX_SECONDS = 60
NEAR_MIN = 0.3  # below FOLLOW_MIN but at least this close to the line: a try at it, not something else
# the asides after the line's last try at it sent with a new one, for a question that follows Ryan's answer
ASIDES_KEPT = 3
HANGUL = re.compile(r"[가-힣]")
ENDS = (".", "?", "!")  # the marks SentenceBuffer cuts a sentence at
CLOSERS = "」』)]\"'”’"  # closing brackets and quotes a sentence end may sit inside
# Sohee's sounds made ahead for a pick (todo 13) come after every model sound waiting, which go by line number
SOHEE_RANK = 1000
# the longest one of them waits for a recording's answer, so a request that never closes cannot stop them for good
QUIET_WAIT = 60


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
        # notes being made, one call per line: Ryan's when asked, the learner's in the background from the start
        self.threes: dict[tuple[str, int], asyncio.Task] = {}
        # Sohee's Korean asked for, one call per line; a list pick's lines come with theirs from the repository
        self.kos: dict[tuple[str, int], asyncio.Task] = {}
        self.sohees: dict[str, asyncio.Task] = {}  # Sohee's sounds made ahead, one task per run of a list pick
        self.answers_running = 0  # recordings being answered now; Sohee's sounds made ahead wait for none
        self.quiet = asyncio.Event()
        self.quiet.set()
        self.saved_lock = asyncio.Lock()  # the saved-sentence file is read and written one change at a time
        # `/home` runs in a worker thread: two at once must not both take the day's tip
        self.tip_lock = threading.Lock()
        self.plays: dict[str, asyncio.Task] = {}  # play copies being made, one per recording

    # --- fixed phrases ------------------------------------------------------------------------

    def said(self, name: str) -> Said:
        return self._ryan_said(PHRASES[name])

    def _ryan_said(self, text: str) -> Said:
        return Said(text=text, audio=self.voice.key("ryan", "korean", text))

    def home_tip(self, day: date | None = None) -> Said | None:
        """Ryan's shadowing tip for the day's first start, the next in turn; None once it was said that day (spec
        ryan-shadowing-tip 2, 4). The Mac's date. Remembered in the data folder, so a restart does not say it again."""
        today = (day or date.today()).isoformat()
        with self.tip_lock:
            try:
                last, nxt = self.store.load_tip()
                if last == today:
                    return None
                self.store.save_tip(today, nxt + 1)
            except OSError as e:
                # the first screen is the way into the app: a tip.json the Mac cannot read or write (a full or
                # read-only disk) costs the day's tip, never the screen (final review)
                log.warning("tip.json unusable, no tip today: %s", type(e).__name__)
                return None
        return self._ryan_said(TIPS[nxt % len(TIPS)])

    async def warm(self) -> None:
        # made once and played many times, so heard back (check); the tips too, said once a day
        for text in [*PHRASES.values(), *TIPS]:
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

    async def create(self, situation: str, topic: str = topics.OTHER) -> Roleplay:
        """A new roleplay in a topic from a situation the learner described or Jake suggested: Claude writes it."""
        frame, draft = await self.claude.make_script(situation, topics.get(topic))
        rp = Roleplay(id=self.store.new_id(), created=datetime.now().isoformat(timespec="seconds"),
                      situation=situation, frame=frame, topic=topic,
                      lines=[ScriptLine(idx=i, speaker=s, text=t) for i, (s, t) in enumerate(draft)])
        self.store.save(rp)
        for line in rp.lines:
            self.schedule(rp.id, line.idx)
        return rp

    async def create_pick(self, topic_id: str, pick_id: str) -> Roleplay:
        """A list pick from its script in the repository, without Claude (spec fixed-list-scripts 2, ADR-0013). An
        earlier run of the pick makes this the group's next run and lends what it already made. KeyError: no such
        pick in the topic."""
        p = topics.pick(topic_id, pick_id)
        # no await from reading the records to saving the new one: two picks arriving together finish one after the
        # other on the event loop, so the second finds the first and the pick keeps one group (spec 2)
        runs = sorted((r for r in self.store.all() if r.pick == pick_id), key=lambda r: r.created)
        rp = Roleplay(id=self.store.new_id(), created=datetime.now().isoformat(timespec="seconds"),
                      situation=p.situation, frame=p.frame.model_copy(), topic=topic_id, pick=pick_id,
                      origin=group_of(runs[0]) if runs else None,
                      lines=[self._with_ko(self._prepared(runs, ScriptLine(idx=i, speaker=s, text=t)),
                                           p.ko[i] if i < len(p.ko) else "")
                             for i, (s, t) in enumerate(p.script)])
        self.store.save(rp)
        for line in rp.lines:
            if not self.prepared(line):
                self.schedule(rp.id, line.idx)
        if any(l.ko and l.ko_audio is None for l in rp.lines):
            task = asyncio.create_task(self._sohee_later(rp.id))
            task.add_done_callback(_quiet)
            task.add_done_callback(lambda _: self.sohees.pop(rp.id, None))
            self.sohees[rp.id] = task
        return rp

    def _with_ko(self, line: ScriptLine, ko: str) -> ScriptLine:
        """The line with Sohee's Korean written in the repository, which wins over what an earlier run had Claude
        make; her sound comes with it when the Mac has made it before (todo 13). Without it, the line as it is."""
        if not ko:
            return line
        key = self.voice.key("sohee", "korean", ko)
        return line.model_copy(update={"ko": ko, "ko_audio": key if self.voice.path(key).is_file() else None})

    async def _sohee_later(self, rp_id: str) -> None:
        """Sohee's sounds for the run's lines that have her Korean, made ahead so a tap on 「통역」 plays at once
        (todo 13). After the run's model sounds and the learner's notes, so the first line is not held back; one at a
        time and not while a recording is being answered, since a sound being made holds the voice worker and Ryan's
        answer would wait behind it. A sound the learner asked for first is not made again."""
        mine = [t for (r, _), t in [*self.tasks.items(), *self.threes.items()] if r == rp_id]
        if mine:
            await asyncio.wait(mine)  # not gather: a cancelled wait must not cancel the line's own tasks
        for idx in range(len(self.load(rp_id).lines)):
            _, line = self.get_line(rp_id, idx)
            if not line.ko:
                continue
            made = self.voice.key("sohee", "korean", line.ko)
            if self.voice.path(made).is_file():  # a tap, or another run of the pick, made it meanwhile
                if line.ko_audio != made:
                    await self.update_line(rp_id, idx, line.text, ko_audio=made)
                continue
            with contextlib.suppress(asyncio.TimeoutError):
                await asyncio.wait_for(self.quiet.wait(), QUIET_WAIT)
            try:
                key = await self.voice.say(line.ko, "sohee", "korean", urgent=False, rank=SOHEE_RANK + idx,
                                           check=True)
            except VoiceError:
                log.info("sohee sound failed: %s/%d", rp_id, idx)  # a tap on her line tries again
                continue
            await self.update_line(rp_id, idx, line.text, ko_audio=key)

    def _prepared(self, runs: list[Roleplay], line: ScriptLine) -> ScriptLine:
        """The line with what earlier runs (oldest first) made for the same line: same place, speaker and words.
        Each part comes from the newest run that has it; a note without Korean or a reading is made again, Sohee's
        sound comes with her Korean (spec 2), and a sound made for an older key is made again (`_current_sounds`)."""
        same = [l for r in reversed(runs) for l in r.lines[line.idx:line.idx + 1]
                if (l.speaker, l.text) == (line.speaker, line.text)]
        three = next((l.three for l in same if l.three is not None and settled(l.three)), None)
        audio = next((l.audio for l in same if l.audio is not None), None)
        ko = next((l for l in same if l.ko is not None), None)
        return self._current_sounds(line.model_copy(update={"three": three, "audio": audio, "ko": ko and ko.ko,
                                                            "ko_audio": ko and ko.ko_audio}))

    def _current_sounds(self, line: ScriptLine) -> ScriptLine:
        """The line without the sounds an earlier run made for another key than today's: another reference
        recording, rate or way of making (todo voice-reference-in-sound-key, fixed-list-scripts minors 4). A new run
        makes them again; the earlier run's own record keeps what was heard then."""
        drop = {}
        if line.audio is not None and line.audio != self.voice.key("ryan", "english", line.text):
            drop["audio"] = None
        if line.ko_audio is not None and (line.ko is None
                                          or line.ko_audio != self.voice.key("sohee", "korean", line.ko)):
            drop["ko_audio"] = None
        return line.model_copy(update=drop) if drop else line

    async def copy(self, rp_id: str) -> Roleplay:
        """The same script as a new roleplay, to play it again from the start (spec roleplay-practice 6). Notes and
        sounds are reused, so it starts at once, except sounds made for an older key (`_current_sounds`) and notes
        that are not `threeline.settled` (spec fixed-list-scripts 2 「예외」), made again like a list pick's. The old
        record and its tries stay as they are. A list pick plays its script as it is now in the repository; one
        taken off the list is copied (spec fixed-list-scripts 4)."""
        old = self.load(rp_id)
        # outside any try: a KeyError from inside create_pick is a bug, not a pick taken off the list (todo 08 1);
        # taken off the list, it is copied below
        if old.topic is not None and old.pick is not None and topics.listed(old.topic, old.pick) is not None:
            return await self.create_pick(old.topic, old.pick)
        rp = Roleplay(id=self.store.new_id(), created=datetime.now().isoformat(timespec="seconds"),
                      situation=old.situation, frame=old.frame,
                      lines=[self._current_sounds(_unsettled_dropped(l.model_copy(deep=True))) for l in old.lines],
                      origin=old.origin or old.id,  # a copy of a copy still points at the first (ADR-0011)
                      topic=old.topic, pick=old.pick)
        self.store.save(rp)
        for line in rp.lines:
            if not self.prepared(line):
                self.schedule(rp.id, line.idx)
        return rp

    def schedule(self, rp_id: str, idx: int) -> asyncio.Task:
        """Starts what the line still lacks and returns its sound task. The learner's notes are made beside it on
        the task `three` shares, so the line does not wait for them (spec dont-wait-for-line-notes 1); being made
        apart, a sound that fails fast cannot leave the line without its notes either (PR #15 review)."""
        _, line = self.get_line(rp_id, idx)
        if line.speaker == "user" and line.three is None:
            self._three_task(rp_id, idx)
        key = (rp_id, idx)
        task = self.tasks.get(key)
        if task is None or (task.done() and (task.cancelled() or task.exception() is not None)):
            task = asyncio.create_task(self._sound(rp_id, idx))
            task.add_done_callback(_quiet)
            self.tasks[key] = task
        return task

    @staticmethod
    def ready(line: ScriptLine) -> bool:
        """The line can be shown: its model sound is made. The learner's notes come apart (spec
        dont-wait-for-line-notes 1): the line starts as plain text and they open only when asked."""
        return line.audio is not None

    @staticmethod
    def prepared(line: ScriptLine) -> bool:
        """Nothing is left to make: the sound, and the notes of a learner's line (Ryan's are made when asked)."""
        return line.audio is not None and (line.speaker == "ryan" or line.three is not None)

    async def _sound(self, rp_id: str, idx: int) -> None:
        _, line = self.get_line(rp_id, idx)
        if line.audio is None:
            key = await self.voice.say(line.text, "ryan", "english", urgent=False, rank=idx)
            await self.update_line(rp_id, idx, line.text, audio=key)

    async def line(self, rp_id: str, idx: int) -> ScriptLine:
        """The line once its sound is made; the learner's notes go on in the background (a server restarted
        mid-way starts them again here)."""
        _, line = self.get_line(rp_id, idx)
        if self.prepared(line):
            return line
        task = self.schedule(rp_id, idx)
        if self.ready(line):
            return line
        try:
            await asyncio.wait_for(asyncio.shield(task), LINE_WAIT)
        except VoiceError:
            # the line comes without its sound rather than as an error: the roleplay moves on after a pause and
            # shadow practice can still record it (final review); the next request tries the sound again
            log.info("line sound failed: %s/%d", rp_id, idx)
        return self.get_line(rp_id, idx)[1]

    async def recording(self, rp_id: str, idx: int, n: int) -> Path:
        """The learner's recording of one try, for replay. The phone plays it, never keeps it. What is served is its
        play copy, cut to the speech with moov first, so a replay is not silence first (spec play-button-feedback 4);
        made now when it is not there yet, and the original when it cannot be made."""
        src = self.store.find_rec(rp_id, idx, n)
        if src is None:
            raise NotFound(f"{rp_id}/{idx}/{n}")
        dst = self.store.play_path(rp_id, idx, n)
        if dst.is_file():
            return dst
        try:
            await asyncio.shield(self._play_job(src, dst))
        except (audio.AudioError, OSError) as e:
            # its kind only, never the path (REVIEW.md 「녹음 처리」)
            log.info("play copy failed: %s", type(e).__name__)
            return src
        return dst

    def _play_job(self, src: Path, dst: Path) -> asyncio.Task:
        """Makes the play copy once: requests for the same one at the same time share it (as `Voice.rate_file`)."""
        key = str(dst)
        job = self.plays.get(key)
        if job is None:
            job = asyncio.ensure_future(self._make_play(src, dst))
            self.plays[key] = job

            # made at the first replay only, which waits for it: a copy made beside the answer was left running at
            # the end of a test and closing the event loop then hung now and then; a server restart could too
            job.add_done_callback(lambda _: self.plays.pop(key, None))
        return job

    async def _make_play(self, src: Path, dst: Path) -> None:
        wav = self.store.tmp_dir / f"play-{self.store.new_id()}.wav"
        tmp = self.store.tmp_dir / f"play-{self.store.new_id()}.m4a"
        try:
            seconds = await audio.to_wav16k(src, wav)
            span = await asyncio.to_thread(audio.speech_span, wav)
            await audio.play_cut(src, span, seconds, tmp)
            os.replace(tmp, dst)
        finally:
            wav.unlink(missing_ok=True)
            tmp.unlink(missing_ok=True)

    def progress(self, rp_id: str, idx: int) -> dict[str, int]:
        return progress_of(self.load(rp_id), idx)

    async def three(self, rp_id: str, idx: int) -> ThreeLine:
        """A line's notes: Ryan's are made when asked; the learner's are being made in the background and this
        waits for that same call (spec dont-wait-for-line-notes 1). Asks for the same line at once share one Claude
        call (PR #15 review: the end screen asks for every Ryan line and the shadow screen asks again)."""
        _, line = self.get_line(rp_id, idx)
        if line.three is not None:
            return line.three
        return await asyncio.shield(self._three_task(rp_id, idx))

    def _three_task(self, rp_id: str, idx: int) -> asyncio.Task:
        """The one task making this line's notes, started if none is running."""
        task = self.threes.get((rp_id, idx))
        if task is None or task.done():
            task = _keep(self.threes, (rp_id, idx), asyncio.create_task(self._make_three(rp_id, idx)))
        return task

    async def _make_three(self, rp_id: str, idx: int) -> ThreeLine:
        rp, line = self.get_line(rp_id, idx)
        async with self.sem:
            three = await self.claude.annotate(line.text, self.context(rp, idx))
        await self.update_line(rp_id, idx, line.text, three=three)
        return three

    # --- Sohee's interpretation (spec korean-translation) ---------------------------------------

    async def ko(self, rp_id: str, idx: int) -> str:
        """Sohee's Korean for a line, made when first asked and kept on the line; a list pick's line has it from the
        repository already, so Claude is not asked (todo 13). Asks for the same line at once share one Claude call.
        It does not wait for `self.sem`, which three-line notes can fill at the start of a roleplay (spec 5, builder
        check)."""
        _, line = self.get_line(rp_id, idx)
        if line.ko is not None:
            return line.ko
        return await asyncio.shield(self._ko_task(rp_id, idx))

    def _ko_task(self, rp_id: str, idx: int) -> asyncio.Task:
        """The one task making this line's Korean, started if none is running."""
        task = self.kos.get((rp_id, idx))
        if task is None or task.done():
            task = _keep(self.kos, (rp_id, idx), asyncio.create_task(self._make_ko(rp_id, idx)))
        return task

    async def _make_ko(self, rp_id: str, idx: int) -> str:
        rp, line = self.get_line(rp_id, idx)
        # the lines around it as the conversation went: in a record from before 2026-11-07, Ryan's in-role reply
        # answers what the learner actually said (spec 3)
        went = self.history(rp, len(rp.lines))
        before = went[idx - 1] if idx > 0 else None
        after = went[idx + 1] if idx + 1 < len(went) else None
        ko = await self.claude.interpret(rp.frame, (line.speaker, line.text), before, after)
        await self.update_line(rp_id, idx, line.text, ko=ko)
        return ko

    async def ko_audio(self, rp_id: str, idx: int) -> str:
        """Sohee saying the line's Korean, made when first asked: urgent, since the learner waits, and heard back,
        since a lost last sound (「~요」) changes the meaning (spec 4). A list pick's sounds are also made ahead
        (`_sohee_later`); asked for while that one is queued or being made, both wait for the same sound."""
        _, line = self.get_line(rp_id, idx)
        if line.ko is None:
            raise NotFound(f"{rp_id}/{idx}/ko")
        if line.ko_audio is not None and self.voice.path(line.ko_audio).is_file():
            return line.ko_audio
        key = await self.voice.say(line.ko, "sohee", "korean", urgent=True, check=True)
        await self.update_line(rp_id, idx, line.text, ko_audio=key)
        return key

    # --- situation input ----------------------------------------------------------------------

    async def recommend(self, turned_down: Sequence[str] = (), topic: str = topics.OTHER) -> Said:
        """Jake suggests a situation in the topic, not one of its recent ones or those just turned down on the
        screen, in one of his three endings (spec situation-topics 4)."""
        text = await self.claude.recommend(self.store.recent_situations(topic=topic), list(turned_down),
                                           topics.get(topic), pick_ending(turned_down))
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
        """A followed line gets the Mac's feedback; anything else, in every mode, gets teacher Ryan's Korean answer
        and the same line again: the script never changes (spec offscript-aside). Sohee's sounds made ahead wait
        while it runs."""
        with self._answering():
            async with contextlib.aclosing(self._attempt(rp_id, idx, body, mode)) as events:
                async for ev in events:
                    yield ev

    @contextlib.contextmanager
    def _answering(self):
        self.answers_running += 1
        self.quiet.clear()
        try:
            yield
        finally:
            self.answers_running -= 1
            if not self.answers_running:
                self.quiet.set()

    async def _attempt(self, rp_id: str, idx: int, body: bytes, mode: Mode) -> AsyncIterator[dict]:
        t0 = time.perf_counter()
        timings: dict[str, float] = {}
        line = self.target_line(rp_id, idx, mode)
        n, rec = self.store.next_rec(rp_id, idx)
        rec.write_bytes(body)  # kept on the Mac (spec 「녹음과 기록」)
        wav = self.store.tmp_dir / f"{rp_id}-{idx}-{n}.wav"
        heard_ko: str | None = None
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
            close = similarity(line.text, heard) if words(heard) else 0.0
            # Hangul in the English transcript is Korean that was said: the match counts English words only, so the
            # line begun and then Korean would pass as followed (Jake-voice check, 2026-11-08)
            followed = close >= FOLLOW_MIN and not HANGUL.search(heard)
            if not followed:
                # forced to English, whisper translates Korean or leaves it in Hangul (spec offscript-aside 2). Every
                # recording that does not follow the line is asked again: a near one may be the line begun and then
                # Korean, translated (phone test 2026-11-08). Accented English heard as Korean then loses its points;
                # the text cannot tell the two apart (auto-detection also translates English into Korean).
                try:
                    auto, lang = await self.whisper.transcribe_auto(wav)
                except WhisperError as e:
                    # only a check for Korean: the English transcript stands (todo offscript-aside minors 2). The
                    # error carries the failure's type name only, never the transcript
                    log.info("auto transcription failed: %s", e)
                    auto, lang = "", ""
                if lang == "korean" and HANGUL.search(auto):
                    heard_ko = auto
            # a try at the line that came out wrong: English and close to it, so it gets the Mac's points
            near = not followed and heard_ko is None and close >= NEAR_MIN
        finally:
            with contextlib.suppress(FileNotFoundError):
                wav.unlink()
        timings["transcribed"] = time.perf_counter() - t0
        shown = heard_ko or heard
        if not (words(shown) or HANGUL.search(shown)):
            yield self.error("no_speech")
            return
        # n: the recording just saved, so the app can play it back at once (spec three-line-listen 7)
        yield {"type": "heard", "text": shown, "followed": followed, "n": n}

        issues: list[Issue] = []
        said: list[str] = []
        keys: list[str] = []
        failed = False
        rp = self.load(rp_id)
        if followed:
            issues = find_issues(line.text, heard, limit=2)
            # 「나아진 점」: what the last try at this line pointed out (followed, or a near miss with points), in any
            # mode; a copied roleplay keeps its own record (spec 「잘한 점 후보」, offscript-aside 6)
            earlier = [a for a in rp.attempts.get(idx, []) if a.followed or (a.issues and not a.aside)]
            before = earlier[-1].issues if earlier else []
            # the roleplay's own turns only: a practice runs in an order the app keeps
            last = mode in ("turn", "retry") and idx == len(rp.lines) - 1
            text = self.claude.feedback(line.text, heard, praise_candidates(line.text, heard, before), issues, last)
            nxt = idx + 1 if mode == "turn" else idx
        else:
            # the Mac's points only for a try at the line; far from it, they would point at unrelated words
            if near:
                issues = find_issues(line.text, heard, limit=2)
            # 「바로 앞에」 (spec 3): only what came after the last try at the line (followed, with points, or an old
            # record's), so an earlier practice's exchange is not sent along
            tries = rp.attempts.get(idx, [])
            since = next((i + 1 for i in range(len(tries) - 1, -1, -1) if not tries[i].aside), 0)
            asides = tries[since:][-ASIDES_KEPT:]
            text = self._aside(self.claude.aside(rp.frame, self.history(rp, idx), line.text, heard, heard_ko, issues,
                                                 [(a.heard, a.say_ko) for a in asides]))
            # a try at the line with points moves on like a followed one, so a line whisper keeps mishearing never
            # traps the learner (user, 2026-11-07); anything else is an aside and stays on the line
            nxt = idx + 1 if (mode == "turn" and issues) else idx
        async for ev in self.speak(text, said, keys, timings, t0):
            if ev["type"] == "error":
                failed = True
            yield ev
        timings["total"] = time.perf_counter() - t0
        await self.save_attempt(rp_id, idx, Attempt(n=n, mode=mode, heard=shown, followed=followed, issues=issues,
                                                    say_ko="".join(said), audio=keys, timings=timings,
                                                    at=datetime.now().isoformat(timespec="seconds"),
                                                    aside=not followed and not issues),
                                pos=nxt if (mode == "turn" and (followed or issues) and not failed) else None)
        log.info("attempt %s/%d n=%d followed=%s korean=%s issues=%d transcribed=%.2f first_text=%.2f "
                 "first_audio=%.2f total=%.2f", rp_id, idx, n, followed, heard_ko is not None, len(issues),
                 timings.get("transcribed", 0), timings.get("first_text", 0), timings.get("first_audio", 0),
                 timings["total"])
        if not failed:
            yield {"type": "done", "next": nxt, "issues": len(issues)}

    async def _aside(self, text: AsyncIterator[str]) -> AsyncIterator[str]:
        """Teacher Ryan's answer; when Claude cannot answer, stops midway or ends without text (a streamed refusal,
        thinking that used up the tokens), the fixed 「이번에는 대사를 그대로 따라 말해 볼까요?」 instead of an
        error or an empty box, so the learner can try the line again (spec offscript-aside 3)."""
        fixed = self.said("retry_offscript").text
        sent = ""
        # trailing spaces wait for the next piece, so a cut piece can take its period right after the text; after a
        # sentence end they go at once, so SentenceBuffer cuts that sentence for the voice without waiting (todo
        # teacher-answer-cut 3)
        held = ""
        try:
            async for delta in text:
                body = delta.rstrip()
                if not body:
                    held += delta
                    continue
                out = held + (delta if body.endswith(ENDS) else body)
                held = "" if body.endswith(ENDS) else delta[len(body):]
                yield out
                sent += out
        except ClaudeUnavailable:
            log.info("aside answer unavailable")
        else:
            if sent:
                return
            log.info("aside answer empty")
        if not sent:
            yield fixed
            return
        # a cut sentence ends before the fixed phrase, so both read and voice it as two sentences. A piece that already
        # ends one, 「…」 or a mark inside a closing bracket or quote included, takes no other period (todo
        # teacher-answer-cut 2); SentenceBuffer does not cut after those, so the fixed phrase starts a new sentence for
        # the voice on its own (`NewSentence`, PR #44 review)
        if not sent.rstrip().rstrip(CLOSERS).endswith((*ENDS, "…")):
            yield "."
        yield NewSentence(("" if sent != sent.rstrip() else " ") + fixed)

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
                    if isinstance(delta, NewSentence):  # the sentence so far ends here for the voice
                        for s in buf.flush():
                            await sentences.put(s)
                    delta = str(delta)
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
        """The conversation as it went: for a line said differently in a record from before 2026-11-07, what the
        learner actually said."""
        out: Draft = []
        for l in rp.lines[:upto]:
            text = l.text
            if l.speaker == "user":
                # asides are not turns (spec offscript-aside 6); old records' turns said differently still are
                turns = [a for a in rp.attempts.get(l.idx, []) if a.mode == "turn" and not a.aside]
                # what was said only where Ryan answered it in role: records from before 2026-11-07 (a reply line
                # follows); a near miss since then is a try at the script line
                answered = l.idx + 1 < len(rp.lines) and rp.lines[l.idx + 1].kind == "reply"
                if turns and not turns[-1].followed and answered:
                    text = turns[-1].heard
            out.append((l.speaker, text))
        return out

    def summary(self, rp_id: str, rps: list[Roleplay] | None = None) -> dict:
        """The end screen: every line with the learner's tries made inside the roleplay (spec roleplay-practice 3).
        Practice after the roleplay is left out: 「주고받은 말」 is what was said, and in a record from before
        2026-11-07 Ryan's in-role reply to a line said differently answers that try. The closing words go by the
        same tries. `rps`: every record, when the caller has just read them (`latest`), so they are not read again
        (todo 01, ADR-0011 「영향」)."""
        rp = self.load(rp_id)
        group = group_of(rp)
        all_rps = self.store.all() if rps is None else rps
        runs = [r for r in all_rps if group_of(r) == group]  # for 「처음 녹음」 (spec review-practice 4)
        lines, issues_left, said = [], False, False
        for l in rp.lines:
            # asides stay off the end screen and out of its closing words (spec offscript-aside 6)
            tries = kept_tries(rp, l)
            issues_left = issues_left or bool(tries and tries[-1].issues)
            said = said or bool(tries)
            lines.append({"line": l.model_dump(mode="json"), "tries": [
                {"n": a.n, "mode": a.mode, "heard": a.heard, "followed": a.followed,
                 "issues": [{"target": i.target, "heard": i.heard, "say_ko": issue_ko(i, l.text, a.heard)}
                            for i in a.issues],
                 # Ryan's one point for a roleplay turn said differently, in records from before 2026-11-07 (asides
                 # are left out above); a retry said differently only asked to follow the line, not a point
                 # a pronunciation point is already in issues, so it is not repeated (PR #15 review)
                 "point_ko": a.say_ko if a.mode == "turn" and not a.followed and not a.issues else ""}
                for a in tries], "first": first_try(runs, rp, l.idx)})
        # no line said (skipped without a recording, spec record-cancel-skip 3): no praise for what was not heard
        closing = "closing_retry" if issues_left else "closing_clean" if said else "closing_plain"
        return {"say": self.said(closing).model_dump(), "lines": lines}

    # --- 다시 연습 (spec review-practice, ADR-0011): read from the records, no Claude call -----------------------

    def past(self) -> list[dict]:
        return past_items(self.store.all())

    def latest(self, group: str) -> dict:
        """The newest run of a script the learner spoke in, with its end-screen summary (spec review-practice 3)."""
        rps = self.store.all()
        rp = latest_run(rps, group)
        if rp is None:
            raise NotFound(group)
        return {"roleplay": rp.model_dump(mode="json"), "summary": self.summary(rp.id, rps)}

    def resume(self) -> dict | None:
        """The conversation to resume and where (spec resume-roleplay 1, 2; resume-unrecorded 2-5): the newest roleplay
        with a line of mine left unrecorded, where it starts, whether it went to the end, and what was heard on every
        recorded line of mine, so the app can show them and pass them. Read from the records; no Claude call."""
        rp = to_resume(self.store.all())
        if rp is None:
            return None
        at, ended = resume_start(rp)
        return {"roleplay": rp.model_dump(mode="json"), "at": at, "progress": progress_of(rp, at),
                "said": said_on(rp), "ended": ended}

    def saved(self) -> list[dict]:
        """Saved sentences, newest first (spec review-practice 6). The line is found again by its sentence when the
        script was rebuilt after it was saved (records from before 2026-11-07); one that is gone is left out of the
        list but kept in the file."""
        out = []
        items = self.store.load_saved()  # in the order saved, so two saves in one second keep their order
        for _, s in sorted(enumerate(items), key=lambda p: (p[1].at, p[0]), reverse=True):
            found = self._resolve(s)
            if found is not None:
                rp, line = found
                out.append({"key": s.key, "rp_id": rp.id, "idx": line.idx, "speaker": line.speaker, "text": line.text,
                            "title_ko": rp.frame.title_ko, "at": s.at})
        return out

    def _resolve(self, s: Saved) -> tuple[Roleplay, ScriptLine] | None:
        """The roleplay and line a saved entry points at: its own line while it still says the sentence, else the
        first line of that roleplay that does; None when the roleplay or the sentence is gone."""
        try:
            rp = self.store.load(s.rp_id)
        except KeyError:
            return None
        except ValueError:  # an unreadable record is skipped like in `Store.all`, not the whole list (todo 01)
            log.warning("unreadable roleplay %s", s.rp_id)
            return None
        here = rp.lines[s.idx] if s.idx < len(rp.lines) else None
        line = here if here and sentence_key(here.text) == s.key else next(
            (l for l in rp.lines if sentence_key(l.text) == s.key), None)
        return (rp, line) if line is not None else None

    async def set_saved(self, rp_id: str, idx: int, on: bool) -> dict:
        """Saves or unsaves the line's sentence; one entry per sentence wherever it was saved (spec 5)."""
        _, line = self.get_line(rp_id, idx)
        key = sentence_key(line.text)
        async with self.saved_lock:
            items = self.store.load_saved()
            if on:
                # an entry whose line is gone is not on the list, so it must not keep the sentence from being saved
                # again (PR #27 review): it is replaced by this line
                items = [s for s in items if s.key != key or self._resolve(s) is not None]
                if all(s.key != key for s in items):
                    items.append(Saved(key=key, rp_id=rp_id, idx=idx, at=datetime.now().isoformat(timespec="seconds")))
            else:
                items = [s for s in items if s.key != key]
            self.store.save_saved(items)
        return {"key": key, "on": on}

    async def skip(self, rp_id: str, idx: int) -> int:
        """「건너뛰기」 on a line of mine inside the roleplay: the place moves past it, so resuming starts after it
        (spec resume-roleplay 3). No try and no recording are kept; the place only moves forward. NotFound: no such
        line, or Ryan's."""
        _, line = self.get_line(rp_id, idx)
        if line.speaker != "user":
            raise NotFound(f"{rp_id}/{idx}")
        async with self.lock(rp_id):
            rp = self.store.load(rp_id)
            rp.pos = max(rp.pos, idx + 1)
            self.store.save(rp)
            return rp.pos

    async def save_attempt(self, rp_id: str, idx: int, attempt: Attempt, pos: int | None) -> None:
        async with self.lock(rp_id):
            rp = self.store.load(rp_id)
            rp.attempts.setdefault(idx, []).append(attempt)
            if pos is not None:
                rp.pos = max(rp.pos, pos)
            self.store.save(rp)


def progress_of(rp: Roleplay, idx: int) -> dict[str, int]:
    """「내 대사 no/total」 for the roleplay header. On Ryan's line it is the learner's next line. Records from before
    2026-11-07 may end with fewer learner lines after a failed rebuild, so no is kept within total."""
    total = sum(1 for l in rp.lines if l.speaker == "user")
    before = sum(1 for l in rp.lines if l.speaker == "user" and l.idx < idx)
    return {"no": min(before + 1, total), "total": total}


def _unsettled_dropped(line: ScriptLine) -> ScriptLine:
    """The line without a note that is not worth reusing, so it is made again (`threeline.settled`)."""
    return line.model_copy(update={"three": None}) if line.three is not None and not settled(line.three) else line


def _keep(tasks: dict, key, task: asyncio.Task) -> asyncio.Task:
    """Keeps `task` under `key` while it runs. Its done callback runs on a later turn of the loop, and a new ask may
    have put its own task under the key in between: the callback removes only its own (todo line-notes minors 1)."""
    tasks[key] = task
    task.add_done_callback(_quiet)
    task.add_done_callback(lambda t: tasks.pop(key) if tasks.get(key) is t else None)
    return task


def _quiet(task: asyncio.Task) -> None:
    """Background work may fail (no internet): a line's sound and notes, Sohee's Korean. The next request retries, so
    do not warn about it."""
    if not task.cancelled() and task.exception() is not None:
        log.info("background prep failed: %s", type(task.exception()).__name__)
