import pytest

from je_server.claude import ClaudeUnavailable
from je_server.engine import NotFound

pytestmark = pytest.mark.anyio


async def test_create_then_lines_are_prepared(engine):
    rp = await engine.create("길 묻기")
    user_idx = next(l.idx for l in rp.lines if l.speaker == "user")
    line = await engine.line(rp.id, user_idx)
    assert line.three is not None and line.audio is not None
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
    e2 = engine_factory()  # same data folder, no tasks in memory
    line = await e2.line(rp.id, 1)
    assert line.three is not None and line.audio is not None


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
    fake_claude.fail_next = True
    with pytest.raises(ClaudeUnavailable):
        await engine.line(rp.id, 1)
    assert (await engine.line(rp.id, 1)).three is not None


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
    assert said.text.endswith("어때요?") and (said.text, "jake", "korean", True) in fake_voice.calls
    assert said.text in fake_voice.checked  # heard back: its end was once swallowed (2026-11-05)


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
    gate.set()
    assert (await engine.line(rp.id, 1)).three is not None


async def test_progress_counts_the_learners_lines(engine):
    rp = await engine.create("길 묻기")  # lines: ryan 0, user 1, ryan 2, user 3, ryan 4, user 5, ryan 6
    assert [engine.progress(rp.id, i) for i in (0, 1, 2, 3, 5, 6)] == [
        {"no": 1, "total": 3}, {"no": 1, "total": 3}, {"no": 2, "total": 3},
        {"no": 2, "total": 3}, {"no": 3, "total": 3}, {"no": 3, "total": 3}]


async def test_progress_never_passes_total(engine, fake_claude, fake_whisper, speech_bytes):
    # a rebuild that fails closes with Ryan's goodbye: lines become ryan 0, user 1, reply 2, closing 3
    fake_claude.fail_continue = True
    rp = await engine.create("길 묻기")
    await engine.line(rp.id, 1)
    fake_whisper.text = "I have no idea at all."
    [e async for e in engine.attempt(rp.id, 1, speech_bytes, "turn")]
    await engine.line(rp.id, 3)
    assert engine.progress(rp.id, 3) == {"no": 1, "total": 1}
