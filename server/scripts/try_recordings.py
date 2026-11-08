"""Send recordings to the Mac server the way the app does, without the phone (guide DEVENV_폰없이_녹음_시험하기).

The roleplay is copied first (「이 상황 다시 하기」, POST /roleplays/{id}/copy, no Claude call), and each recording is
sent to the copy as a try at one line (POST /roleplays/{copy}/lines/{idx}/attempts). The line is checked and printed
from the copy: a list pick's copy plays the list's current script, which may differ from the run copied. For each it prints what was
heard, whether it followed the line, Ryan's answer, the done event and the times the server saved. At the end the copy's
folder is deleted with its recordings, so the learner's records get no test tries; `--keep` leaves it and prints its id.

Ryan's answer calls Claude, so each recording costs money: feedback about $0.0003 (Haiku), teacher Ryan about $0.007
(Sonnet). The server's address and token come from server/.env, as the server reads them; the token is never printed.
What this prints (lines, transcripts, answers) stays in the terminal: recordings and their transcripts do not go into
public files (REVIEW.md).

Run in server/:
    uv run python scripts/try_recordings.py --list
    uv run python scripts/try_recordings.py <roleplay id> <line idx> <recording.m4a>... [--mode turn] [--keep]
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from je_server import topics  # noqa: E402
from je_server.config import load_settings  # noqa: E402
from je_server.models import Roleplay  # noqa: E402
from je_server.store import ID  # noqa: E402

MODES = ("turn", "retry", "practice", "shadow")


class Stop(Exception):
    """Nothing more is sent; the message says why."""


class Http:
    """The server, as the app calls it: a bearer token on every request."""

    def __init__(self, host: str, port: int, token: str, timeout: float = 120):
        self.base, self.token, self.timeout = f"http://{host}:{port}", token, timeout

    def _open(self, method: str, path: str, body: bytes | None = None, ctype: str | None = None):
        headers = {"Authorization": f"Bearer {self.token}", **({"Content-Type": ctype} if ctype else {})}
        req = urllib.request.Request(self.base + path, data=body, method=method, headers=headers)
        return urllib.request.urlopen(req, timeout=self.timeout)

    def json(self, method: str, path: str) -> dict:
        with self._open(method, path, b"" if method == "POST" else None) as r:
            return json.load(r)

    def lines(self, path: str, body: bytes) -> list[dict]:
        """The attempt's NDJSON events (heard, text, audio, error, done)."""
        with self._open("POST", path, body, "audio/mp4") as r:
            return [json.loads(l) for l in r if l.strip()]


@dataclass
class Try:
    file: str
    heard: str = ""
    followed: bool | None = None
    said: str = ""  # Ryan's answer, the text pieces joined
    audio: int = 0  # sentences Ryan's voice made
    error: str | None = None
    done: dict | None = None  # next and issues, when the try ended normally
    timings: dict[str, float] = field(default_factory=dict)


def _check_line(rp: dict, idx: int, mode: str) -> dict:
    """The line a try is said against: Ryan's for shadow practice, the learner's for the rest (engine.target_line)."""
    lines = rp["lines"]
    if not 0 <= idx < len(lines):
        raise Stop(f"no line {idx}: the roleplay has lines 0 to {len(lines) - 1}")
    want = "ryan" if mode == "shadow" else "user"
    if lines[idx]["speaker"] != want:
        whose = "Ryan's line" if lines[idx]["speaker"] == "ryan" else "the learner's line"
        raise Stop(f"line {idx} is {whose}; mode {mode} is said against {'Ryan' if want == 'ryan' else 'the learner'}")
    return lines[idx]


def _timings(data_dir: Path, rp_id: str, idx: int) -> dict[str, float]:
    path = data_dir / "roleplays" / rp_id / "roleplay.json"
    tries = Roleplay.model_validate_json(path.read_text(encoding="utf-8")).attempts.get(idx, [])
    return tries[-1].timings if tries else {}


def send(http, data_dir: Path, rp_id: str, idx: int, path: Path, mode: str) -> Try:
    t = Try(file=path.name)
    for ev in http.lines(f"/roleplays/{rp_id}/lines/{idx}/attempts?mode={mode}", path.read_bytes()):
        kind = ev.get("type")
        if kind == "heard":
            t.heard, t.followed = ev["text"], ev["followed"]
        elif kind == "text":
            t.said += ev["delta"]
        elif kind == "audio":
            t.audio += 1
        elif kind == "error":
            t.error = ev["code"]
        elif kind == "done":
            t.done = {k: v for k, v in ev.items() if k != "type"}
    if t.heard:  # an attempt is saved only once something was heard
        t.timings = _timings(data_dir, rp_id, idx)
    return t


def remove_copy(data_dir: Path, copy_id: str, source_id: str) -> None:
    """Deletes the copy this script made, and nothing else: a well-formed id, a folder whose record says it is a copy
    of the source's group (Engine.copy keeps the first roleplay as origin)."""
    if not ID.match(copy_id) or copy_id == source_id:
        raise Stop(f"not a copy id: {copy_id!r}")
    root = data_dir / "roleplays"
    rp = Roleplay.model_validate_json((root / copy_id / "roleplay.json").read_text(encoding="utf-8"))
    source = Roleplay.model_validate_json((root / source_id / "roleplay.json").read_text(encoding="utf-8"))
    if rp.id != copy_id or rp.origin is None or rp.origin != (source.origin or source.id):
        raise Stop(f"{copy_id} is not a copy of {source_id}; left as it is")
    shutil.rmtree(root / copy_id)


def show(t: Try, out: Callable[[str], object]) -> None:
    out(f"[{t.file}]")
    if t.heard:
        out(f"  heard: {t.heard}  (followed: {'yes' if t.followed else 'no'})")
    if t.said:
        out(f"  ryan: {t.said.strip()}")
    if t.error:
        out(f"  error: {t.error}")
    if t.done is not None:
        out(f"  done: next {t.done.get('next')}, issues {t.done.get('issues')}, ryan's voice {t.audio} sentence(s)")
    if t.timings:
        out("  seconds: " + ", ".join(f"{k} {v:.2f}" for k, v in t.timings.items()))


def run(http, data_dir: Path, rp_id: str, idx: int, files: list[Path], mode: str, keep: bool = False,
        out: Callable[[str], object] = print) -> list[Try]:
    """The line is checked and printed from the copy, where the recordings go: a list pick's copy plays the script as
    it is now in the repository, which may differ from the run copied (todo 25)."""
    copy = http.json("POST", f"/roleplays/{rp_id}/copy")
    try:
        line = _check_line(copy, idx, mode)
    except Stop:
        remove_copy(data_dir, copy["id"], rp_id)  # nothing was sent to it: gone even with --keep
        raise
    out(f"line {idx}: {line['text']}")
    tries: list[Try] = []
    try:
        for path in files:
            tries.append(send(http, data_dir, copy["id"], idx, path, mode))
            show(tries[-1], out)
    finally:
        if keep:
            out(f"kept the copy {copy['id']}; delete its folder under the data folder's roleplays/ when done")
        else:
            remove_copy(data_dir, copy["id"], rp_id)
    return tries


def copy_lines(rp: Roleplay) -> tuple[list[tuple[int, str, str]], bool]:
    """The lines a copy of `rp` gets, as (idx, speaker, text), and whether they are the list's current script: a list
    pick still on its list plays the repository's script, anything else its own lines (`Engine.copy`)."""
    if rp.pick is not None and rp.topic is not None:
        try:
            script = topics.pick(rp.topic, rp.pick).script
        except KeyError:
            pass  # taken off the list: copied from the record
        else:
            return [(i, speaker, text) for i, (speaker, text) in enumerate(script)], True
    return [(l.idx, l.speaker, l.text) for l in rp.lines], False


def list_roleplays(data_dir: Path, n: int = 10) -> None:
    """The newest roleplays with the line numbers a copy of each gets, to pick one to try. Copies are marked."""
    found = []
    for f in (data_dir / "roleplays").glob("*/roleplay.json"):
        try:
            found.append(Roleplay.model_validate_json(f.read_text(encoding="utf-8")))
        except ValueError:
            continue
    for rp in sorted(found, key=lambda r: r.created, reverse=True)[:n]:
        lines, current = copy_lines(rp)
        print(f"{rp.id}  {rp.created}  {rp.frame.title_ko}" + ("  (copy)" if rp.origin else "")
              + ("  (list: current script)" if current else ""))
        for i, speaker, text in lines:
            print(f"    {i} {'ryan' if speaker == 'ryan' else 'me  '}  {text}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--list", action="store_true", help="show the newest roleplays and their lines")
    ap.add_argument("roleplay", nargs="?")
    ap.add_argument("idx", nargs="?", type=int)
    ap.add_argument("recordings", nargs="*", type=Path)
    ap.add_argument("--mode", choices=MODES, default="turn")
    ap.add_argument("--keep", action="store_true", help="leave the copy instead of deleting it")
    args = ap.parse_args()
    s = load_settings()
    if args.list:
        list_roleplays(s.data_dir)
        return 0
    if not (args.roleplay and args.idx is not None and args.recordings):
        ap.error("give a roleplay id, a line idx and at least one recording (or --list)")
    if missing := [str(p) for p in args.recordings if not p.is_file()]:
        ap.error("no such recording: " + ", ".join(missing))
    try:
        run(Http(s.host, s.port, s.token), s.data_dir, args.roleplay, args.idx, args.recordings, args.mode, args.keep)
    except Stop as e:
        print(f"stopped: {e}", file=sys.stderr)
        return 1
    except urllib.error.HTTPError as e:  # the server's error code only; the request and its token are not shown
        print(f"server answered {e.code}: {e.read().decode(errors='replace')[:200]}", file=sys.stderr)
        return 1
    except urllib.error.URLError as e:
        print(f"cannot reach the server ({e.reason}); is it running? server/scripts/autostart.sh status",
              file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
