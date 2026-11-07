import json

import pytest

pytestmark = pytest.mark.anyio


async def run(engine, rp_id, idx, body, mode="turn"):
    return [e async for e in engine.attempt(rp_id, idx, body, mode)]


async def test_followed_attempt_streams_text_then_audio(engine_with_rp, speech_bytes):
    engine, rp_id, user_idx = engine_with_rp
    ev = await run(engine, rp_id, user_idx, speech_bytes)
    kinds = [e["type"] for e in ev]
    assert kinds[0] == "heard" and ev[0]["followed"] is True
    assert "text" in kinds and "audio" in kinds
    assert ev[-1] == {"type": "done", "next": user_idx + 1, "issues": 0}
    saved = engine.store.load(rp_id).attempts[user_idx][0]
    assert saved.say_ko == "끝까지 자신 있게 말했어요. 다음 대사로 넘어가요."
    assert saved.timings["first_text"] > 0 and len(saved.audio) == 2
    assert engine.store.load(rp_id).pos == user_idx + 1


async def test_feedback_audio_is_urgent_ryan_korean(engine_with_rp, speech_bytes, fake_voice):
    engine, rp_id, user_idx = engine_with_rp
    await run(engine, rp_id, user_idx, speech_bytes)
    assert ("끝까지 자신 있게 말했어요.", "ryan", "korean", True) in fake_voice.calls


async def test_misheard_word_is_sent_as_issue(engine_with_rp, speech_bytes, fake_whisper, fake_claude):
    engine, rp_id, user_idx = engine_with_rp
    fake_whisper.text = "It's light over there."
    ev = await run(engine, rp_id, user_idx, speech_bytes)
    assert ev[-1]["issues"] == 1
    sent = fake_claude.feedback_calls[0]
    assert sent["issues"][0]["target"] == "right" and set(sent["issues"][0]["sound"]) == {"R", "L"}
    assert fake_whisper.langs == ["en"]


async def test_praise_never_claims_unchecked_things(engine_with_rp, speech_bytes, fake_claude):
    engine, rp_id, user_idx = engine_with_rp
    await run(engine, rp_id, user_idx, speech_bytes)
    assert fake_claude.feedback_calls[0]["praise"] == ["대사를 빠짐없이 알아듣게 말했어요"]


async def test_fixed_word_from_last_try_is_praised(engine_with_rp, speech_bytes, fake_whisper, fake_claude):
    engine, rp_id, user_idx = engine_with_rp
    fake_whisper.text = "It's light over there."
    await run(engine, rp_id, user_idx, speech_bytes)
    fake_whisper.text = "It's right over there."
    await run(engine, rp_id, user_idx, speech_bytes, "retry")
    assert fake_claude.feedback_calls[1]["praise"][0] == "이번에는 right의 R 소리가 제대로 났어요"


async def test_silent_recording_says_no_speech_and_keeps_script(engine_with_rp, silent_bytes, fake_whisper):
    engine, rp_id, user_idx = engine_with_rp
    before = engine.store.load(rp_id).lines
    ev = await run(engine, rp_id, user_idx, silent_bytes)
    assert ev == [{"type": "error", "code": "no_speech", "say": engine.said("no_speech").model_dump()}]
    assert engine.store.load(rp_id).lines == before and fake_whisper.calls == 0
    assert engine.store.rec_path(rp_id, user_idx, 1).exists()  # the recording itself is kept


async def test_empty_transcript_is_no_speech(engine_with_rp, speech_bytes, fake_whisper):
    engine, rp_id, user_idx = engine_with_rp
    fake_whisper.text = ""
    ev = await run(engine, rp_id, user_idx, speech_bytes)
    assert ev[-1]["code"] == "no_speech"


async def test_feedback_prompt_gets_only_text(engine_with_rp, speech_bytes, fake_claude):
    engine, rp_id, user_idx = engine_with_rp
    await run(engine, rp_id, user_idx, speech_bytes)
    sent = json.dumps(fake_claude.feedback_calls[0], ensure_ascii=False)
    assert ".m4a" not in sent and ".wav" not in sent and str(engine.store.root) not in sent


async def test_claude_down_during_feedback_still_ends(engine_with_rp, speech_bytes, fake_claude):
    engine, rp_id, user_idx = engine_with_rp
    fake_claude.fail_next = True
    ev = await run(engine, rp_id, user_idx, speech_bytes)
    assert ev[-1]["type"] == "error" and ev[-1]["code"] == "claude_unavailable" and ev[-1]["say"]["audio"]


async def test_recordings_are_numbered_and_kept(engine_with_rp, speech_bytes, silent_bytes):
    engine, rp_id, user_idx = engine_with_rp
    await run(engine, rp_id, user_idx, silent_bytes)
    await run(engine, rp_id, user_idx, speech_bytes, "retry")
    assert engine.store.rec_path(rp_id, user_idx, 1).exists() and engine.store.rec_path(rp_id, user_idx, 2).exists()
    assert engine.store.load(rp_id).attempts[user_idx][0].n == 2


async def test_retry_keeps_position(engine_with_rp, speech_bytes):
    engine, rp_id, user_idx = engine_with_rp
    ev = await run(engine, rp_id, user_idx, speech_bytes, "retry")
    assert ev[-1]["next"] == user_idx


def test_attempt_route_streams_ndjson(client, speech_bytes):
    rp = client.post("/roleplays", json={"situation": "길 묻기"}).json()
    client.get(f"/roleplays/{rp['id']}/lines/1")
    r = client.post(f"/roleplays/{rp['id']}/lines/1/attempts?mode=turn", content=speech_bytes,
                    headers={"Content-Type": "audio/mp4"})
    assert r.status_code == 200 and r.headers["content-type"].startswith("application/x-ndjson")
    events = [json.loads(l) for l in r.text.splitlines() if l]
    assert events[0]["type"] == "heard" and events[-1]["type"] == "done"


def test_attempt_route_rejects_ryan_line_and_bad_mode(client, speech_bytes):
    rp = client.post("/roleplays", json={"situation": "길 묻기"}).json()
    assert client.post(f"/roleplays/{rp['id']}/lines/0/attempts", content=speech_bytes).status_code == 404
    assert client.post(f"/roleplays/{rp['id']}/lines/1/attempts?mode=x", content=speech_bytes).status_code == 422


# --- practice after the roleplay (spec 2026-11-05-roleplay-practice 4, 5, 7) ------------------------------------


async def test_shadow_on_ryan_line_is_evaluated_like_a_followed_line(engine_with_rp, speech_bytes, fake_whisper,
                                                                    fake_claude):
    engine, rp_id, _ = engine_with_rp
    ryan = engine.store.load(rp_id).lines[0]
    fake_whisper.text = ryan.text
    ev = await run(engine, rp_id, 0, speech_bytes, "shadow")
    assert ev[0] == {"type": "heard", "text": ryan.text, "followed": True}
    assert ev[-1] == {"type": "done", "next": 0, "issues": 0}
    assert fake_claude.feedback_calls[0]["line"] == ryan.text
    saved = engine.store.load(rp_id)
    assert saved.attempts[0][0].mode == "shadow" and saved.pos == 0


async def test_shadow_said_differently_asks_to_follow(engine_with_rp, speech_bytes, fake_whisper, fake_claude):
    engine, rp_id, _ = engine_with_rp
    before = engine.store.load(rp_id).lines
    fake_whisper.text = "I have no idea at all."
    ev = await run(engine, rp_id, 0, speech_bytes, "shadow")
    assert [e["delta"] for e in ev if e["type"] == "text"] == [engine.said("retry_offscript").text]
    assert fake_claude.offscript_calls == [] and engine.store.load(rp_id).lines == before


async def test_practice_keeps_pos_and_script(engine_with_rp, speech_bytes, fake_whisper, fake_claude):
    engine, rp_id, user_idx = engine_with_rp
    before = engine.store.load(rp_id).lines
    fake_whisper.text = "I have no idea at all."
    ev = await run(engine, rp_id, user_idx, speech_bytes, "practice")
    assert ev[-1] == {"type": "done", "next": user_idx, "issues": 0}
    assert fake_claude.offscript_calls == []
    saved = engine.store.load(rp_id)
    assert saved.lines == before and saved.pos == 0 and saved.attempts[user_idx][0].mode == "practice"


async def test_mode_must_match_the_speaker(engine_with_rp):
    from je_server.engine import NotFound

    engine, rp_id, user_idx = engine_with_rp
    with pytest.raises(NotFound):
        engine.target_line(rp_id, 0, "turn")
    with pytest.raises(NotFound):
        engine.target_line(rp_id, user_idx, "shadow")


async def test_feedback_knows_when_the_line_ends_the_roleplay(engine, speech_bytes, fake_whisper, fake_claude):
    # phone test 2026-11-07: the script ended with the learner's line and Ryan still said 「다음 대사로 넘어가요」
    fake_claude.script_last = "user"
    rp = await engine.create("길 묻기")
    first = next(l for l in rp.lines if l.speaker == "user")
    last = rp.lines[-1]
    assert last.speaker == "user" and last.idx != first.idx
    for line, mode in ((first, "turn"), (last, "turn"), (last, "retry"), (last, "practice")):
        await engine.line(rp.id, line.idx)
        fake_whisper.text = line.text
        await run(engine, rp.id, line.idx, speech_bytes, mode)
    # practice runs in an order only the app knows, so the server never calls a practice line the last
    assert [c["last"] for c in fake_claude.feedback_calls] == [False, True, True, False]
