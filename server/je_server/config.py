"""Settings from server/.env and the repository's .env.

Paths to the local voice setup, the whisper model and the private images live only in
server/.env, which git ignores. Nothing here has a default that points at a personal folder.
"""
from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from .claude import QUICKS, TALKERS, WRITERS

SERVER_DIR = Path(__file__).resolve().parent.parent
REPO_DIR = SERVER_DIR.parent
DEFAULT_DATA_DIR = "~/Library/Application Support/jake-english"
MIN_TOKEN = 32
# Without JE_CLAUDE_WRITER / JE_CLAUDE_QUICK / JE_CLAUDE_RECOMMEND the server runs the spec's models (keys of
# claude.WRITERS, claude.QUICKS; the recommendation picks from QUICKS too)
DEFAULT_WRITER = "sonnet"
DEFAULT_QUICK = "haiku"
DEFAULT_RECOMMEND = "sonnet"
DEFAULT_TALK = "sonnet"  # JE_CLAUDE_TALK: Ryan in free talk, a key of claude.TALKERS
DEFAULT_HINT = "sonnet"  # JE_CLAUDE_HINT: Sohee chance in free talk, a key of claude.QUICKS


@dataclass(frozen=True)
class Settings:
    token: str
    data_dir: Path
    anthropic_api_key: str
    tts_python: str
    tts_module: str
    whisper_model: str
    assets_dir: Path
    host: str = "127.0.0.1"
    port: int = 8787
    whisper_exe: str = "whisper-server"
    whisper_port: int = 8788
    claude_writer: str = DEFAULT_WRITER
    claude_quick: str = DEFAULT_QUICK
    claude_recommend: str = DEFAULT_RECOMMEND
    claude_talk: str = DEFAULT_TALK
    claude_hint: str = DEFAULT_HINT


def _model_name(env: Mapping[str, str], key: str, choices: Mapping[str, object], default: str) -> str:
    name = env.get(key, "").strip().lower() or default
    if name not in choices:
        raise ValueError(f"{key} must be one of {', '.join(choices)}, not {name!r}")
    return name


def read_env_file(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.exists():
        return out
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        out[key.strip()] = value.strip().strip('"').strip("'")
    return out


def load_settings(env: Mapping[str, str] | None = None) -> Settings:
    if env is None:
        merged = {**read_env_file(REPO_DIR / ".env"), **read_env_file(SERVER_DIR / ".env")}
        merged.update(os.environ)
        env = merged
    token = env.get("JE_TOKEN", "")
    if len(token) < MIN_TOKEN:
        raise ValueError(f"JE_TOKEN must be set in server/.env and be at least {MIN_TOKEN} characters")
    return Settings(
        token=token,
        data_dir=Path(env.get("JE_DATA_DIR", DEFAULT_DATA_DIR)).expanduser(),
        anthropic_api_key=env.get("ANTHROPIC_API_KEY", ""),
        tts_python=env.get("JE_TTS_PYTHON", ""),
        tts_module=env.get("JE_TTS_MODULE", ""),
        whisper_model=env.get("JE_WHISPER_MODEL", ""),
        assets_dir=Path(env.get("JE_ASSETS_DIR", "")).expanduser(),
        host=env.get("JE_HOST", "127.0.0.1"),
        port=int(env.get("JE_PORT", "8787")),
        whisper_exe=env.get("JE_WHISPER_SERVER", "whisper-server"),
        whisper_port=int(env.get("JE_WHISPER_PORT", "8788")),
        claude_writer=_model_name(env, "JE_CLAUDE_WRITER", WRITERS, DEFAULT_WRITER),
        claude_quick=_model_name(env, "JE_CLAUDE_QUICK", QUICKS, DEFAULT_QUICK),
        claude_recommend=_model_name(env, "JE_CLAUDE_RECOMMEND", QUICKS, DEFAULT_RECOMMEND),
        claude_talk=_model_name(env, "JE_CLAUDE_TALK", TALKERS, DEFAULT_TALK),
        claude_hint=_model_name(env, "JE_CLAUDE_HINT", QUICKS, DEFAULT_HINT),
    )
