"""Sohee chance (spec free-talk-design 9): what Claude is given for a hint on Ryan's line, and the Mac's checks on what
comes back. Claude writes the hint; the Mac keeps it short and easy: two or three English openers of a few words that
end in …, one Korean line, and one short full sentence that starts with an opener, so the second step matches the
first (2026-11-09 user)."""
from __future__ import annotations

import re

from .models import Hint, Roleplay, ScriptLine

HANGUL = re.compile(r"[가-힣]")
STARTERS = (2, 3)  # how many openers; more are cut to the first three
STARTER_WORDS = (2, 6)  # words in an opener, … left out
MEANING_MAX = 80  # letters in the Korean line
FULL_WORDS = 12
DOTS = "…"
# quotes the prompt asks not to write; single quotes only at the ends, inside they are English apostrophes (I'm)
QUOTES_ANYWHERE = str.maketrans("", "", "\"“”「」『』")
QUOTES_AT_ENDS = "'‘’"
_TRAILING_DOTS = re.compile(r"\s*(?:\.\.\.|…)$")


def _tidy(text: str) -> str:
    """One line without the quotes the prompt asks not to write."""
    return " ".join(text.translate(QUOTES_ANYWHERE).split()).strip(QUOTES_AT_ENDS).strip()


def _fold(text: str) -> str:
    """For comparing a full sentence with an opener: case and the curly apostrophe aside."""
    return text.replace("’", "'").lower()


def _starter(text: str) -> str | None:
    """An opener with its dots as one …, or None when it breaks a rule."""
    s = _TRAILING_DOTS.sub(DOTS, _tidy(text))
    if not s.endswith(DOTS) or HANGUL.search(s):
        return None
    return s if STARTER_WORDS[0] <= len(s[: -len(DOTS)].split()) <= STARTER_WORDS[1] else None


def check(data: object) -> Hint | None:
    """The hint in Claude's answer (prompts.HINT_SCHEMA), tidied, or None when it breaks a rule: then it is asked
    again (`Claude.hint`)."""
    if not isinstance(data, dict):
        return None
    meaning, raw, full = data.get("meaning_ko"), data.get("starters"), data.get("full")
    if not (isinstance(meaning, str) and isinstance(full, str) and isinstance(raw, list)):
        return None
    if not all(isinstance(s, str) for s in raw[: STARTERS[1]]):
        return None
    starters = [_starter(s) for s in raw[: STARTERS[1]]]
    if len(starters) < STARTERS[0] or None in starters:
        return None
    meaning, full = _tidy(meaning), _tidy(full)
    if not HANGUL.search(meaning) or len(meaning) > MEANING_MAX:
        return None
    if HANGUL.search(full) or len(full.split()) > FULL_WORDS:
        return None
    # the opener without its … and a comma before it (「Not really,…」 → 「Not really. I was busy.」)
    stems = [_fold(s[: -len(DOTS)].rstrip().rstrip(",").rstrip()) for s in starters]
    if not any(_fold(full).startswith(stem) for stem in stems):
        return None
    return Hint(meaning_ko=meaning, starters=starters, full=full)


def _heard(line: ScriptLine) -> str:
    """Ryan's reply as the learner heard it: when cut off, the sentences heard (no note, unlike `talk.messages`)."""
    if line.heard_upto is None:
        return line.text
    return " ".join(p.text for p in (line.parts or [])[: line.heard_upto])


def conversation(rp: Roleplay, upto: int) -> list[dict]:
    """What Claude is given for a hint on line `upto`: the talk up to it as text only, Ryan's replies and my turns
    (a Korean turn as it was heard). Old records' `help` lines, the fixes and a reply cut before a word are left
    out. Never the recordings (ADR-0004)."""
    out: list[dict] = []
    for line in rp.lines[: upto + 1]:
        if line.kind == "reply" and line.speaker == "ryan":
            who, said = "라이언", _heard(line)
        elif line.kind in ("turn", "ask"):
            who, said = "학습자", line.text
        else:
            continue
        if said:
            out.append({"말한 사람": who, "말": said})
    return out
