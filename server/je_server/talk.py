"""Free talk (spec docs/superpowers/specs/2026-11-08-free-talk-design.md 2, 3).

A free talk is a record of `kind "talk"`: it has no script, but it is kept like a roleplay and its lines go by number
along the same routes. Ryan opens with the next of `TALK_OPENERS` in turn. The recordings stay on the Mac; Claude is
given only the text (`messages`), and never my Korean turns or Ryan's Korean answers.

A turn (`Talks.turn`) is my line with its try and recording, then Ryan's line: his English reply streamed sentence by
sentence (spec 4), or the fixed Korean `talk_english` when I spoke Korean (spec 3). The learner may cut Ryan's sounds
off and speak again once his line is saved (spec 2).

Ending a talk (`Talks.end`, spec 6, 7) asks Claude for the fixes, keeps those `fixes.check` lets through as my `fix`
lines after the talk, and makes the first one's sounds before answering. Those lines mark the talk as ended.
"""
from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from collections.abc import AsyncIterator
from datetime import datetime
from pathlib import Path

from . import audio, fixes, sentences
from .asr import WhisperError
from .claude import ClaudeUnavailable
from .compare import words
from .engine import HANGUL, MAX_SECONDS, Engine, NotFound, _keep
from .models import Attempt, Fix, Frame, Roleplay, Said, ScriptLine
from .phrases import TALK_OPENERS
from .prompts import TALK_CUT, TALK_CUT_SILENT, TALK_START
from .tts import VoiceError

log = logging.getLogger("je_server")

TALK_FRAME = Frame(title_ko="자유 대화", user_role_ko="나", ryan_role_ko="대화 상대", place_ko="자유 대화",
                   goal_ko="대본 없이 영어로 이야기하기")


def _ryan_text(line: ScriptLine) -> str:
    """Ryan's reply as the learner heard it: when cut off, the sentences heard and a note of where."""
    if line.heard_upto is None:
        return line.text
    if line.heard_upto == 0:
        return TALK_CUT_SILENT
    heard = " ".join(p.text for p in (line.parts or [])[: line.heard_upto])
    return f"{heard} {TALK_CUT}"


def messages(rp: Roleplay) -> list[dict]:
    """What Claude is given for Ryan's next answer: the start, Ryan's replies (assistant) and my English turns (user).
    My Korean turns, Ryan's Korean answers and the fixes are left out. The same role twice in a row is joined by a
    line break (when Claude could not answer, my next turn follows my last)."""
    out: list[dict] = [{"role": "user", "content": TALK_START}]
    for line in rp.lines:
        if line.kind == "reply" and line.speaker == "ryan":
            role, text = "assistant", _ryan_text(line)
        elif line.kind == "turn":
            role, text = "user", line.text
        else:
            continue
        if out[-1]["role"] == role:
            out[-1]["content"] += "\n" + text
        else:
            out.append({"role": role, "content": text})
    return out


def fix_input(rp: Roleplay) -> tuple[list[dict], dict[int, str]]:
    """What Claude is given to pick the fixes (spec 7): Ryan's English replies and my English turns with their line
    numbers, and my English turns by line number for `fixes.check`. My Korean turns and Ryan's Korean answers are left
    out (spec 7 「고치지 않는 것」), as in `messages`."""
    conversation: list[dict] = []
    turns: dict[int, str] = {}
    for line in rp.lines:
        if line.kind == "reply" and line.speaker == "ryan":
            who = "라이언"
        elif line.kind == "turn":
            who = "학습자"
            turns[line.idx] = line.text
        else:
            continue
        conversation.append({"차례": line.idx, "말한 사람": who, "말": line.text})
    return conversation, turns


class TalkEnded(Exception):
    """The talk was ended: it has its fix lines, so it takes no more turns."""


class TalkBusy(Exception):
    """A turn of the talk is running and Ryan's line is not saved yet, or the talk is being ended."""


class _Unheard(Exception):
    """The recording holds no turn; `code` names the error to send (`no_speech`, `too_long`)."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


class Talks:
    def __init__(self, engine: Engine):
        self.engine = engine
        self.turning: set[str] = set()  # talks with a turn running whose Ryan line is not saved yet
        # the rest of a cut-off reply still being made for 「🔊 듣기」, one task per line (`_mark_heard`)
        self.finishing: dict[tuple[str, int], asyncio.Task] = {}
        # talks being ended, one task per talk: a second 「대화 끝내기」 waits for the same Claude call
        self.ending: dict[str, asyncio.Task] = {}

    async def create(self) -> Roleplay:
        """A new free talk that starts with Ryan's next first question. The turn is taken and kept in one go, so two
        asks at the same time get two questions."""
        store, voice = self.engine.store, self.engine.voice
        n = store.load_talk()
        opener = TALK_OPENERS[n % len(TALK_OPENERS)]
        store.save_talk(n + 1)
        try:
            audio = await voice.say(opener, "ryan", "english", urgent=True, check=True)
        except VoiceError:
            log.warning("could not make the sound of a first question")
            audio = voice.key("ryan", "english", opener)
        line = ScriptLine(idx=0, speaker="ryan", text=opener, kind="reply",
                          parts=[Said(text=opener, audio=audio)])
        rp = Roleplay(id=store.new_id(), created=datetime.now().isoformat(timespec="seconds"),
                      situation=TALK_FRAME.title_ko, frame=TALK_FRAME, lines=[line], kind="talk")
        store.save(rp)
        return rp

    def check_open(self, rp_id: str) -> Roleplay:
        """The talk, when it can take a turn now. NotFound: no such free talk. TalkEnded: it was ended. TalkBusy: a turn
        is running and Ryan's line is not saved yet, or the talk is being ended (a turn then would take the line number
        of the first fix line)."""
        rp = self.engine.load(rp_id)
        if rp.kind != "talk":
            raise NotFound(rp_id)
        if any(line.kind == "fix" for line in rp.lines):
            raise TalkEnded(rp_id)
        if rp_id in self.turning or self._ending(rp_id) is not None:
            raise TalkBusy(rp_id)
        return rp

    def _ending(self, rp_id: str) -> asyncio.Task | None:
        task = self.ending.get(rp_id)
        return task if task is not None and not task.done() else None

    async def end(self, rp_id: str, heard: int | None = None) -> dict:
        """「대화 끝내기」 (spec 6, 7): the fixes of my English turns as `fix` lines, each with the recording of the turn
        it fixes. `heard`: how many sentences of Ryan's last reply I heard (as in `turn`). Asked again, the same lines
        without Claude; two at once share one Claude call. NotFound: no such free talk. TalkBusy: a turn is running.
        ClaudeUnavailable: Claude could not pick the fixes; nothing is kept and the next end asks again."""
        rp = self.engine.load(rp_id)
        if rp.kind != "talk":
            raise NotFound(rp_id)  # an ended talk is not refused, unlike `check_open`: it answers with its fixes
        if rp_id in self.turning:
            raise TalkBusy(rp_id)
        done = [line for line in rp.lines if line.kind == "fix"]
        if done:
            return self._end_body(rp, done)
        task = self._ending(rp_id)
        if task is None:  # no await since the checks: a turn sent now finds this task and is refused
            task = _keep(self.ending, rp_id, asyncio.create_task(self._end(rp_id, heard)))
        return await asyncio.shield(task)

    async def _end(self, rp_id: str, heard: int | None) -> dict:
        engine, voice = self.engine, self.engine.voice
        t0 = time.perf_counter()
        first_sound = 0.0
        rp = engine.load(rp_id)
        await self._mark_heard(rp, heard)
        last = rp.lines[-1]
        if last.speaker == "ryan" and last.kind == "reply" and last.parts:
            # the rest of Ryan's last reply, when its sounds are still being made, waits behind the fixes' sounds
            # (the voice leaves out those made)
            voice.demote([p.audio for p in last.parts])
        conversation, turns = fix_input(rp)
        # no English turn of mine: nothing to fix, and Claude is not asked (spec 6)
        found = fixes.check(await engine.claude.fixes(conversation), turns) if turns else []
        lines: list[ScriptLine] = []
        if found:
            async with engine.lock(rp_id):
                rp = engine.store.load(rp_id)
                lines = [line for line in rp.lines if line.kind == "fix"]
                added = not lines  # else made meanwhile: those stand
                if added:
                    lines = [ScriptLine(idx=len(rp.lines) + i, speaker="user", kind="fix", text=f.fixed,
                                        fix=Fix(of=f.of, said=f.said, why_ko=f.why_ko)) for i, f in enumerate(found)]
                    rp.lines.extend(lines)
                    engine.store.save(rp)
            if added:
                # the closing review opens on the first fix with Ryan's explanation, then its model sound: those two
                # first and urgent (spec 7 「기다림」); the rest, and every line's notes, are made behind
                first = lines[0]
                made: dict = {}
                try:
                    why = await voice.say(first.fix.why_ko, "ryan", "korean", urgent=True)
                    made["fix"] = first.fix.model_copy(update={"why_audio": why})
                    made["audio"] = await voice.say(first.text, "ryan", "english", urgent=True)
                    first_sound = time.perf_counter() - t0
                except VoiceError:
                    log.info("first fix sound failed")  # made again behind, with the rest
                if made:
                    await engine.update_line(rp_id, first.idx, first.text, **made)
                for line in lines:
                    engine.schedule(rp_id, line.idx)
            rp = engine.load(rp_id)
            lines = [line for line in rp.lines if line.kind == "fix"]
        # times and counts only, never what was said (REVIEW.md 「녹음 처리」)
        log.info("talk end %s fixes=%d first_fix_sound=%.2f total=%.2f", rp_id, len(lines), first_sound,
                 time.perf_counter() - t0)
        return self._end_body(rp, lines)

    def _end_body(self, rp: Roleplay, lines: list[ScriptLine]) -> dict:
        """The answer to `end`: each fix line with the recording of my last try at the turn it fixes (for 「🔊 내 녹음
        들어 보기」), or no lines and Ryan's 「고칠 곳을 찾지 못했어요」 (spec 7)."""
        if not lines:
            return {"items": [], "say": self.engine.said("talk_no_fixes").model_dump()}
        items = []
        for line in lines:
            tries = [a for a in rp.attempts.get(line.fix.of, []) if a.mode == "turn"]
            rec = {"rp_id": rp.id, "idx": line.fix.of, "n": tries[-1].n} if tries else None
            items.append({"line": line.model_dump(mode="json"), "rec": rec})
        return {"items": items, "say": None}

    async def turn(self, rp_id: str, body: bytes, heard: int | None) -> AsyncIterator[dict]:
        """One turn of mine and Ryan's line after it. `heard`: how many sentences of Ryan's last reply I heard before I
        spoke (None: the app does not know, read as all). Sohee's sounds made ahead wait while it runs."""
        with self.engine._answering():
            async with contextlib.aclosing(self._turn(rp_id, body, heard)) as events:
                async for ev in events:
                    yield ev

    async def _turn(self, rp_id: str, body: bytes, heard: int | None) -> AsyncIterator[dict]:
        engine = self.engine
        try:
            rp = self.check_open(rp_id)
        except (TalkEnded, TalkBusy) as e:
            # the route's `check_open` answers these first, so only two requests at once get here. No fixed phrase
            # says them (`engine.error` would find none): the app shows its own words
            yield {"type": "error", "code": "ended" if isinstance(e, TalkEnded) else "busy", "say": None}
            return
        self.turning.add(rp_id)  # no await since the check: two turns sent together cannot both pass it
        held = True

        def release() -> None:
            # as soon as Ryan's line is saved: while its sounds are still being made, the learner may cut them off and
            # send the next turn (spec 2). Only once, so a turn whose sounds end late does not free the next one
            nonlocal held
            if held:
                held = False
                self.turning.discard(rp_id)

        try:
            t0 = time.perf_counter()
            timings: dict[str, float] = {}
            await self._mark_heard(rp, heard)
            idx = len(rp.lines)
            n, rec = engine.store.next_rec(rp_id, idx)
            rec.write_bytes(body)  # kept on the Mac (ADR-0004): Claude is given the text only
            try:
                shown, korean = await self._hear(rp_id, idx, n, rec)
            except _Unheard as e:
                yield engine.error(e.code)  # no line is kept; the recording stays, as in a roleplay
                return
            timings["transcribed"] = time.perf_counter() - t0
            await self._add(rp_id, ScriptLine(idx=idx, speaker="user", text=shown, kind="ask" if korean else "turn"),
                            Attempt(n=n, mode="turn", heard=shown, followed=False, issues=[], say_ko="", audio=[],
                                    timings=timings, at=datetime.now().isoformat(timespec="seconds")))
            yield {"type": "heard", "text": shown, "n": n, "idx": idx, "korean": korean}

            ryan = idx + 1
            failed = False
            if korean:
                # Korean said with 「말하기」 gets the fixed 「영어로 말해 볼까요?」, and Claude never sees it (spec 3)
                help_ = engine.said("talk_english")
                yield {"type": "text", "delta": help_.text}
                await self._add(rp_id, ScriptLine(idx=ryan, speaker="ryan", text=help_.text, kind="help",
                                                  audio=help_.audio, parts=[help_]))
                release()
                yield {"type": "reply", "idx": ryan, "kind": "help", "parts": [help_.model_dump()]}
                yield {"type": "audio", "key": help_.audio}
            else:
                async def saved(text: str) -> dict:
                    # the parts are the sentences `speak` voiced, so 「🔊 듣기」 and a cut-off count use the same ones
                    parts = [Said(text=s, audio=engine.voice.key("ryan", "english", s)) for s in sentences.split(text)]
                    await self._add(rp_id, ScriptLine(idx=ryan, speaker="ryan", text=text.strip(), kind="reply",
                                                      parts=parts))
                    release()
                    return {"type": "reply", "idx": ryan, "kind": "reply", "parts": [p.model_dump() for p in parts]}

                # Ryan speaks from his first sentence while the rest is written (spec 4, 5: 2.8 s sooner than voicing
                # the whole reply). When Claude cannot answer, my line stays and Ryan's is not kept (spec 4)
                async for ev in engine.speak(self._reply_text(rp_id), [], [], timings, t0, lang="english",
                                             on_text_end=saved):
                    failed = failed or ev["type"] == "error"
                    yield ev
            timings["total"] = time.perf_counter() - t0
            await self._keep_timings(rp_id, idx, n, timings)
            # times and counts only, never what was said (REVIEW.md 「녹음 처리」)
            log.info("talk %s/%d n=%d korean=%s transcribed=%.2f first_text=%.2f first_audio=%.2f total=%.2f",
                     rp_id, idx, n, korean, timings["transcribed"], timings.get("first_text", 0),
                     timings.get("first_audio", 0), timings["total"])
            if not failed:
                yield {"type": "done", "idx": ryan}
        finally:
            release()

    async def _mark_heard(self, rp: Roleplay, heard: int | None) -> None:
        """Marks how much of Ryan's last reply was heard when I cut it off, so his next reply knows (`messages`). The
        rest of its sounds are put behind the new reply's and still made, for 「🔊 듣기」 (spec 2). Heard to the end
        (or the count not known) marks nothing."""
        last = rp.lines[-1] if rp.lines else None
        if (heard is None or last is None or last.speaker != "ryan" or last.kind != "reply" or not last.parts
                or heard >= len(last.parts)):
            return
        await self.engine.update_line(rp.id, last.idx, last.text, heard_upto=heard)
        rest = last.parts[heard:]
        self.engine.voice.demote([p.audio for p in rest])
        key = (rp.id, last.idx)
        if key not in self.finishing:
            _keep(self.finishing, key, asyncio.create_task(self._finish(rest)))

    async def _finish(self, parts: list[Said]) -> None:
        """The sounds of a cut-off reply's rest that are not made yet, not urgent: after the new reply's."""
        voice = self.engine.voice
        for p in parts:
            if voice.path(p.audio).is_file():
                continue
            try:
                await voice.say(p.text, "ryan", "english", urgent=False)
            except VoiceError:
                log.info("cut reply sound failed")  # 「🔊 듣기」 skips it

    async def _hear(self, rp_id: str, idx: int, n: int, rec: Path) -> tuple[str, bool]:
        """What I said, and whether it was Korean. _Unheard: the recording holds no turn. The WAV is deleted after."""
        whisper = self.engine.whisper
        wav = self.engine.store.tmp_dir / f"{rp_id}-{idx}-{n}.wav"
        try:
            try:
                seconds = await audio.to_wav16k(rec, wav)
            except audio.AudioError:
                raise _Unheard("no_speech") from None
            if seconds > MAX_SECONDS:
                raise _Unheard("too_long")
            if not await audio.has_speech(wav):
                raise _Unheard("no_speech")
            # English only, no auto language (spec 3): 0.85 s sooner, and auto took 1 in 4 of my English for Korean
            heard = await whisper.transcribe(wav, "en")
            korean = bool(HANGUL.search(heard))
            shown = heard
            if korean:
                # Korean said with 「말하기」, left in Hangul by the English transcript: heard again in Korean
                try:
                    shown = await whisper.transcribe(wav, "ko")
                except WhisperError as e:
                    # the English transcript is shown instead; the error carries its type name only
                    log.info("korean transcription failed: %s", e)
        finally:
            wav.unlink(missing_ok=True)
        if not (words(shown) or HANGUL.search(shown)):
            raise _Unheard("no_speech")
        return shown, korean

    async def _reply_text(self, rp_id: str) -> AsyncIterator[str]:
        """Ryan's reply from Claude, given the talk so far as turns (spec 4). No text at all is Claude not answering."""
        got = ""
        async for piece in self.engine.claude.talk(messages(self.engine.load(rp_id))):
            got += piece
            yield piece
        if not got.strip():
            raise ClaudeUnavailable("empty")

    async def _add(self, rp_id: str, line: ScriptLine, attempt: Attempt | None = None) -> None:
        """Adds a line, and my try on it, to the record as it is now."""
        async with self.engine.lock(rp_id):
            rp = self.engine.store.load(rp_id)
            rp.lines.append(line)
            if attempt is not None:
                rp.attempts.setdefault(line.idx, []).append(attempt)
            self.engine.store.save(rp)

    async def _keep_timings(self, rp_id: str, idx: int, n: int, timings: dict[str, float]) -> None:
        """The turn's times, once Ryan's sounds are sent, on its try only: the next turn may have added lines since."""
        async with self.engine.lock(rp_id):
            rp = self.engine.store.load(rp_id)
            for a in rp.attempts.get(idx, []):
                if a.n == n:
                    a.timings = dict(timings)
            self.engine.store.save(rp)
