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
    # 2026-11-05 Ryan's greeting sounded drawn out at 1x, so his Korean became 1.3x like the reply reader.
    # The user then set Jake's Korean to 1.1x, later found Ryan's 1.3x a bit fast (1.2x) and then had Jake at 1x.
    # English model lines stay at 1x.
    await voice.say("안녕하세요.", "ryan", "korean", urgent=True)
    await voice.say("Hello.", "ryan", "english", urgent=True)
    await voice.say("카페 상황으로 하고 싶어.", "jake", "korean", urgent=True)
    rates = (tmp_path / ".tmp" / "rates.txt").read_text(encoding="utf-8").splitlines()
    assert rates == ["ryan korean 1.2", "ryan english 1.0", "jake korean 1.0"]


async def test_key_changes_with_speaking_rate():
    from je_server import tts

    assert audio_key("ryan", "korean", "안녕") != tts.hashlib.sha256("ryan|korean|안녕".encode()).hexdigest()


async def test_new_rates_are_not_served_from_the_old_cache():
    # sounds made before the rates changed were keyed with 1.3; asking again must make new ones (Jake 1.1, Ryan 1.2)
    from je_server import tts

    def old_key(voice, lang, text):
        return tts.hashlib.sha256(f"{voice}|{lang}|1.3|{text}".encode()).hexdigest()

    text = "카페 상황으로 하고 싶어."
    assert audio_key("jake", "korean", text) != old_key("jake", "korean", text)
    # Ryan's Korean moved from 1.3x to 1.2x (2026-11-05), so his old phrases are not served either
    assert audio_key("ryan", "korean", text) != old_key("ryan", "korean", text)


async def test_same_slow_copy_made_twice_at_once(voice, tmp_path):
    # PR #12 review: two requests for an uncached 0.8x copy shared one temp file; one got FileNotFoundError
    import shutil

    from audiotools import make_m4a

    key = audio_key("ryan", "english", "Slow down.")
    shutil.copy(make_m4a(tmp_path, "sine=f=220:r=24000", 2), voice.path(key))
    paths = await asyncio.gather(*[voice.rate_file(key, 0.8) for _ in range(3)])
    assert len(set(paths)) == 1 and paths[0].exists() and paths[0].stat().st_size > 0


async def test_a_worker_too_slow_to_start_is_not_kept(tmp_path):
    # PR #12 review: a restart that timed out left the half-started worker in place; the next job read its
    # late {"ready": true} as the answer and failed, and the answers stayed one job behind after that
    v = Voice(sys.executable, f"slow-second:{tmp_path / 'launches'}", tmp_path, worker=FAKE_WORKER)
    v.start_timeout = 0.3
    await v.start()
    try:
        with pytest.raises(VoiceError):
            await v.say("DIE", "ryan", "english", urgent=True)
        with pytest.raises(VoiceError):
            await v.say("Slow start.", "ryan", "english", urgent=True)  # the restart times out
        for text in ("After.", "And after."):
            assert v.path(await v.say(text, "ryan", "english", urgent=True)).exists()
    finally:
        await v.stop()


# --- 2026-11-05: Jake's recommended situation came out as 「…연습하고 싶~」, its last sound swallowed by the
# voice model (whisper heard 「싶다」; three new takes of the same sentence all ended clearly). Sounds made once and
# played as they are (Jake, Ryan's fixed phrases) are heard back and made again when the last word is missing.


def test_ends_right():
    from je_server.tts import ends_right

    assert not ends_right("은행 창구에서 서류를 물어보는 상황으로 연습하고 싶어.", "은행 창구에서 서류를 물어보는 상황으로 연습하고 싶다.")
    assert ends_right("안녕하세요, 제이크! 오늘도 만나서 반가워요.", "안녕하세요 제이크 오늘도 만나서 반가워요")
    assert ends_right("Thanks for your help! Have a good day.", "Thanks for your help. Have a good day!")
    assert not ends_right("연습하고 싶어.", "")


def heard_in_turn(*texts):
    """A stand-in for whisper that hears these texts in turn (the last one again after that)."""
    heard: list[tuple[str, str]] = []

    async def hear(path, lang):
        assert path.exists()
        heard.append((path.name, lang))
        return texts[min(len(heard) - 1, len(texts) - 1)]

    return hear, heard


async def test_checked_sound_is_made_again_when_its_end_is_missing(tmp_path):
    hear, heard = heard_in_turn("상황으로 연습하고 싶다.", "상황으로 연습하고 싶어.")
    v = Voice(sys.executable, "unused", tmp_path, worker=FAKE_WORKER, hear=hear)
    await v.start()
    try:
        key = await v.say("상황으로 연습하고 싶어.", "jake", "korean", urgent=True, check=True)
    finally:
        await v.stop()
    assert calls(tmp_path) == ["상황으로 연습하고 싶어."] * 2 and v.path(key).exists()
    assert [lang for _, lang in heard] == ["ko", "ko"]


async def test_check_keeps_the_last_take_after_retries(tmp_path):
    hear, heard = heard_in_turn("연습하고 싶다.")
    v = Voice(sys.executable, "unused", tmp_path, worker=FAKE_WORKER, hear=hear)
    await v.start()
    try:
        key = await v.say("연습하고 싶어.", "jake", "korean", urgent=True, check=True)
    finally:
        await v.stop()
    assert len(calls(tmp_path)) == 3 and len(heard) == 3 and v.path(key).exists()


async def test_unchecked_sound_is_not_heard(tmp_path):
    hear, heard = heard_in_turn("Nothing like it.")
    v = Voice(sys.executable, "unused", tmp_path, worker=FAKE_WORKER, hear=hear)
    await v.start()
    try:
        await v.say("좋아요, 잘했어요.", "ryan", "korean", urgent=True)
    finally:
        await v.stop()
    assert heard == [] and calls(tmp_path) == ["좋아요, 잘했어요."]


async def test_a_failing_check_does_not_lose_the_sound(tmp_path):
    async def hear(path, lang):
        raise RuntimeError("whisper down")

    v = Voice(sys.executable, "unused", tmp_path, worker=FAKE_WORKER, hear=hear)
    await v.start()
    try:
        key = await v.say("반가워요.", "ryan", "korean", urgent=False, check=True)
    finally:
        await v.stop()
    assert v.path(key).exists() and calls(tmp_path) == ["반가워요."]


async def test_korean_sounds_made_before_the_pause_fix_are_not_served():
    # Korean sounds changed how they are made (shorter pauses inside a sentence, the end check), so the old
    # files must not be served; English model lines did not change and keep their keys
    from je_server import tts

    def old_key(voice, lang, text):
        return tts.hashlib.sha256(f"{voice}|{lang}|{tts.SPEAK_RATE[voice, lang]}|{text}".encode()).hexdigest()

    assert audio_key("ryan", "korean", "반가워요.") != old_key("ryan", "korean", "반가워요.")
    assert audio_key("ryan", "english", "Hello.") == old_key("ryan", "english", "Hello.")
