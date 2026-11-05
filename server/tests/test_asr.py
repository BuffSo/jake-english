import httpx
import pytest

from je_server.asr import Whisper

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


def whisper_with(handler) -> Whisper:
    w = Whisper("whisper-server", "model.bin", 9999)
    w.client = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://127.0.0.1:9999")
    return w


async def test_transcribe_sends_language_and_cleans_text(tmp_path):
    seen = {}

    def handler(request: httpx.Request):
        seen["path"] = request.url.path
        seen["body"] = request.read()
        return httpx.Response(200, json={"text": " [BLANK_AUDIO] Where is the station?\n"})

    wav = tmp_path / "a.wav"
    wav.write_bytes(b"RIFF")
    text = await whisper_with(handler).transcribe(wav, "en")
    assert text == "Where is the station?"
    assert seen["path"] == "/inference"
    assert b'name="language"' in seen["body"] and b"\r\n\r\nen\r\n" in seen["body"]
    assert b"response_format" in seen["body"]


async def test_bracket_only_text_is_empty(tmp_path):
    wav = tmp_path / "a.wav"
    wav.write_bytes(b"RIFF")
    w = whisper_with(lambda r: httpx.Response(200, json={"text": " (silence) "}))
    assert await w.transcribe(wav, "auto") == ""
