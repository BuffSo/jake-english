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


def test_messages_allow_echo_on_every_second_english_turn():
    one = _talk(("ryan", "reply", "Hi!"), ("user", "turn", "I go park."))
    assert messages(one)[-1]["content"] == "I go park."
    two = _talk(("ryan", "reply", "Hi!"), ("user", "turn", "I go park."), ("ryan", "reply", "Fun!"),
                ("user", "turn", "My dog like it."))
    msgs = messages(two)
    assert msgs[-1]["content"] == "My dog like it.\n" + TALK_ECHO
    assert TALK_ECHO not in repr(msgs[:-1])
    three = _talk(("ryan", "reply", "Hi!"), ("user", "turn", "a"), ("ryan", "reply", "b"), ("user", "turn", "c"),
                  ("ryan", "reply", "d"), ("user", "turn", "e"))
    assert TALK_ECHO not in messages(three)[-1]["content"]


def test_fix_input_still_skips_old_help_lines_and_korean_turns():
    from je_server.talk import fix_input
    rp = _talk(("ryan", "reply", "Hi!"), ("user", "ask", "안녕"), ("ryan", "help", "Try English."),
               ("user", "turn", "I walked."))
    conversation, turns, helped = fix_input(rp)
    assert [c["말"] for c in conversation] == ["Hi!", "I walked."] and turns == {3: "I walked."} and helped == {}


def test_korean_turns_do_not_count_for_the_echo_and_carry_none():
    rp = _talk(("ryan", "reply", "Hi!"), ("user", "turn", "a b"), ("ryan", "reply", "x"), ("user", "ask", "뭐요?"),
               ("ryan", "reply", "y"), ("user", "turn", "c d"))
    assert messages(rp)[-1]["content"] == "c d\n" + TALK_ECHO  # my 2nd English turn
    rp = _talk(("ryan", "reply", "Hi!"), ("user", "turn", "a b"), ("ryan", "reply", "x"), ("user", "turn", "c d"),
               ("ryan", "reply", "y"), ("user", "ask", "뭐요?"))
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
    assert msgs[2]["content"] == ("I walked to the park with my dog.\nYesterday I go to the market and buy two apple."
                                  "\n" + TALK_ECHO)  # my 2nd English turn


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
    assert sent[-1]["content"] == first + "\n" + "I went to the park." + "\n" + TALK_ECHO  # my 2nd English turn


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
    rp = await talks.create()
    await run(talks, rp.id, speech_bytes)
    assert f"talk {rp.id}/1 n=1 korean=False " in caplog.text
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


@pytest.mark.parametrize("heard", [
    "I want to the park with my dog.",  # followed (0.88), one word heard wrong
    "We went to a big park.",  # near (0.43): a try at it that came out wrong
    "I went to the park with my dog.",  # the sentence itself, nothing heard wrong
])
async def test_turn_after_the_full_sentence_is_compared_with_it(talks, engine, speech_bytes, fake_whisper,
                                                                fake_claude, heard):
    from je_server.compare import FOLLOW_MIN, find_issues, similarity
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
    assert attempt.issues == find_issues(full, heard, 2)
    assert attempt.followed == (similarity(full, heard) >= FOLLOW_MIN)
    # Claude is told the turn was helped; it is still my 2nd English turn for the echo
    assert fake_claude.talk_calls[-1][-1]["content"] == heard + "\n" + TALK_HELPED + "\n" + TALK_ECHO


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
    two = _talk(("ryan", "reply", "Hi!"), ("user", "turn", "a b"), ("ryan", "reply", "x"),
                ("user", "turn", "I want to the park."))
    _helped(two, 3, "I went to the park.")
    msgs = messages(two)
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
