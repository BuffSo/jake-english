"""Free talk: the first question in turn, and what Claude is given (spec free-talk-design 2, 3)."""
import pytest
from fakes import talk_example

from je_server.models import Said
from je_server.phrases import PHRASES, TALK_OPENERS
from je_server.prompts import TALK_CUT, TALK_CUT_SILENT, TALK_START
from je_server.talk import TALK_FRAME, Talks, messages

pytestmark = pytest.mark.anyio


async def test_create_starts_with_the_next_opener_in_turn(talks, engine, fake_voice):
    a = await talks.create()
    b = await talks.create()
    assert [a.lines[0].text, b.lines[0].text] == [TALK_OPENERS[0], TALK_OPENERS[1]]
    assert a.kind == "talk" and a.frame == TALK_FRAME and len(a.lines) == 1
    line = a.lines[0]
    assert line.speaker == "ryan" and line.kind == "reply"
    assert line.parts == [Said(text=TALK_OPENERS[0], audio=fake_voice.key("ryan", "english", TALK_OPENERS[0]))]
    assert engine.load(a.id) == a


async def test_openers_keep_their_turn_across_a_restart(engine_factory):
    first = await Talks(engine_factory()).create()
    second = await Talks(engine_factory()).create()
    assert [first.lines[0].text, second.lines[0].text] == [TALK_OPENERS[0], TALK_OPENERS[1]]


async def test_openers_wrap_after_the_last(talks):
    made = [(await talks.create()).lines[0].text for _ in range(11)]
    assert made[10] == TALK_OPENERS[0]


async def test_opener_sound_is_made_if_missing(talks, fake_voice):
    await talks.create()
    assert (TALK_OPENERS[0], "ryan", "english", True) in fake_voice.calls


async def test_openers_and_talk_phrases_are_made_ahead(engine, fake_voice):
    await engine.warm()
    assert set(TALK_OPENERS) <= set(fake_voice.checked)
    for text in TALK_OPENERS:
        assert (text, "ryan", "english", False) in fake_voice.calls
    assert (PHRASES["talk_english"], "ryan", "korean", False) in fake_voice.calls


def test_messages_put_ryan_as_assistant_after_the_start():
    msgs = messages(talk_example())
    assert [m["role"] for m in msgs] == ["user", "assistant", "user", "assistant", "user", "assistant"]
    assert msgs[0]["content"] == TALK_START


def test_messages_tell_where_ryan_was_cut_off():
    msgs = messages(talk_example())
    assert msgs[3]["content"] == "Sounds lovely! " + TALK_CUT


def test_messages_say_when_ryan_was_cut_off_before_a_word():
    rp = talk_example()
    rp.lines[4] = rp.lines[4].model_copy(update={"heard_upto": 0})
    assert messages(rp)[3]["content"] == TALK_CUT_SILENT


def test_messages_leave_korean_turns_and_fixes_out():
    import re

    msgs = messages(talk_example())
    assert not [m for m in msgs if re.search(r"[가-힣]", m["content"])]
    assert not [m for m in msgs if "went to the market" in m["content"]]
    assert msgs[-1] == {"role": "assistant", "content": "Nice! What did you get there?"}


def test_messages_join_two_learner_turns_in_a_row():
    rp = talk_example()
    rp.lines = [rp.lines[0], rp.lines[3], rp.lines[5]]
    msgs = messages(rp)
    assert [m["role"] for m in msgs] == ["user", "assistant", "user"]
    assert msgs[2]["content"] == "I walked to the park with my dog.\nYesterday I go to the market and buy two apple."
