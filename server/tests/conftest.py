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


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def fake_claude():
    from fakes import FakeClaude

    return FakeClaude()


@pytest.fixture
def fake_voice(tmp_path):
    from fakes import FakeVoice

    return FakeVoice(tmp_path / "data" / "audio")


@pytest.fixture
def fake_whisper():
    from fakes import FakeWhisper

    return FakeWhisper()


@pytest.fixture
def engine_factory(tmp_path, fake_claude, fake_voice, fake_whisper):
    from je_server.engine import Engine
    from je_server.store import Store

    def make():
        return Engine(Store(tmp_path / "data"), fake_claude, fake_voice, fake_whisper)

    return make


@pytest.fixture
def engine(engine_factory):
    return engine_factory()


@pytest.fixture
def talks(engine):
    from je_server.talk import Talks

    return Talks(engine)


@pytest.fixture
def client(settings, auth, engine, fake_voice, fake_whisper):
    from fastapi.testclient import TestClient

    from je_server.app import Services, create_app

    app = create_app(settings, Services(engine=engine, voice=fake_voice, whisper=fake_whisper))
    with TestClient(app, headers=auth) as c:
        yield c


@pytest.fixture
def speech_bytes(tmp_path):
    from audiotools import make_m4a

    return make_m4a(tmp_path, "sine=f=220:r=44100", 2).read_bytes()


@pytest.fixture
def silent_bytes(tmp_path):
    from audiotools import make_m4a

    return make_m4a(tmp_path, "anullsrc=r=44100:cl=mono", 2).read_bytes()


@pytest.fixture
async def engine_with_rp(engine):
    rp = await engine.create("길 묻기")
    user_idx = next(l.idx for l in rp.lines if l.speaker == "user")
    await engine.line(rp.id, user_idx)
    return engine, rp.id, user_idx
