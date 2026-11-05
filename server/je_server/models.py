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
