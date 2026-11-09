"""Sohee chance (spec free-talk-design 9): what Claude is given for a hint on Ryan's line, and the Mac's checks on what
comes back. Claude writes the hint; the Mac keeps it short and easy: two or three English openers of a few words that
end in …, one Korean line, and one short full sentence that starts with an opener, so the second step matches the
first (2026-11-09 user)."""
from __future__ import annotations

import re
from typing import Any

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
_WORD = re.compile(r"[a-z0-9']+")
# an opener of this many words or more found word for word in Ryan's line says his words back, not an answer (spec 9
# 「첫마디가 라이언의 말을 그대로 되풀이하거나」); shorter ones (「I usually…」 to 「What do you usually do?」) are how
# an answer starts
REPEAT_WORDS = 3
UNSHOWN = ("full", "full_three")  # what a hint's answer to the app leaves out until 「전체 문장 보기」


def _tidy(text: str) -> str:
    """One line without the quotes the prompt asks not to write."""
    return " ".join(text.translate(QUOTES_ANYWHERE).split()).strip(QUOTES_AT_ENDS).strip()


def _fold(text: str) -> str:
    """For comparing a full sentence with an opener: case and the curly apostrophe aside."""
    return text.replace("’", "'").lower()


def _words(text: str) -> list[str]:
    return _WORD.findall(_fold(text))


def _repeats(starter: str, ryan: list[str]) -> bool:
    """Whether the opener (with its …) is `REPEAT_WORDS` or more words found in a row in Ryan's line, case and
    punctuation aside."""
    said = _words(starter[: -len(DOTS)])
    n = len(said)
    return n >= REPEAT_WORDS and any(ryan[i:i + n] == said for i in range(len(ryan) - n + 1))


def _starter(text: str) -> str | None:
    """An opener with its dots as one …, or None when it breaks a rule."""
    s = _TRAILING_DOTS.sub(DOTS, _tidy(text))
    if not s.endswith(DOTS) or HANGUL.search(s):
        return None
    return s if STARTER_WORDS[0] <= len(s[: -len(DOTS)].split()) <= STARTER_WORDS[1] else None


def check(data: object, ryan: str = "") -> Hint | None:
    """The hint in Claude's answer (prompts.HINT_SCHEMA), tidied, or None when it breaks a rule: then it is asked
    again (`Claude.hint`). `ryan`: his line the hint is for; an opener that repeats it is dropped (`_repeats`), and
    fewer than two left is a rule broken."""
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
    heard = _words(ryan)
    starters = [s for s in starters if not _repeats(s, heard)]
    if len(starters) < STARTERS[0]:
        return None
    meaning, full = _tidy(meaning), _tidy(full)
    if not HANGUL.search(meaning) or len(meaning) > MEANING_MAX:
        return None
    if HANGUL.search(full) or len(full.split()) > FULL_WORDS:
        return None
    # the opener without its … and a comma before it (「Not really,…」 → 「Not really. I was busy.」), as whole words:
    # 「Yes, I…」 does not start 「Yes, it was fun.」 (final review)
    stems = [_fold(s[: -len(DOTS)].rstrip().rstrip(",").rstrip()) for s in starters]
    if not any(re.match(re.escape(stem) + r"(?![a-z0-9'])", _fold(full)) for stem in stems):
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
        if line.dropped:
            continue
        if line.kind == "reply" and line.speaker == "ryan":
            who, said = "라이언", _heard(line)
        elif line.kind in ("turn", "ask"):
            who, said = "학습자", line.text
        else:
            continue
        if said:
            out.append({"말한 사람": who, "말": said})
    return out


def hide_unshown(data: Any) -> Any:
    """An answer to the app (JSON, as dumped) without the full sentence of a hint not shown yet, nor its notes: the app
    gets it only from 「전체 문장 보기」 on (spec 9). Every route that sends lines passes its answer through this; the
    record itself keeps the sentence (`Store.save` writes the model). `data` is not changed."""
    if isinstance(data, list):
        return [hide_unshown(v) for v in data]
    if not isinstance(data, dict):
        return data
    out = {k: hide_unshown(v) for k, v in data.items()}
    hint = out.get("hint")
    if isinstance(hint, dict) and not hint.get("full_shown"):
        out["hint"] = {k: v for k, v in hint.items() if k not in UNSHOWN}
    return out
