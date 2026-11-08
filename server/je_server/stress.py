"""Stress values kept for each recording, to run the 2026-11-05 stress test again once recordings pile up
(spec stress-log, docs/guide/PRONUNCIATION_녹음으로_강세평가_시험_20261105.md). Nothing here is pointed out to the
learner, and nothing leaves the Mac.

The judging follows the guide's second method: MFA vowel segments, and in each word the vowel whose loudness, pitch
and length add up highest is taken as stressed (3 dB, 2 semitones and 40 ms count one point each). Only values per
vowel are kept, never the pitch or loudness curves (ADR-0004).
"""
from __future__ import annotations

import difflib
import re
import statistics

from . import cmu
from .models import ThreeLine
from .threeline import word_text

FORMAT = 1
DB_STEP = 3.0
ST_STEP = 2.0
DUR_STEP = 0.04

# Closed-class words, read weak in a sentence by the rule the PRD's 「강세 기준」 states (content words strong, words
# like has, of, and weak). Negative forms (don't, can't, not, no) are left out: they are usually stressed.
FUNCTION_WORDS = frozenset("""
a an the
and but or nor so yet if than that because as though while
of to in on at for with from by about into onto over after before under between through during without up down out
off around
i me my mine you your yours he him his she her hers it its we us our ours they them their theirs
this these those what which who whom whose there here
am is are was were be been being have has had do does did
will would shall should can could may might must
i'm i've i'll i'd you're you've you'll you'd he's he'll he'd she's she'll she'd it's it'll we're we've we'll we'd
they're they've they'll they'd that's there's here's what's who's let's
""".split())


def is_vowel(phone: str) -> bool:
    return phone[-1:].isdigit()


def _points(v: dict, pitch: bool) -> float:
    return v["db"] / DB_STEP + v["dur"] / DUR_STEP + (v["st"] / ST_STEP if pitch else 0.0)


def judge(syl: list[dict]) -> tuple[int | None, float | None]:
    """The stressed vowel of a word and how far ahead it is of the next (the guide's confidence). A word with fewer
    than two vowels, or a vowel without loudness or length, is not judged. When one vowel has no pitch, the whole word
    is counted without pitch so its vowels are compared alike."""
    if len(syl) < 2 or any(v.get("db") is None or v.get("dur") is None for v in syl):
        return None, None
    pitch = all(v.get("st") is not None for v in syl)
    points = [_points(v, pitch) for v in syl]
    order = sorted(range(len(points)), key=lambda i: points[i], reverse=True)
    return order[0], points[order[0]] - points[order[1]]


def dict_stress(word: str, phones: list[str]) -> dict | None:
    """Where CMUdict puts the primary stress, among its pronunciations with as many vowels as the one MFA chose.
    More than one place (record, the noun and the verb) means the dictionary does not settle it."""
    count = sum(1 for p in phones if is_vowel(p))
    same = [p for p in cmu.prons(word) if cmu.vowel_count(p) == count]
    if not same:
        return None
    primary = sorted({i for p in same if (i := cmu.primary_index(p)) is not None})
    return {"primary": primary, "secondary": any(ph.endswith("2") for p in same for ph in p)}


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9']", "", text.lower().replace("’", "'"))


def line_marks(three: ThreeLine | None, heard: list[str]) -> list[dict | None]:
    """The three-line marks for each heard word: the strong syllable, the weak ones, a word stressed for meaning and
    the syllable count. Words are matched in order by their letters; a heard word the line does not have gets None."""
    marks: list[dict | None] = [None] * len(heard)
    if three is None:
        return marks
    line = [_norm(word_text(w)) for w in three.words]
    matcher = difflib.SequenceMatcher(None, line, [_norm(h) for h in heard], autojunk=False)
    for a, b, size in matcher.get_matching_blocks():
        for k in range(size):
            w = three.words[a + k]
            strong = [i for i, s in enumerate(w.syl) if s.m == "s"]
            marks[b + k] = {"s": strong[0] if strong else None, "w": [i for i, s in enumerate(w.syl) if s.m == "w"],
                            "emph": w.emph, "n": len(w.syl)}
    return marks


def _stressed(word: dict) -> dict | None:
    syl = word["syl"]
    primary = [v for v in syl if v["p"].endswith("1")]
    if primary:
        return primary[0]
    return syl[0] if len(syl) == 1 else None


def _z(values: list[float | None]) -> list[float]:
    """Standardised within the recording; a missing value counts as average (0)."""
    known = [v for v in values if v is not None]
    if len(known) < 2:
        return [0.0] * len(values)
    mean, sd = statistics.fmean(known), statistics.pstdev(known)
    return [0.0 if v is None or sd == 0 else (v - mean) / sd for v in values]


def sentence_scores(words: list[dict]) -> list[float | None]:
    """Each word's sentence stress: loudness, pitch and length of its stressed vowel, standardised among the words of
    the recording and added (the guide's 「문장 강세」). A word with no stressed vowel to measure gets None."""
    rows = [v if v is not None and v.get("db") is not None and v.get("dur") is not None else None
            for v in map(_stressed, words)]
    feats = {k: _z([v[k] if v is not None else None for v in rows]) for k in ("db", "st", "dur")}
    return [None if v is None else feats["db"][i] + feats["st"][i] + feats["dur"][i] for i, v in enumerate(rows)]
