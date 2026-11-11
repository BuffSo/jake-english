"""server/.env lines left empty must mean the default, the same as a missing line.

server/.env.example leaves JE_DATA_DIR empty and says empty means the Mac's app data folder. Before this fix an empty
value became Path(""), the folder the server was started from (usually server/, inside the repository), so a fresh
clone that only copied .env.example kept its practice records in the repository, where an agent searches, copies and
commits files. The other lines with a default (JE_HOST, JE_PORT, JE_WHISPER_SERVER, JE_WHISPER_PORT) follow the same
rule: empty used to stop the server with int("") or run an empty program name.
"""
from pathlib import Path

import pytest

from je_server.config import load_settings

TOKEN = {"JE_TOKEN": "x" * 32}
BLANKS = ["", "  "]


@pytest.mark.parametrize("env", [{}, {"JE_DATA_DIR": ""}, {"JE_DATA_DIR": "  "}])
def test_data_dir_defaults_to_the_app_data_folder(env, monkeypatch, tmp_path):
    # a made-up home, so the expected folder is written out here apart from config.py
    monkeypatch.setenv("HOME", str(tmp_path))
    data_dir = load_settings({**TOKEN, **env}).data_dir
    assert data_dir == tmp_path / "Library" / "Application Support" / "jake-english"
    assert data_dir.is_absolute()


def test_data_dir_set_in_env_wins(monkeypatch, tmp_path):
    assert load_settings({**TOKEN, "JE_DATA_DIR": str(tmp_path / "data")}).data_dir == tmp_path / "data"
    monkeypatch.setenv("HOME", str(tmp_path))
    assert load_settings({**TOKEN, "JE_DATA_DIR": "~/elsewhere"}).data_dir == tmp_path / "elsewhere"


@pytest.mark.parametrize("blank", BLANKS)
def test_empty_host_and_port_keep_the_defaults(blank):
    s = load_settings({**TOKEN, "JE_HOST": blank, "JE_PORT": blank})
    assert s.host == "127.0.0.1" and s.port == 8787


@pytest.mark.parametrize("blank", BLANKS)
def test_empty_whisper_settings_keep_the_defaults(blank):
    s = load_settings({**TOKEN, "JE_WHISPER_SERVER": blank, "JE_WHISPER_PORT": blank})
    assert s.whisper_exe == "whisper-server" and s.whisper_port == 8788


def test_host_port_and_whisper_settings_read_from_env():
    s = load_settings({**TOKEN, "JE_HOST": " 127.0.0.2 ", "JE_PORT": "8791",
                       "JE_WHISPER_SERVER": "/opt/whisper/bin/whisper-server", "JE_WHISPER_PORT": " 8792 "})
    assert s.host == "127.0.0.2" and s.port == 8791
    assert s.whisper_exe == "/opt/whisper/bin/whisper-server" and s.whisper_port == 8792
