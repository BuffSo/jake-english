"""Free talk: the first question in turn, what Claude is given, and a turn (spec free-talk-design 2, 3, 4)."""
import asyncio
import logging
import re

import pytest
from fakes import talk_example

from je_server.claude import ClaudeUnavailable
from je_server.engine import NotFound
from je_server.models import Said
from je_server.phrases import PHRASES, TALK_OPENERS, TALK_PHRASES
from je_server.prompts import TALK_CUT, TALK_CUT_SILENT, TALK_ECHO, TALK_KOREAN, TALK_START
from je_server.talk import TALK_FRAME, TalkBusy, TalkEnded, Talks, messages

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
    for text in TALK_PHRASES.values():
        assert (text, "ryan", "english", False) in fake_voice.calls
        assert (text, "ryan", "korean", False) not in fake_voice.calls
    assert set(TALK_PHRASES.values()) <= set(fake_voice.checked)


async def test_roleplay_no_speech_stays_korean(engine):
    assert engine.error("no_speech")["say"]["text"] == PHRASES["no_speech"]


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


def _talk(*lines):
    from je_server.models import ScriptLine
    rp = talk_example()
    rp.lines = [ScriptLine(idx=i, speaker=sp, kind=k, text=t) for i, (sp, k, t) in enumerate(lines)]
    return rp


def test_messages_send_korean_turns_marked():
    rp = _talk(("ryan", "reply", "How was work today?"), ("user", "ask", "야근했다고 어떻게 말해요?"))
    assert messages(rp)[-1] == {"role": "user", "content": TALK_KOREAN + "야근했다고 어떻게 말해요?"}
    assert TALK_ECHO not in messages(rp)[-1]["content"]


def test_messages_leave_fixes_and_old_help_lines_out():
    rp = _talk(("ryan", "reply", "Hi!"), ("user", "ask", "안녕"), ("ryan", "help", "Could you try that in English?"),
               ("user", "turn", "I walked."), ("ryan", "reply", "Nice!"), ("user", "fix", "I walked home."))
    assert [m["content"] for m in messages(rp)] == [TALK_START, "Hi!", TALK_KOREAN + "안녕\nI walked.", "Nice!"]


def _turns(n: int):
    """A talk of Ryan's opener and then `n` of my English turns, each answered but the last."""
    lines = [("ryan", "reply", "Hi!")]
    for i in range(n):
        lines += [("user", "turn", f"I go park {i}.")] + ([("ryan", "reply", f"Fun {i}!")] if i < n - 1 else [])
    return _talk(*lines)


def test_messages_allow_echo_on_every_third_english_turn():
    # with the cue Sonnet recast every mistake turn (8/8), so every third turn gives about a third (spec 4 「되받기」)
    for n in (1, 2, 4, 5, 7):
        assert TALK_ECHO not in repr(messages(_turns(n))), n
    for n in (3, 6):
        msgs = messages(_turns(n))
        assert msgs[-1]["content"] == f"I go park {n - 1}.\n" + TALK_ECHO, n
        assert TALK_ECHO not in repr(msgs[:-1]), n


def test_fix_input_still_skips_old_help_lines_and_korean_turns():
    from je_server.talk import fix_input
    rp = _talk(("ryan", "reply", "Hi!"), ("user", "ask", "안녕"), ("ryan", "help", "Try English."),
               ("user", "turn", "I walked."))
    conversation, turns, helped = fix_input(rp)
    assert [c["말"] for c in conversation] == ["Hi!", "I walked."] and turns == {3: "I walked."} and helped == {}


def test_korean_turns_do_not_count_for_the_echo_and_carry_none():
    rp = _talk(("ryan", "reply", "Hi!"), ("user", "turn", "a b"), ("ryan", "reply", "x"), ("user", "ask", "뭐요?"),
               ("ryan", "reply", "y"), ("user", "turn", "c d"), ("ryan", "reply", "z"), ("user", "turn", "e f"))
    assert messages(rp)[-1]["content"] == "e f\n" + TALK_ECHO  # my 3rd English turn
    rp = _talk(("ryan", "reply", "Hi!"), ("user", "turn", "a b"), ("ryan", "reply", "x"), ("user", "turn", "c d"),
               ("ryan", "reply", "y"), ("user", "turn", "e f"), ("ryan", "reply", "z"), ("user", "ask", "뭐요?"))
    assert messages(rp)[-1]["content"] == TALK_KOREAN + "뭐요?"


def test_messages_after_ryans_reply_carry_no_echo():
    msgs = messages(talk_example())
    assert TALK_ECHO not in repr(msgs)
    assert msgs[-1] == {"role": "assistant", "content": "Nice! What did you get there?"}


def test_messages_join_two_learner_turns_in_a_row():
    rp = talk_example()
    rp.lines = [rp.lines[0], rp.lines[3], rp.lines[5]]
    msgs = messages(rp)
    assert [m["role"] for m in msgs] == ["user", "assistant", "user"]
    # my 2nd English turn: no echo cue (it comes on the 3rd)
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


async def test_korean_turn_gets_ryans_english_reply_from_claude(talks, engine, speech_bytes, fake_whisper,
                                                                 fake_claude):
    fake_whisper.by_lang = {"en": "I am 피곤해 today", "ko": "오늘 피곤해요"}
    rp = await talks.create()
    ev = await run(talks, rp.id, speech_bytes)
    assert fake_whisper.langs == ["en", "ko"]
    assert ev[0] == {"type": "heard", "text": "오늘 피곤해요", "n": 1, "idx": 1, "korean": True}
    assert ev[-1] == {"type": "done", "idx": 2}
    saved = engine.load(rp.id)
    assert [l.kind for l in saved.lines[1:]] == ["ask", "reply"]
    assert saved.lines[2].text == " ".join(REPLY)
    assert fake_claude.talk_calls[-1][-1]["content"] == TALK_KOREAN + "오늘 피곤해요"


async def test_korean_transcription_failing_still_goes_to_claude(talks, engine, speech_bytes, fake_whisper,
                                                                 fake_claude):
    fake_whisper.by_lang = {"en": "I am 피곤해 today"}
    fake_whisper.fail_lang = "ko"
    rp = await talks.create()
    ev = await run(talks, rp.id, speech_bytes)
    assert ev[0] == {"type": "heard", "text": "I am 피곤해 today", "n": 1, "idx": 1, "korean": True}
    assert ev[-1] == {"type": "done", "idx": 2}
    assert [l.kind for l in engine.load(rp.id).lines[1:]] == ["ask", "reply"]
    assert len(fake_claude.talk_calls) == 1


async def test_korean_by_probability_is_heard_again_in_korean(talks, engine, speech_bytes, fake_whisper,
                                                             fake_claude):
    # Korean the English transcript translated (no Hangul), but whisper gives it Korean (spec 3)
    fake_whisper.by_lang = {"en": "How do you say I went to the river?", "ko": "강가에 갔다는 말은 어떻게 해요?"}
    fake_whisper.korean_p = 0.995
    rp = await talks.create()
    ev = await run(talks, rp.id, speech_bytes)
    assert fake_whisper.langs == ["en", "ko"]
    assert ev[0] == {"type": "heard", "text": "강가에 갔다는 말은 어떻게 해요?", "n": 1, "idx": 1, "korean": True}
    assert [l.kind for l in engine.load(rp.id).lines[1:]] == ["ask", "reply"]
    assert fake_claude.talk_calls[-1][-1]["content"] == TALK_KOREAN + "강가에 갔다는 말은 어떻게 해요?"


async def test_korean_probability_at_the_bar(talks, engine, speech_bytes, fake_whisper):
    fake_whisper.by_lang = {"en": "I like rainy days.", "ko": "비 오는 날이 좋아요."}
    for p, korean in ((0.98, True), (0.979, False)):
        fake_whisper.korean_p = p
        fake_whisper.langs = []
        rp = await talks.create()
        ev = await run(talks, rp.id, speech_bytes)
        assert ev[0]["korean"] is korean
        assert fake_whisper.langs == (["en", "ko"] if korean else ["en"])


async def test_korean_by_probability_falls_back_to_english_when_korean_fails(talks, engine, speech_bytes,
                                                                            fake_whisper, fake_claude):
    # no Hangul to show: an English turn, so Claude is not told English text is Korean
    fake_whisper.by_lang = {"en": "I like rainy days."}
    fake_whisper.korean_p = 0.99
    fake_whisper.fail_lang = "ko"
    rp = await talks.create()
    ev = await run(talks, rp.id, speech_bytes)
    assert ev[0] == {"type": "heard", "text": "I like rainy days.", "n": 1, "idx": 1, "korean": False}
    assert engine.load(rp.id).lines[1].kind == "turn"
    assert fake_claude.talk_calls[-1][-1]["content"] == "I like rainy days."


async def test_korean_by_probability_without_hangul_stays_english(talks, engine, speech_bytes, fake_whisper):
    # whisper forced to Korean may write English speech as English
    fake_whisper.by_lang = {"en": "I like rainy days.", "ko": "I like rainy days."}
    fake_whisper.korean_p = 0.99
    rp = await talks.create()
    ev = await run(talks, rp.id, speech_bytes)
    assert ev[0] == {"type": "heard", "text": "I like rainy days.", "n": 1, "idx": 1, "korean": False}
    assert engine.load(rp.id).lines[1].kind == "turn"


async def test_claude_down_mid_reply_keeps_my_turn_only(talks, engine, speech_bytes, fake_whisper, fake_claude):
    rp = await talks.create()
    fake_claude.talk_fail_after = 1
    ev = await run(talks, rp.id, speech_bytes)
    kinds = [e["type"] for e in ev]
    assert [e for e in ev if e["type"] == "error"] == [
        {"type": "error", "code": "claude_unavailable", "say": engine.talk_said("claude_down").model_dump()}]
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
    assert sent[-1]["content"] == first + "\n" + "I went to the park."  # my 2nd English turn: no echo cue


async def test_claude_down_mid_reply_frees_the_talk_at_the_error(talks, engine, speech_bytes, fake_claude,
                                                                 fake_voice):
    # the error goes out at once while the sentence already written is still being voiced (1-3 s): no Ryan line can be
    # kept after it, so the talk is free from the error on and 「대화 끝내기」 right after it is not refused as busy
    rp = await talks.create()
    fake_claude.talk_fail_after = 1
    gate = asyncio.Event()
    say = fake_voice.say

    async def held(text, voice, lang, urgent, rank=0, check=False):
        if text == REPLY[0]:
            await gate.wait()
        return await say(text, voice, lang, urgent, rank, check)

    fake_voice.say = held
    events = talks.turn(rp.id, speech_bytes, None)
    try:
        async for ev in events:
            if ev["type"] == "error":
                break
        assert ev["code"] == "claude_unavailable"
        assert rp.id not in talks.turning
        assert talks.check_open(rp.id).id == rp.id
        assert await talks.end(rp.id) == no_fixes(engine)
    finally:
        gate.set()
    rest = [e async for e in events]
    assert rest == [{"type": "audio", "key": fake_voice.key("ryan", "english", REPLY[0])}]  # voiced; no done
    assert talks.turning == set()
    assert [(l.speaker, l.kind) for l in engine.load(rp.id).lines] == [("ryan", "reply"), ("user", "turn")]


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
    assert ev == [{"type": "error", "code": "no_speech", "say": engine.talk_said("no_speech").model_dump()}]
    assert ev[0]["say"]["text"] == TALK_PHRASES["no_speech"]
    assert ev[0]["say"]["audio"] == engine.voice.key("ryan", "english", TALK_PHRASES["no_speech"])
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
    fake_whisper.korean_p = 0.25
    rp = await talks.create()
    await run(talks, rp.id, speech_bytes)
    assert f"talk {rp.id}/1 n=1 korean=False korean_p=0.250 " in caplog.text
    assert fake_whisper.text not in caplog.text and not [s for s in REPLY if s in caplog.text]


# --- ending a talk (spec free-talk-design 6, 7) ------------------------------------------------------------------

SAID = ["I go to the park yesterday.", "I eat two apple there.", "My friend come with me.", "We was very happy."]
FIXED = ["I went to the park yesterday.", "I ate two apples there.", "My friend came with me.", "We were very happy."]
WHY = ["지난 일이라 go를 went로 바꿔요.", "사과가 둘이라 apples예요.", "지난 일이라 came이에요.", "we 뒤에는 were를 써요."]
NO_SOUND = {"heard": "", "meant": "", "say_ko": ""}


def fix_item(i: int, idx: int) -> dict:
    """What Claude picks for my turn at line `idx`, from the made-up fix number `i`."""
    return {"idx": idx, "said": SAID[i], "fixed": FIXED[i], "why_ko": WHY[i], "sound": dict(NO_SOUND)}


async def talked(talks, fake_whisper, speech_bytes, said=SAID[:2]) -> str:
    """A talk with my English turns `said` at lines 1, 3, 5…, each answered by Ryan."""
    rp = await talks.create()
    for text in said:
        fake_whisper.text = text
        await run(talks, rp.id, speech_bytes)
    return rp.id


def no_fixes(engine, sohee: int = 0) -> dict:
    return {"items": [], "say": engine.said("talk_no_fixes").model_dump(), "sohee": sohee}


async def test_end_appends_the_checked_fixes_as_my_lines(talks, engine, speech_bytes, fake_whisper, fake_claude):
    rp_id = await talked(talks, fake_whisper, speech_bytes, SAID)
    fake_claude.fix_items = [fix_item(i, 1 + 2 * i) for i in range(4)]
    body = await talks.end(rp_id)
    added = engine.load(rp_id).lines[9:]  # after the opener and four turns with Ryan's replies
    assert [(l.idx, l.speaker, l.kind, l.text) for l in added] == [(9 + i, "user", "fix", FIXED[i]) for i in range(3)]
    assert [(l.fix.of, l.fix.said, l.fix.why_ko) for l in added] == [(1 + 2 * i, SAID[i], WHY[i]) for i in range(3)]
    assert [it["line"]["idx"] for it in body["items"]] == [9, 10, 11]
    assert [it["rec"] for it in body["items"]] == [{"rp_id": rp_id, "idx": 1 + 2 * i, "n": 1} for i in range(3)]
    assert body["say"] is None


async def test_end_makes_the_first_fix_sounds_first_and_urgent(talks, engine, speech_bytes, fake_whisper,
                                                                fake_claude, fake_voice):
    rp_id = await talked(talks, fake_whisper, speech_bytes)
    fake_claude.fix_items = [fix_item(0, 1), fix_item(1, 3)]
    fake_voice.calls.clear()
    body = await talks.end(rp_id)
    await engine.line(rp_id, 6)  # the second fix's sounds, made behind
    first = [(WHY[0], "ryan", "korean", True), (FIXED[0], "ryan", "english", True)]
    later = [n for n, c in enumerate(fake_voice.calls) if c[0] in (WHY[1], FIXED[1])]
    assert later and max(fake_voice.calls.index(c) for c in first) < min(later)
    assert (WHY[1], "ryan", "korean", False) in fake_voice.calls
    assert (FIXED[1], "ryan", "english", False) in fake_voice.calls
    line = body["items"][0]["line"]
    assert line["audio"] == fake_voice.key("ryan", "english", FIXED[0])
    assert line["fix"]["why_audio"] == fake_voice.key("ryan", "korean", WHY[0])


async def test_two_ends_at_once_ask_claude_once(talks, speech_bytes, fake_whisper, fake_claude):
    rp_id = await talked(talks, fake_whisper, speech_bytes)
    fake_claude.fix_items = [fix_item(0, 1)]
    fake_claude.fix_gate = asyncio.Event()
    both = asyncio.gather(talks.end(rp_id), talks.end(rp_id))
    await until(lambda: fake_claude.fix_calls)
    fake_claude.fix_gate.set()
    a, b = await both
    assert len(fake_claude.fix_calls) == 1 and a == b and len(a["items"]) == 1


async def test_end_again_returns_the_same_fixes_without_claude(talks, speech_bytes, fake_whisper, fake_claude):
    rp_id = await talked(talks, fake_whisper, speech_bytes)
    fake_claude.fix_items = [fix_item(0, 1)]
    fake_claude.annotate_gate = asyncio.Event()  # the fix line's notes, made behind, do not change it in between
    first = await talks.end(rp_id)
    second = await talks.end(rp_id)
    assert len(fake_claude.fix_calls) == 1 and first == second and first["items"]
    fake_claude.annotate_gate.set()
    await until(lambda: not talks.engine.threes)


async def test_end_without_english_turns_says_nothing_to_fix_without_claude(talks, engine, speech_bytes,
                                                                             fake_whisper, fake_claude):
    rp = await talks.create()
    fake_whisper.by_lang = {"en": "I am 피곤해 today", "ko": "오늘 피곤해요"}
    await run(talks, rp.id, speech_bytes)
    body = await talks.end(rp.id)
    assert body == no_fixes(engine) and body["say"]["text"] == PHRASES["talk_no_fixes"]
    assert fake_claude.fix_calls == []


@pytest.mark.parametrize("items", [[], [fix_item(0, 2)]])  # nothing, or only Ryan's line picked
async def test_end_with_nothing_to_fix_says_so(talks, engine, speech_bytes, fake_whisper, fake_claude, items):
    rp_id = await talked(talks, fake_whisper, speech_bytes)
    lines = engine.load(rp_id).lines
    fake_claude.fix_items = items
    assert await talks.end(rp_id) == no_fixes(engine)
    assert len(fake_claude.fix_calls) == 1 and engine.load(rp_id).lines == lines


async def test_end_sends_english_turns_and_ryans_replies_not_korean_turns(talks, speech_bytes, fake_whisper, fake_claude):
    rp = await talks.create()
    fake_whisper.by_lang = {"en": "I am 피곤해 today", "ko": "오늘 피곤해요"}
    await run(talks, rp.id, speech_bytes)  # my Korean turn (1) and Ryan's English reply (2)
    fake_whisper.by_lang = {}
    fake_whisper.text = SAID[0]
    await run(talks, rp.id, speech_bytes)  # my English turn (3) and Ryan's reply (4)
    await talks.end(rp.id)
    [sent] = fake_claude.fix_calls
    assert [(c["차례"], c["말한 사람"]) for c in sent] == [
        (0, "라이언"), (2, "라이언"), (3, "학습자"), (4, "라이언")]  # no Korean turn
    assert not [c for c in sent if HANGUL.search(c["말"])]
    assert [c["말"] for c in sent] == [rp.lines[0].text, " ".join(REPLY), SAID[0], " ".join(REPLY)]


async def test_end_while_a_turn_runs_is_busy(talks, speech_bytes, fake_claude):
    rp = await talks.create()
    fake_claude.talk_gate = asyncio.Event()
    turn = asyncio.create_task(run(talks, rp.id, speech_bytes))
    await until(lambda: fake_claude.talk_calls)
    with pytest.raises(TalkBusy):
        await talks.end(rp.id)
    fake_claude.talk_gate.set()
    await turn
    assert fake_claude.fix_calls == []


async def test_a_turn_while_the_talk_ends_is_busy(talks, engine, speech_bytes, fake_whisper, fake_claude):
    # a turn sent while Claude picks the fixes would take the line number the first fix line gets
    rp_id = await talked(talks, fake_whisper, speech_bytes)
    fake_claude.fix_items = [fix_item(0, 1)]
    fake_claude.fix_gate = asyncio.Event()
    ending = asyncio.create_task(talks.end(rp_id))
    await until(lambda: fake_claude.fix_calls)
    with pytest.raises(TalkBusy):
        talks.check_open(rp_id)
    assert await run(talks, rp_id, speech_bytes) == [{"type": "error", "code": "busy", "say": None}]
    fake_claude.fix_gate.set()
    body = await ending
    assert body["items"][0]["line"]["idx"] == 5 and len(engine.load(rp_id).lines) == 6


async def test_a_turn_after_end_is_ended(talks, speech_bytes, fake_whisper, fake_claude):
    rp_id = await talked(talks, fake_whisper, speech_bytes)
    fake_claude.fix_items = [fix_item(0, 1)]
    await talks.end(rp_id)
    with pytest.raises(TalkEnded):
        talks.check_open(rp_id)


async def test_end_marks_where_ryan_was_cut_off(talks, engine, speech_bytes, fake_whisper):
    rp_id = await talked(talks, fake_whisper, speech_bytes, SAID[:1])
    await talks.end(rp_id, heard=1)
    assert engine.load(rp_id).lines[2].heard_upto == 1


async def test_end_puts_ryans_last_sounds_behind_the_fixes(talks, engine, speech_bytes, fake_whisper, fake_voice):
    rp_id = await talked(talks, fake_whisper, speech_bytes, SAID[:1])
    assert fake_voice.demoted == []
    await talks.end(rp_id)
    assert fake_voice.demoted == [p.audio for p in engine.load(rp_id).lines[2].parts]


async def test_end_of_a_roleplay_is_not_found(talks, engine):
    rp = await engine.create("길 묻기")
    with pytest.raises(NotFound):
        await talks.end(rp.id)


async def test_end_when_claude_is_down_raises_and_keeps_no_lines(talks, engine, speech_bytes, fake_whisper,
                                                                  fake_claude):
    rp_id = await talked(talks, fake_whisper, speech_bytes)
    lines = engine.load(rp_id).lines
    fake_claude.fail_next = True
    with pytest.raises(ClaudeUnavailable):
        await talks.end(rp_id)
    assert engine.load(rp_id).lines == lines
    fake_claude.fix_items = [fix_item(0, 1)]
    assert len((await talks.end(rp_id))["items"]) == 1  # tried again on the next end


async def test_end_log_has_times_and_counts_only(talks, speech_bytes, fake_whisper, fake_claude, caplog):
    caplog.set_level(logging.INFO, logger="je_server")
    rp_id = await talked(talks, fake_whisper, speech_bytes)
    fake_claude.fix_items = [fix_item(0, 1), fix_item(1, 3)]
    await talks.end(rp_id)
    assert re.search(rf"talk end {rp_id} fixes=2 first_fix_sound=\d+\.\d\d total=\d+\.\d\d", caplog.text)
    assert not [t for t in (*SAID, *FIXED, *WHY) if t in caplog.text]


# --- Sohee chance (spec free-talk-design 9) ----------------------------------------------------------------------

async def replied(talks, speech_bytes) -> str:
    """A talk with Ryan's opener (0), my turn (1) and his reply (2)."""
    rp = await talks.create()
    await run(talks, rp.id, speech_bytes)
    return rp.id


async def test_hint_is_made_once_and_kept_on_the_line(talks, engine, speech_bytes, fake_claude):
    from je_server import hints

    rp_id = await replied(talks, speech_bytes)
    hint = await talks.hint(rp_id, 2)
    assert hint == fake_claude.hint_value
    assert engine.load(rp_id).lines[2].hint == hint
    assert fake_claude.hint_calls == [hints.conversation(engine.load(rp_id), 2)]
    # his line, for the Mac's check on openers that repeat it (spec 9)
    assert fake_claude.hint_ryans == [engine.load(rp_id).lines[2].text]
    assert await talks.hint(rp_id, 2) == hint and len(fake_claude.hint_calls) == 1
    assert (await talks.hint(rp_id, 0)) == hint  # Ryan's first question takes one too
    assert fake_claude.hint_calls[1] == hints.conversation(engine.load(rp_id), 0)


async def test_two_hints_at_once_ask_claude_once(talks, speech_bytes, fake_claude):
    rp_id = await replied(talks, speech_bytes)
    fake_claude.hint_gate = asyncio.Event()
    both = asyncio.gather(talks.hint(rp_id, 2), talks.hint(rp_id, 2))
    await until(lambda: fake_claude.hint_calls)
    fake_claude.hint_gate.set()
    a, b = await both
    assert len(fake_claude.hint_calls) == 1 and a == b == fake_claude.hint_value
    await until(lambda: not talks.hinting)


async def test_hint_when_claude_is_down_keeps_nothing(talks, engine, speech_bytes, fake_claude):
    rp_id = await replied(talks, speech_bytes)
    fake_claude.fail_next = True
    with pytest.raises(ClaudeUnavailable):
        await talks.hint(rp_id, 2)
    assert engine.load(rp_id).lines[2].hint is None
    assert await talks.hint(rp_id, 2) == fake_claude.hint_value  # asked again on the next press


async def test_hint_on_a_line_that_is_not_ryans_reply_is_not_found(talks, engine, speech_bytes, fake_whisper,
                                                                   fake_claude):
    rp_id = await talked(talks, fake_whisper, speech_bytes, SAID[:1])
    fake_claude.fix_items = [fix_item(0, 1)]
    await talks.end(rp_id)  # a fix line at 3
    for idx in (1, 3, 99):  # my turn, the fix line, no line
        with pytest.raises(NotFound):
            await talks.hint(rp_id, idx)
    roleplay = await engine.create("길 묻기")
    with pytest.raises(NotFound):
        await talks.hint(roleplay.id, 0)
    old = _talk(("ryan", "reply", "Hi!"), ("user", "ask", "안녕"), ("ryan", "help", "Could you try that in English?"))
    engine.store.save(old)
    with pytest.raises(NotFound):
        await talks.hint(old.id, 2)  # an old record's fixed line
    assert fake_claude.hint_calls == []


async def test_full_before_hint_is_refused(talks, speech_bytes, fake_claude):
    from je_server.talk import NoHint

    rp_id = await replied(talks, speech_bytes)
    for ask in (talks.hint_audio(rp_id, 2), talks.show_full(rp_id, 2), talks.hint_sound(rp_id, 2, 0),
                talks.hint_three(rp_id, 2)):
        with pytest.raises(NoHint):
            await ask
    await talks.hint(rp_id, 2)
    with pytest.raises(NoHint):
        await talks.hint_three(rp_id, 2)  # its notes only once the full sentence was shown
    with pytest.raises(NotFound):
        await talks.show_full(rp_id, 1)


async def test_hint_audio_is_sohee_saying_the_meaning_and_kept(talks, engine, speech_bytes, fake_claude, fake_voice):
    from je_server.phrases import SOHEE_PHRASES

    rp_id = await replied(talks, speech_bytes)
    hint = await talks.hint(rp_id, 2)
    said = f"{hint.meaning_ko} {SOHEE_PHRASES['hint_start']}"
    key = await talks.hint_audio(rp_id, 2)
    assert key == fake_voice.key("sohee", "korean", said)
    assert (said, "sohee", "korean", True) in fake_voice.calls and said in fake_voice.checked
    assert engine.load(rp_id).lines[2].hint.audio == key
    fake_voice.calls.clear()
    assert await talks.hint_audio(rp_id, 2) == key and fake_voice.calls == []


async def test_full_marks_the_line_and_says_sohees_line(talks, engine, speech_bytes, fake_claude, fake_voice):
    from je_server.phrases import SOHEE_PHRASES

    rp_id = await replied(talks, speech_bytes)
    hint = await talks.hint(rp_id, 2)
    assert not engine.load(rp_id).lines[2].hint.full_shown
    body = await talks.show_full(rp_id, 2)
    phrase = SOHEE_PHRASES["hint_full"]
    assert body == {"text": hint.full, "say": {"text": phrase, "audio": fake_voice.key("sohee", "korean", phrase)}}
    assert engine.load(rp_id).lines[2].hint.full_shown
    assert await talks.show_full(rp_id, 2) == body and len(fake_claude.hint_calls) == 1


async def test_hint_sounds_starters_then_full_only_after_shown(talks, speech_bytes, fake_claude, fake_voice):
    from je_server.talk import NoHint

    rp_id = await replied(talks, speech_bytes)
    hint = await talks.hint(rp_id, 2)
    for n, starter in enumerate(hint.starters):
        assert await talks.hint_sound(rp_id, 2, n) == fake_voice.key("ryan", "english", starter)
        assert (starter, "ryan", "english", True) in fake_voice.calls
    after = len(hint.starters)
    with pytest.raises(NoHint):
        await talks.hint_sound(rp_id, 2, after)
    await talks.show_full(rp_id, 2)
    assert await talks.hint_sound(rp_id, 2, after) == fake_voice.key("ryan", "english", hint.full)
    assert (hint.full, "ryan", "english", True) in fake_voice.calls
    with pytest.raises(NotFound):
        await talks.hint_sound(rp_id, 2, after + 1)


async def test_hint_three_notes_the_full_sentence_once(talks, engine, speech_bytes, fake_claude):
    rp_id = await replied(talks, speech_bytes)
    hint = await talks.hint(rp_id, 2)
    await talks.show_full(rp_id, 2)
    three = await talks.hint_three(rp_id, 2)
    rp = engine.load(rp_id)
    assert ("annotate", (hint.full, engine.context(rp, 2))) in fake_claude.calls
    assert rp.lines[2].hint.full_three == three
    asked = len(fake_claude.calls)
    assert await talks.hint_three(rp_id, 2) == three and len(fake_claude.calls) == asked


async def test_hint_changes_at_once_keep_each_other(talks, engine, speech_bytes, fake_claude, fake_voice):
    # Sohee's sound is still being made when 「전체 문장 보기」 is pressed: both stay on the line
    rp_id = await replied(talks, speech_bytes)
    await talks.hint(rp_id, 2)
    entered, gate = asyncio.Event(), asyncio.Event()
    say = fake_voice.say

    async def held(text, voice, lang, urgent, rank=0, check=False):
        if voice == "sohee":
            entered.set()
            await gate.wait()
        return await say(text, voice, lang, urgent, rank, check)

    fake_voice.say = held
    sound = asyncio.create_task(talks.hint_audio(rp_id, 2))
    await entered.wait()
    await talks.show_full(rp_id, 2)
    gate.set()
    key = await sound
    hint = engine.load(rp_id).lines[2].hint
    assert hint.full_shown and hint.audio == key


async def test_hint_log_has_times_and_counts_only(talks, speech_bytes, fake_claude, caplog):
    caplog.set_level(logging.INFO, logger="je_server")
    rp_id = await replied(talks, speech_bytes)
    await talks.hint(rp_id, 2)
    assert re.search(rf"hint {rp_id}/2 starters=2 total=\d+\.\d\d", caplog.text)
    h = fake_claude.hint_value
    assert not [t for t in (h.meaning_ko, h.full, *h.starters) if t in caplog.text]


async def test_sohees_phrases_are_made_ahead(engine, fake_voice):
    from je_server.phrases import SOHEE_PHRASES

    await engine.warm()
    phrase = SOHEE_PHRASES["hint_full"]
    assert (phrase, "sohee", "korean", False) in fake_voice.calls and phrase in fake_voice.checked


@pytest.mark.parametrize("steps, count", [
    ({}, 0),
    ({2: False}, 1),  # the hint only
    ({2: True}, 2),  # the hint and the full sentence
    ({0: True, 2: False}, 3),  # two of Ryan's lines, summed
])
async def test_end_counts_sohee_chances(talks, engine, speech_bytes, fake_whisper, steps, count):
    rp_id = await talked(talks, fake_whisper, speech_bytes, SAID[:1])  # Ryan at 0 and 2, my turn at 1
    for idx, full in steps.items():
        await talks.hint(rp_id, idx)
        if full:
            await talks.show_full(rp_id, idx)
    assert await talks.end(rp_id) == no_fixes(engine, count)  # nothing to fix: the count is still there


async def test_end_with_nothing_to_fix_counts_a_hint_made_while_claude_picked(talks, engine, speech_bytes,
                                                                               fake_whisper, fake_claude):
    # PR review: the no-fixes answer was built from the record as read before the Claude call
    rp_id = await talked(talks, fake_whisper, speech_bytes, SAID[:1])
    fake_claude.fix_gate = asyncio.Event()
    ending = asyncio.create_task(talks.end(rp_id))
    await until(lambda: fake_claude.fix_calls)
    await talks.hint(rp_id, 2)
    await talks.show_full(rp_id, 2)
    fake_claude.fix_gate.set()
    assert await ending == no_fixes(engine, 2)


async def test_end_with_fixes_counts_sohee_chances_too(talks, speech_bytes, fake_whisper, fake_claude):
    rp_id = await talked(talks, fake_whisper, speech_bytes, SAID[:1])
    await talks.hint(rp_id, 2)
    await talks.show_full(rp_id, 2)
    fake_claude.fix_items = [fix_item(0, 1)]
    body = await talks.end(rp_id)
    assert body["items"] and body["sohee"] == 2
    assert (await talks.end(rp_id))["sohee"] == 2  # asked again, from the record


async def test_two_hint_notes_at_once_ask_claude_once(talks, speech_bytes, fake_claude):
    rp_id = await replied(talks, speech_bytes)
    hint = await talks.hint(rp_id, 2)
    await talks.show_full(rp_id, 2)
    fake_claude.annotate_gate = asyncio.Event()
    both = asyncio.gather(talks.hint_three(rp_id, 2), talks.hint_three(rp_id, 2))
    await until(lambda: [c for c in fake_claude.calls if c[0] == "annotate" and c[1][0] == hint.full])
    fake_claude.annotate_gate.set()
    a, b = await both
    assert a == b and len([c for c in fake_claude.calls if c[0] == "annotate" and c[1][0] == hint.full]) == 1
    await until(lambda: not talks.hint_threes)


# --- a turn after Sohee's full sentence (spec free-talk-design 7 「고르는 차례」, 9 「그 문장을 말하면」) -----------------

async def shown_full(talks, speech_bytes) -> tuple[str, str]:
    """A talk whose last line is Ryan's reply (2) with Sohee's full sentence shown; the talk and that sentence."""
    rp_id = await replied(talks, speech_bytes)
    hint = await talks.hint(rp_id, 2)
    await talks.show_full(rp_id, 2)
    return rp_id, hint.full


@pytest.mark.parametrize("heard, points", [
    ("I want to the park with my dog.", [("went", "want")]),  # followed (0.88), one word heard wrong
    # near (0.43): a try at it that came out wrong. Only I heard as we sounds close; the added and missing words are
    # not mishearings
    ("We went to a big park.", [("i", "we")]),
    ("I went to the park with my dog.", []),  # the sentence itself, nothing heard wrong
])
async def test_turn_after_the_full_sentence_is_compared_with_it(talks, engine, speech_bytes, fake_whisper,
                                                                fake_claude, heard, points):
    from je_server.compare import FOLLOW_MIN, similarity
    from je_server.engine import NEAR_MIN
    from je_server.prompts import TALK_HELPED

    rp_id, full = await shown_full(talks, speech_bytes)
    assert similarity(full, heard) >= NEAR_MIN
    fake_whisper.text = heard
    ev = await run(talks, rp_id, speech_bytes)
    # no evaluation now: Ryan just answers, as after any turn
    assert ev[0] == {"type": "heard", "text": heard, "n": 1, "idx": 3, "korean": False}
    assert ev[-1] == {"type": "done", "idx": 4} and fake_claude.feedback_calls == []
    saved = engine.load(rp_id)
    line, [attempt] = saved.lines[3], saved.attempts[3]
    assert (line.kind, line.text, line.given) == ("turn", heard, full)
    assert [(i.target, i.heard) for i in attempt.issues] == points
    assert attempt.followed == (similarity(full, heard) >= FOLLOW_MIN)
    # Claude is told the turn was helped (my 2nd English turn: no echo cue yet)
    assert fake_claude.talk_calls[-1][-1]["content"] == heard + "\n" + TALK_HELPED


async def test_far_from_the_given_sentence_is_a_plain_turn(talks, engine, speech_bytes, fake_whisper, fake_claude):
    from je_server.compare import similarity
    from je_server.engine import NEAR_MIN
    from je_server.prompts import TALK_HELPED

    rp_id, full = await shown_full(talks, speech_bytes)
    heard = "I stayed home and watched TV."  # my own words, not Sohee's sentence
    assert similarity(full, heard) < NEAR_MIN
    fake_whisper.text = heard
    await run(talks, rp_id, speech_bytes)
    saved = engine.load(rp_id)
    [attempt] = saved.attempts[3]
    assert saved.lines[3].given is None and attempt.issues == [] and not attempt.followed
    assert TALK_HELPED not in repr(fake_claude.talk_calls[-1])


async def test_a_hint_without_the_full_sentence_gives_no_given(talks, engine, speech_bytes, fake_whisper):
    rp_id = await replied(talks, speech_bytes)
    hint = await talks.hint(rp_id, 2)  # the first step only
    fake_whisper.text = hint.full
    await run(talks, rp_id, speech_bytes)
    saved = engine.load(rp_id)
    assert saved.lines[3].given is None and saved.attempts[3][0].issues == []


async def test_only_ryans_reply_right_before_my_turn_counts(talks, engine, speech_bytes, fake_whisper):
    rp = await talks.create()
    hint = await talks.hint(rp.id, 0)
    await talks.show_full(rp.id, 0)  # on the opener (0), the last line when my first turn starts
    fake_whisper.text = hint.full
    await run(talks, rp.id, speech_bytes)  # my turn (1), Ryan (2)
    await run(talks, rp.id, speech_bytes)  # the same sentence again (3), after Ryan's reply without a hint
    saved = engine.load(rp.id)
    assert saved.lines[1].given == hint.full and saved.lines[3].given is None


async def full_on_opener(talks, fake_claude, full: str) -> str:
    """A new talk with Sohee's full sentence `full` shown on Ryan's opener (0); the talk."""
    from je_server.models import Hint

    fake_claude.hint_value = Hint(meaning_ko="점심을 누구와 먹는지 물어요.", starters=["Yes, I…", "Not really,…"],
                                  full=full)
    rp = await talks.create()
    await talks.hint(rp.id, 0)
    await talks.show_full(rp.id, 0)
    return rp.id


@pytest.mark.parametrize("heard", [
    "Yes, I usually eat lunch with my friends.",  # a word swapped, as Sohee invites (「낱말을 바꿔 말해도 돼요」)
    "Not really, I usually eat alone.",  # the other opener, finished my own way
])
async def test_a_helped_turn_keeps_no_word_swapped_or_added(talks, engine, speech_bytes, fake_whisper, fake_claude,
                                                            heard):
    from je_server.compare import similarity
    from je_server.engine import NEAR_MIN

    # final review: these became 「coworkers가 friends처럼 들렸어요」 and 「yes가 not really처럼 들렸어요」
    full = "Yes, I usually eat lunch with my coworkers."
    rp_id = await full_on_opener(talks, fake_claude, full)
    assert similarity(full, heard) >= NEAR_MIN  # still said from it
    fake_whisper.text = heard
    await run(talks, rp_id, speech_bytes)
    saved = engine.load(rp_id)
    assert saved.lines[1].given == full and saved.attempts[1][0].issues == []
    # nothing heard wrong on it, so nothing to fix: Claude is not asked
    assert await talks.end(rp_id) == no_fixes(engine, 2) and fake_claude.fix_calls == []


async def test_a_helped_turn_keeps_a_word_that_sounds_close(talks, engine, speech_bytes, fake_whisper, fake_claude):
    from je_server.sounds import find

    full = "I turned right at the bank."
    rp_id = await full_on_opener(talks, fake_claude, full)
    fake_whisper.text = "I turned light at the bank."
    await run(talks, rp_id, speech_bytes)
    [issue] = engine.load(rp_id).attempts[1][0].issues
    assert (issue.target, issue.heard, issue.sound, issue.explain) == ("right", "light", ("R", "L"),
                                                                       find("R", "L").explain)


async def test_a_turn_after_claude_failed_is_still_said_from_the_full_sentence(talks, engine, speech_bytes,
                                                                             fake_whisper, fake_claude):
    # PR review: Ryan's reply failed, so my last turn is the record's last line; the app's 「소희 찬스」 stays on his
    # reply before it (`lastReply`), and a turn said from its full sentence then is still helped
    rp = await talks.create()
    fake_claude.talk_fail_after = 1
    fake_whisper.text = SAID[0]
    await run(talks, rp.id, speech_bytes)  # my turn (1), no Ryan line
    fake_claude.talk_fail_after = None
    hint = await talks.hint(rp.id, 0)
    await talks.show_full(rp.id, 0)
    fake_whisper.text = hint.full
    await run(talks, rp.id, speech_bytes)  # my turn (2), Ryan (3)
    saved = engine.load(rp.id)
    assert [l.kind for l in saved.lines] == ["reply", "turn", "turn", "reply"]
    assert saved.lines[1].given is None and saved.lines[2].given == hint.full


async def test_a_full_sentence_once_said_does_not_help_again_after_claude_failed(talks, engine, speech_bytes,
                                                                                fake_whisper, fake_claude):
    rp = await talks.create()
    hint = await talks.hint(rp.id, 0)
    await talks.show_full(rp.id, 0)
    fake_claude.talk_fail_after = 1
    fake_whisper.text = hint.full
    await run(talks, rp.id, speech_bytes)  # said from it (1), no Ryan line
    fake_claude.talk_fail_after = None
    await run(talks, rp.id, speech_bytes)  # the same words again (2): a turn of my own now
    saved = engine.load(rp.id)
    assert saved.lines[1].given == hint.full and saved.lines[2].given is None


async def test_a_korean_turn_after_the_full_sentence_is_never_helped(talks, engine, speech_bytes, fake_whisper):
    rp_id, full = await shown_full(talks, speech_bytes)
    fake_whisper.by_lang = {"en": f"{full} 맞아요?", "ko": "공원에 갔어요 맞아요?"}
    await run(talks, rp_id, speech_bytes)
    saved = engine.load(rp_id)
    assert saved.lines[3].kind == "ask" and saved.lines[3].given is None and saved.attempts[3][0].issues == []


def _helped(rp, idx: int, given: str, issues=()):
    """Marks my turn at `idx` as said from Sohee's `given` sentence, its try with the Mac's `issues`."""
    from je_server.models import Attempt

    line = rp.lines[idx]
    rp.lines[idx] = line.model_copy(update={"given": given})
    rp.attempts[idx] = [Attempt(n=1, mode="turn", heard=line.text, followed=True, issues=list(issues), say_ko="",
                                audio=[], timings={})]


def test_messages_tell_claude_the_turn_was_helped():
    from je_server.prompts import TALK_HELPED

    rp = _talk(("ryan", "reply", "Hi!"), ("user", "turn", "I want to the park."))
    _helped(rp, 1, "I went to the park.")
    assert messages(rp)[-1] == {"role": "user", "content": "I want to the park.\n" + TALK_HELPED}
    # a helped turn is still kind "turn": it counts for the echo, and the echo comes after the note
    three = _talk(("ryan", "reply", "Hi!"), ("user", "turn", "a b"), ("ryan", "reply", "x"), ("user", "turn", "c d"),
                  ("ryan", "reply", "y"), ("user", "turn", "I want to the park."))
    _helped(three, 5, "I went to the park.")
    msgs = messages(three)
    assert msgs[-1]["content"] == "I want to the park.\n" + TALK_HELPED + "\n" + TALK_ECHO
    assert msgs[2]["content"] == "a b"


def test_fix_input_keeps_helped_turns_apart():
    from je_server.fixes import Helped
    from je_server.models import Issue
    from je_server.talk import fix_input

    given = "I went to the park."
    issues = [Issue(target="went", heard="want")]
    rp = _talk(("ryan", "reply", "Hi!"), ("user", "turn", "I walked."), ("ryan", "reply", "Where?"),
               ("user", "turn", "I want to the park."), ("ryan", "reply", "Nice!"), ("user", "turn", given))
    _helped(rp, 3, given, issues)
    _helped(rp, 5, given)  # said from the sentence with nothing heard wrong: nothing to fix
    conversation, turns, helped = fix_input(rp)
    # Claude still reads the whole talk as it went, with what was heard
    assert [(c["차례"], c["말"]) for c in conversation] == [(l.idx, l.text) for l in rp.lines]
    assert turns == {1: "I walked."}
    assert helped == {3: Helped(given=given, heard="I want to the park.", issues=issues)}


def test_fix_input_marks_helped_turns_in_the_talk():
    from je_server.models import Issue
    from je_server.talk import fix_input

    given = "I went to the park."
    rp = _talk(("ryan", "reply", "Hi!"), ("user", "turn", "I walked."), ("ryan", "reply", "Where?"),
               ("user", "turn", "I want to the park."), ("ryan", "reply", "Nice!"), ("user", "turn", given))
    _helped(rp, 3, given, [Issue(target="went", heard="want")])
    _helped(rp, 5, given)  # heard as the sentence: still a helped turn, not one of my own to pick
    conversation, _, _ = fix_input(rp)
    # so Claude does not spend one of its own three picks on them (the Mac would drop it)
    assert [c["차례"] for c in conversation if c.get("도움 받은 차례") is True] == [3, 5]
    assert [c for c in conversation if c["차례"] == 1] == [{"차례": 1, "말한 사람": "학습자", "말": "I walked."}]


def test_helped_input_is_what_claude_is_given_for_the_helped_turns():
    from je_server.fixes import Helped
    from je_server.models import Issue
    from je_server.talk import helped_input

    issue = Issue(target="right", heard="light", sound=("R", "L"), explain="R 설명이에요.")
    helped = {7: Helped("I turned right.", "I turned light.", [issue]), 3: Helped("I went home.", "I want home.", [])}
    assert helped_input(helped) == [
        {"차례": 3, "알려 준 문장": "I went home.", "들린 말": "I want home.", "짚을 것": []},
        {"차례": 7, "알려 준 문장": "I turned right.", "들린 말": "I turned light.",
         "짚을 것": [{"대사 낱말": "right", "들린 낱말": "light", "소리 내는 법": "R 설명이에요."}]},
    ]


async def helped_talk(talks, fake_claude, fake_whisper, speech_bytes, own: bool) -> tuple[str, str, str]:
    """A talk with, when `own`, my own English turn (1, SAID[0]) and then a turn said from Sohee's full sentence (3 with
    `own`, else 1) with R heard as L. The talk, the sentence and what was heard."""
    from je_server.models import Hint

    full, heard = "I turned right at the bank.", "I turned light at the bank."
    fake_claude.hint_value = Hint(meaning_ko="어디서 돌았는지 물어요.", starters=["I turned…", "I went…"], full=full)
    rp = await talks.create()
    if own:
        fake_whisper.text = SAID[0]
        await run(talks, rp.id, speech_bytes)
    ryan = len(talks.engine.load(rp.id).lines) - 1  # his last reply: the opener, or his answer to my turn
    await talks.hint(rp.id, ryan)
    await talks.show_full(rp.id, ryan)
    fake_whisper.text = heard
    await run(talks, rp.id, speech_bytes)
    return rp.id, full, heard


async def test_end_fixes_a_helped_turn_last_with_the_macs_points(talks, engine, speech_bytes, fake_whisper,
                                                                  fake_claude):
    from je_server.sounds import find

    rp_id, full, heard = await helped_talk(talks, fake_claude, fake_whisper, speech_bytes, own=True)
    why = "right가 light처럼 들렸어요."
    fake_claude.fix_items = [{"idx": 3, "said": heard, "fixed": "I turned right at the big bank.", "why_ko": why,
                              "sound": dict(NO_SOUND)}, fix_item(0, 1)]
    body = await talks.end(rp_id)
    [sent] = fake_claude.fix_helped
    assert sent == [{"차례": 3, "알려 준 문장": full, "들린 말": heard,
                     "짚을 것": [{"대사 낱말": "right", "들린 낱말": "light", "소리 내는 법": find("R", "L").explain}]}]
    assert [c["차례"] for c in fake_claude.fix_calls[0]] == [0, 1, 2, 3, 4]  # the helped turn is in the talk
    added = engine.load(rp_id).lines[5:]
    # my own pick first, then the helped turn: its sentence is Sohee's, its words what was heard, its why the Mac's
    assert [(l.text, l.fix.of, l.fix.said, l.fix.why_ko) for l in added] == [
        (FIXED[0], 1, SAID[0], WHY[0]), (full, 3, heard, why + " " + find("R", "L").explain)]
    assert [it["rec"] for it in body["items"]] == [{"rp_id": rp_id, "idx": i, "n": 1} for i in (1, 3)]


async def test_end_with_only_a_helped_turn_still_asks_claude(talks, engine, speech_bytes, fake_whisper, fake_claude):
    from je_server.sounds import find

    rp_id, full, heard = await helped_talk(talks, fake_claude, fake_whisper, speech_bytes, own=False)
    fake_claude.fix_items = [{"idx": 1, "said": heard, "fixed": full, "why_ko": "right가 light처럼 들렸어요.",
                              "sound": dict(NO_SOUND)}]
    body = await talks.end(rp_id)
    assert len(fake_claude.fix_calls) == 1 and [h["차례"] for h in fake_claude.fix_helped[0]] == [1]
    [line] = [it["line"] for it in body["items"]]
    assert line["text"] == full and line["fix"]["why_ko"].endswith(find("R", "L").explain)


async def test_end_with_only_a_helped_turn_heard_right_has_nothing_to_fix(talks, engine, speech_bytes, fake_whisper,
                                                                         fake_claude):
    rp = await talks.create()
    hint = await talks.hint(rp.id, 0)
    await talks.show_full(rp.id, 0)
    fake_whisper.text = hint.full  # my only English turn, Sohee's sentence heard as it is
    await run(talks, rp.id, speech_bytes)
    assert engine.load(rp.id).lines[1].given == hint.full
    assert await talks.end(rp.id) == no_fixes(engine, 2) and fake_claude.fix_calls == []


# --- lines dropped by saying a turn again (spec talk-resay 3) ----------------------------------------------------

def _gone(rp, *idxs):
    for i in idxs:
        rp.lines[i] = rp.lines[i].model_copy(update={"dropped": True})
    return rp


def test_messages_leave_dropped_lines_out():
    rp = _gone(_talk(("ryan", "reply", "R0"), ("user", "turn", "T1"), ("ryan", "reply", "R2"), ("user", "turn", "T3")),
               1, 2)
    assert [m["content"] for m in messages(rp)] == [TALK_START, "R0", "T3"]


def test_dropped_turns_do_not_count_for_the_echo():
    rp = _turns(3)
    assert TALK_ECHO in messages(rp)[-1]["content"]
    turn_idxs = [l.idx for l in rp.lines if l.kind == "turn"]
    # one of the three dropped (with its reply): two left, no echo
    assert TALK_ECHO not in repr(messages(_gone(_turns(3), turn_idxs[0], turn_idxs[0] + 1)))
    # four turns, one dropped: three live, so the echo is on the last one
    four = _gone(_turns(4), 1, 2)
    assert messages(four)[-1]["content"].endswith(TALK_ECHO)


def test_fix_input_leaves_dropped_lines_out():
    from je_server.talk import fix_input
    rp = _gone(_talk(("ryan", "reply", "Hi!"), ("user", "turn", "I go park."), ("ryan", "reply", "Fun!"),
                     ("user", "turn", "I went to the park.")), 1, 2)
    conversation, turns, helped = fix_input(rp)
    assert [c["말"] for c in conversation] == ["Hi!", "I went to the park."] and turns == {3: "I went to the park."}


def _helped_talk(*, drop_helped: bool):
    """Ryan's reply 0 with Sohee's full sentence shown, my turn 1 said from it, Ryan's reply 2, and then my turn."""
    from je_server.models import Hint
    rp = _talk(("ryan", "reply", "Where?"), ("user", "turn", "I turned light at the bank."), ("ryan", "reply", "Ok."))
    rp.lines[0] = rp.lines[0].model_copy(update={
        "hint": Hint(meaning_ko="어디서 돌았는지 물어요.", starters=["I turned…", "I went…"],
                     full="I turned right at the bank.", full_shown=True)})
    rp.lines[1] = rp.lines[1].model_copy(update={"given": "I turned right at the bank."})
    return _gone(rp, 1, 2) if drop_helped else rp


def test_a_dropped_helped_turn_lets_the_next_turn_be_helped():
    from je_server.talk import _from_full
    heard = "I turned light at the bank."
    assert _from_full(_helped_talk(drop_helped=False), heard) == (None, False, [])  # that turn was already helped
    # dropped: the reply 0 is his latest live reply and the turn said again is compared to its sentence too
    full, followed, issues = _from_full(_helped_talk(drop_helped=True), heard)
    assert full == "I turned right at the bank." and followed and issues
    # his latest reply is found past a dropped reply
    rp = _helped_talk(drop_helped=True)
    rp.lines[0] = rp.lines[0].model_copy(update={"hint": None})
    assert _from_full(rp, heard) == (None, False, [])


async def _stored(talks, *lines):
    rp = _talk(*lines)
    talks.engine.store.save(rp)
    return rp


async def test_cut_mark_goes_on_the_last_live_reply(talks, engine):
    from je_server.models import Said
    parts = [Said(text="Oh, nice!", audio="a" * 64), Said(text="Who went?", audio="b" * 64)]
    for how in ("turn", "end"):
        rp = _talk(("ryan", "reply", "Hi!"), ("user", "turn", "I go."), ("ryan", "reply", "Nice! Who?"),
                   ("user", "turn", "Me."), ("ryan", "reply", "Fun."))
        rp.lines[2] = rp.lines[2].model_copy(update={"parts": parts})
        engine.store.save(_gone(rp, 3, 4))
        if how == "turn":
            await talks._mark_heard(engine.load(rp.id), 1)
        else:
            await talks.end(rp.id, heard=1)
        assert engine.load(rp.id).lines[2].heard_upto == 1
        assert engine.load(rp.id).lines[4].heard_upto is None


async def test_end_counts_no_sohee_chance_on_a_dropped_reply(talks, engine):
    from je_server.models import Hint
    rp = _talk(("ryan", "reply", "Hi!"), ("user", "turn", "I go."), ("ryan", "reply", "Nice!"))
    hint = Hint(meaning_ko="좋다고 해요.", starters=["Yes, I…", "Not really,…"], full="Yes, I do.", full_shown=True)
    rp.lines[0] = rp.lines[0].model_copy(update={"hint": hint})
    rp.lines[2] = rp.lines[2].model_copy(update={"hint": hint})
    assert talks._end_body(rp, [])["sohee"] == 4
    assert talks._end_body(_gone(rp, 1, 2), [])["sohee"] == 2


# --- dropping my last turn to say it again (spec talk-resay 3, 4) ------------------------------------------------

def _dropped(engine, rp_id) -> list[bool]:
    return [l.dropped for l in engine.load(rp_id).lines]


def _held_sound(fake_voice, text: str) -> asyncio.Event:
    """Holds the making of `text`'s sound until the event is set (Ryan's sounds still coming)."""
    gate = asyncio.Event()
    say = fake_voice.say

    async def held(t, voice, lang, urgent, rank=0, check=False):
        if t == text:
            await gate.wait()
        return await say(t, voice, lang, urgent, rank, check)

    fake_voice.say = held
    return gate


async def test_drop_marks_my_turn_and_ryans_reply(talks, engine, speech_bytes):
    rp_id = await replied(talks, speech_bytes)
    before = engine.load(rp_id).lines
    await talks.drop(rp_id, 1)
    after = engine.load(rp_id).lines
    assert [l.dropped for l in after] == [False, True, True]
    # kept with their numbers and words (spec 3 「기록」)
    assert [l.model_copy(update={"dropped": False}) for l in after] == before
    await talks.drop(rp_id, 1)  # sent again: the same
    assert engine.load(rp_id).lines == after


async def test_drop_a_korean_turn_or_one_ryan_could_not_answer(talks, engine, speech_bytes, fake_whisper,
                                                                fake_claude):
    fake_whisper.by_lang = {"en": "I am 피곤해 today", "ko": "오늘 피곤해요"}
    rp_id = await replied(talks, speech_bytes)
    assert engine.load(rp_id).lines[1].kind == "ask"
    await talks.drop(rp_id, 1)
    assert _dropped(engine, rp_id) == [False, True, True]
    fake_whisper.by_lang = {}
    fake_claude.talk_fail_after = 0
    rp = await talks.create()
    await run(talks, rp.id, speech_bytes)  # Claude could not answer: my line only
    await talks.drop(rp.id, 1)
    assert _dropped(engine, rp.id) == [False, True]


async def test_drop_refuses_what_is_not_my_last_turn(talks, engine, speech_bytes):
    from je_server.talk import CannotDrop
    roleplay = await engine.create("길 묻기")
    mine = next(l.idx for l in roleplay.lines if l.speaker == "user")
    for rp_id, idx in ((roleplay.id, mine), ("000000000000", 1)):
        with pytest.raises(NotFound):
            await talks.drop(rp_id, idx)
    rp_id = await replied(talks, speech_bytes)
    await run(talks, rp_id, speech_bytes)  # my turns at 1 and 3, Ryan's lines at 0, 2, 4
    for idx in (0, 2, 4, 5, 99):
        with pytest.raises(NotFound):
            await talks.drop(rp_id, idx)
    with pytest.raises(CannotDrop) as e:
        await talks.drop(rp_id, 1)
    assert e.value.code == "not_last"
    assert not any(_dropped(engine, rp_id))
    await talks.drop(rp_id, 3)
    assert _dropped(engine, rp_id) == [False, False, False, True, True]


async def test_drop_refuses_after_sohee_chance_on_the_reply(talks, engine, speech_bytes, fake_claude):
    from je_server.talk import CannotDrop
    # Sohee chance on Ryan's line before my turn does not count (spec 4)
    rp_id = await replied(talks, speech_bytes)
    await talks.hint(rp_id, 0)
    await talks.drop(rp_id, 1)
    assert _dropped(engine, rp_id) == [False, True, True]
    # on his reply to my turn it does, from the press on: while the hint is made and once it is kept
    rp_id = await replied(talks, speech_bytes)
    fake_claude.hint_gate = asyncio.Event()
    making = asyncio.create_task(talks.hint(rp_id, 2))
    await until(lambda: len(fake_claude.hint_calls) == 2)
    with pytest.raises(CannotDrop) as e:
        await talks.drop(rp_id, 1)
    assert e.value.code == "hinted"
    fake_claude.hint_gate.set()
    await making
    await until(lambda: not talks.hinting)
    with pytest.raises(CannotDrop) as e:
        await talks.drop(rp_id, 1)
    assert e.value.code == "hinted"
    assert not any(_dropped(engine, rp_id))


async def test_drop_refuses_an_ended_or_ending_talk(talks, engine, speech_bytes, fake_whisper, fake_claude):
    rp_id = await talked(talks, fake_whisper, speech_bytes, SAID[:1])
    fake_claude.fix_items = [fix_item(0, 1)]
    fake_claude.fix_gate = asyncio.Event()
    ending = asyncio.create_task(talks.end(rp_id))
    await until(lambda: fake_claude.fix_calls)
    with pytest.raises(TalkBusy):
        await talks.drop(rp_id, 1)
    fake_claude.fix_gate.set()
    await ending
    with pytest.raises(TalkEnded):
        await talks.drop(rp_id, 1)
    assert not any(_dropped(engine, rp_id))


async def test_drop_while_claude_writes_stops_it_and_keeps_no_reply(talks, engine, speech_bytes, fake_claude):
    rp = await talks.create()
    fake_claude.talk_gate = asyncio.Event()  # never set: Claude has not written a word
    turn = asyncio.create_task(run(talks, rp.id, speech_bytes))
    await until(lambda: fake_claude.talk_calls)
    assert talks.running[rp.id].idx == 1 and rp.id in talks.turning
    await talks.drop(rp.id, 1)
    ev = await asyncio.wait_for(turn, 2)
    assert [e["type"] for e in ev] == ["heard"]  # no reply, no done
    await until(lambda: fake_claude.talk_closed)  # Claude's stream was closed, not left to write
    lines = engine.load(rp.id).lines
    assert [(l.idx, l.speaker, l.dropped) for l in lines] == [(0, "ryan", False), (1, "user", True)]
    assert talks.turning == set() and talks.running == {}


async def test_drop_after_the_reply_is_saved_demotes_its_sounds(talks, engine, speech_bytes, fake_voice):
    rp = await talks.create()
    gate = _held_sound(fake_voice, REPLY[1])
    events = talks.turn(rp.id, speech_bytes, None)
    try:
        kinds = []
        async for ev in events:
            kinds.append(ev["type"])
            if ev["type"] == "audio":
                break
        assert "reply" in kinds and kinds.count("audio") == 1  # the second sentence's sound is being made
        await talks.drop(rp.id, 1)
        # the sounds not made yet wait behind the next reply's (spec 3 「만들던 답 버리기」)
        assert {fake_voice.key("ryan", "english", s) for s in REPLY[1:]} <= set(fake_voice.demoted)
        assert [e async for e in events] == []  # no more sounds, no done
    finally:
        gate.set()
    assert _dropped(engine, rp.id) == [False, True, True]
    assert talks.turning == set() and talks.running == {}


async def test_drop_before_the_reply_is_saved_demotes_the_sentences_written(talks, engine, speech_bytes,
                                                                             fake_claude, fake_voice):
    rp = await talks.create()
    gate = _held_sound(fake_voice, REPLY[0])
    fake_claude.talk_gate = asyncio.Event()
    turn = asyncio.create_task(run(talks, rp.id, speech_bytes))
    await until(lambda: fake_claude.talk_calls)
    lock = engine.lock(rp.id)
    await lock.acquire()
    try:
        dropping = asyncio.create_task(talks.drop(rp.id, 1))
        await asyncio.sleep(0.01)  # the drop waits first
        fake_claude.talk_gate.set()
        await asyncio.sleep(0.01)  # Claude's whole text is written; its save waits behind the drop
    finally:
        lock.release()
    await dropping
    try:
        ev = await asyncio.wait_for(turn, 2)
    finally:
        gate.set()
    assert not {"reply", "audio", "done"} & {e["type"] for e in ev}
    assert _dropped(engine, rp.id) == [False, True]  # no Ryan line, so only the turn knows the sentences written
    assert {fake_voice.key("ryan", "english", s) for s in REPLY} <= set(fake_voice.demoted)


async def test_drop_and_reply_save_in_either_order_keep_line_numbers(talks, engine, speech_bytes, fake_claude,
                                                                      fake_voice):
    for drop_first in (True, False):
        rp = await talks.create()
        fake_claude.talk_gate = asyncio.Event()
        turn = asyncio.create_task(run(talks, rp.id, speech_bytes))
        await until(lambda: len(fake_claude.talk_calls) == (1 if drop_first else 2))
        voiced = len(fake_voice.calls)
        lock = engine.lock(rp.id)
        await lock.acquire()  # the drop and the reply's save wait for it, in the order they come
        try:
            if drop_first:
                dropping = asyncio.create_task(talks.drop(rp.id, 1))
                await asyncio.sleep(0.01)
                fake_claude.talk_gate.set()
            else:
                fake_claude.talk_gate.set()
                # the reply's sentences are being voiced, so its whole text is waiting to be saved
                await until(lambda: len(fake_voice.calls) > voiced)
                dropping = asyncio.create_task(talks.drop(rp.id, 1))
                await asyncio.sleep(0.01)
        finally:
            lock.release()
        await dropping
        await asyncio.wait_for(turn, 2)
        lines = engine.load(rp.id).lines
        assert [l.idx for l in lines] == list(range(len(lines)))
        assert [l.dropped for l in lines] == ([False, True] if drop_first else [False, True, True]), drop_first
        assert talks.turning == set() and talks.running == {}


async def test_a_turn_right_after_a_drop_is_taken(talks, engine, speech_bytes, fake_whisper, fake_claude,
                                                  fake_voice):
    rp = await talks.create()
    gate = _held_sound(fake_voice, REPLY[1])
    old = talks.turn(rp.id, speech_bytes, None)
    try:
        async for ev in old:
            if ev["type"] == "audio":
                break
        await talks.drop(rp.id, 1)
        # the turn said again, before the dropped one has ended
        fake_whisper.text = "I went to the park."
        fake_claude.talk_pieces = ["Oh, nice! ", "Did you rest?"]
        ev = await run(talks, rp.id, speech_bytes)
        assert ev[0]["idx"] == 3 and ev[-1] == {"type": "done", "idx": 4}  # 1 and 2 are not used again
        assert [m["content"] for m in fake_claude.talk_calls[-1]] == [TALK_START, TALK_OPENERS[0],
                                                                      "I went to the park."]
        assert [e async for e in old] == []
    finally:
        gate.set()
    lines = engine.load(rp.id).lines
    assert [l.idx for l in lines] == [0, 1, 2, 3, 4]
    assert [l.dropped for l in lines] == [False, True, True, False, False]


async def test_a_dropped_turn_ending_late_does_not_free_the_next(talks, engine, speech_bytes, fake_whisper,
                                                                 fake_claude):
    rp = await talks.create()
    old = talks.turn(rp.id, speech_bytes, None)
    assert (await anext(old))["type"] == "heard"  # it has not ended
    await talks.drop(rp.id, 1)
    assert talks.check_open(rp.id).id == rp.id  # free at once
    fake_claude.talk_gate = asyncio.Event()
    fake_whisper.text = "I went to the park."
    new = asyncio.create_task(run(talks, rp.id, speech_bytes))
    await until(lambda: fake_claude.talk_calls)
    assert [e async for e in old] == []  # it ends now, without asking Claude: it was dropped before
    with pytest.raises(TalkBusy):
        talks.check_open(rp.id)  # still the new turn's
    assert talks.running[rp.id].idx == 2
    fake_claude.talk_gate.set()
    assert (await new)[-1] == {"type": "done", "idx": 3}
    assert len(fake_claude.talk_calls) == 1
    assert [l.dropped for l in engine.load(rp.id).lines] == [False, True, False, False]
    assert talks.turning == set() and talks.running == {}


async def test_drop_log_has_counts_only(talks, speech_bytes, fake_whisper, fake_claude, caplog):
    caplog.set_level(logging.INFO, logger="je_server")
    rp_id = await replied(talks, speech_bytes)
    await talks.drop(rp_id, 1)
    assert f"talk drop {rp_id}/1 lines=2 running=False" in caplog.text
    rp = await talks.create()
    fake_claude.talk_gate = asyncio.Event()
    turn = asyncio.create_task(run(talks, rp.id, speech_bytes))
    await until(lambda: len(fake_claude.talk_calls) == 2)
    await talks.drop(rp.id, 1)
    await turn
    assert f"talk drop {rp.id}/1 lines=1 running=True" in caplog.text
    assert fake_whisper.text not in caplog.text and not [s for s in REPLY if s in caplog.text]
