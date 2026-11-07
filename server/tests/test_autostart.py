"""scripts/autostart.sh: the launchd agent it writes for the Mac server (ADR-0012).

The script runs in a throwaway git repo with a worktree, a fake HOME and fake tools on PATH;
nothing here touches launchctl or the real LaunchAgents folder.
"""
from __future__ import annotations

import os
import plistlib
import shutil
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "autostart.sh"
SYSTEM_PATH = "/usr/bin:/bin:/usr/sbin:/sbin"


def git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True,
                   env={**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com",
                        "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com"})


def tool(folder: Path, name: str) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    exe = folder / name
    exe.write_text("#!/bin/sh\n")
    exe.chmod(0o755)
    return exe


@pytest.fixture
def repo(tmp_path):
    """The original folder (main) with server/.env, and a worktree of it, like an Orca card."""
    main = tmp_path / "main"
    (main / "server" / "scripts").mkdir(parents=True)
    shutil.copy(SCRIPT, main / "server" / "scripts" / "autostart.sh")
    git(tmp_path, "init", "-q", "-b", "main", str(main))
    git(main, "add", "server")
    git(main, "commit", "-q", "-m", "init")
    git(main, "worktree", "add", "-q", "-b", "card", str(tmp_path / "card"))
    (main / "server" / ".env").write_text("JE_TOKEN=x\n")  # git ignores it, so only main has it
    return main, tmp_path / "card"


@pytest.fixture
def tools(tmp_path):
    return {"uv": tool(tmp_path / "uvbin", "uv"),
            "ffmpeg": tool(tmp_path / "brew", "ffmpeg"),
            "whisper-server": tool(tmp_path / "whisper", "whisper-server")}


def run(folder: Path, home: Path, tools: dict[str, Path], *args: str) -> subprocess.CompletedProcess:
    path = ":".join([*dict.fromkeys(str(p.parent) for p in tools.values()), SYSTEM_PATH])
    return subprocess.run(["/bin/sh", str(folder / "server" / "scripts" / "autostart.sh"), *args],
                          capture_output=True, text=True, env={"HOME": str(home), "PATH": path})


def plist_from(result: subprocess.CompletedProcess) -> dict:
    assert result.returncode == 0, result.stderr
    return plistlib.loads(result.stdout.encode())


def test_runs_the_original_folders_server_even_from_a_worktree(repo, tools, tmp_path):
    main, card = repo
    job = plist_from(run(card, tmp_path / "home", tools, "plist"))
    assert job["WorkingDirectory"] == str((main / "server").resolve())
    assert job["ProgramArguments"] == [str(tools["uv"]), "run", "python", "-m", "je_server"]


def test_path_has_the_folders_of_uv_ffmpeg_and_whisper_server(repo, tools, tmp_path):
    # launchd's own PATH is only the system folders, where none of them are
    main, _ = repo
    job = plist_from(run(main, tmp_path / "home", tools, "plist"))
    folders = job["EnvironmentVariables"]["PATH"].split(":")
    assert folders == [str(tmp_path / "uvbin"), str(tmp_path / "brew"), str(tmp_path / "whisper"),
                       "/usr/bin", "/bin", "/usr/sbin", "/sbin"]


def test_starts_at_login_comes_back_when_it_dies_and_logs_where_it_always_has(repo, tools, tmp_path):
    main, _ = repo
    home = tmp_path / "home"
    job = plist_from(run(main, home, tools, "plist"))
    assert job["RunAtLoad"] is True
    assert job["KeepAlive"] is True
    log = str(home / "Library" / "Logs" / "jake-english" / "server.log")
    assert job["StandardOutPath"] == log
    assert job["StandardErrorPath"] == log


def test_refuses_when_a_tool_the_server_needs_is_not_on_path(repo, tools, tmp_path):
    main, _ = repo
    del tools["ffmpeg"]
    result = run(main, tmp_path / "home", tools, "plist")
    assert result.returncode != 0
    assert "ffmpeg" in result.stderr
    assert result.stdout == ""


def test_refuses_when_the_original_folder_has_no_server_env(repo, tools, tmp_path):
    main, card = repo
    (main / "server" / ".env").unlink()
    result = run(card, tmp_path / "home", tools, "plist")
    assert result.returncode != 0
    assert "server/.env" in result.stderr
    assert result.stdout == ""


FAKE_LAUNCHCTL = """#!/bin/sh
# launchd stand-in: after bootout the job stays listed (state SIGTERMed) for two more prints,
# as the real one does while the server shuts whisper and the voice down
state="$HOME/fake-launchd"
case "$1" in
  print)
    [ -f "$state/loaded" ] || exit 113
    if [ -f "$state/stopping" ]; then
      left=$(cat "$state/stopping")
      if [ "$left" -le 0 ]; then rm -f "$state/loaded" "$state/stopping"; exit 113; fi
      echo $((left - 1)) > "$state/stopping"
    fi
    ;;
  bootout) echo 2 > "$state/stopping" ;;
esac
"""


def test_stop_returns_only_once_the_old_server_is_gone(repo, tools, tmp_path):
    # a card starts its worktree server right after `stop`; the old whisper-server must not hold its port
    main, _ = repo
    home = tmp_path / "home"
    (home / "fake-launchd").mkdir(parents=True)
    (home / "fake-launchd" / "loaded").touch()
    tools["launchctl"] = tool(tmp_path / "fakebin", "launchctl")
    tools["launchctl"].write_text(FAKE_LAUNCHCTL)
    result = run(main, home, tools, "stop")
    assert result.returncode == 0, result.stderr
    assert not (home / "fake-launchd" / "loaded").exists()


def test_escapes_paths_for_the_plist(tmp_path, tools):
    # a folder name with & would otherwise break the XML
    base = tmp_path / "a&b"
    base.mkdir()
    main = base / "main"
    (main / "server" / "scripts").mkdir(parents=True)
    shutil.copy(SCRIPT, main / "server" / "scripts" / "autostart.sh")
    git(base, "init", "-q", "-b", "main", str(main))
    (main / "server" / ".env").write_text("JE_TOKEN=x\n")
    job = plist_from(run(main, tmp_path / "home", tools, "plist"))
    assert job["WorkingDirectory"] == str((main / "server").resolve())
