"""Match a transcript against the line and find changed sounds with CMUdict (spec 「평가」).

The Mac decides what to point out; Claude only puts it into Ryan's words (ADR-0004 「영향」).
"""
from __future__ import annotations

import re
from difflib import SequenceMatcher

from . import cmu, sounds
from .models import Issue

FOLLOW_MIN = 0.6  # word-level similarity at or above this counts as following the line
PRAISE_PHONES = {"R": "R", "L": "L", "F": "F", "V": "V", "TH": "TH", "DH": "TH", "Z": "Z"}
FUNCTION_WORDS = {"a", "an", "the", "of", "to", "for", "and", "or", "in", "on", "at", "is", "are", "was", "it",
                  "this", "that", "there", "their", "they", "them", "with", "from", "as", "be", "i", "you", "we"}


def words(text: str) -> list[str]:
    t = text.lower().replace("’", "'")
    return [w.strip("'") for w in re.findall(r"[a-z0-9']+", t) if w.strip("'")]


def similarity(target: str, heard: str) -> float:
    a, b = words(target), words(heard)
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b, autojunk=False).ratio()


def word_pairs(target: str, heard: str) -> list[tuple[str, str]]:
    a, b = words(target), words(heard)
    out = []
    for tag, i1, i2, j1, j2 in SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if tag == "replace" and i2 - i1 == j2 - j1:
            out += list(zip(a[i1:i2], b[j1:j2]))
    return out


def sound_pairs(target_word: str, heard_word: str) -> list[tuple[str, str]]:
    best: tuple[int, list[tuple[str, str]]] | None = None
    for tp in cmu.prons(target_word):
        for hp in cmu.prons(heard_word):
            a, b = cmu.strip_stress(tp), cmu.strip_stress(hp)
            edits, pairs = 0, []
            for tag, i1, i2, j1, j2 in SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
                if tag == "equal":
                    continue
                edits += max(i2 - i1, j2 - j1)
                if tag == "replace" and i2 - i1 == j2 - j1:
                    pairs += list(zip(a[i1:i2], b[j1:j2]))
            if best is None or edits < best[0]:
                best = (edits, pairs)
    return best[1] if best else []


def find_issues(target: str, heard: str, limit: int) -> list[Issue]:
    out: list[Issue] = []
    seen: set[frozenset] = set()
    for tw, hw in word_pairs(target, heard):
        for a, b in sound_pairs(tw, hw):
            s = sounds.find(a, b)
            if s and frozenset((a, b)) not in seen:
                seen.add(frozenset((a, b)))
                out.append(Issue(target=tw, heard=hw, sound=(a, b), explain=s.explain))
                break
        if len(out) >= limit:
            break
    return out


def praise_candidates(target: str, heard: str) -> list[str]:
    a, b = words(target), words(heard)
    sm = SequenceMatcher(None, a, b, autojunk=False)
    out = []
    for tag, i1, i2, _, _ in sm.get_opcodes():
        if tag != "equal":
            continue
        for w in a[i1:i2]:
            if w in FUNCTION_WORDS:
                continue
            phones = {p for pron in cmu.prons(w)[:1] for p in cmu.strip_stress(pron)}
            hit = next((PRAISE_PHONES[p] for p in PRAISE_PHONES if p in phones), None)
            if hit and len(out) < 2:
                out.append(f"{w}의 {hit} 소리를 알아듣게 냈어요")
    if not word_pairs(target, heard) and similarity(target, heard) == 1.0:
        out.append("문장 전체를 또렷하게 말했어요")
    elif similarity(target, heard) >= 0.8:
        out.append("대사를 거의 다 알아듣게 말했어요")
    out.append("끝까지 자신 있게 말했어요")
    return out
