"""The character pictures the app shows live in the repository (server/assets/, ADR-0015).

A fresh clone with an empty JE_ASSETS_DIR must still serve every picture, so the server reads the repository folder
by default, and the tests check that every name the server lists has its file there (a forgotten picture fails CI).
"""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from je_server.app import ASSETS, Services, create_app
from je_server.config import Settings, load_settings

REPO_ASSETS = Path(__file__).resolve().parents[1] / "assets"  # server/assets, worked out apart from config.py
PNG = b"\x89PNG\r\n\x1a\n"
TOKEN = "x" * 32


@pytest.mark.parametrize("env", [{}, {"JE_ASSETS_DIR": ""}, {"JE_ASSETS_DIR": "  "}])
def test_assets_dir_defaults_to_the_repository_folder(env):
    assert load_settings({"JE_TOKEN": TOKEN, **env}).assets_dir == REPO_ASSETS


def test_assets_dir_set_in_env_wins(tmp_path):
    # kept as before: a Mac can point the server at its own folder (e.g. to try a new picture before committing it)
    assert load_settings({"JE_TOKEN": TOKEN, "JE_ASSETS_DIR": str(tmp_path)}).assets_dir == tmp_path


def test_every_listed_picture_is_a_png_in_the_repository():
    missing = sorted(n for n in ASSETS if not (REPO_ASSETS / n).is_file())
    assert missing == []
    for n in ASSETS:
        assert (REPO_ASSETS / n).read_bytes()[:8] == PNG, n


def test_repository_folder_holds_only_listed_pictures():
    # drafts, body pictures and originals stay in the private folder; only what the server serves goes public
    assert REPO_ASSETS.is_dir()
    # dotfiles (the Mac's .DS_Store) are ignored by git and never served
    extra = sorted(p.name for p in REPO_ASSETS.iterdir()
                   if p.name not in ASSETS and p.name != "README.md" and not p.name.startswith("."))
    assert extra == []


def test_fresh_clone_serves_every_home_picture(tmp_path, engine, fake_voice, fake_whisper):
    # the settings a fresh clone gets: JE_ASSETS_DIR left empty
    loaded = load_settings({"JE_TOKEN": TOKEN, "JE_ASSETS_DIR": "", "JE_DATA_DIR": str(tmp_path / "data")})
    settings = Settings(token=TOKEN, data_dir=loaded.data_dir, anthropic_api_key="", tts_python="", tts_module="",
                        whisper_model="", assets_dir=loaded.assets_dir)
    app = create_app(settings, Services(engine=engine, voice=fake_voice, whisper=fake_whisper))
    with TestClient(app, headers={"Authorization": f"Bearer {TOKEN}"}) as c:
        images = c.get("/home").json()["images"]
        paths = [images["front"], images["listening"], images["jake"], images["sohee"]["face"],
                 images["sohee"]["whisper"], *(p for pair in images["thinking"].values() for p in pair)]
        assert len(paths) == len(ASSETS)
        for path in paths:
            assert "?v=" in path, path  # the file is on disk, so the address carries its version
            r = c.get(path)
            assert r.status_code == 200 and r.content[:8] == PNG, path
