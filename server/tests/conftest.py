import pytest

from je_server.config import Settings


@pytest.fixture
def settings(tmp_path):
    return Settings(
        token="t" * 32,
        data_dir=tmp_path / "data",
        anthropic_api_key="test-key",
        tts_python="python3",
        tts_module="tts.py",
        whisper_model="model.bin",
        assets_dir=tmp_path / "assets",
    )


@pytest.fixture
def auth(settings):
    return {"Authorization": f"Bearer {settings.token}"}
