"""Free talk (spec docs/superpowers/specs/2026-11-08-free-talk-design.md 2, 3).

A free talk is a record of `kind "talk"`: it has no script, but it is kept like a roleplay and its lines go by number
along the same routes. Ryan opens with the next of `TALK_OPENERS` in turn. The recordings stay on the Mac and Claude is
given text only (ADR-0004). Ryan's replies and the fixes are asked with my turns (`messages`, `fix_input`): my Korean
turns go to Claude marked `TALK_KOREAN` and Ryan answers them in English; only the fixes leave them out. Old records'
fixed `help` lines are skipped.

A turn (`Talks.turn`) is my line with its try and recording, then Ryan's line: his English reply streamed sentence by
sentence (spec 4), also when I spoke Korean (spec 3). Its fixed error lines are English (`TALK_PHRASES`). The learner may
cut Ryan's sounds off and speak again once his line is saved (spec 2). An English turn after Sohee's full sentence on
Ryan's reply right before it, and close to that sentence, is kept as said from it (`ScriptLine.given`, spec 9 「그 문장을
말하면」): with the words the Mac heard differently, no evaluation then, and fixed last after the talk (spec 7).

Ending a talk (`Talks.end`, spec 6, 7) asks Claude for the fixes, keeps those `fixes.check` lets through as my `fix`
lines after the talk, and makes the first one's sounds before answering. Those lines mark the talk as ended.

Sohee chance (`Talks.hint` and after, spec 9) is a hint on one of Ryan's replies, made once and kept on his line: a
Korean line Sohee says and English openers in Ryan's voice; then, once asked (「전체 문장 보기」), one full sentence with
its sound and notes. The routes answer each step on its own, like Sohee's interpretation (`/ko`, `/ko/audio`).
"""
from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from collections.abc import AsyncIterator
from datetime import datetime
from pathlib import Path

from . import audio, fixes, hints, sentences
from .asr import WhisperError
from .claude import ClaudeUnavailable, _points
from .compare import FOLLOW_MIN, find_issues, similarity, words
from .engine import HANGUL, MAX_SECONDS, NEAR_MIN, Engine, NotFound, _keep
from .models import Attempt, Fix, Frame, Hint, Issue, Roleplay, Said, ScriptLine, ThreeLine
from .phrases import SOHEE_PHRASES, TALK_OPENERS
from .prompts import TALK_CUT, TALK_CUT_SILENT, TALK_ECHO, TALK_HELPED, TALK_KOREAN, TALK_START
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
    """What Claude is given for Ryan's next answer: the start, Ryan's replies (assistant) and my turns (user). A Korean
    turn is marked `TALK_KOREAN`; a turn said from Sohee's full sentence is what was heard, then `TALK_HELPED`. When
    my last line is an English turn and its number is a multiple of three (the 3rd, 6th ...; Korean turns do not count,
    helped ones do), the server allows Ryan to echo the right form: `TALK_ECHO` ends that last message only (with the
    cue Ryan recast nearly every mistake, so this gives about a third of them, spec 4 「되받기」). Old records'
    `help` lines and the fixes are left out. The same role twice in a row is joined by a line break (when Claude could
    not answer, my next turn follows my last)."""
    out: list[dict] = [{"role": "user", "content": TALK_START}]
    for line in rp.lines:
        if line.kind == "reply" and line.speaker == "ryan":
            role, text = "assistant", _ryan_text(line)
        elif line.kind == "turn":
            role, text = "user", line.text if line.given is None else line.text + "\n" + TALK_HELPED
        elif line.kind == "ask":
            role, text = "user", TALK_KOREAN + line.text
        else:
            continue
        if out[-1]["role"] == role:
            out[-1]["content"] += "\n" + text
        else:
            out.append({"role": role, "content": text})
    if rp.lines and rp.lines[-1].kind == "turn" and sum(l.kind == "turn" for l in rp.lines) % 3 == 0:
        out[-1]["content"] += "\n" + TALK_ECHO
    return out


def fix_input(rp: Roleplay) -> tuple[list[dict], dict[int, str], dict[int, fixes.Helped]]:
    """What Claude is given to pick the fixes (spec 7): Ryan's English replies and my English turns with their line
    numbers, as heard; my own English turns by line number for `fixes.check`; and my turns said from Sohee's full
    sentence by line number, apart from those (spec 7 「고르는 차례」), only those with the Mac's points: one heard as
    the sentence has nothing to fix. Those helped turns are marked `"도움 받은 차례": true` in the talk (all of them,
    with points or not), so Claude does not spend one of its own three picks on one (the Mac would drop it). My Korean
    turns and old records' `help` lines are left out (spec 7 「고치지 않는 것」)."""
    conversation: list[dict] = []
    turns: dict[int, str] = {}
    helped: dict[int, fixes.Helped] = {}
    for line in rp.lines:
        if line.kind == "reply" and line.speaker == "ryan":
            who = "라이언"
        elif line.kind == "turn":
            who = "학습자"
            if line.given is None:
                turns[line.idx] = line.text
            else:
                tries = [a for a in rp.attempts.get(line.idx, []) if a.mode == "turn"]
                if tries and tries[-1].issues:
                    helped[line.idx] = fixes.Helped(given=line.given, heard=line.text, issues=tries[-1].issues)
        else:
            continue
        entry: dict = {"차례": line.idx, "말한 사람": who, "말": line.text}
        if line.kind == "turn" and line.given is not None:
            entry["도움 받은 차례"] = True  # as FIX_SYSTEM 「받는 것」 names it
        conversation.append(entry)
    return conversation, turns, helped


def helped_input(helped: dict[int, fixes.Helped]) -> list[dict]:
    """The helped turns as Claude is given them, in turn order, with the Mac's points (`claude._points`)."""
    return [{"차례": idx, "알려 준 문장": h.given, "들린 말": h.heard, "짚을 것": _points(h.issues)}
            for idx, h in sorted(helped.items())]


def _from_full(rp: Roleplay, heard: str) -> tuple[str | None, bool, list[Issue]]:
    """The sentence my English turn was said from, whether it followed it, and the words heard differently: Sohee's
    full sentence on Ryan's reply right before the turn (the record's last line as the turn started), once shown, when
    the turn is near it or follows it, by the bounds of a roleplay's line (`Engine._attempt`). Those words are kept so
    the fixes do not take a transcription slip for my grammar (spec 9 「그 문장을 말하면」). Else, or far from it (my
    own words), a plain turn: None, False, []."""
    last = rp.lines[-1] if rp.lines else None
    hint = last.hint if last is not None and last.speaker == "ryan" and last.kind == "reply" else None
    if hint is None or not hint.full_shown:
        return None, False, []
    close = similarity(hint.full, heard)
    if close < NEAR_MIN:
        return None, False, []
    return hint.full, close >= FOLLOW_MIN, find_issues(hint.full, heard, limit=2)


class TalkEnded(Exception):
    """The talk was ended: it has its fix lines, so it takes no more turns."""


class TalkBusy(Exception):
    """A turn of the talk is running and Ryan's line is not saved yet, or the talk is being ended."""


class NoHint(Exception):
    """A step of Sohee chance asked before the one it follows: the line has no hint yet, or its full sentence was not
    shown yet (the app shows the steps in turn, spec 9)."""


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
        # hints being made, one task per Ryan line: a second 「소희 찬스」 waits for the same Claude call
        self.hinting: dict[tuple[str, int], asyncio.Task] = {}
        # a hint's full sentence's notes being made, one task per line, like `Engine.threes`
        self.hint_threes: dict[tuple[str, int], asyncio.Task] = {}

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
        conversation, turns, helped = fix_input(rp)
        # no English turn of mine to fix (none, or only helped ones heard as the sentence): Claude is not asked (spec 6)
        found = (fixes.check(await engine.claude.fixes(conversation, helped_input(helped)), turns, helped)
                 if turns or helped else [])
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
        들어 보기」), or no lines and Ryan's 「고칠 곳을 찾지 못했어요」 (spec 7). `sohee`: how many Sohee chances I used,
        the hint and the full sentence each counted once on each of Ryan's replies (spec 9 「대화 끝」)."""
        sohee = sum(1 + line.hint.full_shown for line in rp.lines
                    if line.speaker == "ryan" and line.kind == "reply" and line.hint is not None)
        if not lines:
            return {"items": [], "say": self.engine.said("talk_no_fixes").model_dump(), "sohee": sohee}
        items = []
        for line in lines:
            tries = [a for a in rp.attempts.get(line.fix.of, []) if a.mode == "turn"]
            rec = {"rp_id": rp.id, "idx": line.fix.of, "n": tries[-1].n} if tries else None
            items.append({"line": line.model_dump(mode="json"), "rec": rec})
        return {"items": items, "say": None, "sohee": sohee}

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
                yield engine.talk_error(e.code)  # no line is kept; the recording stays, as in a roleplay
                return
            timings["transcribed"] = time.perf_counter() - t0
            given, followed, issues = (None, False, []) if korean else _from_full(rp, shown)
            await self._add(rp_id, ScriptLine(idx=idx, speaker="user", text=shown, kind="ask" if korean else "turn",
                                              given=given),
                            Attempt(n=n, mode="turn", heard=shown, followed=followed, issues=issues, say_ko="",
                                    audio=[], timings=timings, at=datetime.now().isoformat(timespec="seconds")))
            yield {"type": "heard", "text": shown, "n": n, "idx": idx, "korean": korean}

            ryan = idx + 1
            failed = False
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
                                         on_text_end=saved,
                                         down=engine.talk_error("claude_unavailable", "claude_down")):
                if ev["type"] == "error":
                    # no Ryan line can be kept after it (`saved` runs only for a whole reply), so the talk is free
                    # as the app reads the error, not once the sentence already written is voiced (1-3 s): a quick
                    # 「대화 끝내기」 or next turn is not refused as busy. `_keep_timings` finds its own try
                    failed = True
                    release()
                yield ev
            timings["total"] = time.perf_counter() - t0
            await self._keep_timings(rp_id, idx, n, timings)
            # times and counts only, never what was said (REVIEW.md 「녹음 처리」)
            log.info("talk %s/%d n=%d korean=%s helped=%s transcribed=%.2f first_text=%.2f first_audio=%.2f "
                     "total=%.2f", rp_id, idx, n, korean, given is not None, timings["transcribed"],
                     timings.get("first_text", 0), timings.get("first_audio", 0), timings["total"])
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

    # --- Sohee chance (spec 9) ------------------------------------------------------------------------------------

    def _reply(self, rp_id: str, idx: int) -> tuple[Roleplay, ScriptLine]:
        """The free talk and Ryan's reply at `idx`. NotFound: no such free talk, or that line is not his reply (my turn,
        a fix, an old record's fixed `help` line)."""
        rp = self.engine.load(rp_id)
        if rp.kind != "talk" or not 0 <= idx < len(rp.lines):
            raise NotFound(f"{rp_id}/{idx}")
        line = rp.lines[idx]
        if line.speaker != "ryan" or line.kind != "reply":
            raise NotFound(f"{rp_id}/{idx}")
        return rp, line

    def _hint(self, rp_id: str, idx: int, full: bool = False) -> tuple[Roleplay, Hint]:
        """The talk and the hint on Ryan's reply at `idx`. NoHint: none yet, or `full` and its full sentence was not
        shown yet."""
        rp, line = self._reply(rp_id, idx)
        if line.hint is None or (full and not line.hint.full_shown):
            raise NoHint(f"{rp_id}/{idx}")
        return rp, line.hint

    async def hint(self, rp_id: str, idx: int) -> Hint:
        """「소희 찬스」 on Ryan's reply at `idx`: made when first asked and kept on the line, so asked again (or the talk
        opened again) it is not made again. Two asks at once share one Claude call. NotFound: not his reply in a free
        talk. ClaudeUnavailable: nothing is kept and the next ask tries again."""
        _, line = self._reply(rp_id, idx)
        if line.hint is not None:
            return line.hint
        task = self.hinting.get((rp_id, idx))
        if task is None or task.done():
            task = _keep(self.hinting, (rp_id, idx), asyncio.create_task(self._make_hint(rp_id, idx)))
        return await asyncio.shield(task)

    async def _make_hint(self, rp_id: str, idx: int) -> Hint:
        t0 = time.perf_counter()
        rp, line = self._reply(rp_id, idx)
        hint = await self.engine.claude.hint(hints.conversation(rp, idx))
        await self.engine.update_line(rp_id, idx, line.text, hint=hint)
        # times and counts only, never what was said (REVIEW.md 「녹음 처리」)
        log.info("hint %s/%d starters=%d total=%.2f", rp_id, idx, len(hint.starters), time.perf_counter() - t0)
        return hint

    async def _keep_hint(self, rp_id: str, idx: int, **changes) -> None:
        """Changes the line's hint as it is now: its sound, 「전체 문장 보기」 and the notes may be asked at once, and
        each keeps the others' changes."""
        async with self.engine.lock(rp_id):
            rp = self.engine.store.load(rp_id)
            line = rp.lines[idx]
            rp.lines[idx] = line.model_copy(update={"hint": line.hint.model_copy(update=changes)})
            self.engine.store.save(rp)

    async def hint_audio(self, rp_id: str, idx: int) -> str:
        """Sohee saying the hint's Korean line and 「이렇게 시작해 보세요.」 in one sound, made when first asked and kept.
        Urgent, since the learner waits, and heard back, like her interpretation (`Engine.ko_audio`)."""
        _, hint = self._hint(rp_id, idx)
        voice = self.engine.voice
        if hint.audio is not None and voice.path(hint.audio).is_file():
            return hint.audio
        key = await voice.say(f"{hint.meaning_ko} {SOHEE_PHRASES['hint_start']}", "sohee", "korean", urgent=True,
                              check=True)
        await self._keep_hint(rp_id, idx, audio=key)
        return key

    async def show_full(self, rp_id: str, idx: int) -> dict:
        """「전체 문장 보기」: the full sentence and Sohee's 「이렇게 말해 봐요.」 (made ahead, `Engine.warm`). Marked on
        the line, for the count at the end; the first step's answer never has it."""
        _, hint = self._hint(rp_id, idx)
        if not hint.full_shown:
            await self._keep_hint(rp_id, idx, full_shown=True)
        phrase = SOHEE_PHRASES["hint_full"]
        said = Said(text=phrase, audio=self.engine.voice.key("sohee", "korean", phrase))
        return {"text": hint.full, "say": said.model_dump()}

    async def hint_sound(self, rp_id: str, idx: int, n: int) -> str:
        """Ryan's English model sound of an opener (`n` below their count) or of the full sentence (`n` their count,
        once shown): Ryan's voice, since Sohee's would make a Korean accent the model (spec 9 「소리」). NotFound: no
        such sound."""
        _, hint = self._hint(rp_id, idx)
        if n < len(hint.starters):
            text = hint.starters[n]
        elif n == len(hint.starters):
            if not hint.full_shown:
                raise NoHint(f"{rp_id}/{idx}")
            text = hint.full
        else:
            raise NotFound(f"{rp_id}/{idx}/{n}")
        return await self.engine.voice.say(text, "ryan", "english", urgent=True)

    async def hint_three(self, rp_id: str, idx: int) -> ThreeLine:
        """The full sentence's notes (「읽는 법 보기」), made when first asked and kept, once it was shown. Two asks at
        once share one Claude call."""
        _, hint = self._hint(rp_id, idx, full=True)
        if hint.full_three is not None:
            return hint.full_three
        task = self.hint_threes.get((rp_id, idx))
        if task is None or task.done():
            task = _keep(self.hint_threes, (rp_id, idx), asyncio.create_task(self._make_hint_three(rp_id, idx)))
        return await asyncio.shield(task)

    async def _make_hint_three(self, rp_id: str, idx: int) -> ThreeLine:
        rp, hint = self._hint(rp_id, idx, full=True)
        async with self.engine.sem:
            three = await self.engine.claude.annotate(hint.full, self.engine.context(rp, idx))
        await self._keep_hint(rp_id, idx, full_three=three)
        return three
