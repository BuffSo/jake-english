"""Choosing the corrections after a free talk (spec free-talk-design 7).

Claude picks at most three places in my English turns; the Mac decides which of them to keep (ADR-0004 「영향」: what
to point out is the Mac's decision). Only pointing out what is surely wrong is the rule (「확실한 것만 짚는다」), so an
item that does not hold up against the turns is dropped.

A pronunciation guess is kept only when the two words' dictionary sounds differ by two or fewer and the changed sound
is on the sound list; the list's explanation is then added word for word (speaking-practice spec 「소리 설명 목록」),
never Claude's own.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .compare import listed_sound, words
from .models import Roleplay, ScriptLine
from .review import sentence_key

MAX_FIXES = 3
FIXED_MAX_WORDS = 12
_HANGUL = re.compile(r"[가-힣]")


@dataclass(frozen=True)
class Found:
    of: int  # the line number of my turn
    said: str
    fixed: str
    why_ko: str


def _guess(sound: object, said: str) -> str | None:
    """The sound-list explanation sentence for a guess that holds up, else None."""
    if not isinstance(sound, dict):
        return None
    heard, meant, say = (str(sound.get(k) or "").strip() for k in ("heard", "meant", "say_ko"))
    if len(words(heard)) != 1 or len(words(meant)) != 1 or heard.lower() not in words(said):
        return None
    listed = listed_sound(meant, heard)
    if listed is None or not _HANGUL.search(say) or "처럼 들렸" not in say or "말했" in say:
        return None
    # the sentence names both words (Haiku once wrote the template "meant가 heard처럼 들렸어요." as it stood)
    if meant.lower() not in say.lower() or heard.lower() not in say.lower():
        return None
    return " ".join([say, listed[1]])


def check(items: list[dict], turns: dict[int, str]) -> list[Found]:
    """Keep the items that hold up. `turns` is my English turns: line number to what was heard."""
    seen: set[int] = set()
    kept: list[Found] = []
    for it in items:
        idx, said, fixed = it.get("idx"), str(it.get("said") or ""), str(it.get("fixed") or "")
        if idx not in turns or idx in seen:
            continue
        seen.add(idx)
        if not said.strip() or sentence_key(said) not in sentence_key(turns[idx]):
            continue
        if not fixed.strip() or len(words(fixed)) > FIXED_MAX_WORDS or sentence_key(fixed) == sentence_key(said):
            continue
        why = str(it.get("why_ko") or "").strip()
        guess = _guess(it.get("sound"), said)
        if guess is not None:
            why = " ".join(p for p in (why, guess) if p)
        elif not why or not _HANGUL.search(why):
            continue
        kept.append(Found(idx, said, fixed, why))
    return sorted(kept, key=lambda f: f.of)[:MAX_FIXES]


def line_before(rp: Roleplay, idx: int) -> ScriptLine | None:
    """The line to play before practising line `idx`: for a fix line, Ryan's last English line before the turn it
    fixes (Ryan's Korean `help` lines are not part of the talk, so they are walked past, like the app's `savedBefore`)."""
    line = rp.lines[idx] if 0 <= idx < len(rp.lines) else None
    if line is None or line.fix is None:
        return rp.lines[idx - 1] if 1 <= idx <= len(rp.lines) else None
    at = line.fix.of - 1
    while 0 <= at < len(rp.lines) and not (rp.lines[at].speaker == "ryan" and rp.lines[at].kind != "help"):
        at -= 1
    return rp.lines[at] if 0 <= at < len(rp.lines) else None
