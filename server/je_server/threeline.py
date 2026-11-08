"""Machine checks for the three-line display.

Rules come from docs/guide/PRONUNCIATION_한글발음_세줄표시_20261105.md 「기계로 검사할 수 있는 것」:
rule 2 (one highlighted Hangul letter), rule 7 (highlight on the dictionary stress), rule 5 (the same
Korean in the Korean line and the reading line). When a line still fails after retries, `degrade`
removes the failing marks: no mark is better than a wrong one (PRD 「실패로 볼 것」 1).

Rule 5 compares Hangul letters only. A sound in the reading may run over words with a space, put its hyphens
anywhere, or name one letter inside a syllable (스테이's 「테」): the Korean line shows no hyphens, so the learner sees
the same letters either way. Checking the hyphens against the syllables threw away 37 of 47 readings that failed in a
2026-11-08 first-try diagnosis (todo three_line_notes_degrade_rate).
"""
from __future__ import annotations

import difflib
import re
from dataclasses import dataclass
from typing import Literal

from . import cmu
from .models import Syllable, ThreeLine, Word

REF = re.compile(r"\[\[(.*?)\]\]")
HANGUL = re.compile(r"^[가-힣]$")
REF_OK = re.compile(r"^[가-힣]+([- ][가-힣]+)*$")  # Hangul runs joined by one hyphen or space


@dataclass(frozen=True)
class Problem:
    kind: Literal["words", "hi", "stress", "ref"]
    word: int | None
    detail: str


def _norm_words(text: str) -> list[str]:
    t = text.lower().replace("’", "'")
    return re.sub(r"[^a-z0-9' ]", "", t.replace("-", "")).split()


def word_text(w: Word) -> str:
    return "".join(s.en for s in w.syl)


def refs(reading: str) -> list[str]:
    return REF.findall(reading)


def korean_line(three: ThreeLine) -> str:
    out = ""
    for w in three.words:
        out += "".join(s.ko for s in w.syl)
        if not w.link:
            out += " "
    return out.strip()


def _word_gaps(want: list[str], got: list[str]) -> str:
    """What the given words lack or add against the line's, for the retry to fix (a model that runs two words into
    one sound may drop the small word between them, 2026-11-08 server test)."""
    out = []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(a=got, b=want, autojunk=False).get_opcodes():
        had, need = " ".join(got[i1:i2]), " ".join(want[j1:j2])
        if op == "insert":
            out.append(f"missing {need!r} " + (f"after {got[i1 - 1]!r}" if i1 else "at the start"))
        elif op == "delete":
            out.append(f"extra {had!r}")
        elif op == "replace":
            out.append(f"{had!r} should be {need!r}")
    return "; ".join(out)


def check(text: str, three: ThreeLine) -> list[Problem]:
    problems: list[Problem] = []
    want, got = _norm_words(text), _norm_words(" ".join(word_text(w) for w in three.words))
    if want != got:
        problems.append(Problem("words", None, f"the English syllables do not spell the line ({_word_gaps(want, got)}). "
                                "Give every word of the line its own entry in order, even a word swallowed in speech "
                                "(mark it w)"))
    for i, w in enumerate(three.words):
        for s in w.syl:
            if s.m == "s" and not (HANGUL.match(s.hi) and s.hi in s.ko):
                problems.append(Problem("hi", i, f"'{word_text(w)}': hi must be one Hangul letter inside ko"))
                break
            if s.m != "s" and s.hi:
                problems.append(Problem("hi", i, f"'{word_text(w)}': hi is only for strong syllables"))
                break
        strong = [j for j, s in enumerate(w.syl) if s.m == "s"]
        if w.emph or len(w.syl) < 2 or not strong:
            continue
        fits = [p for p in cmu.prons(word_text(w)) if cmu.vowel_count(p) == len(w.syl)]
        if fits and not any(strong == [cmu.primary_index(p)] for p in fits):
            problems.append(Problem("stress", i, f"'{word_text(w)}': the strong syllable is not the dictionary stress"))
    letters = "".join(s.ko for w in three.words for s in w.syl)
    for r in refs(three.reading):
        if not REF_OK.match(r) or re.sub(r"[- ]", "", r) not in letters:
            problems.append(Problem("ref", None, f"[[{r}]] is not written with the Korean line's letters"))
    return problems


def _vowel(letter: str) -> int:
    """The vowel (medial jamo) of a Hangul syllable letter."""
    return (ord(letter) - 0xAC00) // 28 % 21


def tidy(three: ThreeLine) -> ThreeLine:
    """The note with each strong syllable's highlight made a letter of its ko, where the model plainly meant one: it
    gave the letter without its final consonant (ko 딛, hi 디) and only one letter of ko has that vowel. Otherwise the
    note is as given and `check` finds the highlight. In a 2026-11-08 first-try diagnosis all 16 `hi` problems were
    this: the prompt's 「the letter that carries the vowel」 was read as the letter without the final consonant."""

    def fixed(s: Syllable) -> Syllable:
        if s.m != "s" or not HANGUL.match(s.hi) or s.hi in s.ko:
            return s
        same = [c for c in s.ko if HANGUL.match(c) and _vowel(c) == _vowel(s.hi)]
        return s.model_copy(update={"hi": same[0]}) if len(same) == 1 else s

    return three.model_copy(update={"words": [w.model_copy(update={"syl": [fixed(s) for s in w.syl]})
                                              for w in three.words]})


def plain(text: str) -> ThreeLine:
    return ThreeLine(words=[Word(syl=[Syllable(en=t, ko="", m="n")]) for t in text.split()], reading="")


def settled(three: ThreeLine) -> bool:
    """Korean and a reading: a note worth reusing. A list pick and a copy make one without them again (spec
    fixed-list-scripts 2): `plain` has no Korean, and the `ref` degrade drops the reading. A note that lost only some
    highlights (`hi`, `stress`) cannot be told from a good one and is reused."""
    return any(s.ko for w in three.words for s in w.syl) and bool(three.reading.strip())


def degrade(text: str, three: ThreeLine, problems: list[Problem]) -> ThreeLine:
    if not problems:
        return three
    if any(p.kind == "words" for p in problems):
        return plain(text)  # the syllables do not spell the line, so none of the marks can be trusted
    bad = {p.word for p in problems if p.kind in ("hi", "stress")}
    words = [
        Word(syl=[Syllable(en=s.en, ko=s.ko, m="n" if (i in bad and s.m == "s") else s.m,
                           hi="" if i in bad else s.hi) for s in w.syl], emph=w.emph, link=w.link)
        for i, w in enumerate(three.words)
    ]
    reading = "" if any(p.kind == "ref" for p in problems) else three.reading
    return ThreeLine(words=words, reading=reading)
