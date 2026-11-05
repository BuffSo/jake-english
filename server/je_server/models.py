"""Data shapes shared by the server and the app (contract/ holds JSON examples)."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

Mark = Literal["s", "w", "n"]  # s: yellow (strong), w: small gray (weak), n: as is


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


class Issue(BaseModel):
    target: str
    heard: str
    sound: tuple[str, str]
    explain: str


class Attempt(BaseModel):
    n: int
    mode: Literal["turn", "retry"]
    heard: str
    followed: bool
    issues: list[Issue]
    say_ko: str
    audio: list[str]
    timings: dict[str, float]


class Roleplay(BaseModel):
    id: str
    created: str
    situation: str
    frame: Frame
    lines: list[ScriptLine]
    attempts: dict[int, list[Attempt]] = {}
    pos: int = 0


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
