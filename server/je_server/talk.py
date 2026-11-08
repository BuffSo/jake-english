"""Free talk (spec docs/superpowers/specs/2026-11-08-free-talk-design.md 2, 3).

A free talk is a record of `kind "talk"`: it has no script, but it is kept like a roleplay and its lines go by number
along the same routes. Ryan opens with the next of `TALK_OPENERS` in turn. The recordings stay on the Mac; Claude is
given only the text (`messages`), and never my Korean turns or Ryan's Korean answers.
"""
from __future__ import annotations

import logging
from datetime import datetime

from .engine import Engine
from .models import Frame, Roleplay, Said, ScriptLine
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


class Talks:
    def __init__(self, engine: Engine):
        self.engine = engine

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
