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
from .names import HANGUL_WORD, is_name, resembles, romanize, same_name, syllables  # noqa: F401 (romanize, syllables: tests)

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
NUMBER_LIMIT = 10**12  # digits up to this are read as words; longer ones stay digits


def _number(n: int) -> str:
    """Words for 0 <= n < NUMBER_LIMIT, the way the transcriber's digits are read out (1,000 is one thousand,
    2,500,000 two million five hundred thousand)."""
    if n < 20:
        return _ONES[n]
    if n < 100:
        tens, ones = divmod(n, 10)
        return _TENS[tens] + (f" {_ONES[ones]}" if ones else "")
    for size, name in ((10**9, "billion"), (10**6, "million"), (1000, "thousand"), (100, "hundred")):
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


def _price(dollars: int, cents: int) -> list[Token]:
    """$5.99 the ways people read a price: five dollars ninety nine, five ninety nine, five dollars and ninety nine
    cents. The voice and the learner may say either (todo follow-feedback leftovers 5)."""
    unit = "dollar" if dollars == 1 else "dollars"
    d = _number(dollars)
    if not cents:
        return [d, unit]
    c = _number(cents) if cents >= 10 else f"oh {_ONES[cents]}"  # $2.05 is two oh five, as 5:05 is
    cent = "cent" if cents == 1 else "cents"
    return [(f"{d} {unit} {c}", f"{d} {c}", f"{d} {unit} and {_number(cents)} {cent}")]


def _tokens(text: str, hangul: bool = False) -> list[Token]:
    """`hangul`: Hangul words stay as words, for a name the transcriber wrote in Hangul (spec teacher-answer-context
    3); otherwise only Latin letters and digits count."""
    t = text.lower().replace("’", "'")
    t = re.sub(r"(?<=\d),(?=\d{3})", "", t)  # 1,000 is one number
    t = re.sub(r"\b([ap])\.?m\b\.?", r"\1m", t)
    t = re.sub(r"\$(\d{1,12})\.(\d\d)\b", r"pricex\1x\2", t)  # read below, with or without dollars
    t = re.sub(r"\$(\d+)", lambda m: f"{m[1]} dollar" + ("" if m[1] == "1" else "s"), t)
    t = re.sub(r"(\d+)%", r"\1 percent", t)
    t = re.sub(r"\b(\d{1,2}):00\b", r"\1", t)  # 9:00 is nine (o'clock is dropped below)
    out: list[Token] = []
    for w in re.findall(r"[a-z0-9']+|[가-힣]+" if hangul else r"[a-z0-9']+", t):
        w = w.strip("'")
        if not w:
            continue
        if w == "o'clock":
            continue
        if m := re.fullmatch(r"pricex(\d+)x(\d\d)", w):
            for p in _price(int(m[1]), int(m[2])):
                out += p.split() if isinstance(p, str) else [p]
            continue
        if (m := re.fullmatch(r"(\d+)(?:st|nd|rd|th)", w)) and int(m[1]) < NUMBER_LIMIT:
            out += _ordinal(int(m[1])).split()
        elif w.isdigit() and len(w) == 2 and w[0] == "0":  # the 05 of 5:05 is "oh five"
            out += ["oh", _ONES[int(w[1])]]
        elif w.isdigit() and int(w) < NUMBER_LIMIT:
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
    eleven a.m., 9:00 and nine o'clock, 5:05 and five oh five, $100 and a hundred dollars, $5.99 and five ninety nine,
    2nd and second, wanna and want to, OK and okay are the same words. A number or a price is read the first way
    (`_readings`, `_price`)."""
    return _read(_tokens(text))


def _paired(target: str, heard: str, hangul: bool = False) -> tuple[list[str], list[str]]:
    """The line's and the transcript's words, with each number on either side read the way that matches the other
    side best: 270 in the line and "two seventy" heard are the same words, and so are the other way round."""
    a, b = _tokens(target), _tokens(heard, hangul)
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
    korean: bool = False  # Hangul words other than a name of the line written in Hangul


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
    """Added words where the learner started over: the line's words right before or after them said once or more
    ("we need, we need two tickets", "we, we, we need"), or a try at the words after them that came out wrong and was
    then said again (the same first word and at least half the same: "could I sit the, could I see the menu"). The
    Mac points at what the learner finally said (todo follow-feedback leftovers 2)."""
    n = len(added)
    for m in range(1, n + 1):
        if n % m:
            continue
        chunks = [line[at:at + m]] + ([line[at - m:at]] if at >= m else [])
        if any(len(c) == m and added == c * (n // m) for c in chunks):
            return True
    ahead = line[at:at + n]
    return (n >= 2 and len(ahead) == n and added[0] == ahead[0]
            and SequenceMatcher(None, added, ahead, autojunk=False).ratio() >= 0.5)


def compare(target: str, heard: str) -> Comparison:
    """The transcript against the line. Hangul in it counts only where it stands for a name of the line; anywhere
    else it is Korean that was said, left out as before (spec teacher-answer-context 3)."""
    c = _compare(target, heard, hangul=bool(HANGUL_WORD.search(heard)))
    return _compare(target, heard) if c.korean else c


def korean_said(line: str, text: str) -> bool:
    """Hangul in the transcript other than a name of the line written in Hangul (spec teacher-answer-context 3): the
    transcriber wrote 「Get off at 홍대」 for a try at the line, which is no Korean said."""
    return bool(HANGUL_WORD.search(text)) and _compare(line, text, hangul=True).korean


def _compare(target: str, heard: str, hangul: bool = False) -> Comparison:
    # fillers are never points, on either side: the transcriber usually leaves them out (spec 「평가」 2)
    wa, wb = _paired(target, heard, hangul)
    a = [w for w in wa if w not in FILLERS]
    b = [w for w in wb if w not in FILLERS]
    diffs: list[Issue] = []
    matched: set[str] = set()
    count = heard_count = restarted = 0
    korean = False
    for tag, i1, i2, j1, j2 in SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        ta, hb = a[i1:i2], b[j1:j2]
        # a name the dictionary does not have, heard as one or more words (spec teacher-answer-context 3). Hangul
        # anywhere else is Korean said; word for word when the counts match, so a name in Hangul next to another
        # word heard wrong still stands for the name
        # The Hangul has to look like the name too: a Korean word said where the name goes, or a question after it,
        # is Korean said (PR #62 review: 「Get off at 홍대 맞나요?」 passed as followed)
        names = bool(ta) and all(map(is_name, ta))
        if tag == "replace" and len(ta) == len(hb):
            korean |= any(HANGUL_WORD.match(h) and not (is_name(t) and resembles(t, h)) for t, h in zip(ta, hb))
        else:
            korean |= any(HANGUL_WORD.match(h) and not (names and any(resembles(t, h) for t in ta)) for h in hb)
        if tag == "equal" or "".join(ta) == "".join(hb):  # checkout and check out
            count += len(ta)
            heard_count += len(hb)
            matched.update(ta)
        elif tag == "insert" and _restart(a, i1, hb):
            restarted += len(hb)
        elif tag == "replace" and len(ta) == len(hb):
            for t, h in zip(ta, hb):
                # to for two, four for for, a name spelled the transcriber's way: how it was written
                if _same_sound(t, h) or (is_name(t) and same_name(t, h)):
                    count += 1
                    heard_count += 1
                    matched.add(t)
                else:
                    diffs.append(_issue([t], [h], _listed(t, h)))
        elif tag == "replace" and names and same_name("".join(ta), "".join(hb)):  # Insadong heard as Insa Dong
            count += len(ta)
            heard_count += len(hb)
            matched.update(ta)
        else:
            found = next((f for t in ta for h in hb if (f := _listed(t, h))), None)
            diffs.append(_issue(ta, hb, found))
    return Comparison(diffs=diffs, matched=count, total=len(a), matched_words=matched, heard_matched=heard_count,
                      heard_total=len(b) - restarted, korean=korean)


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


def _as_written(found: str, text: str) -> str:
    """The words of a point as `text` writes them, each one that `text` writes in one way only: the Mac compares in
    lowercase, and the end screen showed 「i」 for 「I」 (todo follow-feedback leftovers 3). A word written both ways,
    or not written at all (a number read out), stays as compared."""
    forms: dict[str, set[str]] = {}
    for w in re.findall(r"[A-Za-z0-9'’]+", text):
        w = w.replace("’", "'").strip("'")
        forms.setdefault(w.lower(), set()).add(w)
    return " ".join(next(iter(f)) if len(f := forms.get(w, set())) == 1 else w for w in found.split())


def issue_ko(i: Issue, line: str = "", heard: str = "") -> str:
    """The end screen's line for a point, worded like Ryan's: what was heard, never what was said. `line` and
    `heard` give the words as written. An added word takes 「도」, which fits after any word, where 이 or 가 would
    depend on how it ends in Korean (the user's choice, 2026-11-08)."""
    target, said = _as_written(i.target, line), _as_written(i.heard, heard)
    if not i.target:
        return f"대사에 없는 「{said}」도 들렸어요"
    if not i.heard:
        return f"「{target}」 → 들리지 않았어요"
    return f"「{target}」 → 「{said}」처럼 들렸어요"


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
