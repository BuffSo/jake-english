"""Free talk: the first question in turn, what Claude is given, and a turn (spec free-talk-design 2, 3, 4)."""
import asyncio
import logging
import re

import pytest
from fakes import talk_example

from je_server.engine import NotFound
from je_server.models import Said
from je_server.phrases import PHRASES, TALK_OPENERS
from je_server.prompts import TALK_CUT, TALK_CUT_SILENT, TALK_START
from je_server.talk import TALK_FRAME, TalkBusy, Talks, messages

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


# --- a turn ---------------------------------------------------------------------------------------

REPLY = ["Sounds fun!", "I walk there too.", "Was it busy?"]  # FakeClaude.talk_pieces, cut into sentences
HANGUL = re.compile(r"[가-힣]")


async def run(talks, rp_id, body, heard=None):
    return [e async for e in talks.turn(rp_id, body, heard)]


async def until(check):
    for _ in range(500):
        if check():
            return
        await asyncio.sleep(0.01)
    raise AssertionError("never came")


async def test_turn_events_in_order(talks, speech_bytes, fake_whisper, fake_voice):
    rp = await talks.create()
    ev = await run(talks, rp.id, speech_bytes)
    kinds = [e["type"] for e in ev]
    assert kinds[0] == "heard" and kinds[-1] == "done"
    assert set(kinds[1:-1]) == {"text", "reply", "audio"}
    assert kinds.count("reply") == 1 and kinds.count("audio") == 3
    # the reply comes once its text is all there; its sounds may come before or after it
    assert kinds.index("reply") > max(i for i, k in enumerate(kinds) if k == "text")
    assert ev[0] == {"type": "heard", "text": fake_whisper.text, "n": 1, "idx": 1, "korean": False}
    reply = ev[kinds.index("reply")]
    assert reply["idx"] == 2 and reply["kind"] == "reply"
    assert [p["text"] for p in reply["parts"]] == REPLY
    assert [p["audio"] for p in reply["parts"]] == [fake_voice.key("ryan", "english", s) for s in REPLY]
    assert ev[-1] == {"type": "done", "idx": 2}


async def test_turn_is_transcribed_in_english_only(talks, speech_bytes, fake_whisper):
    rp = await talks.create()
    await run(talks, rp.id, speech_bytes)
    assert fake_whisper.langs == ["en"]


async def test_turn_saves_my_line_the_recording_and_ryans_reply(talks, engine, speech_bytes, fake_whisper):
    rp = await talks.create()
    await run(talks, rp.id, speech_bytes)
    saved = engine.load(rp.id)
    mine = saved.lines[1]
    assert (mine.idx, mine.speaker, mine.kind, mine.text) == (1, "user", "turn", fake_whisper.text)
    [attempt] = saved.attempts[1]
    assert attempt.mode == "turn" and attempt.n == 1 and attempt.heard == fake_whisper.text
    assert {"transcribed", "first_text", "first_audio", "total"} <= set(attempt.timings)
    assert engine.store.find_rec(rp.id, 1, 1) is not None
    ryan = saved.lines[2]
    assert (ryan.idx, ryan.speaker, ryan.kind, ryan.text) == (2, "ryan", "reply", " ".join(REPLY))
    assert [p.text for p in ryan.parts] == REPLY and ryan.heard_upto is None


async def test_reply_goes_to_claude_as_turns(talks, speech_bytes, fake_whisper, fake_claude):
    rp = await talks.create()
    await run(talks, rp.id, speech_bytes)
    [sent] = fake_claude.talk_calls
    assert [m["role"] for m in sent] == ["user", "assistant", "user"]
    assert sent[-1]["content"] == fake_whisper.text


async def test_hangul_in_the_english_transcript_is_heard_again_in_korean(talks, engine, speech_bytes, fake_whisper,
                                                                         fake_claude):
    fake_whisper.by_lang = {"en": "I am 피곤해 today", "ko": "오늘 피곤해요"}
    rp = await talks.create()
    ev = await run(talks, rp.id, speech_bytes)
    assert fake_whisper.langs == ["en", "ko"]
    assert ev[0] == {"type": "heard", "text": "오늘 피곤해요", "n": 1, "idx": 1, "korean": True}
    assert [e["type"] for e in ev] == ["heard", "text", "reply", "audio", "done"]
    help_ = engine.said("talk_english")
    assert ev[1] == {"type": "text", "delta": PHRASES["talk_english"]}
    assert ev[2] == {"type": "reply", "idx": 2, "kind": "help", "parts": [help_.model_dump()]}
    assert ev[3] == {"type": "audio", "key": help_.audio} and ev[4] == {"type": "done", "idx": 2}
    saved = engine.load(rp.id)
    assert (saved.lines[1].kind, saved.lines[1].text) == ("ask", "오늘 피곤해요")
    ryan = saved.lines[2]
    assert (ryan.speaker, ryan.kind, ryan.text) == ("ryan", "help", PHRASES["talk_english"])
    assert ryan.audio == help_.audio and ryan.parts == [help_]
    assert fake_claude.talk_calls == []


async def test_korean_transcription_failing_still_answers_in_korean(talks, engine, speech_bytes, fake_whisper):
    fake_whisper.by_lang = {"en": "I am 피곤해 today"}
    fake_whisper.fail_lang = "ko"
    rp = await talks.create()
    ev = await run(talks, rp.id, speech_bytes)
    assert ev[0] == {"type": "heard", "text": "I am 피곤해 today", "n": 1, "idx": 1, "korean": True}
    assert ev[2]["kind"] == "help" and ev[-1] == {"type": "done", "idx": 2}
    assert engine.load(rp.id).lines[2].kind == "help"


async def test_korean_turns_are_not_sent_to_claude(talks, speech_bytes, fake_whisper, fake_claude):
    fake_whisper.by_lang = {"en": "I am 피곤해 today", "ko": "오늘 피곤해요"}
    rp = await talks.create()
    await run(talks, rp.id, speech_bytes)
    fake_whisper.by_lang = {}
    await run(talks, rp.id, speech_bytes)
    [sent] = fake_claude.talk_calls  # the English turn's only
    assert not [m for m in sent if HANGUL.search(m["content"])]
    assert sent[-1] == {"role": "user", "content": fake_whisper.text}


async def test_claude_down_mid_reply_keeps_my_turn_only(talks, engine, speech_bytes, fake_whisper, fake_claude):
    rp = await talks.create()
    fake_claude.talk_fail_after = 1
    ev = await run(talks, rp.id, speech_bytes)
    kinds = [e["type"] for e in ev]
    assert [e for e in ev if e["type"] == "error"] == [
        {"type": "error", "code": "claude_unavailable", "say": engine.said("claude_down").model_dump()}]
    assert "done" not in kinds and "reply" not in kinds
    assert [(l.speaker, l.kind) for l in engine.load(rp.id).lines] == [("ryan", "reply"), ("user", "turn")]
    assert talks.turning == set()
    # my next turn follows the last one: both go to Claude as one user message (spec 4)
    first = fake_whisper.text
    fake_claude.talk_fail_after = None
    fake_whisper.text = "I went to the park."
    ev = await run(talks, rp.id, speech_bytes)
    assert ev[0]["idx"] == 2 and ev[-1] == {"type": "done", "idx": 3}
    sent = fake_claude.talk_calls[1]
    assert [m["role"] for m in sent] == ["user", "assistant", "user"]
    assert sent[-1]["content"] == first + "\n" + "I went to the park."


@pytest.mark.parametrize("pieces", [[], ["  "]])
async def test_a_reply_without_text_is_claude_down(talks, engine, speech_bytes, fake_claude, pieces):
    fake_claude.talk_pieces = pieces
    rp = await talks.create()
    ev = await run(talks, rp.id, speech_bytes)
    assert [e["code"] for e in ev if e["type"] == "error"] == ["claude_unavailable"]
    assert "reply" not in [e["type"] for e in ev] and len(engine.load(rp.id).lines) == 2


async def test_no_speech_turn_saves_no_line(talks, engine, silent_bytes, fake_whisper):
    rp = await talks.create()
    ev = await run(talks, rp.id, silent_bytes)
    assert ev == [{"type": "error", "code": "no_speech", "say": engine.said("no_speech").model_dump()}]
    assert len(engine.load(rp.id).lines) == 1 and fake_whisper.calls == 0
    assert engine.store.find_rec(rp.id, 1, 1) is not None  # the recording itself is kept, as in a roleplay
    assert talks.turning == set()


async def test_empty_transcript_is_no_speech(talks, engine, speech_bytes, fake_whisper):
    fake_whisper.text = ""
    rp = await talks.create()
    ev = await run(talks, rp.id, speech_bytes)
    assert [e["code"] for e in ev] == ["no_speech"] and len(engine.load(rp.id).lines) == 1


async def test_cut_reply_is_kept_and_told(talks, engine, speech_bytes, fake_claude):
    rp = await talks.create()
    await run(talks, rp.id, speech_bytes)
    await run(talks, rp.id, speech_bytes, heard=1)
    assert engine.load(rp.id).lines[2].heard_upto == 1
    # the start, the first question, my turn, the cut reply, my next turn
    assert fake_claude.talk_calls[1][3] == {"role": "assistant", "content": "Sounds fun! " + TALK_CUT}


@pytest.mark.parametrize("heard", [3, 99])
async def test_heard_all_of_the_reply_is_not_a_cut(talks, engine, speech_bytes, fake_voice, heard):
    rp = await talks.create()
    await run(talks, rp.id, speech_bytes)
    await run(talks, rp.id, speech_bytes, heard=heard)
    assert engine.load(rp.id).lines[2].heard_upto is None
    assert fake_voice.demoted == [] and talks.finishing == {}


async def test_cut_reply_rest_is_demoted_and_still_made(talks, engine, speech_bytes, fake_voice, fake_claude):
    rp = await talks.create()
    await run(talks, rp.id, speech_bytes)
    rest = engine.load(rp.id).lines[2].parts[1:]
    for p in rest:
        fake_voice.path(p.audio).unlink()
    # the rest waits behind the new reply's sounds: hold every sound that is not urgent until the new turn is done
    gate = asyncio.Event()
    say = fake_voice.say

    async def held(text, voice, lang, urgent, rank=0, check=False):
        if not urgent:
            await gate.wait()
        return await say(text, voice, lang, urgent, rank, check)

    fake_voice.say = held
    fake_voice.calls.clear()
    fake_claude.talk_pieces = ["Oh, nice! ", "Did you rest?"]
    ev = await run(talks, rp.id, speech_bytes, heard=1)
    assert ev[-1] == {"type": "done", "idx": 4}
    assert fake_voice.demoted == [p.audio for p in rest]
    job = talks.finishing[(rp.id, 2)]
    assert not any(fake_voice.path(p.audio).exists() for p in rest)
    gate.set()
    await job
    assert all(fake_voice.path(p.audio).exists() for p in rest)
    assert [c for c in fake_voice.calls if c[0] in {p.text for p in rest}] == [
        (p.text, "ryan", "english", False) for p in rest]
    assert talks.finishing == {}


async def test_a_second_turn_while_one_runs_is_busy(talks, speech_bytes, fake_claude):
    rp = await talks.create()
    fake_claude.talk_gate = asyncio.Event()
    first = asyncio.create_task(run(talks, rp.id, speech_bytes))
    await until(lambda: fake_claude.talk_calls)
    assert await run(talks, rp.id, speech_bytes) == [{"type": "error", "code": "busy", "say": None}]
    with pytest.raises(TalkBusy):
        talks.check_open(rp.id)
    fake_claude.talk_gate.set()
    assert (await first)[-1] == {"type": "done", "idx": 2}
    assert talks.turning == set()


async def test_a_turn_can_start_once_the_reply_text_is_saved(talks, speech_bytes):
    rp = await talks.create()
    events = talks.turn(rp.id, speech_bytes, None)
    kinds = []
    async for ev in events:
        kinds.append(ev["type"])
        if ev["type"] == "reply":
            break
    assert kinds.count("audio") < len(REPLY)  # Ryan's sounds are still coming
    assert talks.check_open(rp.id).id == rp.id  # the learner may cut them off and speak (spec 2)
    await events.aclose()


async def test_a_turn_ending_late_does_not_free_the_next(talks, engine, speech_bytes, fake_claude):
    rp = await talks.create()
    first = talks.turn(rp.id, speech_bytes, None)
    async for ev in first:
        if ev["type"] == "reply":
            break
    fake_claude.talk_gate = asyncio.Event()
    second = asyncio.create_task(run(talks, rp.id, speech_bytes, heard=1))
    await until(lambda: len(fake_claude.talk_calls) == 2)
    assert [e async for e in first][-1] == {"type": "done", "idx": 2}  # the first turn's sounds end now
    with pytest.raises(TalkBusy):
        talks.check_open(rp.id)  # still the second turn's
    fake_claude.talk_gate.set()
    assert (await second)[-1] == {"type": "done", "idx": 4}
    saved = engine.load(rp.id)
    assert [l.idx for l in saved.lines] == [0, 1, 2, 3, 4] and saved.lines[2].heard_upto == 1
    assert "total" in saved.attempts[1][0].timings and "total" in saved.attempts[3][0].timings
    assert talks.turning == set()


async def test_turn_on_a_roleplay_is_not_found(talks, engine):
    rp = await engine.create("길 묻기")
    with pytest.raises(NotFound):
        talks.check_open(rp.id)


async def test_turn_log_has_times_and_counts_only(talks, speech_bytes, fake_whisper, caplog):
    caplog.set_level(logging.INFO, logger="je_server")
    rp = await talks.create()
    await run(talks, rp.id, speech_bytes)
    assert f"talk {rp.id}/1 n=1 korean=False " in caplog.text
    assert fake_whisper.text not in caplog.text and not [s for s in REPLY if s in caplog.text]
