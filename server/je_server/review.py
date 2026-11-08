"""Reading past records for 「다시 연습」 (spec 2026-11-07-review-practice, ADR-0011). Pure functions over
`Roleplay` records; nothing here calls Claude."""
from __future__ import annotations

import re

from .models import Attempt, Roleplay, ScriptLine

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


def kept_tries(rp: Roleplay, line: ScriptLine) -> list[Attempt]:
    """The tries at a line of mine that the conversation keeps: inside the roleplay, asides to teacher Ryan left out
    (spec offscript-aside 6). The end screen, the past list and resuming all go by these, so a line counts as
    recorded in one place (spec resume-unrecorded 1). Ryan's lines have none."""
    if line.speaker != "user":
        return []
    return [a for a in rp.attempts.get(line.idx, []) if a.mode in ROLEPLAY_MODES and not a.aside]


def spoken(rp: Roleplay) -> bool:
    """The learner said at least one of their lines inside the roleplay; asides to teacher Ryan do not count
    (spec offscript-aside 6)."""
    return any(kept_tries(rp, l) for l in rp.lines)


def _groups(rps: list[Roleplay]) -> dict[str, list[Roleplay]]:
    out: dict[str, list[Roleplay]] = {}
    for rp in rps:
        if rp.kind != "talk" and spoken(rp):
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


# --- the conversation to resume (spec resume-roleplay 1, 2; resume-unrecorded 1-3) ----------------------------------


def unrecorded(rp: Roleplay) -> list[int]:
    """My lines without a kept try: skipped, not reached yet, or said to teacher Ryan only. Practice does not record
    a line of the conversation (spec resume-unrecorded 1)."""
    return [l.idx for l in rp.lines if l.speaker == "user" and not kept_tries(rp, l)]


def to_resume(rps: list[Roleplay]) -> Roleplay | None:
    """The newest roleplay, when a line of mine is left unrecorded in it. Only the newest: an older one is not looked
    for, since a new conversation was started after it (spec resume-roleplay 1, resume-unrecorded 2)."""
    # a free talk is left out, so doing one does not hide the roleplay left midway (spec free-talk-design 8)
    rps = [r for r in rps if r.kind != "talk"]
    if not rps:
        return None
    rp = max(rps, key=lambda r: (r.created, r.id))
    return rp if unrecorded(rp) else None


def resume_start(rp: Roleplay) -> tuple[int, bool]:
    """Where the resumed conversation starts, and whether it went to the end. Left mid-way (an unrecorded line at or
    after its place): the first of those, so an earlier skipped line waits until the end is reached. Gone to the end:
    the first unrecorded line. Either way from the line after my line before it, so Ryan's line leads in again
    (spec resume-unrecorded 3)."""
    left = unrecorded(rp)
    ahead = [i for i in left if i >= rp.pos]
    target = (ahead or left)[0]
    mine_before = [l.idx for l in rp.lines if l.speaker == "user" and l.idx < target]
    return (mine_before[-1] + 1 if mine_before else 0), not ahead


def said_on(rp: Roleplay) -> list[dict]:
    """What was heard on every recorded line of mine, for the resumed conversation's bubbles: the last kept try, like
    the end screen. A line without one is unrecorded (spec resume-roleplay 2, resume-unrecorded 3)."""
    out = []
    for line in rp.lines:
        tries = kept_tries(rp, line)
        if tries:
            out.append({"idx": line.idx, "heard": tries[-1].heard, "n": tries[-1].n})
    return out
