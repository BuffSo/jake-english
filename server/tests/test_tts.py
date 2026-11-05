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


async def test_speaking_rate_by_voice_and_language(voice, tmp_path):
    # 2026-11-05 Ryan's greeting sounded drawn out at 1x, so his Korean is 1.3x like the reply reader.
    # The user then set Jake's Korean to 1.1x and kept Ryan's. English model lines stay at 1x.
    await voice.say("안녕하세요.", "ryan", "korean", urgent=True)
    await voice.say("Hello.", "ryan", "english", urgent=True)
    await voice.say("카페 상황으로 하고 싶어.", "jake", "korean", urgent=True)
    rates = (tmp_path / ".tmp" / "rates.txt").read_text(encoding="utf-8").splitlines()
    assert rates == ["ryan korean 1.3", "ryan english 1.0", "jake korean 1.1"]


async def test_key_changes_with_speaking_rate():
    from je_server import tts

    assert audio_key("ryan", "korean", "안녕") != tts.hashlib.sha256("ryan|korean|안녕".encode()).hexdigest()


async def test_new_jake_rate_is_not_served_from_the_old_cache():
    # sounds made before Jake's rate changed were keyed with 1.3; asking again must make a new one at 1.1
    from je_server import tts

    def old_key(voice, lang, text):
        return tts.hashlib.sha256(f"{voice}|{lang}|1.3|{text}".encode()).hexdigest()

    text = "카페 상황으로 하고 싶어."
    assert audio_key("jake", "korean", text) != old_key("jake", "korean", text)
    # Ryan's Korean did not change, so his prepared phrases are still found in the cache
    assert audio_key("ryan", "korean", text) == old_key("ryan", "korean", text)


async def test_same_slow_copy_made_twice_at_once(voice, tmp_path):
    # PR #12 review: two requests for an uncached 0.8x copy shared one temp file; one got FileNotFoundError
    import shutil

    from audiotools import make_m4a

    key = audio_key("ryan", "english", "Slow down.")
    shutil.copy(make_m4a(tmp_path, "sine=f=220:r=24000", 2), voice.path(key))
    paths = await asyncio.gather(*[voice.rate_file(key, 0.8) for _ in range(3)])
    assert len(set(paths)) == 1 and paths[0].exists() and paths[0].stat().st_size > 0
