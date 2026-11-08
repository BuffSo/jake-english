"""The 2026-11-05 stress test's tables again, from the values kept in {data}/stress/ (spec stress-log 「표 다시 내기」).

Prints counts and ratios only, never heard words, lines or word letters, so the output can go into the public guide as
it is. The five function words of the weak-form table are fixed names, not the learner's words.
"""
from __future__ import annotations

import json
import statistics
from pathlib import Path

from .stress import FORMAT

WEAK_WORDS = ("for", "a", "to", "of", "the")
ROW_NAMES = {
    "dict": "낱말 강세, 사전과",
    "no_secondary": "위에서 2차 강세가 없는 낱말만",
    "top_quarter": "위에서 확실도 위 25%만",
    "mark": "낱말 강세, 대사에 표시한 강세와",
}


def load(data_dir: Path, since: str | None = None) -> tuple[list[dict], int]:
    """The value files of this format, from `since` (YYYY-MM-DD) on, and how many files could not be read. A try is
    dated by when it was recorded; tries before 2026-11-07 have no such time and are dated by when their roleplay was
    made, then by when they were measured (value files written before `created` was kept)."""
    records, broken = [], 0
    for path in sorted((data_dir / "stress").glob("*/*.json")):
        try:
            r = json.loads(path.read_text(encoding="utf-8"))
        except ValueError:
            broken += 1
            continue
        if not isinstance(r, dict) or r.get("v") != FORMAT:
            continue
        if since and (r.get("at") or r.get("created") or r.get("measured") or "")[:10] < since:
            continue
        records.append(r)
    return records, broken


def auc(pos: list[float], neg: list[float]) -> float | None:
    """How often a positive is above a negative (ties count half): 0.5 is a guess, 1.0 always right."""
    if not pos or not neg:
        return None
    return sum(1.0 if p > n else 0.5 if p == n else 0.0 for p in pos for n in neg) / (len(pos) * len(neg))


def _words(records: list[dict]) -> list[dict]:
    return [w for r in records if r.get("status") == "ok" for w in r.get("words", [])]


def _ratio(flags: list[bool]) -> float | None:
    return sum(flags) / len(flags) if flags else None


def word_rows(records: list[dict]) -> list[tuple[str, int, float | None, float | None]]:
    """(row, words, judged right, the baseline) for word stress. Against the dictionary only words of two or more
    vowels whose dictionary stress is one place count, with 「always the first syllable」 as the baseline (the guide's
    filter). Against the line's marks only words whose marked syllable count is the vowel count, with 「the mark is on
    the first syllable」 as the baseline."""
    judged = [w for w in _words(records) if w.get("pick") is not None]
    by_dict = [w for w in judged if w.get("dict") and len(w["dict"]["primary"]) == 1]
    no_second = [w for w in by_dict if not w["dict"]["secondary"]]
    top: list[dict] = by_dict if len(by_dict) == 1 else []  # `quantiles` needs two values
    if len(by_dict) >= 2:
        # inclusive: the default (exclusive) puts the cut above the largest margin when there are only a few words
        cut = statistics.quantiles([w["margin"] for w in by_dict], n=4, method="inclusive")[2]
        top = [w for w in by_dict if w["margin"] >= cut]
    marked = [w for w in judged if (m := w.get("mark")) and m["s"] is not None and m["n"] == len(w["syl"])]

    def row(name: str, words: list[dict], want) -> tuple[str, int, float | None, float | None]:
        return (name, len(words), _ratio([w["pick"] == want(w) for w in words]), _ratio([want(w) == 0 for w in words]))

    def primary(w: dict) -> int:
        return w["dict"]["primary"][0]

    return [row("dict", by_dict, primary), row("no_secondary", no_second, primary),
            row("top_quarter", top, primary), row("mark", marked, lambda w: w["mark"]["s"])]


def sentence(records: list[dict]) -> tuple[int, int, float | None]:
    """Content words, function words and the AUC of content words scoring above function words."""
    scored = [w for w in _words(records) if w.get("score") is not None]
    pos = [w["score"] for w in scored if w["content"]]
    neg = [w["score"] for w in scored if not w["content"]]
    return len(pos), len(neg), auc(pos, neg)


def weak_forms(records: list[dict]) -> dict[str, tuple[int, int]]:
    """For each of the five function words, how many times MFA chose a weak form (every vowel unstressed) and in
    all."""
    out = {}
    for word in WEAK_WORDS:
        found = [w for w in _words(records) if w["w"] == word and any(p[-1:].isdigit() for p in w["phones"])]
        out[word] = (sum(all(p.endswith("0") for p in w["phones"] if p[-1:].isdigit()) for w in found), len(found))
    return out


def _f(x: float | None) -> str:
    return "-" if x is None else f"{x:.2f}"


def _section(title: str, records: list[dict]) -> list[str]:
    ok = [r for r in records if r.get("status") == "ok"]
    lines = [f"### {title} (녹음 {len(ok)})", "", "| 시험 | 낱말 수 | 맞은 비율 | 비교 기준 |", "|---|---|---|---|"]
    for name, n, right, base in word_rows(ok):
        what = "표시가 첫 음절인 비율" if name == "mark" else "첫 음절 찍기"
        lines.append(f"| {ROW_NAMES[name]} | {n} | {_f(right)} | {what} {_f(base)} |")
    pos, neg, a = sentence(ok)
    lines.append(f"| 문장 강세(내용어가 더 센가) | 내용어 {pos}, 기능어 {neg} | AUC {_f(a)} | 0.5가 찍기 |")
    lines += ["", "| 기능어 | 약형 | 전체 |", "|---|---|---|"]
    lines += [f"| {word} | {weak} | {n} |" for word, (weak, n) in weak_forms(ok).items()]
    return lines


def render(records: list[dict], broken: int = 0) -> str:
    ok = [r for r in records if r.get("status") == "ok"]
    head = [f"- 녹음: 잼 {len(ok)}, 정렬 실패 {len(records) - len(ok)}" + (f", 깨진 값 파일 {broken}" if broken else ""),
            f"- 낱말: {len(_words(ok))}", ""]
    return "\n".join([*head, *_section("대사를 따라 말한 것", [r for r in records if r.get("followed")]), "",
                      *_section("다르게 말한 영어", [r for r in records if not r.get("followed")])]) + "\n"
