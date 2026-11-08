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


# spec play-button-feedback 4: the play copy of a recording starts just before the speech and ends just after it
LOUD_1_TO_2 = "aevalsrc='if(between(t,1,2),0.5*sin(2*PI*220*t),0)':s=16000:d=5"


async def test_speech_span_finds_the_loud_part(tmp_path):
    span = audio.speech_span(make_wav(tmp_path, LOUD_1_TO_2, 5))
    assert span is not None
    assert abs(span[0] - 1.0) <= 0.05 and abs(span[1] - 2.0) <= 0.05


async def test_speech_span_none_for_silence(tmp_path):
    assert audio.speech_span(make_wav(tmp_path, "anullsrc=r=16000:cl=mono", 2)) is None


async def test_a_soft_start_stays_in_the_cut(tmp_path):
    # a soft first word (about -40 dBFS) before a loud one: -35 dBFS would start the cut after it
    soft = "aevalsrc='if(between(t,0.5,1),0.014*sin(2*PI*220*t),if(between(t,1,2),0.5*sin(2*PI*220*t),0))':s=16000:d=3"
    span = audio.speech_span(make_wav(tmp_path, soft, 3))
    assert span is not None and abs(span[0] - 0.5) <= 0.05


async def test_play_cut_trims_and_puts_moov_first(tmp_path):
    from audiotools import top_boxes

    src = make_m4a(tmp_path, LOUD_1_TO_2.replace("s=16000", "s=44100"), 5)
    await audio.play_cut(src, (1.0, 2.0), 5.0, tmp_path / "cut.m4a")
    assert 1.5 <= duration(tmp_path / "cut.m4a") <= 1.7  # 0.8 .. 2.4
    boxes = top_boxes(tmp_path / "cut.m4a")
    assert boxes.index("moov") < boxes.index("mdat")


async def test_play_cut_without_speech_keeps_everything(tmp_path):
    from audiotools import top_boxes

    src = make_m4a(tmp_path, "anullsrc=r=44100:cl=mono", 3)
    await audio.play_cut(src, None, 3.0, tmp_path / "cut.m4a")
    assert abs(duration(tmp_path / "cut.m4a") - duration(src)) <= 0.05
    boxes = top_boxes(tmp_path / "cut.m4a")
    assert boxes.index("moov") < boxes.index("mdat")


async def test_play_cut_keeps_the_ends_inside_the_recording(tmp_path):
    src = make_m4a(tmp_path, "sine=f=220:r=44100", 2)
    await audio.play_cut(src, (0.05, 1.9), 2.0, tmp_path / "cut.m4a")
    assert abs(duration(tmp_path / "cut.m4a") - duration(src)) <= 0.05
