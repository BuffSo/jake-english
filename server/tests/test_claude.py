import json

import pytest

from fakes import (FakeAnthropic, connection_error, refusal_response, script_json, three_json,
                   three_json_with_wrong_stress)
from je_server.claude import Claude, ClaudeUnavailable
from je_server.threeline import check

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


async def test_make_script_retries_when_turns_are_wrong():
    # 2026-11-05 the user found 5 learner lines too many and chose 3
    fake = FakeAnthropic([script_json(user_turns=5), script_json(user_turns=3)])
    frame, draft = await Claude(fake).make_script("길 묻기")
    assert sum(1 for s, _ in draft if s == "user") == 3 and len(fake.requests) == 2
    assert draft[0][0] == "ryan" and draft[-1][0] == "ryan"
    assert all(a[0] != b[0] for a, b in zip(draft, draft[1:]))
    assert frame.title_ko == "길 묻기"
    assert "not 5" in fake.requests[1]["messages"][0]["content"]  # the retry says what was wrong


async def test_make_script_gives_up_after_second_bad_script():
    fake = FakeAnthropic([script_json(user_turns=2), script_json(user_turns=4)])
    with pytest.raises(ClaudeUnavailable):
        await Claude(fake).make_script("길 묻기")


async def test_requests_use_spec_model_settings():
    fake = FakeAnthropic([script_json(user_turns=3)])
    await Claude(fake).make_script("길 묻기")
    r = fake.requests[0]
    assert r["model"] == "claude-sonnet-5-5" and r["thinking"] == {"type": "between_tools"}
    assert r["output_config"]["effort"] == "low" and r["output_config"]["format"]["type"] == "json_schema"
    assert "temperature" not in r and "top_p" not in r and "top_k" not in r
    assert "길 묻기" in r["messages"][0]["content"]


async def test_annotate_returns_first_good_answer():
    fake = FakeAnthropic([three_json()])
    three = await Claude(fake).annotate("I like coffee.", "카페에서")
    assert check("I like coffee.", three) == [] and three.words[2].syl[0].m == "s"
    assert len(fake.requests) == 1


async def test_annotate_retries_then_degrades():
    bad = three_json_with_wrong_stress()
    fake = FakeAnthropic([bad, bad, bad])
    three = await Claude(fake).annotate("I like coffee.", "카페에서")
    assert len(fake.requests) == 3
    assert check("I like coffee.", three) == []
    assert all(s.m != "s" for s in three.words[2].syl)
    assert "stress" in fake.requests[1]["messages"][0]["content"]


async def test_annotate_bad_json_falls_back_to_plain():
    fake = FakeAnthropic(["not json", "{}", "[1]"])
    three = await Claude(fake).annotate("I like coffee.", "")
    assert [w.syl[0].en for w in three.words] == ["I", "like", "coffee."]


async def test_api_failure_becomes_unavailable():
    with pytest.raises(ClaudeUnavailable):
        await Claude(FakeAnthropic([connection_error()])).recommend([])


async def test_refusal_becomes_unavailable():
    with pytest.raises(ClaudeUnavailable):
        await Claude(FakeAnthropic([refusal_response()])).make_script("길 묻기")


async def test_recommend_uses_haiku_and_avoids_recent():
    fake = FakeAnthropic([json.dumps({"request_ko": "카페에서 주문하는 상황으로 연습해 보면 어때요?"})])
    text = await Claude(fake).recommend(["길에서 케이블카 타는 곳을 묻는 상황"])
    assert text.endswith("어때요?")
    r = fake.requests[0]
    # 존댓말: Jake's cloned voice swallowed the 반말 ending 「싶어.」 4 times in 5, 「싶어요.」 once (2026-11-05).
    # Jake suggests the situation to the learner, he does not ask for it on the learner's behalf (user, same day).
    system = str(r["system"])
    assert "연습해 보면 어때요?" in system and "반말" not in system and "싶어" not in system
    assert r["model"] == "claude-haiku-5-5" and r["thinking"] == {"type": "disabled"}
    assert "effort" not in r.get("output_config", {})
    assert "케이블카" in r["messages"][0]["content"]


async def test_recommend_avoids_turned_down():
    # 2026-11-06 the user: Jake's suggestion waits for 「이걸로 할게요」 or 「다른 걸로요」, and one turned down
    # with 「다른 걸로요」 must not come back
    answer = json.dumps({"request_ko": "호텔 프런트에서 체크인하는 상황으로 연습해 보면 어때요?"})
    fake = FakeAnthropic([answer, answer])
    await Claude(fake).recommend(["길에서 케이블카 타는 곳을 묻는 상황"], ["카페에서 주문하는 상황으로 연습해 보면 어때요?"])
    content = fake.requests[0]["messages"][0]["content"]
    assert "케이블카" in content and "방금 거절한 상황:\n- 카페에서 주문하는" in content
    assert "turned down" in str(fake.requests[0]["system"])
    await Claude(fake).recommend([])  # nothing turned down: the message has no empty list for it
    assert "거절" not in fake.requests[1]["messages"][0]["content"]


async def test_feedback_streams_with_haiku_and_sends_findings():
    from je_server.models import Issue

    fake = FakeAnthropic([["끝까지 ", "잘했어요."]])
    issue = Issue(target="running", heard="learning", sound=("R", "L"), explain="R은 혀가 어디에도 닿지 않게")
    out = [t async for t in Claude(fake).feedback("I'm running.", "I'm learning.", ["끝까지 말했어요"], [issue])]
    assert "".join(out) == "끝까지 잘했어요."
    r = fake.requests[0]
    assert r["model"] == "claude-haiku-5-5" and r["thinking"] == {"type": "disabled"} and "temperature" not in r
    body = json.loads(r["messages"][0]["content"])
    assert body["짚을 것"][0]["소리 내는 법"] == "R은 혀가 어디에도 닿지 않게"


async def test_feedback_connection_error_is_unavailable():
    fake = FakeAnthropic([connection_error()])
    with pytest.raises(ClaudeUnavailable):
        [t async for t in Claude(fake).feedback("a", "b", [], [])]


async def test_offscript_uses_sonnet_and_sends_what_was_said():
    from fakes import FRAME
    from je_server.models import Frame

    fake = FakeAnthropic([json.dumps({"point_kind": "none", "point_ko": "", "meant": "", "heard_word": "",
                                      "reply_en": "No problem!"})])
    out = await Claude(fake).offscript(Frame(**FRAME), [("ryan", "Where is it?")], "It's there.", "I don't know.")
    assert out.reply_en == "No problem!" and fake.requests[0]["model"] == "claude-sonnet-5-5"
    body = json.loads(fake.requests[0]["messages"][0]["content"])
    assert body["학습자가 한 말(받아쓴 글)"] == "I don't know." and body["대본의 대사"] == "It's there."


async def test_offscript_empty_reply_is_unavailable():
    from fakes import FRAME
    from je_server.models import Frame

    fake = FakeAnthropic([json.dumps({"point_kind": "none", "point_ko": "", "meant": "", "heard_word": "",
                                      "reply_en": " "})])
    with pytest.raises(ClaudeUnavailable):
        await Claude(fake).offscript(Frame(**FRAME), [], "a", "b")


async def test_continue_script_retries_wrong_shape():
    from fakes import FRAME
    from je_server.models import Frame

    bad = json.dumps({"lines": [{"speaker": "ryan", "text": "Hi."}]})
    good = json.dumps({"lines": [{"speaker": "user", "text": "Thanks."}, {"speaker": "ryan", "text": "Bye!"}]})
    fake = FakeAnthropic([bad, good])
    draft = await Claude(fake).continue_script(Frame(**FRAME), [("ryan", "Hi.")], 1)
    assert draft == [("user", "Thanks."), ("ryan", "Bye!")] and len(fake.requests) == 2
    assert "start with the learner" in fake.requests[1]["messages"][0]["content"]


async def test_any_api_status_error_becomes_unavailable():
    # final review: a 400 (e.g. no credit left) or 401 surfaced as a bare 500 or a dropped stream
    from fakes import status_error

    for code in (400, 401, 429, 503):
        with pytest.raises(ClaudeUnavailable):
            await Claude(FakeAnthropic([status_error(code)])).make_script("길 묻기")
    with pytest.raises(ClaudeUnavailable):
        [t async for t in Claude(FakeAnthropic([status_error(400)])).feedback("a", "b", [], [])]


async def test_live_turn_calls_give_up_before_the_app_does():
    # the app waits 30s between stream events; a stalled connection must end on the server side first
    from fakes import FRAME
    from je_server.claude import LIVE_OPTIONS
    from je_server.models import Frame

    assert LIVE_OPTIONS["timeout"] * (LIVE_OPTIONS["max_retries"] + 1) < 30
    fake = FakeAnthropic([["ok"], json.dumps({"point_kind": "none", "point_ko": "", "meant": "", "heard_word": "",
                                              "reply_en": "Sure."})])
    c = Claude(fake)
    [t async for t in c.feedback("a", "b", [], [])]
    await c.offscript(Frame(**FRAME), [], "a", "b")
    assert fake.options == [LIVE_OPTIONS, LIVE_OPTIONS]


async def test_continue_script_needs_the_exact_number_of_learner_lines():
    # PR #12 review: ±1 let a rebuild after line 1 add 3 learner lines, 4 in total (the user chose 3)
    from fakes import FRAME
    from je_server.models import Frame

    three = json.dumps({"lines": [{"speaker": s, "text": t} for s, t in
                                  [("user", "a"), ("ryan", "b"), ("user", "c"), ("ryan", "d"), ("user", "e"),
                                   ("ryan", "f")]]})
    two = json.dumps({"lines": [{"speaker": s, "text": t} for s, t in
                                [("user", "a"), ("ryan", "b"), ("user", "c"), ("ryan", "d")]]})
    fake = FakeAnthropic([three, two])
    draft = await Claude(fake).continue_script(Frame(**FRAME), [("ryan", "Hi.")], 2)
    assert sum(1 for s, _ in draft if s == "user") == 2 and len(fake.requests) == 2


def test_feedback_prompt_puts_the_improvement_first():
    from je_server import prompts

    assert "「이번에는」으로 시작하는 후보가 있으면 그것을 말해요" in prompts.FEEDBACK_SYSTEM
