import asyncio
import sys
from pathlib import Path

import pytest

from je_server.tts import Voice, VoiceError, audio_key

pytestmark = pytest.mark.anyio
FAKE_WORKER = Path(__file__).with_name("fake_tts_worker.py")


@pytest.fixture
def anyio_backend():
    return "asyncio"


def calls(tmp_path) -> list[str]:
    log = tmp_path / ".tmp" / "calls.txt"
    return log.read_text(encoding="utf-8").splitlines() if log.exists() else []


@pytest.fixture
async def voice(tmp_path):
    v = Voice(sys.executable, "unused", tmp_path, worker=FAKE_WORKER)
    await v.start()
    yield v
    await v.stop()


async def test_say_caches_by_text(voice, tmp_path):
    k1 = await voice.say("Hello.", "ryan", "english", urgent=False)
    k2 = await voice.say("Hello.", "ryan", "english", urgent=True)
    assert k1 == k2 == audio_key("ryan", "english", "Hello.")
    assert voice.path(k1).exists() and calls(tmp_path) == ["Hello."]


async def test_key_depends_on_voice_and_lang():
    assert len({audio_key("ryan", "english", "Hi"), audio_key("jake", "english", "Hi"),
                audio_key("ryan", "korean", "Hi")}) == 3
    assert len(audio_key("ryan", "english", "Hi")) == 64


async def test_same_text_in_flight_is_made_once(voice, tmp_path):
    keys = await asyncio.gather(*[voice.say("Once.", "ryan", "english", urgent=False) for _ in range(3)])
    assert len(set(keys)) == 1 and calls(tmp_path) == ["Once."]


async def test_urgent_jumps_the_queue(voice, tmp_path):
    slow = [asyncio.create_task(voice.say(f"line {i}", "ryan", "english", urgent=False)) for i in range(3)]
    fast = asyncio.create_task(voice.say("평가", "ryan", "korean", urgent=True))
    await asyncio.gather(*slow, fast)
    assert calls(tmp_path).index("평가") <= 1


async def test_worker_error_raises(voice):
    with pytest.raises(VoiceError):
        await voice.say("FAIL", "ryan", "english", urgent=True)


async def test_worker_restarts_after_dying(voice):
    with pytest.raises(VoiceError):
        await voice.say("DIE", "ryan", "english", urgent=True)
    assert voice.path(await voice.say("After.", "ryan", "english", urgent=True)).exists()


async def test_prepared_jobs_go_in_rank_order(voice, tmp_path):
    jobs = [asyncio.create_task(voice.say(f"rank {r}", "ryan", "english", urgent=False, rank=r)) for r in (5, 3, 9, 1)]
    await asyncio.gather(*jobs)
    # all four are queued before the worker takes one, so it takes them by rank
    assert calls(tmp_path) == ["rank 1", "rank 3", "rank 5", "rank 9"]
