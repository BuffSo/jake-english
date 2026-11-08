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


async def test_line_without_attempts_has_no_tries(engine_with_rp):
    engine, rp_id, user_idx = engine_with_rp
    assert tries(engine.summary(rp_id), user_idx) == []


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


async def test_summary_first_points_at_earlier_run(engine_with_rp, speech_bytes, fake_whisper):
    engine, rp_id, user_idx = engine_with_rp
    fake_whisper.text = "It's right over there."
    await run(engine, rp_id, user_idx, speech_bytes)
    first = engine.store.load(rp_id)  # both tries land in the same second here; in use the first run is days earlier
    first.attempts[user_idx][0].at = "2026-11-05T10:00:00"
    engine.store.save(first)
    again = await engine.copy(rp_id)
    await engine.line(again.id, user_idx)
    await run(engine, again.id, user_idx, speech_bytes)
    line_of = lambda s, idx: next(l for l in s["lines"] if l["line"]["idx"] == idx)
    assert line_of(engine.summary(again.id), user_idx)["first"] == {"rp_id": rp_id, "idx": user_idx, "n": 1}
    assert line_of(engine.summary(rp_id), user_idx)["first"] is None
    assert line_of(engine.summary(again.id), 0)["first"] is None


async def test_aside_is_not_on_the_end_screen(engine_with_rp, speech_bytes, fake_whisper):
    engine, rp_id, user_idx = engine_with_rp
    fake_whisper.text = "Wait, let me try that again."
    await run(engine, rp_id, user_idx, speech_bytes)
    assert tries(engine.summary(rp_id), user_idx) == []


async def test_aside_after_issue_keeps_closing_retry(engine_with_rp, speech_bytes, fake_whisper):
    engine, rp_id, user_idx = engine_with_rp
    fake_whisper.text = "It's light over there."
    await run(engine, rp_id, user_idx, speech_bytes)
    fake_whisper.text = "Wait, let me try that again."
    await run(engine, rp_id, user_idx, speech_bytes, "retry")
    s = engine.summary(rp_id)
    assert len(tries(s, user_idx)) == 1 and s["say"] == engine.said("closing_retry").model_dump()


async def test_old_offscript_try_still_shows_its_point(engine_with_rp):
    # records from before 2026-11-07: a turn said differently, with Ryan's point and no aside mark
    from je_server.models import Attempt

    engine, rp_id, user_idx = engine_with_rp
    await engine.save_attempt(rp_id, user_idx, Attempt(n=1, mode="turn", heard="I have no idea.", followed=False,
                                                       issues=[], say_ko="이럴 때는 I'm not sure도 좋아요.",
                                                       audio=[], timings={}), None)
    [t] = tries(engine.summary(rp_id), user_idx)
    assert t["followed"] is False and t["point_ko"] == "이럴 때는 I'm not sure도 좋아요."


async def test_latest_reads_the_records_once(engine_with_rp, speech_bytes, fake_whisper, monkeypatch):
    # todo 01-3 (ADR-0011 「영향」): the last conversation reads every record; picking the run and its 「처음 녹음」
    # read them twice before
    engine, rp_id, user_idx = engine_with_rp
    await run(engine, rp_id, user_idx, speech_bytes)
    reads = []
    real = engine.store.all
    monkeypatch.setattr(engine.store, "all", lambda: reads.append(1) or real())
    got = engine.latest(rp_id)
    assert len(reads) == 1
    assert got["roleplay"]["id"] == rp_id and got["summary"] == engine.summary(rp_id)



async def test_summary_shows_points_as_the_words_are_written(engine_with_rp):
    # todo follow-feedback leftovers 3: the points are kept in lowercase; the end screen writes them as the line does
    from je_server.models import Attempt, Issue

    engine, rp_id, user_idx = engine_with_rp
    line = engine.load(rp_id).lines[user_idx].text
    assert line.startswith("It's ")
    await engine.save_attempt(rp_id, user_idx, Attempt(n=1, mode="turn", heard="Is right over there.", followed=True,
                                                       issues=[Issue(target="it's", heard="is")], say_ko="…",
                                                       audio=[], timings={}), pos=None)
    [t] = tries(engine.summary(rp_id), user_idx)
    assert t["issues"] == [{"target": "it's", "heard": "is", "say_ko": "「It's」 → 「Is」처럼 들렸어요"}]


# spec record-cancel-skip 3: a roleplay where no line was said ends without praise; skips leave lines without tries
async def test_closing_without_any_line_said_has_no_praise(engine_with_rp):
    engine, rp_id, _ = engine_with_rp
    assert engine.summary(rp_id)["say"] == engine.said("closing_plain").model_dump()


async def test_closing_after_asides_only_has_no_praise(engine_with_rp):
    from je_server.models import Attempt

    engine, rp_id, user_idx = engine_with_rp
    await engine.save_attempt(rp_id, user_idx, Attempt(n=1, mode="turn", heard="넘어가고 싶어요", followed=False,
                                                       issues=[], say_ko="…", audio=[], timings={}, aside=True),
                              pos=None)
    assert engine.summary(rp_id)["say"] == engine.said("closing_plain").model_dump()


async def test_closing_after_practice_only_has_no_praise(engine_with_rp, speech_bytes, fake_whisper):
    engine, rp_id, user_idx = engine_with_rp
    fake_whisper.text = "It's right over there."
    await run(engine, rp_id, user_idx, speech_bytes, "practice")  # practice is not a try inside the roleplay
    assert engine.summary(rp_id)["say"] == engine.said("closing_plain").model_dump()
