"""Time free-talk turns on a test server with recordings, the way the app sends them (guide DEVENV_폰없이_녹음_시험하기).

A talk is made (POST /talks), each recording is sent as one turn (POST /talks/{id}/turns) and the NDJSON events are
stamped when they arrive. With --end the talk is ended (POST /talks/{id}/end). Each English turn calls Claude once and
the end once more, so it costs money (a few tenths of a cent to a cent or so each).

Prints times, word counts, whether the turn was heard as Korean, and for the end the number of fixes and how many of
them guess a sound. What was heard and what Ryan said stays out of the output unless `--show`, and then only in the
terminal: recordings, their transcripts and Ryan's answers do not go into files (REVIEW.md). The address is the
local test server's (`--port`); the token comes from server/.env as the server reads it and is never printed. Point
JE_DATA_DIR at the test server's data copy to also read the times the server saved.

With `--drop` the first recording's turn is dropped (POST /talks/{id}/lines/{idx}/drop) as soon as its `heard`
event arrives, the stream is read to its end, and the seconds from the drop to the end are printed. The other
recordings are then sent as the turn said again. This times dropping a turn and saying it again.

Run in server/:
    uv run python scripts/try_talk.py --port 8791 a.m4a b.m4a [--heard 1] [--end] [--show] [--drop]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

SOUND_GUESS = "처럼 들렸어요"  # the sentence a guessed mispronunciation is written with (spec free-talk-design 2)


def summarize(events: list[tuple[float, dict]]) -> dict:
    """The seconds each stage came, from a turn's events and the second each arrived after the recording was sent.
    A stage that did not happen is None. `reply_words` counts the words of the streamed text."""
    first: dict[str, float] = {}
    korean, text = False, ""
    for at, ev in events:
        kind = ev.get("type")
        if kind == "heard":
            korean = bool(ev.get("korean"))
        elif kind == "text":
            text += ev["delta"]
        if kind in ("heard", "text", "audio", "done"):
            first.setdefault(kind, at)
    return {"heard_s": first.get("heard"), "first_text_s": first.get("text"), "first_audio_s": first.get("audio"),
            "done_s": first.get("done"), "korean": korean, "reply_words": len(text.split())}


def summarize_end(body: dict) -> dict:
    """The number of fixes the end gave and how many of them guess a sound."""
    fixes = [item["line"]["fix"] for item in body.get("items", [])]
    return {"fixes": len(fixes), "sound_guesses": sum(SOUND_GUESS in f["why_ko"] for f in fixes)}


def drop_path(rp_id: str, idx: int) -> str:
    """The path that drops my turn at line `idx`."""
    return f"/talks/{rp_id}/lines/{idx}/drop"


def send_turn(base: str, token: str, rp_id: str, path: Path, heard: int | None, timeout: float = 180,
              on_event=None):
    """One turn: (seconds, event) for each line as it arrives. The first line's time is after the request is sent.
    `on_event(event)`, when given, is called with each event as it arrives."""
    q = f"?heard={heard}" if heard is not None else ""
    req = urllib.request.Request(f"{base}/talks/{rp_id}/turns{q}", data=path.read_bytes(), method="POST",
                                 headers={"Authorization": f"Bearer {token}", "Content-Type": "audio/mp4"})
    events = []
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=timeout) as r:
        for line in r:
            if line.strip():
                ev = json.loads(line)
                events.append((time.perf_counter() - t0, ev))
                if on_event:
                    on_event(ev)
    return events


def post_json(base: str, token: str, path: str, timeout: float = 180) -> tuple[float, dict]:
    req = urllib.request.Request(base + path, data=b"", method="POST", headers={"Authorization": f"Bearer {token}"})
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=timeout) as r:
        body = json.load(r)
    return time.perf_counter() - t0, body


def fmt(x: float | None) -> str:
    return "-" if x is None else f"{x:.2f}s"


def saved_timings(data_dir: Path, rp_id: str, idx: int) -> dict[str, float]:
    """The times the server saved for my turn at line `idx`, when the data folder is readable."""
    try:
        rp = json.loads((data_dir / "roleplays" / rp_id / "roleplay.json").read_text(encoding="utf-8"))
        return rp["attempts"][str(idx)][-1]["timings"]
    except (OSError, KeyError, IndexError, ValueError):
        return {}


def main() -> int:
    from je_server.config import load_settings

    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("recordings", nargs="+", type=Path)
    ap.add_argument("--port", type=int, required=True, help="the test server's port (not the launchd server's)")
    ap.add_argument("--heard", type=int, help="from the second turn on: sentences of Ryan's last reply I heard")
    ap.add_argument("--end", action="store_true", help="end the talk after the turns and count the fixes")
    ap.add_argument("--show", action="store_true", help="print what was heard and Ryan's text (terminal only)")
    ap.add_argument("--drop", action="store_true",
                    help="drop the first recording's turn once heard, time to the stream's end, then say the rest again")
    args = ap.parse_args()
    if missing := [str(p) for p in args.recordings if not p.is_file()]:
        ap.error("no such recording: " + ", ".join(missing))
    s = load_settings()
    base = f"http://127.0.0.1:{args.port}"
    try:
        _, talk = post_json(base, s.token, "/talks")
        for i, path in enumerate(args.recordings):
            dropped: list[float] = []  # [perf_counter at the drop] once the first turn is dropped

            def drop_when_heard(ev: dict) -> None:
                if ev.get("type") == "heard" and not dropped:
                    post_json(base, s.token, drop_path(talk["id"], ev["idx"]))
                    dropped.append(time.perf_counter())

            events = send_turn(base, s.token, talk["id"], path, args.heard if i else None,
                               on_event=drop_when_heard if args.drop and i == 0 else None)
            if dropped:
                print(f"[drop] stream ended {fmt(time.perf_counter() - dropped[0])} after the drop")
            r = summarize(events)
            heard_ev = next((e for _, e in events if e.get("type") == "heard"), None)
            errors = [e["code"] for _, e in events if e.get("type") == "error"]
            print(f"[{path.name}] heard {fmt(r['heard_s'])} first text {fmt(r['first_text_s'])} "
                  f"first sound {fmt(r['first_audio_s'])} done {fmt(r['done_s'])} "
                  f"korean {r['korean']} reply words {r['reply_words']}" + (f" errors {errors}" if errors else ""))
            if heard_ev:
                saved = saved_timings(s.data_dir, talk["id"], heard_ev["idx"])
                if saved:
                    print("  server saved: " + ", ".join(f"{k} {v:.2f}" for k, v in saved.items()))
            if args.show:
                print("  heard:", heard_ev["text"] if heard_ev else "-")
                print("  ryan:", "".join(e["delta"] for _, e in events if e.get("type") == "text").strip())
        if args.end:
            took, body = post_json(base, s.token, f"/talks/{talk['id']}/end")
            r = summarize_end(body)
            print(f"[end] {fmt(took)} fixes {r['fixes']} sound guesses {r['sound_guesses']}")
            if args.show:
                for item in body["items"]:
                    print("  fix:", item["line"]["text"], "|", item["line"]["fix"]["why_ko"])
    except urllib.error.HTTPError as e:  # the status and the server's error code only; no token
        print(f"server answered {e.code}: {e.read().decode(errors='replace')[:200]}", file=sys.stderr)
        return 1
    except urllib.error.URLError as e:
        print(f"cannot reach the server ({e.reason})", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
