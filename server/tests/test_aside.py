"""A recording that does not follow the line: teacher Ryan answers in Korean and the line stays
(spec offscript-aside)."""
import pytest

pytestmark = pytest.mark.anyio


async def run(engine, rp_id, idx, body, mode="turn"):
    return [e async for e in engine.attempt(rp_id, idx, body, mode)]


def said(ev) -> str:
    return "".join(e["delta"] for e in ev if e["type"] == "text")


async def test_aside_answers_in_korean_and_keeps_the_line(engine_with_rp, speech_bytes, fake_whisper, fake_claude):
    engine, rp_id, user_idx = engine_with_rp
    fake_whisper.text = "Wait, let me try that again."
    before = [l.text for l in engine.store.load(rp_id).lines]
    ev = await run(engine, rp_id, user_idx, speech_bytes)
    assert ev[0] == {"type": "heard", "text": "Wait, let me try that again.", "followed": False, "n": 1}
    assert said(ev) == "괜찮아요, 말이 꼬일 수 있어요. 다시 해 볼까요?"
    assert not any(e["type"] == "reply" for e in ev) and ev[-1]["type"] == "done" and ev[-1]["next"] == user_idx
    rp = engine.store.load(rp_id)
    assert [l.text for l in rp.lines] == before and rp.pos == 0 and rp.attempts[user_idx][-1].aside is True
    assert fake_whisper.langs == ["en", "auto"] and fake_claude.feedback_calls == []


@pytest.mark.parametrize("mode", ["retry", "practice"])
async def test_aside_in_every_mode(engine_with_rp, speech_bytes, fake_whisper, fake_claude, mode):
    engine, rp_id, user_idx = engine_with_rp
    fake_whisper.text = "What does this mean?"
    ev = await run(engine, rp_id, user_idx, speech_bytes, mode)
    assert fake_claude.aside_calls and ev[-1]["next"] == user_idx


async def test_aside_in_shadow_uses_ryans_line(engine_with_rp, speech_bytes, fake_whisper, fake_claude):
    engine, rp_id, _ = engine_with_rp
    await engine.line(rp_id, 0)
    fake_whisper.text = "What does this mean?"
    await run(engine, rp_id, 0, speech_bytes, "shadow")
    assert fake_claude.aside_calls[-1]["line"] == engine.store.load(rp_id).lines[0].text


async def test_korean_heard_replaces_the_english_transcript(engine_with_rp, speech_bytes, fake_whisper, fake_claude):
    engine, rp_id, user_idx = engine_with_rp
    fake_whisper.text = "What does this mean?"  # whisper translated the Korean
    fake_whisper.auto_text, fake_whisper.auto_lang = "이게 무슨 뜻이에요?", "korean"
    ev = await run(engine, rp_id, user_idx, speech_bytes)
    assert ev[0]["text"] == "이게 무슨 뜻이에요?"
    sent = fake_claude.aside_calls[-1]
    assert sent["heard"] == "What does this mean?" and sent["heard_ko"] == "이게 무슨 뜻이에요?"
    assert engine.store.load(rp_id).attempts[user_idx][-1].heard == "이게 무슨 뜻이에요?"


async def test_korean_only_hangul_is_not_no_speech(engine_with_rp, speech_bytes, fake_whisper, fake_claude):
    engine, rp_id, user_idx = engine_with_rp
    fake_whisper.text = "다시 할게요"  # forced English left the Hangul as it was
    fake_whisper.auto_text, fake_whisper.auto_lang = "다시 할게요", "korean"
    ev = await run(engine, rp_id, user_idx, speech_bytes)
    assert ev[0]["text"] == "다시 할게요" and ev[-1]["type"] == "done"


async def test_korean_heard_sends_no_issues(engine_with_rp, speech_bytes, fake_whisper, fake_claude):
    engine, rp_id, user_idx = engine_with_rp
    fake_whisper.text = "What does it mean?"  # far from the line: not a try at it
    fake_whisper.auto_text, fake_whisper.auto_lang = "그게 무슨 뜻이에요?", "korean"
    await run(engine, rp_id, user_idx, speech_bytes)
    assert fake_claude.aside_calls[-1]["issues"] == []


async def test_line_then_korean_is_an_aside(engine_with_rp, speech_bytes, fake_whisper, fake_claude):
    # phone test 2026-11-08: the learner began the line, then talked to themself in Korean. Forced to
    # English, whisper translated the Korean, the text came out 0.38 like the line, and Ryan pointed at the
    # translation as words "heard differently". A recording that does not follow the line is always transcribed
    # again; Korean makes it an aside.
    engine, rp_id, user_idx = engine_with_rp
    fake_whisper.text = "It's right... wait, the store is closed."  # 0.36 against the line
    fake_whisper.auto_text, fake_whisper.auto_lang = "잇츠 라잇... 아 그 가게 닫았나", "korean"
    ev = await run(engine, rp_id, user_idx, speech_bytes)
    assert fake_whisper.langs == ["en", "auto"] and ev[0]["text"] == "잇츠 라잇... 아 그 가게 닫았나"
    assert fake_claude.aside_calls[-1]["issues"] == [] and ev[-1] == {"type": "done", "next": user_idx, "issues": 0}
    assert engine.store.load(rp_id).attempts[user_idx][-1].aside is True


async def test_far_english_sends_no_points(engine_with_rp, speech_bytes, fake_whisper, fake_claude):
    engine, rp_id, user_idx = engine_with_rp
    fake_whisper.text = "Can I get a latte instead?"
    await run(engine, rp_id, user_idx, speech_bytes)
    assert fake_claude.aside_calls[-1]["issues"] == []


async def test_near_miss_sends_the_macs_points(engine_with_rp, speech_bytes, fake_whisper, fake_claude):
    # the line is "It's right over there."; two words heard differently fall below FOLLOW_MIN
    engine, rp_id, user_idx = engine_with_rp
    fake_whisper.text = "It's light over hair."
    ev = await run(engine, rp_id, user_idx, speech_bytes)
    assert ev[0]["followed"] is False
    issues = fake_claude.aside_calls[-1]["issues"]
    assert [(i["target"], i["heard"]) for i in issues] == [("right", "light"), ("there", "hair")]
    assert set(issues[0]["sound"]) == {"R", "L"} and issues[0]["explain"]
    assert ev[-1]["issues"] == 2 and fake_whisper.langs == ["en", "auto"]  # English, so a try at the line


async def test_auto_language_not_korean_keeps_english(engine_with_rp, speech_bytes, fake_whisper, fake_claude):
    engine, rp_id, user_idx = engine_with_rp
    fake_whisper.text = "Can I get a latte instead?"
    fake_whisper.auto_text, fake_whisper.auto_lang = "Can I get a latte instead?", "english"
    ev = await run(engine, rp_id, user_idx, speech_bytes)
    assert ev[0]["text"] == "Can I get a latte instead?" and fake_claude.aside_calls[-1]["heard_ko"] is None


async def test_earlier_asides_on_the_line_go_to_claude(engine_with_rp, speech_bytes, fake_whisper, fake_claude):
    engine, rp_id, user_idx = engine_with_rp
    fake_whisper.text = "Wait, let me try that again."
    for _ in range(4):
        await run(engine, rp_id, user_idx, speech_bytes)
    earlier = fake_claude.aside_calls[-1]["earlier"]
    assert len(earlier) == 3 and earlier[-1] == ("Wait, let me try that again.",
                                                  "괜찮아요, 말이 꼬일 수 있어요. 다시 해 볼까요?")


async def test_aside_claude_down_says_the_fixed_phrase(engine_with_rp, speech_bytes, fake_whisper, fake_claude):
    engine, rp_id, user_idx = engine_with_rp
    fake_whisper.text = "Wait, let me try that again."
    fake_claude.aside_fail_after = 0
    ev = await run(engine, rp_id, user_idx, speech_bytes)
    assert said(ev) == engine.said("retry_offscript").text
    assert not any(e["type"] == "error" for e in ev) and ev[-1]["type"] == "done"


async def test_aside_claude_cut_midway_ends_with_fixed_phrase(engine_with_rp, speech_bytes, fake_whisper,
                                                             fake_claude):
    engine, rp_id, user_idx = engine_with_rp
    fake_whisper.text = "Wait, let me try that again."
    fake_claude.aside_fail_after = 1
    ev = await run(engine, rp_id, user_idx, speech_bytes)
    assert said(ev) == "괜찮아요, 말이 꼬일 수 있어요. " + engine.said("retry_offscript").text
    assert not any(e["type"] == "error" for e in ev) and ev[-1]["type"] == "done"


@pytest.mark.parametrize("pieces", [[], ["  "]])
async def test_aside_empty_answer_says_the_fixed_phrase(engine_with_rp, speech_bytes, fake_whisper, fake_claude,
                                                        pieces):
    # the stream ended without text: a streamed refusal, or thinking used up the tokens (todo offscript-aside minors 1)
    engine, rp_id, user_idx = engine_with_rp
    fake_whisper.text = "Wait, let me try that again."
    fake_claude.aside_pieces = pieces
    ev = await run(engine, rp_id, user_idx, speech_bytes)
    fixed = engine.said("retry_offscript").text
    assert said(ev) == fixed and not any(e["type"] == "error" for e in ev) and ev[-1]["type"] == "done"
    assert engine.store.load(rp_id).attempts[user_idx][-1].say_ko == fixed


@pytest.mark.parametrize(("fail_after", "cut"), [(2, "괜찮아요, 말이 꼬일 수."), (1, "괜찮아요, 말이.")])
async def test_aside_cut_midsentence_ends_it_before_the_fixed_phrase(engine_with_rp, speech_bytes, fake_whisper,
                                                                     fake_claude, fake_voice, fail_after, cut):
    # without a sentence end the fixed phrase read on as part of the cut sentence (todo offscript-aside minors 4)
    engine, rp_id, user_idx = engine_with_rp
    fake_whisper.text = "Wait, let me try that again."
    fake_claude.aside_pieces = ["괜찮아요, 말이 ", "꼬일 수", " 있어요."]  # the last piece never comes
    fake_claude.aside_fail_after = fail_after
    ev = await run(engine, rp_id, user_idx, speech_bytes)
    fixed = engine.said("retry_offscript").text
    assert said(ev) == f"{cut} {fixed}"
    spoken = [text for text, voice, lang, _ in fake_voice.calls if (voice, lang) == ("ryan", "korean")]
    assert spoken[-2:] == [cut, fixed]


@pytest.mark.parametrize(("pieces", "cut"), [(["음, 그건…"], "음, 그건…"),
                                            (["라이언이 「좋아요.」"], "라이언이 「좋아요.」")])
async def test_a_cut_piece_already_ending_a_sentence_gets_no_extra_period(engine_with_rp, speech_bytes, fake_whisper,
                                                                         fake_claude, pieces, cut):
    # todo teacher-answer-cut 2: 「…」 ends a sentence, and so does 「.」 inside a closing bracket or quote: the fixed
    # phrase follows without 「….」 or 「.」.」
    engine, rp_id, user_idx = engine_with_rp
    fake_whisper.text = "Wait, let me try that again."
    fake_claude.aside_pieces = pieces + ["다음 조각"]  # the last piece never comes
    fake_claude.aside_fail_after = len(pieces)
    ev = await run(engine, rp_id, user_idx, speech_bytes)
    assert said(ev) == f"{cut} {engine.said('retry_offscript').text}"


async def test_a_piece_ending_its_sentence_is_sent_with_its_space(engine_with_rp, speech_bytes, fake_whisper,
                                                                  fake_claude):
    # todo teacher-answer-cut 3: the space after 「.」 was held for the next piece, so the sentence's voice waited for
    # it; now it goes at once, and a cut after it still leaves one space before the fixed phrase
    engine, rp_id, user_idx = engine_with_rp
    fake_whisper.text = "Wait, let me try that again."
    fake_claude.aside_pieces = ["괜찮아요. ", "그런데"]
    fake_claude.aside_fail_after = 1
    ev = await run(engine, rp_id, user_idx, speech_bytes)
    texts = [e["delta"] for e in ev if e["type"] == "text"]
    assert texts[0] == "괜찮아요. "
    assert said(ev) == f"괜찮아요. {engine.said('retry_offscript').text}"


async def test_both_transcripts_empty_is_no_speech(engine_with_rp, speech_bytes, fake_whisper):
    engine, rp_id, user_idx = engine_with_rp
    fake_whisper.text = ""
    ev = await run(engine, rp_id, user_idx, speech_bytes)
    assert ev[-1]["code"] == "no_speech"


# spec offscript-aside 6 (user, after the final review): a try at the line that got the Mac's points is not an aside.
# It moves on like a followed try with points, so a line whisper keeps mishearing never traps the learner.
async def test_near_miss_is_a_try_at_the_line(engine_with_rp, speech_bytes, fake_whisper):
    engine, rp_id, user_idx = engine_with_rp
    fake_whisper.text = "It's light over hair."
    ev = await run(engine, rp_id, user_idx, speech_bytes)
    assert ev[-1] == {"type": "done", "next": user_idx + 1, "issues": 2}
    rp = engine.store.load(rp_id)
    assert rp.pos == user_idx + 1 and rp.attempts[user_idx][-1].aside is False
    s = engine.summary(rp_id)
    [t] = next(l["tries"] for l in s["lines"] if l["line"]["idx"] == user_idx)
    assert [i["target"] for i in t["issues"]] == ["right", "there"] and t["point_ko"] == ""
    assert s["say"] == engine.said("closing_retry").model_dump()


async def test_history_keeps_the_line_after_a_near_miss(engine_with_rp, speech_bytes, fake_whisper):
    engine, rp_id, user_idx = engine_with_rp
    fake_whisper.text = "It's light over hair."
    await run(engine, rp_id, user_idx, speech_bytes)
    rp = engine.store.load(rp_id)
    assert engine.history(rp, user_idx + 1)[-1] == ("user", rp.lines[user_idx].text)


async def test_near_miss_points_count_for_the_next_praise(engine_with_rp, speech_bytes, fake_whisper, fake_claude):
    engine, rp_id, user_idx = engine_with_rp
    fake_whisper.text = "It's light over hair."
    await run(engine, rp_id, user_idx, speech_bytes)
    fake_whisper.text = "It's right over there."
    await run(engine, rp_id, user_idx, speech_bytes, "retry")
    assert fake_claude.feedback_calls[-1]["praise"][0] == "이번에는 right의 R 소리가 제대로 났어요"


async def test_line_then_hangul_in_the_english_transcript_is_an_aside(engine_with_rp, speech_bytes, fake_whisper,
                                                                     fake_claude):
    # check with a Jake-voice recording 2026-11-08: forced to English, whisper kept the Korean in Hangul after the
    # line. The match counts English words only, so the line alone made it "followed" and 「다음」 showed.
    engine, rp_id, user_idx = engine_with_rp
    fake_whisper.text = "It's right over there... 아, 잠깐만요."
    fake_whisper.auto_text, fake_whisper.auto_lang = "잇츠 라잇 오버 데어 아 잠깐만요", "korean"
    ev = await run(engine, rp_id, user_idx, speech_bytes)
    assert ev[0]["followed"] is False and fake_claude.feedback_calls == []
    assert ev[-1] == {"type": "done", "next": user_idx, "issues": 0}


async def test_first_turn_after_a_korean_aside_moves_on(engine_with_rp, speech_bytes, fake_whisper):
    # forced to English, whisper wrote nothing; auto-detection heard Korean. The aside keeps the first turn a turn,
    # so following the line next moves the roleplay on (todo offscript-aside minors 6)
    engine, rp_id, user_idx = engine_with_rp
    pos = engine.store.load(rp_id).pos
    fake_whisper.text = ""
    fake_whisper.auto_text, fake_whisper.auto_lang = "잠깐만요, 다시 할게요", "korean"
    ev = await run(engine, rp_id, user_idx, speech_bytes)
    assert ev[0] == {"type": "heard", "text": "잠깐만요, 다시 할게요", "followed": False, "n": 1}
    assert ev[-1] == {"type": "done", "next": user_idx, "issues": 0}
    rp = engine.store.load(rp_id)
    assert rp.pos == pos and rp.attempts[user_idx][-1].aside is True

    fake_whisper.text, fake_whisper.auto_text = rp.lines[user_idx].text, None
    ev = await run(engine, rp_id, user_idx, speech_bytes)
    assert ev[-1]["next"] == user_idx + 1 and engine.store.load(rp_id).pos == user_idx + 1


async def test_auto_transcription_failing_goes_on_in_english(engine_with_rp, speech_bytes, fake_whisper, fake_claude):
    # the second transcription is a check for Korean; when whisper-server cannot answer it, the English one stands
    # (todo offscript-aside minors 2)
    engine, rp_id, user_idx = engine_with_rp
    fake_whisper.text = "Wait, let me try that again."
    fake_whisper.auto_fail = True
    ev = await run(engine, rp_id, user_idx, speech_bytes)
    assert ev[0] == {"type": "heard", "text": "Wait, let me try that again.", "followed": False, "n": 1}
    assert fake_claude.aside_calls[-1]["heard_ko"] is None and said(ev) and ev[-1]["type"] == "done"
    assert fake_whisper.langs == ["en", "auto"]  # the second transcription was asked for and its failure passed over


async def test_auto_transcription_failing_keeps_the_macs_points(engine_with_rp, speech_bytes, fake_whisper,
                                                               fake_claude):
    engine, rp_id, user_idx = engine_with_rp
    fake_whisper.text = "It's light over hair."
    fake_whisper.auto_fail = True
    ev = await run(engine, rp_id, user_idx, speech_bytes)
    assert ev[-1] == {"type": "done", "next": user_idx + 1, "issues": 2}


@pytest.mark.parametrize("boundary", ["It's right over there.", "It's light over hair."], ids=["followed", "near"])
async def test_earlier_asides_stop_at_the_last_try_at_the_line(engine_with_rp, speech_bytes, fake_whisper,
                                                              fake_claude, boundary):
    # 「바로 앞에」 (spec 3): what was said before a try at the line, followed or with the Mac's points, is an
    # earlier exchange and not sent along (todo offscript-aside minors 3)
    engine, rp_id, user_idx = engine_with_rp
    for heard in ["Wait, let me try that again.", boundary, "What does this mean?", "What does this mean?"]:
        fake_whisper.text = heard
        await run(engine, rp_id, user_idx, speech_bytes, "practice")
    assert fake_claude.aside_calls[-1]["earlier"] == [("What does this mean?",
                                                       "괜찮아요, 말이 꼬일 수 있어요. 다시 해 볼까요?")]
