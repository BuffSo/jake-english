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
                                   "issues": [{"target": "right", "heard": "light",
                                               "say_ko": "「right」 → 「light」처럼 들렸어요"}], "point_ko": ""}]
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


async def test_retry_said_differently_has_no_point(engine_with_rp, speech_bytes, fake_whisper):
    # final review: a retry said differently only gets 「대사를 그대로 따라 말해 볼까요?」; that is not a point
    engine, rp_id, user_idx = engine_with_rp
    fake_whisper.text = "I have no idea at all."
    await run(engine, rp_id, user_idx, speech_bytes, "retry")
    [t] = tries(engine.summary(rp_id), user_idx)
    assert t["followed"] is False and t["point_ko"] == ""


async def test_pronunciation_point_is_not_repeated(engine_with_rp, speech_bytes, fake_whisper, fake_claude):
    # PR #15 review: a turn said differently with a listed sound stored the point both as an issue and as
    # Ryan's words; the end screen showed it twice
    from je_server.models import Offscript

    engine, rp_id, user_idx = engine_with_rp
    fake_claude.offscript_out = Offscript(point_kind="pronunciation", point_ko="", meant="right",
                                          heard_word="light", reply_en="Oh, I see. Thanks!")
    fake_whisper.text = "I have no idea, it is light there."
    await run(engine, rp_id, user_idx, speech_bytes)
    [t] = tries(engine.summary(rp_id), user_idx)
    assert t["issues"] == [{"target": "right", "heard": "light", "say_ko": "「right」 → 「light」처럼 들렸어요"}]
    assert t["point_ko"] == ""


async def test_summary_says_each_issue_in_korean(engine_with_rp):
    from je_server.models import Attempt, Issue

    engine, rp_id, user_idx = engine_with_rp
    old = Issue.model_validate({"target": "coffee", "heard": "copy", "sound": ["F", "P"], "explain": "…"})
    issues = [old, Issue(target="on", heard="")]
    await engine.save_attempt(rp_id, user_idx, Attempt(n=1, mode="turn", heard="…", followed=True, issues=issues,
                                                       say_ko="…", audio=[], timings={}), pos=None)
    [t] = tries(engine.summary(rp_id), user_idx)
    assert t["issues"] == [{"target": "coffee", "heard": "copy", "say_ko": "「coffee」 → 「copy」처럼 들렸어요"},
                           {"target": "on", "heard": "", "say_ko": "「on」 → 들리지 않았어요"}]
