import pytest

pytestmark = pytest.mark.anyio


async def run(engine, rp_id, idx, body, mode="turn"):
    return [e async for e in engine.attempt(rp_id, idx, body, mode)]


async def test_summary_lists_lines_with_issues_left(engine_with_rp, speech_bytes, fake_whisper):
    engine, rp_id, user_idx = engine_with_rp
    fake_whisper.text = "It's light over there."
    await run(engine, rp_id, user_idx, speech_bytes)
    s = engine.summary(rp_id)
    assert tries(s, user_idx)[-1]["issues"] and s["say"] == engine.said("closing_retry").model_dump()


async def test_fixed_on_retry_drops_from_summary(engine_with_rp, speech_bytes, fake_whisper):
    engine, rp_id, user_idx = engine_with_rp
    fake_whisper.text = "It's light over there."
    await run(engine, rp_id, user_idx, speech_bytes)
    fake_whisper.text = "It's right over there."
    await run(engine, rp_id, user_idx, speech_bytes, "retry")
    s = engine.summary(rp_id)
    assert s["say"] == engine.said("closing_clean").model_dump()


def test_summary_route(client):
    rp = client.post("/roleplays", json={"situation": "길 묻기"}).json()
    j = client.get(f"/roleplays/{rp['id']}/summary").json()
    assert len(j["lines"]) == 7 and len(j["say"]["audio"]) == 64


def tries(s, idx):
    return next(l["tries"] for l in s["lines"] if l["line"]["idx"] == idx)


async def test_summary_shows_roleplay_tries_not_practice(engine_with_rp, speech_bytes, fake_whisper):
    engine, rp_id, user_idx = engine_with_rp
    fake_whisper.text = "It's light over there."
    await run(engine, rp_id, user_idx, speech_bytes)
    fake_whisper.text = "It's right over there."
    await run(engine, rp_id, user_idx, speech_bytes, "practice")
    s = engine.summary(rp_id)
    assert tries(s, user_idx) == [{"n": 1, "mode": "turn", "heard": "It's light over there.", "followed": True,
                                   "issues": [{"target": "right", "heard": "light"}], "point_ko": ""}]
    assert s["say"] == engine.said("closing_retry").model_dump()  # the practice fix does not count
    assert [l["line"]["idx"] for l in s["lines"]] == list(range(7)) and tries(s, 0) == []


async def test_offscript_try_carries_ryans_point(engine_with_rp, speech_bytes, fake_whisper, fake_claude):
    engine, rp_id, user_idx = engine_with_rp
    fake_whisper.text = "I have no idea at all."
    await run(engine, rp_id, user_idx, speech_bytes)
    [t] = tries(engine.summary(rp_id), user_idx)
    assert t["followed"] is False and t["issues"] == [] and t["point_ko"] == fake_claude.offscript_out.point_ko


async def test_line_without_attempts_has_no_tries(engine_with_rp):
    engine, rp_id, user_idx = engine_with_rp
    assert tries(engine.summary(rp_id), user_idx) == []
