"""Hangul readings of the English words that open a Korean sentence, for the Korean voices (`tts.audio_key`).

2026-11-09 a second sentence of Ryan's Korean explanation opened with 「go는」, and it came out like 「종구는」.
Made through the voice worker, an opening 「go는」 came out as another word in all eleven takes (「조우는」,
「쪼우는」…); the same word after a Korean one (「그리고 go는」, 「여기서는 go는」) was 「고는」 in all seven, and so was
「고는」 written in Hangul. Opening a sentence, 「go to는」 went wrong in 7 of 7 takes, 「do는」 in 8 of 10, 「get은」 in 1
of 7; in Hangul all three were right in 4 of 4. The worker makes
each Korean sentence on its own (`tts_worker.split_parts`), so an English word that opens a sentence is the first
thing the model reads, with no Korean before it. Quotes did not help in general ('go' did, 'do' and 'get' did not),
and inside a sentence the model's own reading was right (「과거형 went를」, 「stop이 step처럼」), so only the opening
English words are changed. Readings follow the loanword spelling roughly, from CMUdict's first pronunciation.
"""
from __future__ import annotations

import re

from . import cmu

VOWELS = {
    "AA": "ㅏ", "AE": "ㅐ", "AH": "ㅓ", "AO": "ㅗ", "AW": "ㅏㅜ", "AY": "ㅏㅣ", "EH": "ㅔ", "ER": "ㅓ", "EY": "ㅔㅣ",
    "IH": "ㅣ", "IY": "ㅣ", "OW": "ㅗ", "OY": "ㅗㅣ", "UH": "ㅜ", "UW": "ㅜ",
}
ONSET = {
    "B": "ㅂ", "CH": "ㅊ", "D": "ㄷ", "DH": "ㄷ", "F": "ㅍ", "G": "ㄱ", "HH": "ㅎ", "JH": "ㅈ", "K": "ㅋ", "L": "ㄹ",
    "M": "ㅁ", "N": "ㄴ", "P": "ㅍ", "R": "ㄹ", "S": "ㅅ", "SH": "ㅅ", "T": "ㅌ", "TH": "ㅅ", "V": "ㅂ", "Z": "ㅈ",
    "ZH": "ㅈ",
}
GLIDE = {
    "W": {"ㅏ": "ㅘ", "ㅓ": "ㅝ", "ㅗ": "ㅝ", "ㅔ": "ㅞ", "ㅐ": "ㅙ", "ㅣ": "ㅟ", "ㅜ": "ㅜ"},
    "Y": {"ㅏ": "ㅑ", "ㅓ": "ㅕ", "ㅗ": "ㅛ", "ㅜ": "ㅠ", "ㅔ": "ㅖ", "ㅐ": "ㅒ", "ㅣ": "ㅣ"},
}
SHORT = {"AA", "AE", "AH", "EH", "IH", "UH"}  # a final p, t, k after these is a 받침 (cat 캣, book 북), else 트
STOP_FINAL = {"P": "ㅂ", "T": "ㅅ", "K": "ㄱ"}
NASAL_FINAL = {"M": "ㅁ", "N": "ㄴ", "NG": "ㅇ"}
LIQUID_NASAL = {"L", "R", "M", "N", "NG", "W", "Y"}
FRONT_VOWEL = {"CH": "ㅣ", "JH": "ㅣ", "SH": "ㅣ", "ZH": "ㅣ"}  # 치, 지, 시 rather than 츠, 즈, 스 at a word's end

INITIALS = "ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ"
MEDIALS = "ㅏㅐㅑㅒㅓㅔㅕㅖㅗㅘㅙㅚㅛㅜㅝㅞㅟㅠㅡㅢㅣ"
FINALS = ["", "ㄱ", "ㄲ", "ㄳ", "ㄴ", "ㄵ", "ㄶ", "ㄷ", "ㄹ", "ㄺ", "ㄻ", "ㄼ", "ㄽ", "ㄾ", "ㄿ", "ㅀ", "ㅁ", "ㅂ", "ㅄ",
          "ㅅ", "ㅆ", "ㅇ", "ㅈ", "ㅊ", "ㅋ", "ㅌ", "ㅍ", "ㅎ"]


def _compose(syllables: list[list[str]]) -> str:
    return "".join(chr(0xAC00 + (INITIALS.index(i) * 21 + MEDIALS.index(m)) * 28 + FINALS.index(f))
                   for i, m, f in syllables)


def _onset(phone: str, nxt: str | None) -> bool:
    """Whether the consonant starts the next syllable: before a vowel, a y, or (for k, g, h) a w (quick 퀵, but
    sweet 스위트). ng never does: it ends its syllable, and the vowel after it starts with ㅇ (singer 싱어; PR #77
    review, it had no initial and raised KeyError)."""
    if phone == "NG":
        return False
    return nxt in VOWELS or nxt == "Y" or (nxt == "W" and phone in ("K", "G", "HH"))


def hangul(phones: list[str]) -> str:
    phones = cmu.strip_stress(phones)
    syl: list[list[str]] = []  # [initial, medial, final]; medial "" while the onset waits for its vowel
    glide = ""
    for i, p in enumerate(phones):
        prev = phones[i - 1] if i else None
        nxt = phones[i + 1] if i + 1 < len(phones) else None
        if p in VOWELS:
            first, *rest = VOWELS[p]
            if glide:
                first, glide = GLIDE[glide][first], ""
            if syl and not syl[-1][1]:
                syl[-1][1] = first
            else:
                syl.append(["ㅇ", first, ""])
            syl += [["ㅇ", m, ""] for m in rest]
            if p == "ER" and nxt in VOWELS:
                syl.append(["ㄹ", "", ""])  # every 에버리
        elif p in ("W", "Y"):
            glide = p
            if not (syl and not syl[-1][1]):
                syl.append(["ㅇ", "", ""])
        elif _onset(p, nxt):
            if p == "L" and syl and syl[-1][1] and not syl[-1][2]:
                syl[-1][2] = "ㄹ"  # hello 헐로, play 플레이
            syl.append([ONSET[p], "", ""])
            if p == "SH":
                glide = "Y"  # she 시, show 쇼
        else:
            last = syl[-1] if syl and syl[-1][1] and not syl[-1][2] else None
            if p == "R" and prev in VOWELS:
                if nxt is None and prev != "AA":
                    syl.append(["ㅇ", "ㅓ", ""])  # there 데어, more 모어 (PR #77 review: there was 데, another word)
                continue  # park 파크, car 카
            if last and p in NASAL_FINAL:
                last[2] = NASAL_FINAL[p]
            elif last and p == "L":
                last[2] = "ㄹ"
            elif (last and p in STOP_FINAL and prev in SHORT
                  and (nxt is None or (nxt not in VOWELS and nxt not in LIQUID_NASAL))):
                last[2] = STOP_FINAL[p]  # get 겟, next 넥스트, but went 웬트
            elif p == "NG":
                syl.append(["ㅇ", "ㅡ", "ㅇ"])
            else:
                syl.append([ONSET[p], FRONT_VOWEL.get(p, "ㅡ"), ""])
    return _compose(syl)


def reading(word: str) -> str | None:
    prons = cmu.prons(word)
    return hangul(prons[0]) if prons else None


# an English word run at the start of a sentence (after . ? ! 。 and a space, where the worker makes each Korean sentence
# on its own; or a new line, where the voice module may start a new piece, by length), with Hangul after it on the
# same sentence: an English sentence of its own is left for the English voice. After a new line the word may also end up
# inside a piece; the Hangul is read right there too, so the rule does not try to tell which.
OPENING = re.compile(r"(^|(?<=[.?!。])\s+|\n\s*)([A-Za-z][A-Za-z']*(?: [A-Za-z][A-Za-z']*)*)(?=\s*[가-힣])")


def for_korean_voice(text: str) -> str:
    def read(m: re.Match) -> str:
        words = [reading(w) or w for w in m.group(2).split(" ")]
        return m.group(1) + " ".join(words)

    return OPENING.sub(read, text)
