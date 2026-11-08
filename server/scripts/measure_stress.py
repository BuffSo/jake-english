"""Measure stress values for every recording not measured yet (spec stress-log). Run by hand; run it again any time,
it measures only what is new.

    cd server && uv run python scripts/measure_stress.py [--now]

Reads JE_DATA_DIR (the server's app data folder) and JE_MFA_ENV (the micromamba environment with MFA and parselmouth)
from the repository's .env, server/.env and the environment, like the server. It stops when the app was used in the
last 10 minutes unless --now is given.

Records and recordings are only read. Values go to {data}/stress/{id}/{idx}-{n}.json. WAV copies and MFA's work go to
{data}/tmp/stress-<pid>-<n>/ and are deleted when done, also on failure, Ctrl-C, SIGHUP and SIGTERM; folders left by a
run that was killed outright (SIGKILL, power cut) are deleted by the next run. MFA and the feature script run at background priority
(taskpolicy -b) with one job. Only counts, stage names and seconds are printed, never words or paths. It stops at once
when JE_DATA_DIR has no roleplays/ (a mistyped path would get an empty app data folder made in its place) or the MFA
environment cannot import parselmouth and praatio.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time
import wave
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS.parent))

from je_server import audio, stress  # noqa: E402
from je_server.config import DEFAULT_DATA_DIR, REPO_DIR, SERVER_DIR, read_env_file  # noqa: E402

MODEL = "english_us_arpa"
CHUNK = 20  # recordings per MFA run: the model loads once a run (about 30 s)
TASKPOLICY = "/usr/sbin/taskpolicy"


def _run(cmd: list[str], env_dir: Path, what: str) -> None:
    path = f"{env_dir / 'bin'}:/usr/bin:/bin:/usr/sbin:/sbin"  # MFA finds its own tools (fstcompile) on PATH
    done = subprocess.run([TASKPOLICY, "-b", *cmd], env={**os.environ, "PATH": path},
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if done.returncode != 0:
        raise RuntimeError(f"{what} failed")


def mfa_align(mfa_env: Path, corpus: Path, out: Path, work: Path) -> None:
    _run([str(mfa_env / "bin" / "mfa"), "align", "--clean", "--single_speaker", "-j", "1",
          "--temporary_directory", str(work), str(corpus), MODEL, MODEL, str(out)], mfa_env, "mfa align")


def praat_features(mfa_env: Path, corpus: Path, out: Path, dest: Path) -> dict:
    _run([str(mfa_env / "bin" / "python"), "-I", str(SCRIPTS / "stress_features.py"), str(corpus), str(out),
          str(dest)], mfa_env, "stress features")
    return json.loads(dest.read_text(encoding="utf-8"))


def features_ready(mfa_env: Path) -> bool:
    """Whether the MFA environment's Python has what the feature script needs, checked before minutes of MFA."""
    done = subprocess.run([str(mfa_env / "bin" / "python"), "-I", "-c", "import parselmouth, praatio"],
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return done.returncode == 0


def mfa_version(mfa_env: Path) -> str:
    done = subprocess.run([str(mfa_env / "bin" / "mfa"), "version"], capture_output=True, text=True,
                          env={**os.environ, "PATH": f"{mfa_env / 'bin'}:/usr/bin:/bin"})
    lines = done.stdout.strip().splitlines()
    return lines[-1].strip() if lines else ""


def _chunk(data_dir: Path, jobs: list[stress.Job], mfa_env: Path, work: Path, align: Callable, features: Callable,
           tools: dict, counts: dict) -> None:
    corpus = work / "corpus" / "learner"
    corpus.mkdir(parents=True)
    ready = []
    for job in jobs:
        wav = corpus / f"{job.key}.wav"
        try:
            asyncio.run(audio.to_wav16k(job.rec, wav))
        except (audio.AudioError, OSError, EOFError, wave.Error, ValueError):
            # ffmpeg can exit 0 and leave a WAV `wave` rejects (engine.py's note on reading the WAV): that recording
            # fails, the rest go on. A half-made WAV would go to MFA without its words.
            wav.unlink(missing_ok=True)
            _failed(counts, "wav")
            continue
        (corpus / f"{job.key}.lab").write_text(" ".join(job.words), encoding="utf-8")
        ready.append(job)
    if not ready:
        return
    # the chunk is tried again on the next run; which stage failed is printed, never its message (it may hold paths)
    for stage, step in (("mfa align", lambda: align(mfa_env, work / "corpus", work / "out", work / "mfa")),
                        ("stress features",
                         lambda: features(mfa_env, work / "corpus", work / "out", work / "features.json"))):
        try:
            found = step()
        except Exception:  # noqa: BLE001
            _failed(counts, stage, len(ready))
            return
    measured = datetime.now().isoformat(timespec="seconds")
    for job in ready:
        if job.key in found.get("failed", []):  # the feature script could not measure it: no values, tried again
            _failed(counts, "stress features")
            continue
        aligned = found["files"].get(job.key)
        record = stress.build(job, aligned, {**tools, "praat": found.get("praat", "")}, measured)
        stress.write(stress.out_path(data_dir, job.rp_id, job.idx, job.n), record)
        counts["measured" if aligned is not None else "unaligned"] += 1


def _failed(counts: dict, stage: str, n: int = 1) -> None:
    counts["failed"] += n
    counts["failed_at"][stage] += n


WORK = re.compile(r"^stress-(\d+)-\d+$")


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def remove_dead_work(data_dir: Path) -> None:
    """Deletes the work folders (recording copies, heard words, MFA's work) of runs that are no longer alive: a run
    killed with SIGKILL or a power cut never reaches its finally (PR #61 review). A running one is left alone."""
    tmp = data_dir / "tmp"
    for d in tmp.glob("stress-*") if tmp.is_dir() else []:
        m = WORK.match(d.name)
        if m and d.is_dir() and not _alive(int(m[1])):
            shutil.rmtree(d, ignore_errors=True)


def exit_on_signals() -> None:
    """Closing the terminal (SIGHUP) or `kill` (SIGTERM) end the script through SystemExit, so the chunk's finally
    still deletes its work folder."""
    def leave(signum, frame):
        raise SystemExit(128 + signum)

    for s in (signal.SIGHUP, signal.SIGTERM):
        signal.signal(s, leave)


def run(data_dir: Path, mfa_env: Path, now: bool = False, chunk: int = CHUNK, align: Callable | None = None,
        features: Callable | None = None, version: Callable | None = None) -> dict:
    """Measures the pending tries in chunks and returns the counts. A chunk that fails writes no values, so its
    recordings are tried again next time. MFA, the feature script and the version check can be replaced (tests)."""
    align, features, version = align or mfa_align, features or praat_features, version or mfa_version
    remove_dead_work(data_dir)
    counts = {"measured": 0, "unaligned": 0, "korean_or_empty": 0, "failed": 0,
              "failed_at": {"wav": 0, "mfa align": 0, "stress features": 0}, "busy": False}
    if not now and stress.in_use(data_dir, time.time()):
        counts["busy"] = True
        return counts
    jobs, counts["korean_or_empty"] = stress.pending(data_dir)
    if not jobs:
        return counts
    tools = {"mfa": version(mfa_env), "model": MODEL}
    for i in range(0, len(jobs), chunk):
        work = data_dir / "tmp" / f"stress-{os.getpid()}-{i // chunk}"
        try:
            _chunk(data_dir, jobs[i:i + chunk], mfa_env, work, align, features, tools, counts)
        finally:
            shutil.rmtree(work, ignore_errors=True)
    return counts


def env() -> dict[str, str]:
    """Settings the way the server reads them: the repository's .env, then server/.env, then the environment."""
    return {**read_env_file(REPO_DIR / ".env"), **read_env_file(SERVER_DIR / ".env"), **os.environ}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Measure stress values for recordings not measured yet.")
    parser.add_argument("--now", action="store_true", help="run even when the app was used in the last 10 minutes")
    args = parser.parse_args(argv)
    settings = env()
    mfa_env = Path(settings.get("JE_MFA_ENV", "")).expanduser()
    if not settings.get("JE_MFA_ENV") or not (mfa_env / "bin" / "mfa").exists():
        print("stress: set JE_MFA_ENV in server/.env to the MFA environment folder (server/.env.example)")
        return 1
    data_dir = Path(settings.get("JE_DATA_DIR") or DEFAULT_DATA_DIR).expanduser()
    if not (data_dir / "roleplays").is_dir():
        print("stress: JE_DATA_DIR has no roleplays/; check the path in server/.env (nothing was made)")
        return 1
    if not features_ready(mfa_env):
        print("stress: the MFA environment cannot import parselmouth and praatio (docs/guide, PRONUNCIATION stress)")
        return 1
    t0 = time.monotonic()
    counts = run(data_dir, mfa_env, now=args.now)
    if counts["busy"]:
        print("stress: the app was used in the last 10 minutes; stopped (--now runs anyway)")
        return 2
    stages = ", ".join(f"{stage} {n}" for stage, n in counts["failed_at"].items() if n)
    print(f"stress: measured {counts['measured']}, unaligned {counts['unaligned']}, "
          f"left out (Korean or no words) {counts['korean_or_empty']}, failed {counts['failed']}"
          f"{f' ({stages})' if stages else ''}, {time.monotonic() - t0:.0f} s")
    return 0


if __name__ == "__main__":
    exit_on_signals()
    os.nice(10)  # the WAV conversions too; MFA and Praat also run at background priority
    sys.exit(main())
