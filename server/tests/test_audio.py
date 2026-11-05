import pytest

from audiotools import duration, make_m4a, make_wav
from je_server import audio

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


async def test_silence_and_faint_noise_have_no_speech(tmp_path):
    assert not await audio.has_speech(make_wav(tmp_path, "anullsrc=r=16000:cl=mono", 2))
    assert not await audio.has_speech(make_wav(tmp_path, "anoisesrc=r=16000:a=0.01", 2))


async def test_tone_has_speech(tmp_path):
    assert await audio.has_speech(make_wav(tmp_path, "sine=f=220:r=16000", 2))


async def test_too_short_has_no_speech(tmp_path):
    assert not await audio.has_speech(make_wav(tmp_path, "sine=f=220:r=16000", 0.3))


async def test_to_wav16k_converts_and_reports_length(tmp_path):
    src = make_m4a(tmp_path, "sine=f=220:r=44100", 1.5)
    secs = await audio.to_wav16k(src, tmp_path / "out.wav")
    assert 1.4 < secs < 1.6
    import wave
    with wave.open(str(tmp_path / "out.wav")) as w:
        assert w.getframerate() == 16000 and w.getnchannels() == 1


async def test_to_wav16k_rejects_non_audio(tmp_path):
    bad = tmp_path / "bad.m4a"
    bad.write_bytes(b"not audio")
    with pytest.raises(audio.AudioError):
        await audio.to_wav16k(bad, tmp_path / "out.wav")


async def test_rate_keeps_length_ratio(tmp_path):
    src = make_m4a(tmp_path, "sine=f=220:r=24000", 2)
    await audio.with_rate(src, 0.8, tmp_path / "slow.m4a")
    assert 2.4 < duration(tmp_path / "slow.m4a") < 2.6


async def test_a_single_click_is_not_speech(tmp_path):
    # review: a pocket bump or the tap that ends recording passed the peak-only gate, then whisper said "you"
    click = make_wav(tmp_path, "sine=f=1000:r=16000:duration=0.1,apad", 2)
    assert not await audio.has_speech(click)
