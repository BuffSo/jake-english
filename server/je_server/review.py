"""Reading past records for 「다시 연습」 (spec 2026-11-07-review-practice, ADR-0011). Pure functions over
`Roleplay` records; nothing here calls Claude."""
from __future__ import annotations

import re

from .models import Roleplay

_PIECE = re.compile(r"[a-z0-9']+")


def sentence_key(text: str) -> str:
    """The same sentence, case and punctuation aside (speaking spec 「지난 녹음과 비교」). The app has the same rule
    (`app/src/flow/review.ts`); contract/sentence-keys.json keeps the two in step."""
    return " ".join(_PIECE.findall(text.lower().replace("’", "'")))


# --- past situations (spec 2) -----------------------------------------------------------------------------------

ROLEPLAY_MODES = ("turn", "retry")  # the roleplay's own tries; practice and shadow do not make it 「해 본 상황」


def group_of(rp: Roleplay) -> str:
    """Runs of one script share the first roleplay's ID (ADR-0011)."""
    return rp.origin or rp.id


def spoken(rp: Roleplay) -> bool:
    """The learner said at least one of their lines inside the roleplay; asides to teacher Ryan do not count
    (spec offscript-aside 6)."""
    mine = {l.idx for l in rp.lines if l.speaker == "user"}
    return any(a.mode in ROLEPLAY_MODES and not a.aside for idx, tries in rp.attempts.items() if idx in mine
               for a in tries)


def _groups(rps: list[Roleplay]) -> dict[str, list[Roleplay]]:
    out: dict[str, list[Roleplay]] = {}
    for rp in rps:
        if spoken(rp):
            out.setdefault(group_of(rp), []).append(rp)
    return out


def past_items(rps: list[Roleplay]) -> list[dict]:
    """One row per script that was spoken in: its title, the first day it was done and its newest run."""
    rows = []
    for group, runs in _groups(rps).items():
        runs.sort(key=lambda r: r.created)
        rows.append({"group": group, "title_ko": runs[-1].frame.title_ko, "first": runs[0].created[:10],
                     "latest": runs[-1].created})
    return sorted(rows, key=lambda r: r["latest"], reverse=True)


def latest_run(rps: list[Roleplay], group: str) -> Roleplay | None:
    runs = _groups(rps).get(group, [])
    return max(runs, key=lambda r: r.created) if runs else None


# --- the first recording (spec 4) -------------------------------------------------------------------------------


def first_try(group_runs: list[Roleplay], rp: Roleplay, idx: int) -> dict | None:
    """The earliest followed try at this sentence among the learner's lines of the group, by when it was recorded
    (the run's creation for tries from before `Attempt.at`). None when that is in this run, whatever line or mode:
    「처음 하는 회차에는 나오지 않는다」 (final review), and for Ryan's lines."""
    if not 0 <= idx < len(rp.lines) or rp.lines[idx].speaker != "user":
        return None
    key = sentence_key(rp.lines[idx].text)
    best = None
    for run in group_runs:
        for line in run.lines:
            if line.speaker != "user" or sentence_key(line.text) != key:
                continue
            for a in run.attempts.get(line.idx, []):
                if a.followed:
                    order = (a.at or run.created, run.created, a.n)
                    if best is None or order < best[0]:
                        best = (order, run.id, line.idx, a)
    if best is None:
        return None
    _, run_id, line_idx, a = best
    if run_id == rp.id:
        return None
    return {"rp_id": run_id, "idx": line_idx, "n": a.n}


# --- the conversation to resume (spec resume-roleplay 1, 2) -----------------------------------------------------


def to_resume(rps: list[Roleplay]) -> Roleplay | None:
    """The newest roleplay, when a line of mine is left at or after its place (`pos`). Only the newest: an older one
    left midway is not looked for, since a new conversation was started after it (spec 1)."""
    if not rps:
        return None
    rp = max(rps, key=lambda r: (r.created, r.id))
    return rp if any(l.speaker == "user" and l.idx >= rp.pos for l in rp.lines) else None


def said_before(rp: Roleplay, upto: int) -> list[dict]:
    """What was heard on my lines before `upto`, for the resumed conversation's bubbles: the last try inside the
    roleplay (asides to teacher Ryan left out, like the end screen). A line without one was skipped (spec 2)."""
    out = []
    for line in rp.lines[:upto]:
        if line.speaker != "user":
            continue
        tries = [a for a in rp.attempts.get(line.idx, []) if a.mode in ROLEPLAY_MODES and not a.aside]
        if tries:
            out.append({"idx": line.idx, "heard": tries[-1].heard, "n": tries[-1].n})
    return out
