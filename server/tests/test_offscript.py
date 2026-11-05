import pytest

from je_server import sounds
from je_server.models import Offscript

pytestmark = pytest.mark.anyio


async def run(engine, rp_id, idx, body, mode="turn"):
    return [e async for e in engine.attempt(rp_id, idx, body, mode)]


async def test_offscript_reply_then_new_script(engine_with_rp, speech_bytes, fake_whisper, fake_voice):
    engine, rp_id, user_idx = engine_with_rp
    fake_whisper.text = "Sorry, I don't know this area."
    ev = await run(engine, rp_id, user_idx, speech_bytes)
    assert ev[0] == {"type": "heard", "text": "Sorry, I don't know this area.", "followed": False}
    reply = next(e for e in ev if e["type"] == "reply")["line"]
    assert reply["speaker"] == "ryan" and reply["kind"] == "reply" and reply["idx"] == user_idx + 1
    assert ("Oh, no worries. Thanks anyway!", "ryan", "english", True) in fake_voice.calls
    assert ev[-1] == {"type": "done", "next": user_idx + 2, "issues": 0}
    nxt = await engine.line(rp_id, user_idx + 2)  # waits for the rebuilt script
    assert nxt.speaker == "user" and nxt.three is not None and nxt.audio is not None
    rp = engine.store.load(rp_id)
    assert rp.lines[user_idx].text == "It's right over there."  # past lines stay as they were
    assert sum(1 for l in rp.lines[user_idx + 2:] if l.speaker == "user") == 3  # 4 user lines, 1 used
    assert [l.idx for l in rp.lines] == list(range(len(rp.lines))) and len(rp.lines) == user_idx + 2 + 2 * 3
    assert rp.lines[-1].speaker == "ryan"


async def test_offscript_point_comes_before_reply(engine_with_rp, speech_bytes, fake_whisper):
    engine, rp_id, user_idx = engine_with_rp
    fake_whisper.text = "Sorry, I don't know this area."
    kinds = [e["type"] for e in await run(engine, rp_id, user_idx, speech_bytes)]
    assert kinds.index("text") < kinds.index("reply")


async def test_offscript_history_uses_what_was_said(engine_with_rp, speech_bytes, fake_whisper, fake_claude):
    engine, rp_id, user_idx = engine_with_rp
    fake_whisper.text = "Sorry, I don't know this area."
    await run(engine, rp_id, user_idx, speech_bytes)
    sent = fake_claude.offscript_calls[0]
    assert sent["expected"] == "It's right over there." and sent["heard"] == "Sorry, I don't know this area."
    assert sent["history"][-1][0] == "ryan"


async def test_pronunciation_guess_needs_listed_sound(engine_with_rp, speech_bytes, fake_whisper, fake_claude):
    engine, rp_id, user_idx = engine_with_rp
    fake_whisper.text = "Sorry, I don't know this area."
    fake_claude.offscript_out = Offscript(point_kind="pronunciation", point_ko="", meant="bed", heard_word="red",
                                          reply_en="OK.")
    ev = await run(engine, rp_id, user_idx, speech_bytes)
    assert not any(e["type"] == "text" for e in ev) and ev[-1]["issues"] == 0


async def test_pronunciation_guess_uses_list_explanation(engine_with_rp, speech_bytes, fake_whisper, fake_claude):
    engine, rp_id, user_idx = engine_with_rp
    fake_whisper.text = "Sorry, I'm learning to the station."
    fake_claude.offscript_out = Offscript(point_kind="pronunciation", point_ko="지어낸 설명", meant="running",
                                          heard_word="learning", reply_en="Oh, you're running late?")
    ev = await run(engine, rp_id, user_idx, speech_bytes)
    said = "".join(e["delta"] for e in ev if e["type"] == "text")
    assert sounds.find("R", "L").explain in said and "지어낸 설명" not in said
    assert ev[-1]["issues"] == 1


async def test_retry_mode_never_changes_script(engine_with_rp, speech_bytes, fake_whisper, fake_claude):
    engine, rp_id, user_idx = engine_with_rp
    fake_whisper.text = "Something totally different here."
    before = engine.store.load(rp_id).lines
    ev = await run(engine, rp_id, user_idx, speech_bytes, "retry")
    assert ev[-1]["next"] == user_idx and engine.store.load(rp_id).lines == before
    assert fake_claude.offscript_calls == []


async def test_continue_failure_closes_the_roleplay(engine_with_rp, speech_bytes, fake_whisper, fake_claude):
    engine, rp_id, user_idx = engine_with_rp
    fake_whisper.text = "Sorry, I don't know this area."
    fake_claude.fail_continue = True
    await run(engine, rp_id, user_idx, speech_bytes)
    last = await engine.line(rp_id, user_idx + 2)
    assert last.speaker == "ryan" and len(engine.store.load(rp_id).lines) == user_idx + 3


async def test_offscript_on_last_user_line_needs_no_new_script(engine_with_rp, speech_bytes, fake_whisper,
                                                                fake_claude):
    engine, rp_id, _ = engine_with_rp
    rp = engine.store.load(rp_id)
    last_user = max(l.idx for l in rp.lines if l.speaker == "user")
    await engine.line(rp_id, last_user)
    fake_whisper.text = "Sorry, I don't know this area."
    ev = await run(engine, rp_id, last_user, speech_bytes)
    assert ev[-1]["next"] == last_user + 2 == len(engine.store.load(rp_id).lines)
    assert not any(c[0] == "continue_script" for c in fake_claude.calls)


async def test_claude_down_on_offscript_keeps_script(engine_with_rp, speech_bytes, fake_whisper, fake_claude):
    engine, rp_id, user_idx = engine_with_rp
    fake_whisper.text = "Sorry, I don't know this area."
    before = engine.store.load(rp_id).lines
    fake_claude.fail_next = True
    ev = await run(engine, rp_id, user_idx, speech_bytes)
    assert ev[-1]["code"] == "claude_unavailable" and engine.store.load(rp_id).lines == before
