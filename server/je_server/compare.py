"""Match a transcript against the line and find changed sounds with CMUdict (spec 「평가」).

The Mac decides what to point out; Claude only puts it into Ryan's words (ADR-0004 「영향」).
Every place the transcript differs from the line is a point, except notation the transcriber chose (numbers,
short forms, joined words) and restarts or fillers (spec 「평가」 2, 3).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from itertools import product

from . import cmu, sounds
from .models import Issue

FOLLOW_MIN = 0.6  # word-level similarity at or above this counts as following the line
SOUND_LETTERS = {"R": "R", "L": "L", "F": "F", "P": "P", "V": "V", "B": "B", "TH": "TH", "DH": "TH", "S": "S",
                 "D": "D", "Z": "Z", "JH": "J"}  # CMUdict phoneme → how Ryan names it


FILLERS = frozenset({"um", "uh", "uhm", "umm", "er", "erm", "hmm", "mm"})
# Only a word pair this close in dictionary sounds gets a listed sound, one to one or inside a span whose word count
# changed. Farther apart, the transcriber heard another word, not one sound said differently: a number written as an
# unrelated word swaps several sounds, and one of them may be on the list (guide PRONUNCIATION_따라말하기_짚기
# 「남은 것」, 2026-11-08).
SOUND_MAX_EDITS = 2
_ONES = ("zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen "
         "seventeen eighteen nineteen").split()
_TENS = "_ _ twenty thirty forty fifty sixty seventy eighty ninety".split()
_SHORT = {"wanna": "want to", "gonna": "going to", "ok": "okay"}
_AFTER_A = frozenset({"hundred", "thousand", "dollar"})
MAX_READING_SETS = 64  # numbers in a line and its transcript; past this, each is read the first way


def _number(n: int) -> str:
    """Words for 0 <= n < 1,000,000, the way the transcriber's digits are read out (1,000 is one thousand)."""
    if n < 20:
        return _ONES[n]
    if n < 100:
        tens, ones = divmod(n, 10)
        return _TENS[tens] + (f" {_ONES[ones]}" if ones else "")
    for size, name in ((1000, "thousand"), (100, "hundred")):
        if n >= size:
            head, rest = divmod(n, size)
            return f"{_number(head)} {name}" + (f" {_number(rest)}" if rest else "")
    raise AssertionError(n)


_ORDINAL = {"one": "first", "two": "second", "three": "third", "five": "fifth", "eight": "eighth", "nine": "ninth",
            "twelve": "twelfth"}


def _ordinal(n: int) -> str:
    """2nd is second, 21st is twenty first."""
    *head, last = _number(n).split()
    last = _ORDINAL.get(last) or (last[:-1] + "ieth" if last.endswith("y") else last + "th")
    return " ".join([*head, last])


def _readings(n: int) -> tuple[str, ...]:
    """The ways a number is read out: the cardinal first (270 is two hundred seventy), then from 100 to 9999 the
    pairs people say for sizes, rooms and years (two seventy, three oh five, twenty seventeen, fifteen hundred).
    The voice may read the line's digits either way, and the learner follows the voice (phone test, 2026-11-07)."""
    out = [_number(n)]
    if 100 <= n <= 9999:
        head, tail = divmod(n, 100)
        if tail == 0:
            if n >= 1000 and head % 10:  # 1500 is fifteen hundred; 2000 stays two thousand
                out.append(f"{_number(head)} hundred")
        elif tail < 10:
            out.append(f"{_number(head)} oh {_ONES[tail]}")
        else:
            out.append(f"{_number(head)} {_number(tail)}")
    return tuple(out)


Token = str | tuple[str, ...]  # a word, or the readings of a number


def _tokens(text: str) -> list[Token]:
    t = text.lower().replace("’", "'")
    t = re.sub(r"(?<=\d),(?=\d{3})", "", t)  # 1,000 is one number
    t = re.sub(r"\b([ap])\.?m\b\.?", r"\1m", t)
    t = re.sub(r"\$(\d+)", lambda m: f"{m[1]} dollar" + ("" if m[1] == "1" else "s"), t)
    t = re.sub(r"(\d+)%", r"\1 percent", t)
    t = re.sub(r"\b(\d{1,2}):00\b", r"\1", t)  # 9:00 is nine (o'clock is dropped below)
    out: list[Token] = []
    for w in re.findall(r"[a-z0-9']+", t):
        w = w.strip("'")
        if not w:
            continue
        if w == "o'clock":
            continue
        if (m := re.fullmatch(r"(\d+)(?:st|nd|rd|th)", w)) and int(m[1]) < 1_000_000:
            out += _ordinal(int(m[1])).split()
        elif w.isdigit() and len(w) == 2 and w[0] == "0":  # the 05 of 5:05 is "oh five"
            out += ["oh", _ONES[int(w[1])]]
        elif w.isdigit() and int(w) < 1_000_000:
            r = _readings(int(w))
            out += r[0].split() if len(r) == 1 else [r]
        else:
            out += _SHORT.get(w, w).split()
    return out


def _read(tokens: list[Token], picks: tuple[int, ...] = ()) -> list[str]:
    """The words, each number read the way `picks` says in turn (the first way when it runs out)."""
    out: list[str] = []
    it = iter(picks)
    for t in tokens:
        out += t.split() if isinstance(t, str) else t[next(it, 0)].split()
    # "a hundred", "a dollar fifty": the transcriber writes $100 and $1.50, which read as one hundred, one dollar
    return ["one" if w == "a" and nxt in _AFTER_A else w for w, nxt in zip(out, out[1:] + [""])]


def words(text: str) -> list[str]:
    """Lowercase words with the transcriber's notation evened out: 10 and ten, $5 and five dollars, 11 AM and
    eleven a.m., 9:00 and nine o'clock, 5:05 and five oh five, $100 and a hundred dollars, 2nd and second, wanna and
    want to, OK and okay are the same words. A number is read the first way (`_readings`)."""
    return _read(_tokens(text))


def _paired(target: str, heard: str) -> tuple[list[str], list[str]]:
    """The line's and the transcript's words, with each number on either side read the way that matches the other
    side best: 270 in the line and "two seventy" heard are the same words, and so are the other way round."""
    a, b = _tokens(target), _tokens(heard)
    ways = [len(t) for t in a + b if not isinstance(t, str)]
    if not ways:
        return _read(a), _read(b)
    sets = 1
    for n in ways:
        sets *= n
    if sets > MAX_READING_SETS:
        return _read(a), _read(b)
    na = sum(1 for t in a if not isinstance(t, str))
    best: tuple[float, list[str], list[str]] | None = None
    for picks in product(*(range(n) for n in ways)):
        wa, wb = _read(a, picks[:na]), _read(b, picks[na:])
        ratio = SequenceMatcher(None, wa, wb, autojunk=False).ratio()
        if best is None or ratio > best[0]:
            best = (ratio, wa, wb)
    assert best is not None
    return best[1], best[2]


def similarity(target: str, heard: str) -> float:
    """How closely the transcript follows the line, 0 to 1: the words matched on both sides over all words, by
    `compare`'s match. Notation (joined words, numbers), fillers and restarts do not count against it, so a short line
    the transcriber wrote as more words is still followed (todo follow-feedback leftovers 1). Without those it is the
    plain word match's ratio."""
    c = compare(target, heard)
    if not c.total or not c.heard_total:
        return 0.0
    return (c.matched + c.heard_matched) / (c.total + c.heard_total)


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
    heard_matched: int = 0  # transcript words that matched the line (a word written in two counts both)
    heard_total: int = 0  # transcript words, fillers and restarts aside


def _same_sound(target_word: str, heard_word: str) -> bool:
    """Words with a dictionary pronunciation in common sound the same: which one was written is notation."""
    d = sound_diff(target_word, heard_word)
    return d is not None and d[0] == 0


def _listed(target_word: str, heard_word: str) -> tuple[tuple[str, str], str] | None:
    d = sound_diff(target_word, heard_word)
    if d is None or d[0] > SOUND_MAX_EDITS:
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
    # fillers are never points, on either side: the transcriber usually leaves them out (spec 「평가」 2)
    wa, wb = _paired(target, heard)
    a = [w for w in wa if w not in FILLERS]
    b = [w for w in wb if w not in FILLERS]
    diffs: list[Issue] = []
    matched: set[str] = set()
    count = heard_count = restarted = 0
    for tag, i1, i2, j1, j2 in SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        ta, hb = a[i1:i2], b[j1:j2]
        if tag == "equal" or "".join(ta) == "".join(hb):  # checkout and check out
            count += len(ta)
            heard_count += len(hb)
            matched.update(ta)
        elif tag == "insert" and _restart(a, i1, hb):
            restarted += len(hb)
        elif tag == "replace" and len(ta) == len(hb):
            for t, h in zip(ta, hb):
                if _same_sound(t, h):  # to for two, four for for: how the transcriber wrote it
                    count += 1
                    heard_count += 1
                    matched.add(t)
                else:
                    diffs.append(_issue([t], [h], _listed(t, h)))
        else:
            found = next((f for t in ta for h in hb if (f := _listed(t, h))), None)
            diffs.append(_issue(ta, hb, found))
    return Comparison(diffs=diffs, matched=count, total=len(a), matched_words=matched, heard_matched=heard_count,
                      heard_total=len(b) - restarted)


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
    heard_now = {w for d in c.diffs for w in d.heard.split()}
    for i in before:
        if not i.target:  # a word was added last time: gone if no current difference has it
            if i.heard and not set(i.heard.split()) & heard_now:
                out.append(f"이번에는 {i.heard} 없이 대사대로 들렸어요")
            continue
        words_then = set(i.target.split())
        # gone only if no current difference touches these words; matched_words alone ignores position, and a
        # word can appear twice in the line
        if words_then & now or not words_then <= c.matched_words:
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
