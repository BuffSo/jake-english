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
    fake = FakeAnthropic([script_json(user_turns=3), script_json(user_turns=5)])
    frame, draft = await Claude(fake).make_script("길 묻기")
    assert sum(1 for s, _ in draft if s == "user") == 5 and len(fake.requests) == 2
    assert draft[0][0] == "ryan" and draft[-1][0] == "ryan"
    assert all(a[0] != b[0] for a, b in zip(draft, draft[1:]))
    assert frame.title_ko == "길 묻기"
    assert "4" in fake.requests[1]["messages"][0]["content"]  # the retry says what was wrong


async def test_make_script_gives_up_after_second_bad_script():
    fake = FakeAnthropic([script_json(user_turns=2), script_json(user_turns=7)])
    with pytest.raises(ClaudeUnavailable):
        await Claude(fake).make_script("길 묻기")


async def test_requests_use_spec_model_settings():
    fake = FakeAnthropic([script_json(user_turns=4)])
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
    fake = FakeAnthropic([json.dumps({"request_ko": "카페에서 주문하는 상황으로 연습하고 싶어."})])
    text = await Claude(fake).recommend(["길에서 케이블카 타는 곳을 묻는 상황"])
    assert text.endswith("싶어.")
    r = fake.requests[0]
    assert r["model"] == "claude-haiku-5-5" and r["thinking"] == {"type": "disabled"}
    assert "effort" not in r.get("output_config", {})
    assert "케이블카" in r["messages"][0]["content"]


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
