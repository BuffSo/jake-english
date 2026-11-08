"""Data shapes shared by the server and the app (contract/ holds JSON examples)."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

Mark = Literal["s", "w", "n"]  # s: strong (bold dark orange on screen), w: small gray (weak), n: as is


class Syllable(BaseModel):
    en: str
    ko: str
    m: Mark
    hi: str = ""  # only when m == "s": the one Hangul letter in ko to highlight


class Word(BaseModel):
    syl: list[Syllable]
    emph: bool = False  # stressed for meaning, skipped by the dictionary check
    link: bool = False  # Korean joins the next word without a space


class ThreeLine(BaseModel):
    words: list[Word]
    reading: str  # [[...]] marks a pronunciation, shown as 「...」


class Frame(BaseModel):
    """The situation's basic frame (who, where, what), in Korean."""

    title_ko: str
    user_role_ko: str
    ryan_role_ko: str
    place_ko: str
    goal_ko: str


class Said(BaseModel):
    text: str
    audio: str


Speaker = Literal["ryan", "user"]
Draft = list[tuple[Speaker, str]]

# script: a roleplay's line. reply: Ryan's English line (in a free talk also the first question); in records from before
# 2026-11-07 it is also Ryan's in-role answer to something said differently from the line. The rest are free talk only
# (spec free-talk-design 2): turn is my English turn, ask my Korean turn, help Ryan's fixed English line after it
# (`TALK_ENGLISH`, asking for English), and fix the corrected sentence (said by `user`) that the closing 「대화 돌아보기」
# shows.
LineKind = Literal["script", "reply", "turn", "ask", "help", "fix"]


class Fix(BaseModel):
    """What the closing review says about one of my English turns (spec free-talk-design 2). The line's `text` is the
    corrected sentence and its `audio` the model sound of it."""

    of: int  # the line number of my turn that was corrected
    said: str  # the one sentence of that turn that had the problem, as it was heard
    why_ko: str  # Ryan's explanation in Korean, with the sound list's explanation when a mispronunciation is guessed
    why_audio: str | None = None  # sound key of Ryan saying why_ko in Korean


class ScriptLine(BaseModel):
    idx: int
    speaker: Speaker
    text: str
    kind: LineKind = "script"
    three: ThreeLine | None = None
    audio: str | None = None  # sound key (sha256 hex) of Ryan reading the line
    # Sohee's Korean for the line and the sound key of her saying it (spec korean-translation 5): made when asked, but a
    # list pick's lines start with the Korean written in the repository and their sound is made ahead (todo 13)
    ko: str | None = None
    ko_audio: str | None = None
    # free talk only (spec free-talk-design 2, 8): Ryan's answer sentence by sentence with the sound of each
    parts: list[Said] | None = None
    # how many sentences of the answer were heard when I cut it off; None when heard to the end
    heard_upto: int | None = None
    fix: Fix | None = None


class Issue(BaseModel):
    """One place the transcript differs from the line (spec 「평가」 3)."""

    target: str  # the line's words here, joined by spaces; "" when words were added
    heard: str  # what was heard instead; "" when the line's words were not heard
    sound: tuple[str, str] | None = None  # (line phoneme, heard phoneme), only for a sound on the sound list
    explain: str = ""  # that sound's explanation from the list


# turn: the roleplay's first try at a line; retry: 「다시 해 보기」 inside the roleplay; practice: the learner's lines
# again after the roleplay (spec roleplay-practice 4); shadow: following Ryan's lines after the roleplay (5)
Mode = Literal["turn", "retry", "practice", "shadow"]


class Attempt(BaseModel):
    n: int
    mode: Mode
    heard: str
    followed: bool
    issues: list[Issue]
    say_ko: str
    audio: list[str]
    timings: dict[str, float]
    # when it was recorded, ISO to the second; None on tries made before 2026-11-07 (ADR-0011)
    at: str | None = None
    # the line was not followed and teacher Ryan answered: not a turn, kept out of the end screen, the conversation
    # and the past-situation list (spec offscript-aside 6). Absent on tries from before 2026-11-07.
    aside: bool = False


class Roleplay(BaseModel):
    id: str
    created: str
    situation: str
    frame: Frame
    lines: list[ScriptLine]
    attempts: dict[int, list[Attempt]] = {}
    pos: int = 0
    # the first roleplay of its group when made by 「이 상황 다시 하기」 or by picking the same list line again;
    # None on that first one (ADR-0011, ADR-0013)
    origin: str | None = None
    # the situation topic's id (je_server.topics); None on roleplays made before topics, read as "other"
    # (spec situation-topics 7)
    topic: str | None = None
    # the list line's id (je_server.topics) when picked from a topic's list; runs of one pick share one group
    # (spec fixed-list-scripts 5, ADR-0013). None on other roleplays and on records from before.
    pick: str | None = None
    # a free talk has no script and stays out of the past-situation list, resuming, recent situations and copying;
    # records from before free talk are roleplays
    kind: Literal["roleplay", "talk"] = "roleplay"


class Saved(BaseModel):
    """A sentence the learner saved to practise (spec review-practice 5). The line's words, speaker and situation
    are read from the roleplay, not kept twice (ADR-0011)."""

    key: str  # sentence_key of the line's text: one entry per sentence
    rp_id: str
    idx: int
    at: str  # when it was saved, ISO to the second
