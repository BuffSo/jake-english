import pytest
from fastapi.testclient import TestClient

from je_server.app import create_app
from je_server.config import load_settings


def test_health_needs_token(settings):
    c = TestClient(create_app(settings))
    assert c.get("/health").status_code == 401
    assert c.get("/health", headers={"Authorization": "Bearer wrong"}).status_code == 401
    assert c.get("/health", headers={"Authorization": settings.token}).status_code == 401


def test_health_with_token(settings, auth):
    c = TestClient(create_app(settings))
    r = c.get("/health", headers=auth)
    assert r.status_code == 200 and r.json() == {"ok": True}


def test_settings_require_token(tmp_path):
    with pytest.raises(ValueError, match="JE_TOKEN"):
        load_settings({"JE_DATA_DIR": str(tmp_path)})
    with pytest.raises(ValueError, match="JE_TOKEN"):
        load_settings({"JE_DATA_DIR": str(tmp_path), "JE_TOKEN": "short"})


def test_settings_read_values(tmp_path):
    s = load_settings({"JE_TOKEN": "x" * 32, "JE_DATA_DIR": str(tmp_path), "JE_PORT": "9000"})
    assert s.port == 9000 and s.data_dir == tmp_path and s.host == "127.0.0.1"
