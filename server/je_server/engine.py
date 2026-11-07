"""Roleplay flow: create a script, prepare lines in the background, answer the app's requests."""
from __future__ import annotations

import asyncio
import contextlib
import logging
import re
import time
from collections.abc import AsyncIterator, Sequence
from datetime import datetime
from pathlib import Path

from . import audio
from .asr import WhisperError
from .claude import ClaudeUnavailable
from . import topics
from .compare import FOLLOW_MIN, find_issues, issue_ko, praise_candidates, similarity, words
from .models import Attempt, Draft, Issue, Mode, Roleplay, Said, Saved, ScriptLine, Speaker, ThreeLine
from .sentences import SentenceBuffer
from .tts import VoiceError
from .phrases import PHRASES
from .review import first_try, group_of, latest_run, past_items, sentence_key
from .store import Store
from .tts import audio_key

log = logging.getLogger("je_server")
LINE_WAIT = 120
MAX_SECONDS = 60
NEAR_MIN = 0.3  # below FOLLOW_MIN but at least this close to the line: a try at it, not something else
ASIDES_KEPT = 3  # earlier asides on the line sent with a new one, for a question that follows Ryan's answer
HANGUL = re.compile(r"[가-힣]")


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
        self.threes: dict[tuple[str, int], asyncio.Task] = {}  # notes asked for on demand, one call per line
        self.kos: dict[tuple[str, int], asyncio.Task] = {}  # Sohee's Korean asked for, one call per line
        self.saved_lock = asyncio.Lock()  # the saved-sentence file is read and written one change at a time

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

    async def create(self, situation: str, topic: str = topics.OTHER, first: Speaker | None = None) -> Roleplay:
        """A new roleplay in a topic. `first`: who starts, from a list pick (spec situation-topics 5)."""
        frame, draft = await self.claude.make_script(situation, topics.get(topic), first)
        rp = Roleplay(id=self.store.new_id(), created=datetime.now().isoformat(timespec="seconds"),
                      situation=situation, frame=frame, topic=topic,
                      lines=[ScriptLine(idx=i, speaker=s, text=t) for i, (s, t) in enumerate(draft)])
        self.store.save(rp)
        for line in rp.lines:
            self.schedule(rp.id, line.idx)
        return rp

    async def copy(self, rp_id: str) -> Roleplay:
        """The same script as a new roleplay, to play it again from the start (spec roleplay-practice 6). Notes and
        sounds are reused, so it starts at once; the old record and its tries stay as they are."""
        old = self.load(rp_id)
        rp = Roleplay(id=self.store.new_id(), created=datetime.now().isoformat(timespec="seconds"),
                      situation=old.situation, frame=old.frame, lines=[l.model_copy(deep=True) for l in old.lines],
                      origin=old.origin or old.id,  # a copy of a copy still points at the first (ADR-0011)
                      topic=old.topic)
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

        # both finish before either failure is raised: a sound that fails fast must not leave the line without
        # its notes, since the roleplay screen does not ask for them again (PR #15 review)
        results = await asyncio.gather(notes(), sound(), return_exceptions=True)
        for r in results:
            if isinstance(r, BaseException):
                raise r

    async def line(self, rp_id: str, idx: int) -> ScriptLine:
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
        """「내 대사 no/total」 for the roleplay header. On Ryan's line it is the learner's next line. Records from
        before 2026-11-07 may end with fewer learner lines after a failed rebuild, so no is kept within total."""
        rp = self.load(rp_id)
        total = sum(1 for l in rp.lines if l.speaker == "user")
        before = sum(1 for l in rp.lines if l.speaker == "user" and l.idx < idx)
        return {"no": min(before + 1, total), "total": total}

    async def three(self, rp_id: str, idx: int) -> ThreeLine:
        """Notes on demand (Ryan's lines). Asks for the same line at once share one Claude call (PR #15 review:
        the end screen asks for every Ryan line and the shadow screen asks again)."""
        _, line = self.get_line(rp_id, idx)
        if line.three is not None:
            return line.three
        key = (rp_id, idx)
        task = self.threes.get(key)
        if task is None or task.done():
            task = asyncio.create_task(self._make_three(rp_id, idx))
            task.add_done_callback(_quiet)
            task.add_done_callback(lambda _: self.threes.pop(key, None))
            self.threes[key] = task
        return await asyncio.shield(task)

    async def _make_three(self, rp_id: str, idx: int) -> ThreeLine:
        rp, line = self.get_line(rp_id, idx)
        async with self.sem:
            three = await self.claude.annotate(line.text, self.context(rp, idx))
        await self.update_line(rp_id, idx, line.text, three=three)
        return three

    # --- Sohee's interpretation (spec korean-translation) ---------------------------------------

    async def ko(self, rp_id: str, idx: int) -> str:
        """Sohee's Korean for a line, made when first asked and kept on the line. Asks for the same line at once
        share one Claude call. It waits neither for `self.sem`, which three-line notes can fill at the start of a
        roleplay, nor for a rebuild of the rest of the script (spec 5, builder check)."""
        _, line = self.get_line(rp_id, idx)
        if line.ko is not None:
            return line.ko
        key = (rp_id, idx)
        task = self.kos.get(key)
        if task is None or task.done():
            task = asyncio.create_task(self._make_ko(rp_id, idx))
            task.add_done_callback(_quiet)
            task.add_done_callback(lambda _: self.kos.pop(key, None))
            self.kos[key] = task
        return await asyncio.shield(task)

    async def _make_ko(self, rp_id: str, idx: int) -> str:
        rp, line = self.get_line(rp_id, idx)
        # the lines around it as the conversation went: Ryan's reply answers what the learner actually said (spec 3)
        went = self.history(rp, len(rp.lines))
        before = went[idx - 1] if idx > 0 else None
        after = went[idx + 1] if idx + 1 < len(went) else None
        ko = await self.claude.interpret(rp.frame, (line.speaker, line.text), before, after)
        await self.update_line(rp_id, idx, line.text, ko=ko)
        return ko

    async def ko_audio(self, rp_id: str, idx: int) -> str:
        """Sohee saying the line's Korean, made when first asked: urgent, since the learner waits, and heard back,
        since a lost last sound (「~요」) changes the meaning (spec 4)."""
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
        screen (spec situation-topics 4)."""
        text = await self.claude.recommend(self.store.recent_situations(topic=topic), list(turned_down),
                                           topics.get(topic))
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
        and the same line again: the script never changes (spec offscript-aside)."""
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
                except WhisperError:
                    # only a check for Korean: the English transcript stands (todo offscript-aside minors 2)
                    log.info("auto transcription failed")
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
        yield {"type": "heard", "text": shown, "followed": followed}

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
            asides = [a for a in rp.attempts.get(idx, []) if a.aside][-ASIDES_KEPT:]
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
        held = ""  # trailing spaces wait for the next piece, so a cut piece can take its period right after the text
        try:
            async for delta in text:
                body = delta.rstrip()
                if body:
                    yield held + body
                    sent += held + body
                    held = delta[len(body):]
                else:
                    held += delta
        except ClaudeUnavailable:
            log.info("aside answer unavailable")
        else:
            if sent:
                return
            log.info("aside answer empty")
        if not sent:
            yield fixed
            return
        # a cut sentence ends before the fixed phrase, at the marks SentenceBuffer cuts at, so both read and voice
        # it as two sentences
        yield ("" if sent.endswith((".", "?", "!")) else ".") + " " + fixed

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
        Practice after the roleplay is left out: 「주고받은 말」 is what was said, and Ryan's reply to a line said
        differently answers that try. The closing words go by the same tries. `rps`: every record, when the caller
        has just read them (`latest`), so they are not read again (todo 01, ADR-0011 「영향」)."""
        rp = self.load(rp_id)
        group = group_of(rp)
        all_rps = self.store.all() if rps is None else rps
        runs = [r for r in all_rps if group_of(r) == group]  # for 「처음 녹음」 (spec review-practice 4)
        lines, issues_left = [], False
        for l in rp.lines:
            # asides stay off the end screen and out of its closing words (spec offscript-aside 6)
            tries = ([a for a in rp.attempts.get(l.idx, []) if a.mode in ("turn", "retry") and not a.aside]
                     if l.speaker == "user" else [])
            issues_left = issues_left or bool(tries and tries[-1].issues)
            lines.append({"line": l.model_dump(mode="json"), "tries": [
                {"n": a.n, "mode": a.mode, "heard": a.heard, "followed": a.followed,
                 "issues": [{"target": i.target, "heard": i.heard, "say_ko": issue_ko(i)} for i in a.issues],
                 # Ryan's one point for a roleplay turn said differently; a retry said differently only asked
                 # to follow the line, which is not a point (final review)
                 # a pronunciation point is already in issues, so it is not repeated (PR #15 review)
                 "point_ko": a.say_ko if a.mode == "turn" and not a.followed and not a.issues else ""}
                for a in tries], "first": first_try(runs, rp, l.idx)})
        return {"say": self.said("closing_retry" if issues_left else "closing_clean").model_dump(), "lines": lines}

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

    def saved(self) -> list[dict]:
        """Saved sentences, newest first (spec review-practice 6). The line is found again by its sentence when the
        script was rebuilt after it was saved; one that is gone is left out of the list but kept in the file."""
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
