import pytest

pytestmark = pytest.mark.anyio


async def run(engine, rp_id, idx, body, mode="turn"):
    return [e async for e in engine.attempt(rp_id, idx, body, mode)]


async def test_summary_lists_lines_with_issues_left(engine_with_rp, speech_bytes, fake_whisper):
    engine, rp_id, user_idx = engine_with_rp
    fake_whisper.text = "It's light over there."
    await run(engine, rp_id, user_idx, speech_bytes)
    s = engine.summary(rp_id)
    assert s["retry"] == [user_idx] and s["say"] == engine.said("closing_retry").model_dump()


async def test_fixed_on_retry_drops_from_summary(engine_with_rp, speech_bytes, fake_whisper):
    engine, rp_id, user_idx = engine_with_rp
    fake_whisper.text = "It's light over there."
    await run(engine, rp_id, user_idx, speech_bytes)
    fake_whisper.text = "It's right over there."
    await run(engine, rp_id, user_idx, speech_bytes, "retry")
    s = engine.summary(rp_id)
    assert s["retry"] == [] and s["say"] == engine.said("closing_clean").model_dump()


def test_summary_route(client):
    rp = client.post("/roleplays", json={"situation": "길 묻기"}).json()
    j = client.get(f"/roleplays/{rp['id']}/summary").json()
    assert j["retry"] == [] and len(j["say"]["audio"]) == 64
