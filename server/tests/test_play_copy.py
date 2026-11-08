"""The play copy of a recording (spec play-button-feedback 4): served instead of the original, cut to the speech with
moov first, made once, and never in the way of a try."""
import asyncio

import pytest

from audiotools import duration, make_m4a, top_boxes
from je_server import audio

pytestmark = pytest.mark.anyio

LOUD_1_TO_2 = "aevalsrc='if(between(t,1,2),0.5*sin(2*PI*220*t),0)':s=44100:d=5"


@pytest.fixture
def anyio_backend():
    return "asyncio"


async def run(engine, rp_id, idx, body, mode="turn"):
    return [e async for e in engine.attempt(rp_id, idx, body, mode)]


@pytest.fixture
def quiet_then_tone(tmp_path):
    return make_m4a(tmp_path, LOUD_1_TO_2, 5).read_bytes()


async def test_the_copy_is_cut_and_moov_first(engine_with_rp, quiet_then_tone):
    engine, rp_id, idx = engine_with_rp
    await run(engine, rp_id, idx, quiet_then_tone)
    path = await engine.recording(rp_id, idx, 1)
    assert path == engine.store.play_path(rp_id, idx, 1)
    assert 1.5 <= duration(path) <= 1.7
    boxes = top_boxes(path)
    assert boxes.index("moov") < boxes.index("mdat")
    assert engine.store.find_rec(rp_id, idx, 1).read_bytes() == quiet_then_tone  # the original stays


async def test_nothing_is_left_running_after_an_attempt(engine_with_rp, quiet_then_tone):
    # a copy made beside the answer left an ffmpeg task behind; closing the event loop then hung now and then (the
    # whole test run, 2026-11-08), and a server restart could do the same. The copy is made at the first replay only.
    engine, rp_id, idx = engine_with_rp
    await run(engine, rp_id, idx, quiet_then_tone)
    assert not engine.plays
    assert not engine.store.play_path(rp_id, idx, 1).exists()


async def test_the_copy_is_made_at_the_first_replay_and_kept(engine_with_rp, quiet_then_tone, monkeypatch):
    engine, rp_id, idx = engine_with_rp
    await run(engine, rp_id, idx, quiet_then_tone)
    real = audio.play_cut
    calls = []

    async def counted(*args):
        calls.append(args)
        await real(*args)

    monkeypatch.setattr(audio, "play_cut", counted)
    first = await engine.recording(rp_id, idx, 1)
    second = await engine.recording(rp_id, idx, 1)
    assert first == second == engine.store.play_path(rp_id, idx, 1)
    assert len(calls) == 1


async def test_two_requests_at_once_make_the_copy_once(engine_with_rp, quiet_then_tone, monkeypatch):
    engine, rp_id, idx = engine_with_rp
    await run(engine, rp_id, idx, quiet_then_tone)
    real = audio.play_cut
    calls = []

    async def counted(*args):
        calls.append(args)
        await asyncio.sleep(0.05)
        await real(*args)

    monkeypatch.setattr(audio, "play_cut", counted)
    a, b = await asyncio.gather(engine.recording(rp_id, idx, 1), engine.recording(rp_id, idx, 1))
    assert a == b == engine.store.play_path(rp_id, idx, 1)
    assert len(calls) == 1


async def test_a_failing_cut_serves_the_original(engine_with_rp, quiet_then_tone, monkeypatch):
    engine, rp_id, idx = engine_with_rp

    async def broken(*args):
        raise audio.AudioError("ffmpeg failed")

    monkeypatch.setattr(audio, "play_cut", broken)
    await run(engine, rp_id, idx, quiet_then_tone)
    path = await engine.recording(rp_id, idx, 1)
    assert path == engine.store.find_rec(rp_id, idx, 1)
    assert not engine.store.play_path(rp_id, idx, 1).exists()


async def test_the_copy_is_not_a_try(engine_with_rp, quiet_then_tone):
    engine, rp_id, idx = engine_with_rp
    await run(engine, rp_id, idx, quiet_then_tone)
    await engine.recording(rp_id, idx, 1)
    assert engine.store.play_path(rp_id, idx, 1).is_file()
    n, _ = engine.store.next_rec(rp_id, idx)
    assert n == 2
    assert engine.store.find_rec(rp_id, idx, 2) is None


async def test_a_missing_recording_is_not_found(engine_with_rp):
    from je_server.engine import NotFound

    engine, rp_id, idx = engine_with_rp
    with pytest.raises(NotFound):
        await engine.recording(rp_id, idx, 9)
    assert not engine.store.play_path(rp_id, idx, 9).exists()
