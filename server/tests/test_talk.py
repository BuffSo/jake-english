"""Free talk: the first question in turn, what Claude is given, and a turn (spec free-talk-design 2, 3, 4)."""
import asyncio
import logging
import re

import pytest
from fakes import talk_example

from je_server.claude import ClaudeUnavailable
from je_server.engine import NotFound
from je_server.models import Said
from je_server.phrases import PHRASES, TALK_ENGLISH, TALK_OPENERS
from je_server.prompts import TALK_CUT, TALK_CUT_SILENT, TALK_START
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
    assert (TALK_ENGLISH, "ryan", "english", False) in fake_voice.calls
    assert (TALK_ENGLISH, "ryan", "korean", False) not in fake_voice.calls


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
    help_ = engine.talk_english()
    assert ev[1] == {"type": "text", "delta": TALK_ENGLISH}
    assert ev[2] == {"type": "reply", "idx": 2, "kind": "help", "parts": [help_.model_dump()]}
    assert ev[3] == {"type": "audio", "key": help_.audio} and ev[4] == {"type": "done", "idx": 2}
    saved = engine.load(rp.id)
    assert (saved.lines[1].kind, saved.lines[1].text) == ("ask", "오늘 피곤해요")
    ryan = saved.lines[2]
    assert (ryan.speaker, ryan.kind, ryan.text) == ("ryan", "help", TALK_ENGLISH)
    assert ryan.audio == help_.audio and ryan.parts == [help_]
    assert fake_claude.talk_calls == []


async def test_korean_transcription_failing_still_gets_ryans_english_line(talks, engine, speech_bytes, fake_whisper):
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


def no_fixes(engine) -> dict:
    return {"items": [], "say": engine.said("talk_no_fixes").model_dump()}


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


async def test_end_sends_english_turns_and_ryans_replies_only(talks, speech_bytes, fake_whisper, fake_claude):
    rp = await talks.create()
    fake_whisper.by_lang = {"en": "I am 피곤해 today", "ko": "오늘 피곤해요"}
    await run(talks, rp.id, speech_bytes)  # my Korean turn (1) and Ryan's English help line (2)
    fake_whisper.by_lang = {}
    fake_whisper.text = SAID[0]
    await run(talks, rp.id, speech_bytes)  # my English turn (3) and Ryan's reply (4)
    await talks.end(rp.id)
    [sent] = fake_claude.fix_calls
    assert [(c["차례"], c["말한 사람"]) for c in sent] == [(0, "라이언"), (3, "학습자"), (4, "라이언")]
    assert not [c for c in sent if HANGUL.search(c["말"])]
    assert [c["말"] for c in sent] == [rp.lines[0].text, SAID[0], " ".join(REPLY)]


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
