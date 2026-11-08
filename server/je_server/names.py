"""Names the dictionary does not have, compared by syllable (spec teacher-answer-context 3).

The transcriber does not know Korean place names written in Latin letters (Chungmuro) and spells them its own way, or
writes them in Hangul. CMUdict has no pronunciation for them either, so the Mac cannot compare sounds. A name heard with
as many syllables, each close in sound, is the transcriber's spelling; a syllable dropped, added or changed is pointed
out (the user, 2026-11-08: 「충무로인데 충무공으로 한다든지」 must not pass).

Syllables follow the Revised Romanization of Korean: an onset, a vowel (with its y or w glide) and a final consonant.
Between vowels the next syllable takes the longest onset it can (chungmuro: chung, mu, ro). Hangul is romanized first
and split the same way, so a name written either way splits alike.
"""
from __future__ import annotations

import re

from . import cmu

# Revised Romanization, letter by letter, for the 19 onsets, 21 vowels and 28 finals of a Hangul syllable
_ONSETS_RR = ("g", "kk", "n", "d", "tt", "r", "m", "b", "pp", "s", "ss", "", "j", "jj", "ch", "k", "t", "p", "h")
_VOWELS_RR = ("a", "ae", "ya", "yae", "eo", "e", "yeo", "ye", "o", "wa", "wae", "oe", "yo", "u", "wo", "we", "wi", "yu",
              "eu", "ui", "i")
_FINALS_RR = ("", "k", "k", "k", "n", "n", "n", "t", "l", "k", "m", "l", "l", "l", "p", "l", "m", "p", "p", "t", "t",
              "ng", "t", "t", "k", "t", "p", "t")

# vowel letters a transcriber writes for one Korean vowel, longest first (Revised Romanization and common spellings)
_VOWEL_UNITS = sorted(("a", "e", "i", "o", "u", "ae", "eo", "eu", "ui", "oe", "oo", "ee", "ay", "ey", "ai", "ei",
                       "ya", "yae", "yeo", "ye", "yo", "yu", "wa", "wae", "wo", "we", "wi"), key=len, reverse=True)
_ONSETS = frozenset(("g", "k", "kk", "gg", "c", "q", "ch", "tch", "j", "jj", "z", "d", "t", "tt", "dd", "n", "r", "l",
                     "rr", "ll", "m", "b", "p", "pp", "bb", "f", "v", "s", "ss", "sh", "h"))
# sounds a transcriber spells one for another: plain, tense and aspirated onsets, ㅓ written u or o, ㅐ and ㅔ
_ONSET_CLASS = {**dict.fromkeys(("g", "k", "kk", "gg", "c", "q"), "G"), **dict.fromkeys(("d", "t", "tt", "dd"), "D"),
                **dict.fromkeys(("b", "p", "pp", "bb", "f", "v"), "B"),
                **dict.fromkeys(("j", "jj", "ch", "tch", "z"), "J"), **dict.fromkeys(("s", "ss", "sh"), "S"),
                # ㄹ after a final consonant is said ㄴ (종로 is Jongno): r and n are one group at an onset
                **dict.fromkeys(("r", "l", "rr", "ll", "n"), "R")}
_VOWEL_CLASS = {"a": "A", **dict.fromkeys(("ae", "e", "ay", "ey", "ai", "ei", "oe"), "E"),
                **dict.fromkeys(("i", "ee", "ui"), "I"), **dict.fromkeys(("o", "eo", "u", "eu", "oo"), "O")}
_FINAL_CLASS = {**dict.fromkeys(("k", "g", "c", "ck", "kk", "gg"), "K"), "n": "N", "ng": "NG",
                **dict.fromkeys(("t", "d", "s"), "T"), **dict.fromkeys(("l", "r"), "L"), "m": "M",
                **dict.fromkeys(("p", "b"), "P")}
# final consonants heard one for another: the nasals n, ng and m (the last one runs into the next onset, 감기 said
# 강기), and one before a nasal said as that nasal (학년 is hangnyeon, 합니다 is hamnida, 걷는 is geonneun)
_FINALS_ALIKE = {frozenset(p) for p in (("N", "NG"), ("M", "NG"), ("M", "N"), ("K", "NG"), ("P", "M"), ("T", "N"))}

_PARTS = re.compile(r"[yw]?[aeiou]+(?:y(?![aeiou]))?|(?:[^aeiouyw]|[yw](?![aeiou]))+")
HANGUL_WORD = re.compile(r"[가-힣]+")

Syllable = tuple[str, str, str]  # onset, vowel (with its glide), final consonant


def romanize(text: str) -> str:
    """Hangul syllables letter by letter in Revised Romanization; anything else stays."""
    out = []
    for ch in text:
        n = ord(ch) - 0xAC00
        if 0 <= n < 11172:
            out.append(_ONSETS_RR[n // 588] + _VOWELS_RR[n % 588 // 28] + _FINALS_RR[n % 28])
        else:
            out.append(ch)
    return "".join(out)


def _vowels(run: str) -> list[str]:
    out = []
    while run:
        unit = next((u for u in _VOWEL_UNITS if run.startswith(u)), run[0])
        out.append(unit)
        run = run[len(unit):]
    return out


def syllables(word: str) -> list[Syllable] | None:
    """The word's syllables, Hangul romanized first; None when it is not letters only or has no vowel."""
    w = romanize(word.lower())
    if not w.isascii() or not w.isalpha():
        return None
    out: list[list[str]] = []
    onset = ""
    for part in _PARTS.findall(w):
        if part[0] in "aeiou" or (part[0] in "yw" and len(part) > 1):
            for v in _vowels(part):
                out.append([onset, v, ""])
                onset = ""
            continue
        if not out:  # before the first vowel
            onset = part
            continue
        # between vowels the next syllable takes the longest onset it can; the rest ends the syllable before
        cut = next((k for k in range(max(0, len(part) - 3), len(part)) if part[k:] in _ONSETS), len(part) - 1)
        out[-1][2], onset = part[:cut], part[cut:]
    if not out:
        return None
    if onset:  # after the last vowel
        out[-1][2] += onset
    return [(a, b, c) for a, b, c in out]


def _alike(a: Syllable, b: Syllable) -> bool:
    """One syllable heard close enough: the same onset and vowel group, and the final consonant the same, missing on
    one side or one that runs into the next sound."""
    if _ONSET_CLASS.get(a[0], a[0]) != _ONSET_CLASS.get(b[0], b[0]):
        return False
    va, vb = a[1].lstrip("yw") or a[1], b[1].lstrip("yw") or b[1]
    if _VOWEL_CLASS.get(va, va) != _VOWEL_CLASS.get(vb, vb):
        return False
    fa, fb = _FINAL_CLASS.get(a[2], a[2]), _FINAL_CLASS.get(b[2], b[2])
    return not fa or not fb or fa == fb or frozenset((fa, fb)) in _FINALS_ALIKE


def same_name(target: str, heard: str) -> bool:
    """The heard words, joined, are the line's name as the transcriber spelled it: as many syllables, each alike."""
    a, b = syllables(target), syllables(heard.replace(" ", ""))
    return a is not None and b is not None and len(a) == len(b) and all(map(_alike, a, b))


def is_name(word: str) -> bool:
    """A line word the dictionary does not have, in Latin letters: a name such as a Korean place (lowercase word)."""
    return word.isascii() and word.isalpha() and not cmu.prons(word) and syllables(word) is not None
