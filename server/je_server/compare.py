"""Match a transcript against the line and find changed sounds with CMUdict (spec 「평가」).

The Mac decides what to point out; Claude only puts it into Ryan's words (ADR-0004 「영향」).
Every place the transcript differs from the line is a point, except notation the transcriber chose (numbers,
short forms, joined words) and restarts or fillers (spec 「평가」 2, 3).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher

from . import cmu, sounds
from .models import Issue

FOLLOW_MIN = 0.6  # word-level similarity at or above this counts as following the line
SOUND_LETTERS = {"R": "R", "L": "L", "F": "F", "P": "P", "V": "V", "B": "B", "TH": "TH", "DH": "TH", "S": "S",
                 "D": "D", "Z": "Z", "JH": "J"}  # CMUdict phoneme → how Ryan names it


FILLERS = frozenset({"um", "uh", "uhm", "umm", "er", "erm", "hmm", "mm"})
SPAN_SOUND_MAX_EDITS = 2  # inside a span whose word count changed, only this close a word pair gets a sound
_ONES = ("zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen "
         "seventeen eighteen nineteen").split()
_TENS = "_ _ twenty thirty forty fifty sixty seventy eighty ninety".split()
_SHORT = {"wanna": "want to", "gonna": "going to", "ok": "okay"}


def _number(n: int) -> str:
    if n < 20:
        return _ONES[n]
    tens, ones = divmod(n, 10)
    return _TENS[tens] + (f" {_ONES[ones]}" if ones else "")


def words(text: str) -> list[str]:
    """Lowercase words with the transcriber's notation evened out: 10 and ten, $5 and five dollars, 11 AM and
    eleven a.m., 9:00 and nine o'clock, 5:05 and five oh five, wanna and want to, OK and okay are the same words."""
    t = text.lower().replace("’", "'")
    t = re.sub(r"(?<=\d),(?=\d{3})", "", t)  # 1,000 is one number
    t = re.sub(r"\b([ap])\.?m\b\.?", r"\1m", t)
    t = re.sub(r"\$(\d+)", lambda m: f"{m[1]} dollar" + ("" if m[1] == "1" else "s"), t)
    t = re.sub(r"(\d+)%", r"\1 percent", t)
    t = re.sub(r"\b(\d{1,2}):00\b", r"\1", t)  # 9:00 is nine (o'clock is dropped below)
    out: list[str] = []
    for w in re.findall(r"[a-z0-9']+", t):
        w = w.strip("'")
        if not w:
            continue
        if w == "o'clock":
            continue
        if w.isdigit() and len(w) == 2 and w[0] == "0":  # the 05 of 5:05 is "oh five"
            out += ["oh", _ONES[int(w[1])]]
        elif w.isdigit() and int(w) < 100:
            out += _number(int(w)).split()
        else:
            out += _SHORT.get(w, w).split()
    return out


def similarity(target: str, heard: str) -> float:
    a, b = words(target), words(heard)
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b, autojunk=False).ratio()


def sound_pairs(target_word: str, heard_word: str) -> list[tuple[str, str]]:
    d = sound_diff(target_word, heard_word)
    return d[1] if d else []


def sound_diff(target_word: str, heard_word: str) -> tuple[int, list[tuple[str, str]]] | None:
    """(changed phonemes, one-to-one phoneme swaps) for the closest pair of dictionary pronunciations, or None
    when a word is not in CMUdict."""
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
    return best


@dataclass
class Comparison:
    diffs: list[Issue]  # every difference, in the line's order
    matched: int  # line words heard right
    total: int  # line words
    matched_words: set[str] = field(default_factory=set)


def _listed(target_word: str, heard_word: str, max_edits: int | None = None) -> tuple[tuple[str, str], str] | None:
    d = sound_diff(target_word, heard_word)
    if d is None or (max_edits is not None and d[0] > max_edits):
        return None
    for a, b in d[1]:
        s = sounds.find(a, b)
        if s:
            return (a, b), s.explain
    return None


def _issue(target: list[str], heard: list[str], found: tuple[tuple[str, str], str] | None) -> Issue:
    return Issue(target=" ".join(target), heard=" ".join(heard),
                 sound=found[0] if found else None, explain=found[1] if found else "")


def _restart(line: list[str], at: int, added: list[str]) -> bool:
    """Added words that repeat the line's words right before or after them: the learner started over."""
    n = len(added)
    return (at >= n and line[at - n:at] == added) or line[at:at + n] == added


def compare(target: str, heard: str) -> Comparison:
    a = words(target)
    b = [w for w in words(heard) if w not in FILLERS or w in a]
    diffs: list[Issue] = []
    matched: set[str] = set()
    count = 0
    for tag, i1, i2, j1, j2 in SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        ta, hb = a[i1:i2], b[j1:j2]
        if tag == "equal" or "".join(ta) == "".join(hb):  # checkout and check out
            count += len(ta)
            matched.update(ta)
        elif tag == "insert" and _restart(a, i1, hb):
            continue
        elif tag == "replace" and len(ta) == len(hb):
            diffs += [_issue([t], [h], _listed(t, h)) for t, h in zip(ta, hb)]
        else:
            found = next((f for t in ta for h in hb if (f := _listed(t, h, SPAN_SOUND_MAX_EDITS))), None)
            diffs.append(_issue(ta, hb, found))
    return Comparison(diffs=diffs, matched=count, total=len(a), matched_words=matched)


def find_issues(target: str, heard: str, limit: int) -> list[Issue]:
    """At most `limit` differences, front of the line first. Past the limit a second issue with the same listed
    sound is skipped, so Ryan does not give the same sound tip twice (spec 「평가」 5)."""
    diffs = compare(target, heard).diffs
    if len(diffs) <= limit:
        return diffs
    out: list[Issue] = []
    seen: set[frozenset] = set()
    for i in diffs:
        if i.sound and frozenset(i.sound) in seen:
            continue
        if i.sound:
            seen.add(frozenset(i.sound))
        out.append(i)
        if len(out) >= limit:
            break
    return out


def issue_ko(i: Issue) -> str:
    """The end screen's line for a point, worded like Ryan's: what was heard, never what was said."""
    if not i.target:
        return f"대사에 없는 「{i.heard}」 들렸어요"
    if not i.heard:
        return f"「{i.target}」 → 들리지 않았어요"
    return f"「{i.target}」 → 「{i.heard}」처럼 들렸어요"


def praise_candidates(target: str, heard: str, before: list[Issue], limit: int = 2) -> list[str]:
    """Only what the Mac checked (spec 「잘한 점 후보」): a point from the last followed try at this line that is
    gone now, then what matching the line showed. Never a sound just because the word was written right."""
    c = compare(target, heard)
    out: list[str] = []
    now = {w for d in c.diffs for w in d.target.split()}
    for i in before:
        words_then = set(i.target.split())
        # gone only if no current difference touches these words; matched_words alone ignores position, and a
        # word can appear twice in the line
        if not words_then or words_then & now or not words_then <= c.matched_words:
            continue
        if i.sound:
            out.append(f"이번에는 {i.target}의 {SOUND_LETTERS.get(i.sound[0], i.sound[0])} 소리가 제대로 났어요")
        else:
            out.append(f"이번에는 {i.target}, 대사대로 들렸어요")
    if not c.diffs:
        out.append("대사를 빠짐없이 알아듣게 말했어요")
    elif c.matched == 0:
        pass
    elif len(c.diffs) <= limit:
        out.append("나머지 낱말은 다 알아들었어요")
    elif c.matched * 2 > c.total:
        out.append("대사의 낱말 대부분을 알아들었어요")
    else:
        out.append(f"대사 {c.total}낱말 가운데 {c.matched}낱말을 알아들었어요")
    return out
