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


Speaker = Literal["ryan", "user"]
Draft = list[tuple[Speaker, str]]


class ScriptLine(BaseModel):
    idx: int
    speaker: Speaker
    text: str
    kind: Literal["script", "reply"] = "script"
    three: ThreeLine | None = None
    audio: str | None = None  # sound key (sha256 hex) of Ryan reading the line
    # Sohee's Korean for the line and the sound key of her saying it, made only when asked (spec korean-translation 5)
    ko: str | None = None
    ko_audio: str | None = None


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


class Roleplay(BaseModel):
    id: str
    created: str
    situation: str
    frame: Frame
    lines: list[ScriptLine]
    attempts: dict[int, list[Attempt]] = {}
    pos: int = 0
    # the first roleplay of its group when made by 「이 상황 다시 하기」; None on that first one (ADR-0011)
    origin: str | None = None


class Saved(BaseModel):
    """A sentence the learner saved to practise (spec review-practice 5). The line's words, speaker and situation
    are read from the roleplay, not kept twice (ADR-0011)."""

    key: str  # sentence_key of the line's text: one entry per sentence
    rp_id: str
    idx: int
    at: str  # when it was saved, ISO to the second


class Said(BaseModel):
    text: str
    audio: str


class Offscript(BaseModel):
    """Claude's answer when the learner said something other than the line."""

    point_kind: Literal["none", "expression", "pronunciation"]
    point_ko: str
    meant: str
    heard_word: str
    reply_en: str
