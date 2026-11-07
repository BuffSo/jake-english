"""A list pick starts from its fixed script and joins the pick's group (spec fixed-list-scripts, ADR-0013)."""
import asyncio
import dataclasses

import pytest

from je_server import topics
from je_server.models import Attempt
from je_server.threeline import plain
from je_server.topics import pick

SNEAKER = ("usa", "u-sneaker-size")  # the learner speaks first
CHANGED = "Excuse me, could I try these in another size?"

pytestmark = pytest.mark.anyio


async def ready(engine, rp):
    for l in rp.lines:
        await engine.line(rp.id, l.idx)


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
    assert all(engine.ready(l) for l in second.lines + third.lines)  # notes and sounds came with it
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
    assert all(engine.ready(l) for l in second.lines[1:])


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


async def test_note_without_reading_is_kept(engine):
    # Korean but no reading (the 「ref」 degrade) is still worth reusing; the fake's notes have reading ""
    first = await engine.create_pick(*SNEAKER)
    await ready(engine, first)
    second = await engine.create_pick(*SNEAKER)
    assert second.lines[0].three == engine.store.load(first.id).lines[0].three


async def test_ko_comes_with_its_sound(engine):
    first = await engine.create_pick(*SNEAKER)
    await ready(engine, first)
    await engine.ko(first.id, 1)
    key = await engine.ko_audio(first.id, 1)
    second = await engine.create_pick(*SNEAKER)
    assert second.lines[1].ko == engine.store.load(first.id).lines[1].ko and second.lines[1].ko_audio == key
