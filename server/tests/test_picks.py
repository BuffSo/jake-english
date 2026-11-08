"""A list pick starts from its fixed script and joins the pick's group (spec fixed-list-scripts, ADR-0013)."""
import asyncio
import dataclasses

import pytest

from je_server import topics
from je_server.models import Attempt
from je_server.threeline import plain
from je_server.tts import audio_key
from je_server.topics import pick

SNEAKER = ("usa", "u-sneaker-size")  # the learner speaks first
CHANGED = "Excuse me, could I try these in another size?"

pytestmark = pytest.mark.anyio


async def ready(engine, rp):
    """Every line's sound, and the learner's notes, which come apart from the line now."""
    for l in rp.lines:
        await engine.line(rp.id, l.idx)
        if l.speaker == "user":
            await engine.three(rp.id, l.idx)


def changed_script(monkeypatch):
    """The repository's script edited after earlier runs: its first line says something else."""
    old = pick(*SNEAKER)
    new = dataclasses.replace(old, script=(("user", CHANGED),) + old.script[1:])
    monkeypatch.setattr(topics, "pick", lambda t, i: new)
    return new


async def test_pick_makes_no_claude_script(engine, fake_claude):
    p = pick(*SNEAKER)
    rp = await engine.create_pick(*SNEAKER)
    assert not any(n == "make_script" for n, _ in fake_claude.calls)
    assert [(l.speaker, l.text) for l in rp.lines] == list(p.script)
    assert rp.frame == p.frame and rp.situation == p.situation
    assert (rp.topic, rp.pick, rp.origin) == ("usa", "u-sneaker-size", None)
    assert engine.store.load(rp.id) == rp


async def test_pick_again_joins_the_group_and_calls_no_claude(engine, fake_claude):
    first = await engine.create_pick(*SNEAKER)
    await ready(engine, first)
    calls = len(fake_claude.calls)
    second = await engine.create_pick(*SNEAKER)
    third = await engine.create_pick(*SNEAKER)
    assert second.origin == first.id and third.origin == first.id  # a later run still points at the first
    assert all(engine.prepared(l) for l in second.lines + third.lines)  # notes and sounds came with it
    assert fake_claude.calls[calls:] == []


async def test_picked_runs_are_one_row_in_the_past_list(engine):
    runs = [await engine.create_pick(*SNEAKER) for _ in range(2)]
    for rp in runs:  # a followed turn at a learner line makes the run 「해 본 상황」 (review.spoken)
        await engine.save_attempt(rp.id, 0, Attempt(n=1, mode="turn", heard="x", followed=True, issues=[],
                                                    say_ko="", audio=[], timings={}), pos=1)
    rows = [r for r in engine.past() if r["title_ko"] == "알라모아나 센터에서 운동화 사이즈"]
    assert len(rows) == 1 and rows[0]["group"] == runs[0].id


async def test_two_picks_at_once_share_one_group(engine):
    # two taps that reach the server together: one group, not two (spec 2)
    a, b = await asyncio.gather(engine.create_pick(*SNEAKER), engine.create_pick(*SNEAKER))
    firsts = [r for r in (a, b) if r.origin is None]
    assert len(firsts) == 1 and {a.origin, b.origin} == {None, firsts[0].id}


async def test_pick_while_the_first_is_preparing(engine, fake_claude):
    fake_claude.annotate_gate = asyncio.Event()
    first = await engine.create_pick(*SNEAKER)
    await asyncio.sleep(0)  # the first run's preparation has started and waits for its notes
    second = await engine.create_pick(*SNEAKER)
    assert second.origin == first.id and all(l.three is None for l in second.lines if l.speaker == "user")
    fake_claude.annotate_gate.set()
    await ready(engine, first)
    await ready(engine, second)
    for rp in (first, second):
        assert all(l.three for l in engine.store.load(rp.id).lines if l.speaker == "user")


async def test_changed_line_is_made_again(engine, monkeypatch):
    first = await engine.create_pick(*SNEAKER)
    await ready(engine, first)
    changed_script(monkeypatch)
    second = await engine.create_pick(*SNEAKER)
    assert second.origin == first.id and second.lines[0].text == CHANGED
    assert second.lines[0].three is None and second.lines[0].audio is None
    assert all(engine.prepared(l) for l in second.lines[1:])


async def test_blank_note_is_made_again(engine):
    # spec 2: a note left with no Korean (`plain`) would come back on every run until the line is changed
    first = await engine.create_pick(*SNEAKER)
    await ready(engine, first)
    rec = engine.store.load(first.id)
    rec.lines[0] = rec.lines[0].model_copy(update={"three": plain(rec.lines[0].text)})
    engine.store.save(rec)
    second = await engine.create_pick(*SNEAKER)
    assert second.lines[0].three is None and second.lines[0].audio == rec.lines[0].audio
    await ready(engine, second)
    assert engine.store.load(second.id).lines[0].three != plain(rec.lines[0].text)


async def test_note_without_reading_is_made_again(engine):
    # Korean but no reading (the 「ref」 degrade) would also come back on every run; with the checks fixed it is rare
    # enough to make again (todo three_line_notes_degrade_rate 3)
    first = await engine.create_pick(*SNEAKER)
    await ready(engine, first)
    rec = engine.store.load(first.id)
    rec.lines[0] = rec.lines[0].model_copy(update={"three": rec.lines[0].three.model_copy(update={"reading": " "})})
    engine.store.save(rec)
    second = await engine.create_pick(*SNEAKER)
    assert second.lines[0].three is None and second.lines[0].audio == rec.lines[0].audio
    await ready(engine, second)
    assert engine.store.load(second.id).lines[0].three.reading.strip()


async def test_settled_note_is_reused(engine):
    first = await engine.create_pick(*SNEAKER)
    await ready(engine, first)
    second = await engine.create_pick(*SNEAKER)
    assert second.lines[0].three == engine.store.load(first.id).lines[0].three


async def test_ko_comes_with_its_sound(engine, monkeypatch):
    # a line without Korean in the repository lends what an earlier run had Claude make
    with_korean(monkeypatch, ko=())
    first = await engine.create_pick(*SNEAKER)
    await ready(engine, first)
    await engine.ko(first.id, 1)
    key = await engine.ko_audio(first.id, 1)
    second = await engine.create_pick(*SNEAKER)
    assert second.lines[1].ko == engine.store.load(first.id).lines[1].ko and second.lines[1].ko_audio == key


async def test_copy_of_a_pick_uses_the_current_script(engine, monkeypatch):
    # spec 4: 「이 상황 다시 하기」 on a list pick plays the script as it is now, in the same group
    first = await engine.create_pick(*SNEAKER)
    await ready(engine, first)
    new = changed_script(monkeypatch)
    again = await engine.copy(first.id)
    assert [(l.speaker, l.text) for l in again.lines] == list(new.script)
    assert (again.origin, again.pick, again.topic) == (first.id, "u-sneaker-size", "usa")


async def test_copy_of_a_pick_gone_from_the_list(engine, monkeypatch):
    # spec 4: a line taken off the list can still be played again from its record
    first = await engine.create_pick(*SNEAKER)
    await ready(engine, first)

    def gone(topic_id, pick_id):
        raise KeyError(pick_id)

    monkeypatch.setattr(topics, "pick", gone)
    again = await engine.copy(first.id)
    assert again.lines == engine.store.load(first.id).lines
    assert (again.origin, again.pick) == (first.id, "u-sneaker-size")


# --- Sohee's Korean in the repository and her sound made ahead (todo 13, plan sohee-prepared) ---------------------

KO = tuple(f"테스트 한국어 {i}" for i in range(len(pick(*SNEAKER).script)))


def with_korean(monkeypatch, ko=KO):
    """The pick with Sohee's Korean for its lines, made up for the test; `ko=()`: a pick without it."""
    p = dataclasses.replace(pick(*SNEAKER), ko=ko)
    monkeypatch.setattr(topics, "pick", lambda t, i: p)
    return p


def sohee_calls(fake_voice):
    return [(i, c) for i, c in enumerate(fake_voice.calls) if c[1] == "sohee"]


async def test_pick_lines_carry_the_repository_korean(engine, fake_claude, monkeypatch):
    p = with_korean(monkeypatch)
    rp = await engine.create_pick(*SNEAKER)
    assert [l.ko for l in rp.lines] == list(p.ko)
    assert [await engine.ko(rp.id, l.idx) for l in rp.lines] == list(p.ko)
    assert fake_claude.interpret_calls == []


async def test_first_pick_makes_sohee_sounds_after_the_lines_are_ready(engine, fake_voice, monkeypatch):
    from je_server.engine import SOHEE_RANK

    with_korean(monkeypatch)
    rp = await engine.create_pick(*SNEAKER)
    await engine.sohees[rp.id]
    saved = engine.store.load(rp.id)
    assert [l.ko_audio for l in saved.lines] == [audio_key("sohee", "korean", k) for k in KO]
    sohee = sohee_calls(fake_voice)
    model = [i for i, c in enumerate(fake_voice.calls) if c[1:3] == ("ryan", "english")]
    assert [c for _, c in sohee] == [(k, "sohee", "korean", False) for k in KO]
    assert len(model) == len(KO) and min(i for i, _ in sohee) > max(model)  # the model sounds go first
    assert all(k in fake_voice.checked for k in KO)  # heard back: a lost 「~요」 changes the meaning
    assert [fake_voice.ranks[i] for i, _ in sohee] == [SOHEE_RANK + l.idx for l in rp.lines]


async def test_sohee_waits_for_the_learner_notes(engine, fake_claude, fake_voice, monkeypatch):
    with_korean(monkeypatch)
    fake_claude.annotate_gate = asyncio.Event()
    rp = await engine.create_pick(*SNEAKER)
    for _ in range(10):
        await asyncio.sleep(0)
    assert sohee_calls(fake_voice) == []
    fake_claude.annotate_gate.set()
    await engine.sohees[rp.id]
    assert len(sohee_calls(fake_voice)) == len(KO)


async def test_sohee_waits_for_the_model_sounds(engine, fake_voice, monkeypatch):
    with_korean(monkeypatch)
    gate = asyncio.Event()
    say = fake_voice.say

    async def held(text, voice, lang, urgent, rank=0, check=False):
        if (voice, lang) == ("ryan", "english"):
            await gate.wait()
        return await say(text, voice, lang, urgent, rank, check)

    monkeypatch.setattr(fake_voice, "say", held)
    rp = await engine.create_pick(*SNEAKER)
    for _ in range(10):
        await asyncio.sleep(0)
    assert sohee_calls(fake_voice) == []
    gate.set()
    await engine.sohees[rp.id]
    assert len(sohee_calls(fake_voice)) == len(KO)


async def test_sohee_sound_already_on_the_mac_comes_with_the_line(engine, fake_voice, monkeypatch):
    with_korean(monkeypatch)
    first = await engine.create_pick(*SNEAKER)
    await engine.sohees[first.id]
    n = len(sohee_calls(fake_voice))
    second = await engine.create_pick(*SNEAKER)
    assert [l.ko_audio for l in second.lines] == [audio_key("sohee", "korean", k) for k in KO]
    assert second.id not in engine.sohees and len(sohee_calls(fake_voice)) == n


def held_attempt(engine, fake_whisper, monkeypatch, speech_bytes, rp):
    """An attempt at the run's first line held inside its transcription until `release` is set."""
    entered, release = asyncio.Event(), asyncio.Event()
    hear = fake_whisper.transcribe

    async def held(wav, lang):
        entered.set()
        await release.wait()
        return await hear(wav, lang)

    monkeypatch.setattr(fake_whisper, "transcribe", held)

    async def run():
        return [e async for e in engine.attempt(rp.id, 0, speech_bytes, "turn")]

    return asyncio.create_task(run()), entered, release


async def test_sohee_waits_while_a_recording_is_answered(engine, fake_claude, fake_voice, fake_whisper, monkeypatch,
                                                         speech_bytes):
    # a sound being made holds the worker: Ryan's answer to the recording would wait behind it
    with_korean(monkeypatch)
    fake_claude.annotate_gate = asyncio.Event()
    rp = await engine.create_pick(*SNEAKER)
    job = engine.sohees[rp.id]
    task, entered, release = held_attempt(engine, fake_whisper, monkeypatch, speech_bytes, rp)
    await asyncio.wait_for(entered.wait(), 5)
    fake_claude.annotate_gate.set()
    for _ in range(20):
        await asyncio.sleep(0)
    assert sohee_calls(fake_voice) == []
    release.set()
    await task
    await asyncio.wait_for(job, 5)
    assert len(sohee_calls(fake_voice)) == len(KO)


async def test_sohee_does_not_wait_forever(engine, fake_claude, fake_voice, fake_whisper, monkeypatch, speech_bytes):
    from je_server import engine as engine_module

    monkeypatch.setattr(engine_module, "QUIET_WAIT", 0.01)
    with_korean(monkeypatch)
    fake_claude.annotate_gate = asyncio.Event()  # her turn comes only once the answer has begun
    rp = await engine.create_pick(*SNEAKER)
    job = engine.sohees[rp.id]
    task, entered, _ = held_attempt(engine, fake_whisper, monkeypatch, speech_bytes, rp)
    await asyncio.wait_for(entered.wait(), 5)
    fake_claude.annotate_gate.set()
    await asyncio.wait_for(job, 5)  # an answer that never ends does not stop her for good
    assert len(sohee_calls(fake_voice)) == len(KO)
    task.cancel()


async def test_a_failed_sohee_sound_leaves_the_text_and_the_rest(engine, fake_voice, monkeypatch):
    with_korean(monkeypatch)
    fake_voice.fail_text = KO[1]
    rp = await engine.create_pick(*SNEAKER)
    await engine.sohees[rp.id]
    saved = engine.store.load(rp.id).lines
    assert saved[1].ko == KO[1] and saved[1].ko_audio is None
    assert all(l.ko_audio for l in saved if l.idx != 1)
    fake_voice.fail_text = None
    assert await engine.ko_audio(rp.id, 1) == audio_key("sohee", "korean", KO[1])  # a tap makes it again


async def test_repository_korean_wins_over_an_earlier_runs(engine, monkeypatch):
    # runs from before the Korean was written down have Sohee's Korean made by Claude, and its sound
    with_korean(monkeypatch, ko=())
    first = await engine.create_pick(*SNEAKER)
    await ready(engine, first)
    await engine.ko(first.id, 1)
    old = await engine.ko_audio(first.id, 1)
    with_korean(monkeypatch)
    second = await engine.create_pick(*SNEAKER)
    assert second.lines[1].ko == KO[1] and second.lines[1].ko_audio is None  # her old sound is not lent with it
    await engine.sohees[second.id]
    assert old != audio_key("sohee", "korean", KO[1])
    assert engine.store.load(second.id).lines[1].ko_audio == audio_key("sohee", "korean", KO[1])


async def test_sohee_asked_first_is_not_made_twice(engine, fake_claude, fake_voice, monkeypatch):
    with_korean(monkeypatch)
    fake_claude.annotate_gate = asyncio.Event()  # her turn in the background waits for the notes
    rp = await engine.create_pick(*SNEAKER)
    key = await engine.ko_audio(rp.id, 1)  # the learner tapped 「통역」 first
    fake_claude.annotate_gate.set()
    await engine.sohees[rp.id]
    assert [c for _, c in sohee_calls(fake_voice)].count((KO[1], "sohee", "korean", True)) == 1
    assert all(c[0] != KO[1] for _, c in sohee_calls(fake_voice) if not c[3])
    assert engine.store.load(rp.id).lines[1].ko_audio == key


async def test_sohee_made_by_another_run_is_not_made_again(engine, fake_voice, monkeypatch):
    # two runs picked before either's sounds are made: the second finds the first's files (branch review 6)
    with_korean(monkeypatch)
    first = await engine.create_pick(*SNEAKER)
    second = await engine.create_pick(*SNEAKER)
    await asyncio.gather(engine.sohees[first.id], engine.sohees[second.id])
    assert len(sohee_calls(fake_voice)) == len(KO)
    assert [l.ko_audio for l in engine.store.load(second.id).lines] == [audio_key("sohee", "korean", k) for k in KO]


async def test_a_cancelled_answer_lets_sohee_go_on(engine, fake_whisper, monkeypatch, speech_bytes):
    # a phone that drops the request mid-answer: the count goes back, or every later line would wait QUIET_WAIT
    with_korean(monkeypatch)
    rp = await engine.create_pick(*SNEAKER)
    task, entered, _ = held_attempt(engine, fake_whisper, monkeypatch, speech_bytes, rp)
    await asyncio.wait_for(entered.wait(), 5)
    assert engine.answers_running == 1 and not engine.quiet.is_set()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert engine.answers_running == 0 and engine.quiet.is_set()


async def test_copy_of_a_list_run_lets_an_error_inside_create_pick_show(engine, monkeypatch):
    # todo fixed-list-scripts minors 1: only a pick taken off the list is copied as it is. A KeyError from inside
    # create_pick is a bug: it must show, not be taken for 「off the list」 and leave a copy behind as well.
    rp = await engine.create_pick(*SNEAKER)

    async def broken(topic_id, pick_id):
        raise KeyError("inside create_pick")

    monkeypatch.setattr(engine, "create_pick", broken)
    before = len(engine.store.all())
    with pytest.raises(KeyError, match="inside create_pick"):
        await engine.copy(rp.id)
    assert len(engine.store.all()) == before



# --- sounds made for an older key (todo voice-reference-in-sound-key, fixed-list-scripts minors 4) ---------------

NEW_REFS = {"ryan": {"english": "new-ryan-en", "korean": "new-ryan-ko"}, "sohee_clone": {"korean": "new-sohee"}}


async def test_a_list_run_does_not_take_sounds_made_with_an_old_reference(engine, fake_voice):
    first = await engine.create_pick(*SNEAKER)
    await ready(engine, first)
    await engine._sohee_later(first.id)
    fake_voice.refs = NEW_REFS  # the reference recordings changed and the server started again
    second = await engine.create_pick(*SNEAKER)
    assert all(l.audio is None for l in second.lines)  # made again, not the old voice
    assert all(l.ko_audio is None for l in second.lines)
    assert all(l.three is not None for l in second.lines if l.speaker == "user")  # notes still come along
    await ready(engine, second)
    assert [l.audio for l in engine.store.load(second.id).lines] == [
        fake_voice.key("ryan", "english", l.text) for l in second.lines]


async def test_a_list_run_still_takes_sounds_of_the_same_reference(engine, fake_voice):
    fake_voice.refs = NEW_REFS
    first = await engine.create_pick(*SNEAKER)
    await ready(engine, first)
    second = await engine.create_pick(*SNEAKER)
    assert [l.audio for l in second.lines] == [l.audio for l in engine.store.load(first.id).lines]
    assert all(l.audio for l in second.lines)


async def test_play_again_does_not_take_sounds_made_with_an_old_reference(engine, fake_voice):
    rp = await engine.create("길 묻기")
    for l in rp.lines:
        await engine.line(rp.id, l.idx)
    await engine.ko(rp.id, 0)
    await engine.ko_audio(rp.id, 0)
    fake_voice.refs = NEW_REFS
    again = await engine.copy(rp.id)
    assert all(l.audio is None for l in again.lines) and again.lines[0].ko_audio is None
    assert again.lines[0].ko == engine.store.load(rp.id).lines[0].ko  # the words stay; only sounds are made again
    old = engine.store.load(rp.id)
    assert all(l.audio for l in old.lines)  # the record played then keeps what was heard


async def test_fixed_phrases_follow_the_reference(engine, fake_voice):
    from je_server.phrases import PHRASES

    fake_voice.refs = NEW_REFS
    assert engine.said("greeting").audio == fake_voice.key("ryan", "korean", PHRASES["greeting"])
    assert engine.said("greeting").audio != audio_key("ryan", "korean", PHRASES["greeting"])
