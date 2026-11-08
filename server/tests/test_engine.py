import asyncio

import pytest

from je_server.claude import JAKE_ENDINGS, ClaudeUnavailable
from je_server.engine import NotFound
from je_server.models import Attempt, ScriptLine

pytestmark = pytest.mark.anyio


async def test_create_then_lines_are_prepared(engine):
    # a line comes with its model sound; the learner's notes are made in the background and fetched (spec
    # dont-wait-for-line-notes 1)
    rp = await engine.create("길 묻기")
    user_idx = next(l.idx for l in rp.lines if l.speaker == "user")
    line = await engine.line(rp.id, user_idx)
    assert line.audio is not None
    three = await engine.three(rp.id, user_idx)
    assert three.words and engine.store.load(rp.id).lines[user_idx].three == three
    ryan = await engine.line(rp.id, 0)
    assert ryan.audio is not None and ryan.three is None


async def test_model_audio_is_ryan_english_and_not_urgent(engine, fake_voice):
    rp = await engine.create("길 묻기")
    await engine.line(rp.id, 1)
    assert (rp.lines[1].text, "ryan", "english", False) in fake_voice.calls


async def test_prep_survives_restart(engine_factory, fake_claude):
    e1 = engine_factory()
    rp = await e1.create("길 묻기")
    for t in e1.tasks.values():
        t.cancel()
    for t in e1.threes.values():
        t.cancel()
    e2 = engine_factory()  # same data folder, no tasks in memory
    line = await e2.line(rp.id, 1)
    assert line.audio is not None
    assert (await e2.three(rp.id, 1)).words  # the notes left half made start again


async def test_claude_down_on_create_leaves_no_roleplay(engine, fake_claude):
    fake_claude.fail_next = True
    with pytest.raises(ClaudeUnavailable):
        await engine.create("길 묻기")
    assert engine.store.recent_situations() == []


async def test_claude_down_while_preparing_is_retried_next_time(engine, fake_claude):
    rp = await engine.create("길 묻기")
    for t in engine.tasks.values():
        t.cancel()
    engine.tasks.clear()
    for t in engine.threes.values():
        t.cancel()
    engine.threes.clear()
    fake_claude.fail_next = True
    with pytest.raises(ClaudeUnavailable):  # the notes say Claude is down...
        await engine.three(rp.id, 1)
    assert (await engine.line(rp.id, 1)).audio is not None  # ...but the line still comes
    assert (await engine.three(rp.id, 1)).words  # and the next ask makes them


async def test_ryan_three_on_demand(engine):
    rp = await engine.create("길 묻기")
    three = await engine.three(rp.id, 0)
    assert three.words and engine.store.load(rp.id).lines[0].three == three


async def test_unknown_line_is_not_found(engine):
    rp = await engine.create("길 묻기")
    with pytest.raises(NotFound):
        await engine.line(rp.id, 99)
    with pytest.raises(NotFound):
        await engine.line("0" * 12, 0)


async def test_recommend_is_jake_korean(engine, fake_voice, fake_claude):
    said = await engine.recommend()
    assert fake_claude.endings[-1] in {e for e, _ in JAKE_ENDINGS} and said.text.endswith(fake_claude.endings[-1])
    assert (said.text, "jake", "korean", True) in fake_voice.calls
    assert said.text in fake_voice.checked  # heard back: its end was once swallowed (2026-11-05)


async def test_recommend_does_not_repeat_the_last_turned_down_ending(engine, fake_claude):
    # 「다른 걸로요」: the next suggestion ends another way (spec situation-topics 4)
    for _ in range(20):
        await engine.recommend(["카페에서 주문하는 상황을 추천해요."])
    assert "상황을 추천해요." not in fake_claude.endings  # the weights: test_claude.py, with a seeded random


async def test_recommend_passes_turned_down(engine, fake_claude):
    await engine.create("길 묻기")
    await engine.recommend(["카페에서 주문하는 상황으로 연습해 보면 어때요?"])
    asked = [args for name, args in fake_claude.calls if name == "recommend"]
    assert asked == [(["길 묻기"], ["카페에서 주문하는 상황으로 연습해 보면 어때요?"], "other")]


async def test_fixed_phrases_are_checked(engine, fake_voice):
    from je_server.phrases import PHRASES

    await engine.warm()
    assert set(PHRASES.values()) <= set(fake_voice.checked)


async def test_model_audio_starts_before_notes_finish(engine, fake_claude, fake_voice):
    import asyncio

    gate = asyncio.Event()
    real = fake_claude.annotate

    async def slow(text, context):
        await gate.wait()
        return await real(text, context)

    fake_claude.annotate = slow
    rp = await engine.create("길 묻기")
    await asyncio.sleep(0.05)
    assert any(c[0] == rp.lines[1].text for c in fake_voice.calls)  # audio asked for while notes still wait
    line = await engine.line(rp.id, 1)  # comes while the notes still wait (spec dont-wait-for-line-notes 1)
    assert line.audio is not None and line.three is None
    gate.set()
    assert (await engine.three(rp.id, 1)).words


async def test_progress_counts_the_learners_lines(engine):
    rp = await engine.create("길 묻기")  # lines: ryan 0, user 1, ryan 2, user 3, ryan 4, user 5, ryan 6
    assert [engine.progress(rp.id, i) for i in (0, 1, 2, 3, 5, 6)] == [
        {"no": 1, "total": 3}, {"no": 1, "total": 3}, {"no": 2, "total": 3},
        {"no": 2, "total": 3}, {"no": 3, "total": 3}, {"no": 3, "total": 3}]


async def old_reply_record(engine, said: str = "I have no idea at all.", closing: bool = True):
    """A roleplay as the server left it before 2026-11-07 after a turn said differently: Ryan's reply after line 1,
    then (when the rebuild failed) his goodbye, and the try with no aside mark."""
    rp = await engine.create("길 묻기")
    rp = engine.store.load(rp.id)
    rp.lines = rp.lines[:2] + [ScriptLine(idx=2, speaker="ryan", text="Oh, no worries. Thanks anyway!", kind="reply")]
    if closing:
        rp.lines.append(ScriptLine(idx=3, speaker="ryan", text="Thanks for your help! Have a good day."))
    rp.attempts = {1: [Attempt(n=1, mode="turn", heard=said, followed=False, issues=[], say_ko="", audio=[],
                               timings={})]}
    engine.store.save(rp)
    return rp


async def test_progress_never_passes_total(engine):
    # an old rebuild that failed closed with Ryan's goodbye: lines ryan 0, user 1, reply 2, closing 3
    rp = await old_reply_record(engine)
    assert engine.progress(rp.id, 3) == {"no": 1, "total": 1}


async def test_copy_starts_fresh_with_the_same_script(engine_with_rp, speech_bytes, fake_claude):
    engine, rp_id, user_idx = engine_with_rp
    for i in range(7):  # let background preparation finish, so the record stops changing
        await engine.line(rp_id, i)
    [e async for e in engine.attempt(rp_id, user_idx, speech_bytes, "turn")]
    old = engine.store.load(rp_id)
    calls = len(fake_claude.calls)
    new = await engine.copy(rp_id)
    assert new.id != rp_id and new.lines == old.lines and new.attempts == {} and new.pos == 0
    assert new.situation == old.situation and new.frame == old.frame
    assert engine.store.load(rp_id) == old  # the old record is untouched
    assert ("make_script", (old.situation,)) not in fake_claude.calls[calls:]


async def test_copy_makes_an_unsettled_note_again(engine_with_rp):
    # a note left without its reading would stay so in every copy of the roleplay (todo three_line_notes_degrade_rate 3)
    engine, rp_id, user_idx = engine_with_rp
    old = engine.store.load(rp_id)
    users = [l.idx for l in old.lines if l.speaker == "user"]
    for i in users:
        await engine.three(rp_id, i)
    old = engine.store.load(rp_id)
    old.lines[user_idx] = old.lines[user_idx].model_copy(
        update={"three": old.lines[user_idx].three.model_copy(update={"reading": ""})})
    engine.store.save(old)
    new = await engine.copy(rp_id)
    assert new.lines[user_idx].three is None and new.lines[user_idx].audio == old.lines[user_idx].audio
    assert all(new.lines[i] == old.lines[i] for i in users if i != user_idx)
    assert (await engine.three(new.id, user_idx)).reading


async def test_copy_keeps_reply_lines_in_order(engine):
    rp = await old_reply_record(engine)
    new = await engine.copy(rp.id)
    assert [l.idx for l in new.lines] == list(range(len(new.lines))) and new.lines[2].kind == "reply"
    # text only: background preparation may still add notes and sounds to either record
    shape = lambda lines: [(l.idx, l.speaker, l.text, l.kind) for l in lines]  # noqa: E731
    assert shape(new.lines) == shape(engine.store.load(rp.id).lines)


async def test_a_line_whose_sound_failed_comes_without_audio(engine, fake_voice):
    # final review: a Ryan line whose voice fails must still come (shadow practice can record it, the roleplay
    # moves on after its pause) instead of a 500
    from fakes import DRAFT_RYAN

    fake_voice.fail_text = DRAFT_RYAN[0]
    rp = await engine.create("길 묻기")
    line = await engine.line(rp.id, 0)
    assert line.text == DRAFT_RYAN[0] and line.audio is None


async def test_ryan_notes_asked_twice_at_once_are_made_once(engine, fake_claude):
    # PR #15 review: the end screen asks for every Ryan line's notes and the shadow screen asks again; one
    # Claude call per line must serve both
    import asyncio

    fake_claude.annotate_gate = asyncio.Event()
    rp = await engine.create("길 묻기")
    asks = [asyncio.create_task(engine.three(rp.id, 0)) for _ in range(2)]
    for _ in range(5):
        await asyncio.sleep(0)
    fake_claude.annotate_gate.set()
    a, b = await asyncio.gather(*asks)
    assert a == b
    assert sum(1 for name, args in fake_claude.calls if name == "annotate" and args[0] == rp.lines[0].text) == 1


async def test_a_line_whose_sound_failed_still_gets_its_notes(engine, fake_claude, fake_voice):
    # PR #15 review: a sound that failed fast must not leave the line without notes. Since the line no longer waits
    # for them (spec dont-wait-for-line-notes 1), it comes without its sound at once and the notes go on
    import asyncio

    from fakes import DRAFT_USER

    fake_claude.annotate_gate = asyncio.Event()
    fake_voice.fail_text = DRAFT_USER[0]
    rp = await engine.create("길 묻기")
    line = await engine.line(rp.id, 1)
    assert line.audio is None and line.three is None
    fake_claude.annotate_gate.set()
    assert (await engine.three(rp.id, 1)).words
    # the notes went on from the background call; they were not started again
    assert sum(1 for n, a in fake_claude.calls if n == "annotate" and a[0] == DRAFT_USER[0]) == 1


async def test_notes_asked_while_made_in_the_background_share_one_call(engine, fake_claude):
    import asyncio

    fake_claude.annotate_gate = asyncio.Event()
    rp = await engine.create("길 묻기")
    await asyncio.sleep(0)
    # made in the background as soon as the script is there, before anyone asks (spec dont-wait-for-line-notes 1)
    assert ("annotate", (rp.lines[1].text, engine.context(rp, 1))) in fake_claude.calls
    asks = [asyncio.create_task(engine.three(rp.id, 1)) for _ in range(2)]
    await asyncio.sleep(0)
    fake_claude.annotate_gate.set()
    a, b = await asyncio.gather(*asks)
    assert a == b
    assert [c for c in fake_claude.calls if c == ("annotate", (rp.lines[1].text, engine.context(rp, 1)))] == [
        ("annotate", (rp.lines[1].text, engine.context(rp, 1)))]


@pytest.mark.parametrize("kind", ["three", "ko"])
async def test_a_finished_task_forgets_only_itself(engine, fake_claude, kind):
    # todo line-notes minors 1: a task's done callbacks run on a later turn of the loop. A new ask that comes in
    # between starts its own task; the old callback must not remove it, or the next ask calls Claude once more.
    rp = await engine.create("길 묻기")
    await asyncio.gather(*list(engine.threes.values()), return_exceptions=True)  # the learner's notes made at start
    tasks, start = (engine.threes, engine._three_task) if kind == "three" else (engine.kos, engine._ko_task)
    key = (rp.id, 0)
    fake_claude.fail_next = True
    first = start(*key)
    await asyncio.sleep(0)  # `first` runs and fails at once; its callbacks queue behind this test's next step
    assert first.done() and tasks.get(key) is first
    second = start(*key)
    assert second is not first
    await asyncio.sleep(0)  # `first`'s callbacks run
    assert tasks.get(key) is second
    await second


# --- Sohee's interpretation (spec korean-translation 4, 5) ------------------------------------------------------

async def test_ko_made_once_and_kept_on_the_line(engine, fake_claude):
    rp = await engine.create("길 묻기")
    a, b = await asyncio.gather(engine.ko(rp.id, 0), engine.ko(rp.id, 0))
    assert a == b == "소희: " + rp.lines[0].text and len(fake_claude.interpret_calls) == 1
    assert engine.store.load(rp.id).lines[0].ko == a
    assert await engine.ko(rp.id, 0) == a and len(fake_claude.interpret_calls) == 1
    copy = await engine.copy(rp.id)
    assert copy.lines[0].ko == a  # 「같은 대본으로 처음부터」 does not make it again


async def test_ko_context_is_the_conversation_as_it_went(engine, fake_claude):
    rp = await engine.create("길 묻기")
    await engine.ko(rp.id, 1)
    call = fake_claude.interpret_calls[-1]
    assert call["line"] == ("user", rp.lines[1].text)
    assert call["before"] == ("ryan", rp.lines[0].text) and call["after"] == ("ryan", rp.lines[2].text)
    await engine.ko(rp.id, 0)
    assert fake_claude.interpret_calls[-1]["before"] is None


async def test_ko_of_an_old_reply_sees_what_was_said(engine, fake_claude):
    said = "Do you have oat milk?"
    rp = await old_reply_record(engine, said, closing=False)
    ko = await asyncio.wait_for(engine.ko(rp.id, 2), 1)
    assert ko == "소희: Oh, no worries. Thanks anyway!" and fake_claude.interpret_calls[-1]["before"] == ("user", said)


async def test_ko_does_not_queue_behind_three_line_notes(engine, fake_claude):
    fake_claude.annotate_gate = asyncio.Event()  # every note waits, so Engine.sem is full
    rp = await engine.create("길 묻기")
    await asyncio.sleep(0)
    assert await asyncio.wait_for(engine.ko(rp.id, 0), 1)
    fake_claude.annotate_gate.set()


async def test_ko_audio_is_sohee_urgent_checked_and_kept(engine, fake_voice):
    rp = await engine.create("길 묻기")
    with pytest.raises(NotFound):
        await engine.ko_audio(rp.id, 0)  # no Korean yet
    text = await engine.ko(rp.id, 0)
    key = await engine.ko_audio(rp.id, 0)
    assert (text, "sohee", "korean", True) in fake_voice.calls and text in fake_voice.checked
    assert engine.store.load(rp.id).lines[0].ko_audio == key
    n = len(fake_voice.calls)
    assert await engine.ko_audio(rp.id, 0) == key and len(fake_voice.calls) == n


async def test_copy_points_at_the_first_roleplay(engine):
    rp = await engine.create("길 묻기")
    c1 = await engine.copy(rp.id)
    c2 = await engine.copy(c1.id)
    assert rp.origin is None and c1.origin == rp.id and c2.origin == rp.id
    assert engine.load(c2.id).origin == rp.id


async def test_attempt_records_when(engine_with_rp, speech_bytes, fake_whisper):
    import re

    engine, rp_id, user_idx = engine_with_rp
    fake_whisper.text = "It's right over there."
    [e async for e in engine.attempt(rp_id, user_idx, speech_bytes, "turn")]
    at = engine.load(rp_id).attempts[user_idx][0].at
    assert at is not None and re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d", at)


async def test_heard_carries_the_recording_number(engine_with_rp, speech_bytes, fake_whisper):
    """The app plays the try just sent by its number (spec three-line-listen 7); the file is saved before `heard`."""
    engine, rp_id, user_idx = engine_with_rp
    fake_whisper.text = "It's right over there."
    for n in (1, 2):
        events = [e async for e in engine.attempt(rp_id, user_idx, speech_bytes, "retry")]
        heard = next(e for e in events if e["type"] == "heard")
        assert heard["n"] == n
        assert engine.recording(rp_id, user_idx, n).read_bytes() == speech_bytes


# --- situation topics (spec situation-topics 4, 7) ---------------------------------------------------------------

async def test_create_keeps_the_topic(engine, fake_claude):
    rp = await engine.create("관광객이 길을 묻는다.", "tourist")
    assert engine.store.load(rp.id).topic == "tourist"
    assert ("make_script", ("관광객이 길을 묻는다.", "tourist", None)) in fake_claude.calls


async def test_create_from_a_pick_starts_with_its_speaker(engine, fake_claude):
    # a list pick goes through its fixed script now (spec fixed-list-scripts), still learner first
    rp = await engine.create_pick("usa", "u-hotel-checkin")
    assert rp.lines[0].speaker == "user"
    assert engine.progress(rp.id, 0) == {"no": 1, "total": 3}


async def test_copy_keeps_the_topic(engine):
    rp = await engine.create("호텔 체크인", "usa")
    assert (await engine.copy(rp.id)).topic == "usa"


async def test_recommend_avoids_recent_of_the_same_topic(engine, fake_claude):
    await engine.create("호텔 체크인", "usa")
    await engine.create("관광객 길 안내", "tourist")
    await engine.recommend([], "usa")
    assert [a for n, a in fake_claude.calls if n == "recommend"][-1] == (["호텔 체크인"], [], "usa")


async def test_history_skips_asides(engine_with_rp, speech_bytes, fake_whisper):
    engine, rp_id, user_idx = engine_with_rp
    fake_whisper.text = "Wait, let me try that again."
    [e async for e in engine.attempt(rp_id, user_idx, speech_bytes, "turn")]
    rp = engine.store.load(rp_id)
    assert engine.history(rp, user_idx + 1)[-1] == ("user", rp.lines[user_idx].text)
