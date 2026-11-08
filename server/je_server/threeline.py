"""Machine checks for the three-line display.

Rules come from docs/guide/PRONUNCIATION_한글발음_세줄표시_20261105.md 「기계로 검사할 수 있는 것」:
rule 2 (one highlighted Hangul letter), rule 7 (highlight on the dictionary stress), rule 5 (the same
Korean in the Korean line and the reading line). When a line still fails after retries, `degrade`
removes the failing marks: no mark is better than a wrong one (PRD 「실패로 볼 것」 1).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from . import cmu
from .models import Syllable, ThreeLine, Word

REF = re.compile(r"\[\[(.*?)\]\]")
HANGUL = re.compile(r"^[가-힣]$")
REF_OK = re.compile(r"^[가-힣]+(-[가-힣]+)*$")


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


def _is_run(pieces: list[str], kos: list[str]) -> bool:
    n = len(pieces)
    return any(kos[i:i + n] == pieces for i in range(len(kos) - n + 1))


def check(text: str, three: ThreeLine) -> list[Problem]:
    problems: list[Problem] = []
    if _norm_words(text) != _norm_words(" ".join(word_text(w) for w in three.words)):
        problems.append(Problem("words", None, "the English syllables do not spell the line"))
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
    kos = [s.ko for w in three.words for s in w.syl if s.ko]
    for r in refs(three.reading):
        if not REF_OK.match(r) or not _is_run(r.split("-"), kos):
            problems.append(Problem("ref", None, f"[[{r}]] does not match the Korean line's syllables"))
    return problems


def plain(text: str) -> ThreeLine:
    return ThreeLine(words=[Word(syl=[Syllable(en=t, ko="", m="n")]) for t in text.split()], reading="")


def blank(three: ThreeLine) -> bool:
    """No Korean anywhere: what `plain` leaves. A list pick makes such a note again rather than reuse it (spec
    fixed-list-scripts 2)."""
    return not any(s.ko for w in three.words for s in w.syl)


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
