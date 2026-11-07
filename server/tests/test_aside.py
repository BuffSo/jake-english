"""A recording that does not follow the line: teacher Ryan answers in Korean and the line stays
(spec offscript-aside)."""
import pytest

pytestmark = pytest.mark.anyio


async def run(engine, rp_id, idx, body, mode="turn"):
    return [e async for e in engine.attempt(rp_id, idx, body, mode)]


def said(ev) -> str:
    return "".join(e["delta"] for e in ev if e["type"] == "text")


async def test_aside_answers_in_korean_and_keeps_the_line(engine_with_rp, speech_bytes, fake_whisper, fake_claude):
    engine, rp_id, user_idx = engine_with_rp
    fake_whisper.text = "Wait, let me try that again."
    before = [l.text for l in engine.store.load(rp_id).lines]
    ev = await run(engine, rp_id, user_idx, speech_bytes)
    assert ev[0] == {"type": "heard", "text": "Wait, let me try that again.", "followed": False}
    assert said(ev) == "괜찮아요, 말이 꼬일 수 있어요. 다시 해 볼까요?"
    assert not any(e["type"] == "reply" for e in ev) and ev[-1]["type"] == "done" and ev[-1]["next"] == user_idx
    rp = engine.store.load(rp_id)
    assert [l.text for l in rp.lines] == before and rp.pos == 0 and rp.attempts[user_idx][-1].aside is True
    assert fake_whisper.langs == ["en", "auto"] and fake_claude.feedback_calls == []


@pytest.mark.parametrize("mode", ["retry", "practice"])
async def test_aside_in_every_mode(engine_with_rp, speech_bytes, fake_whisper, fake_claude, mode):
    engine, rp_id, user_idx = engine_with_rp
    fake_whisper.text = "What does this mean?"
    ev = await run(engine, rp_id, user_idx, speech_bytes, mode)
    assert fake_claude.aside_calls and ev[-1]["next"] == user_idx


async def test_aside_in_shadow_uses_ryans_line(engine_with_rp, speech_bytes, fake_whisper, fake_claude):
    engine, rp_id, _ = engine_with_rp
    await engine.line(rp_id, 0)
    fake_whisper.text = "What does this mean?"
    await run(engine, rp_id, 0, speech_bytes, "shadow")
    assert fake_claude.aside_calls[-1]["line"] == engine.store.load(rp_id).lines[0].text


async def test_korean_heard_replaces_the_english_transcript(engine_with_rp, speech_bytes, fake_whisper, fake_claude):
    engine, rp_id, user_idx = engine_with_rp
    fake_whisper.text = "What does this mean?"  # whisper translated the Korean
    fake_whisper.auto_text, fake_whisper.auto_lang = "이게 무슨 뜻이에요?", "korean"
    ev = await run(engine, rp_id, user_idx, speech_bytes)
    assert ev[0]["text"] == "이게 무슨 뜻이에요?"
    sent = fake_claude.aside_calls[-1]
    assert sent["heard"] == "What does this mean?" and sent["heard_ko"] == "이게 무슨 뜻이에요?"
    assert engine.store.load(rp_id).attempts[user_idx][-1].heard == "이게 무슨 뜻이에요?"


async def test_korean_only_hangul_is_not_no_speech(engine_with_rp, speech_bytes, fake_whisper, fake_claude):
    engine, rp_id, user_idx = engine_with_rp
    fake_whisper.text = "다시 할게요"  # forced English left the Hangul as it was
    fake_whisper.auto_text, fake_whisper.auto_lang = "다시 할게요", "korean"
    ev = await run(engine, rp_id, user_idx, speech_bytes)
    assert ev[0]["text"] == "다시 할게요" and ev[-1]["type"] == "done"


async def test_korean_heard_sends_no_issues(engine_with_rp, speech_bytes, fake_whisper, fake_claude):
    engine, rp_id, user_idx = engine_with_rp
    fake_whisper.text = "meaning of over there"  # 0.5 against the line: not followed
    fake_whisper.auto_text, fake_whisper.auto_lang = "over there가 무슨 뜻이에요?", "korean"
    await run(engine, rp_id, user_idx, speech_bytes)
    assert fake_claude.aside_calls[-1]["issues"] == []


async def test_near_miss_sends_the_macs_points(engine_with_rp, speech_bytes, fake_whisper, fake_claude):
    # the line is "It's right over there."; two words heard differently fall below FOLLOW_MIN
    engine, rp_id, user_idx = engine_with_rp
    fake_whisper.text = "It's light over hair."
    ev = await run(engine, rp_id, user_idx, speech_bytes)
    assert ev[0]["followed"] is False
    issues = fake_claude.aside_calls[-1]["issues"]
    assert [(i["target"], i["heard"]) for i in issues] == [("right", "light"), ("there", "hair")]
    assert set(issues[0]["sound"]) == {"R", "L"} and issues[0]["explain"]
    assert ev[-1]["issues"] == 2


async def test_auto_language_not_korean_keeps_english(engine_with_rp, speech_bytes, fake_whisper, fake_claude):
    engine, rp_id, user_idx = engine_with_rp
    fake_whisper.text = "Can I get a latte instead?"
    fake_whisper.auto_text, fake_whisper.auto_lang = "Can I get a latte instead?", "english"
    ev = await run(engine, rp_id, user_idx, speech_bytes)
    assert ev[0]["text"] == "Can I get a latte instead?" and fake_claude.aside_calls[-1]["heard_ko"] is None


async def test_earlier_asides_on_the_line_go_to_claude(engine_with_rp, speech_bytes, fake_whisper, fake_claude):
    engine, rp_id, user_idx = engine_with_rp
    fake_whisper.text = "Wait, let me try that again."
    for _ in range(4):
        await run(engine, rp_id, user_idx, speech_bytes)
    earlier = fake_claude.aside_calls[-1]["earlier"]
    assert len(earlier) == 3 and earlier[-1] == ("Wait, let me try that again.",
                                                  "괜찮아요, 말이 꼬일 수 있어요. 다시 해 볼까요?")


async def test_aside_claude_down_says_the_fixed_phrase(engine_with_rp, speech_bytes, fake_whisper, fake_claude):
    engine, rp_id, user_idx = engine_with_rp
    fake_whisper.text = "Wait, let me try that again."
    fake_claude.aside_fail_after = 0
    ev = await run(engine, rp_id, user_idx, speech_bytes)
    assert said(ev) == engine.said("retry_offscript").text
    assert not any(e["type"] == "error" for e in ev) and ev[-1]["type"] == "done"


async def test_aside_claude_cut_midway_ends_with_fixed_phrase(engine_with_rp, speech_bytes, fake_whisper,
                                                             fake_claude):
    engine, rp_id, user_idx = engine_with_rp
    fake_whisper.text = "Wait, let me try that again."
    fake_claude.aside_fail_after = 1
    ev = await run(engine, rp_id, user_idx, speech_bytes)
    assert said(ev).startswith("괜찮아요, 말이 꼬일 수 있어요.")
    assert said(ev).endswith(engine.said("retry_offscript").text)
    assert not any(e["type"] == "error" for e in ev) and ev[-1]["type"] == "done"


async def test_both_transcripts_empty_is_no_speech(engine_with_rp, speech_bytes, fake_whisper):
    engine, rp_id, user_idx = engine_with_rp
    fake_whisper.text = ""
    ev = await run(engine, rp_id, user_idx, speech_bytes)
    assert ev[-1]["code"] == "no_speech"
