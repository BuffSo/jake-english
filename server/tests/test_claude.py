import json

import pytest

from fakes import (FakeAnthropic, connection_error, refusal_response, script_json, three_json,
                   three_json_with_wrong_stress)
from je_server.claude import Claude, ClaudeUnavailable
from je_server.threeline import check
from je_server.topics import get

OTHER = get("other")

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


async def test_make_script_retries_when_turns_are_wrong():
    # 2026-11-05 the user found 5 learner lines too many and chose 3
    fake = FakeAnthropic([script_json(user_turns=5), script_json(user_turns=3)])
    frame, draft = await Claude(fake).make_script("길 묻기", OTHER)
    assert sum(1 for s, _ in draft if s == "user") == 3 and len(fake.requests) == 2
    assert draft[0][0] == "ryan" and draft[-1][0] == "ryan"
    assert all(a[0] != b[0] for a, b in zip(draft, draft[1:]))
    assert frame.title_ko == "길 묻기"
    assert "not 5" in fake.requests[1]["messages"][0]["content"]  # the retry says what was wrong


async def test_make_script_gives_up_after_second_bad_script():
    fake = FakeAnthropic([script_json(user_turns=2), script_json(user_turns=4)])
    with pytest.raises(ClaudeUnavailable):
        await Claude(fake).make_script("길 묻기", OTHER)


async def test_requests_use_spec_model_settings():
    fake = FakeAnthropic([script_json(user_turns=3)])
    await Claude(fake).make_script("길 묻기", OTHER)
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
        await Claude(FakeAnthropic([connection_error()])).recommend([], [], OTHER)


async def test_refusal_becomes_unavailable():
    with pytest.raises(ClaudeUnavailable):
        await Claude(FakeAnthropic([refusal_response()])).make_script("길 묻기", OTHER)


async def test_recommend_uses_haiku_and_avoids_recent():
    fake = FakeAnthropic([json.dumps({"request_ko": "카페에서 주문하는 상황으로 연습해 보면 어때요?"})])
    text = await Claude(fake).recommend(["길에서 케이블카 타는 곳을 묻는 상황"], [], OTHER)
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
    await Claude(fake).recommend(["길에서 케이블카 타는 곳을 묻는 상황"], ["카페에서 주문하는 상황으로 연습해 보면 어때요?"], OTHER)
    content = fake.requests[0]["messages"][0]["content"]
    assert "케이블카" in content and "방금 거절한 상황:\n- 카페에서 주문하는" in content
    assert "turned down" in str(fake.requests[0]["system"])
    await Claude(fake).recommend([], [], OTHER)  # nothing turned down: the message has no empty list for it
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


async def test_any_api_status_error_becomes_unavailable():
    # final review: a 400 (e.g. no credit left) or 401 surfaced as a bare 500 or a dropped stream
    from fakes import status_error

    for code in (400, 401, 429, 503):
        with pytest.raises(ClaudeUnavailable):
            await Claude(FakeAnthropic([status_error(code)])).make_script("길 묻기", OTHER)
    with pytest.raises(ClaudeUnavailable):
        [t async for t in Claude(FakeAnthropic([status_error(400)])).feedback("a", "b", [], [])]


async def test_live_turn_calls_give_up_before_the_app_does():
    # the app waits 30s between stream events; a stalled connection must end on the server side first
    from fakes import FRAME
    from je_server.claude import LIVE_OPTIONS
    from je_server.models import Frame

    assert LIVE_OPTIONS["timeout"] * (LIVE_OPTIONS["max_retries"] + 1) < 30
    fake = FakeAnthropic([["ok"], ["괜찮아요."]])
    c = Claude(fake)
    [t async for t in c.feedback("a", "b", [], [])]
    [t async for t in c.aside(Frame(**FRAME), [], "a", "b", None, [], [])]
    assert fake.options == [LIVE_OPTIONS, LIVE_OPTIONS]


def test_feedback_prompt_puts_the_improvement_first():
    from je_server import prompts

    assert "「이번에는」으로 시작하는 후보가 있으면 그것을 말해요" in prompts.FEEDBACK_SYSTEM


# --- Sohee's interpretation (spec korean-translation 3) --------------------------------------------------------

async def test_interpret_uses_the_quick_model_with_roles_and_neighbors():
    from fakes import FRAME
    from je_server.models import Frame

    fake = FakeAnthropic([json.dumps({"ko": "역까지 어떻게 가요?"})])
    ko = await Claude(fake).interpret(Frame(**FRAME), ("ryan", "How do I get there?"),
                                      ("user", "It's right over there."), None)
    req = fake.requests[0]
    assert ko == "역까지 어떻게 가요?" and req["model"] == "claude-haiku-5-5"
    body = req["messages"][0]["content"]
    assert "How do I get there?" in body and "It's right over there." in body
    assert FRAME["ryan_role_ko"] in body and FRAME["user_role_ko"] in body
    assert fake.options and fake.options[0]["timeout"] == 12.0  # the learner waits: fail fast (LIVE_OPTIONS)


async def test_interpret_keeps_one_line_without_quotes():
    from fakes import FRAME
    from je_server.models import Frame

    fake = FakeAnthropic([json.dumps({"ko": "「역까지\n어떻게 가요?」"})])
    ko = await Claude(fake).interpret(Frame(**FRAME), ("ryan", "How do I get there?"), None, None)
    assert ko == "역까지 어떻게 가요?"


async def test_interpret_asks_again_without_korean_then_gives_up():
    from fakes import FRAME
    from je_server.models import Frame

    fake = FakeAnthropic([json.dumps({"ko": "How do I get there?"}), json.dumps({"ko": "역까지 어떻게 가요?"})])
    ko = await Claude(fake).interpret(Frame(**FRAME), ("ryan", "How do I get there?"), None, None)
    assert ko == "역까지 어떻게 가요?" and len(fake.requests) == 2
    fake = FakeAnthropic([json.dumps({"ko": ""}), "not json"])
    with pytest.raises(ClaudeUnavailable):
        await Claude(fake).interpret(Frame(**FRAME), ("ryan", "How do I get there?"), None, None)


# --- situation topics (spec situation-topics 4, 5) ---------------------------------------------------------------

def lines_json(*speakers: str) -> str:
    from fakes import FRAME

    return json.dumps({"frame": FRAME, "lines": [{"speaker": s, "text": f"Line {i}."} for i, s in enumerate(speakers)]})


async def test_make_script_sends_the_topic_roles_and_first():
    # 2026-11-07 the user: asking the way in the US, the learner speaks first
    fake = FakeAnthropic([lines_json("user", "ryan", "user", "ryan", "user", "ryan")])
    _, draft = await Claude(fake).make_script("뉴욕 호텔 프런트에서 체크인한다.", get("usa"), first="user")
    content = fake.requests[0]["messages"][0]["content"]
    assert get("usa").roles_en in content and "The learner speaks first." in content
    assert draft[0][0] == "user"


async def test_make_script_lets_the_situation_decide_who_starts():
    fake = FakeAnthropic([lines_json("ryan", "user", "ryan", "user", "ryan", "user")])
    await Claude(fake).make_script("공항에서 짐이 안 나와 직원에게 묻는다.", get("usa"))
    assert "Whoever would naturally speak first" in fake.requests[0]["messages"][0]["content"]


async def test_make_script_retries_when_the_first_speaker_is_wrong():
    # 외국인 관광객: the tourist always asks first (user, 2026-11-07)
    fake = FakeAnthropic([lines_json("user", "ryan", "user", "ryan", "user"),
                          lines_json("ryan", "user", "ryan", "user", "ryan", "user")])
    _, draft = await Claude(fake).make_script("관광객이 길을 묻는다.", get("tourist"))
    assert len(fake.requests) == 2 and draft[0][0] == "ryan"
    assert "Ryan speaks first." in fake.requests[0]["messages"][0]["content"]
    assert "Ryan must speak first" in fake.requests[1]["messages"][0]["content"]


def test_script_may_start_and_end_with_either():
    # the old rule (Ryan first and last) was an AI choice with no recorded reason; the user chose what fits
    ok = Claude.script_problems
    u, r = "user", "ryan"
    assert ok([(s, "Hi.") for s in (u, r, u, r, u)]) == []
    assert ok([(s, "Hi.") for s in (r, u, r, u, r, u)]) == []
    assert ok([(s, "Hi.") for s in (u, r, u, r, u)], first="user") == []
    assert ok([(s, "Hi.") for s in (u, r, u, r, u)], first="ryan") == ["Ryan must speak first"]
    assert ok([(s, "Hi.") for s in (r, u, r, u, r)], first="user") == ["the learner must speak first",
                                                                         "the learner must have 3 lines, not 2"]
    assert ok([(s, "Hi.") for s in (r, u, u, r, u)]) == ["lines must alternate between Ryan and the learner"]


def test_script_prompt_allows_real_places_but_not_people():
    from je_server import prompts

    system = prompts.SCRIPT_SYSTEM
    assert "Ryan speaks first and Ryan speaks last" not in system
    assert "Real shops" in system and "never real people" in system
    assert "exit numbers" in system and "opening hours" in system


def test_script_prompts_end_on_the_learner_when_ryan_would_only_echo():
    # with "whoever would say it", five real scripts in a row still closed on Ryan's "You too!"
    from je_server import prompts

    system = prompts.SCRIPT_SYSTEM
    assert "only echo" in system and "end on the learner's line" in system


async def test_recommend_stays_in_the_topic():
    fake = FakeAnthropic([json.dumps({"request_ko": "명동에서 환전소를 묻는 상황으로 연습해 보면 어때요?"})])
    await Claude(fake).recommend(["관광객이 길을 묻는다."], [], get("tourist"))
    content = fake.requests[0]["messages"][0]["content"]
    t = get("tourist")
    assert t.scenes_en in content and t.example_ko in content
    assert "목록에 있는 상황:" in content and all(p.title_ko in content for p in t.picks)
    assert "연습해 보면 어때요?" in str(fake.requests[0]["system"])


async def test_recommend_without_a_list_has_no_list_heading():
    fake = FakeAnthropic([json.dumps({"request_ko": "전화로 주문을 확인하는 상황으로 연습해 보면 어때요?"})])
    await Claude(fake).recommend([], [], OTHER)
    assert "목록에 있는 상황" not in fake.requests[0]["messages"][0]["content"]


def test_recommend_system_has_no_scene_of_its_own():
    # final review: the fixed example was a tourist-in-Korea scene, which could pull 미국 여행 and 그 밖의 상황 toward
    # it; the scene comes from the topic's example in the message, the system keeps only the sentence form
    from je_server import prompts

    assert "케이블카" not in prompts.RECOMMEND_SYSTEM and "외국인" not in prompts.RECOMMEND_SYSTEM
    assert "상황으로 연습해 보면 어때요?" in prompts.RECOMMEND_SYSTEM


async def test_script_lines_drop_stray_braces():
    script = json.loads(script_json(user_turns=3))
    script["lines"][0]["text"] += "}"
    _, draft = await Claude(FakeAnthropic([json.dumps(script)])).make_script("길 묻기", OTHER)
    assert not any("}" in t for _, t in draft)


async def test_feedback_says_whether_the_line_is_the_last():
    from je_server import prompts

    fake = FakeAnthropic([["잘했어요."], ["잘했어요."]])
    c = Claude(fake)
    [t async for t in c.feedback("Thanks!", "Thanks!", [], [], last=True)]
    [t async for t in c.feedback("Hi.", "Hi.", [], [])]
    assert [json.loads(r["messages"][0]["content"])["마지막 대사"] for r in fake.requests] == [True, False]
    assert "마지막 대사" in prompts.FEEDBACK_SYSTEM and "다음 대사로 넘어가자고 하지 않아요" in prompts.FEEDBACK_SYSTEM
    assert "마지막 대사여도 한 번 더 해 보자고 해요. 이때는 대화를 마쳤다고 말하지 않아요" in prompts.FEEDBACK_SYSTEM


async def test_aside_streams_korean_on_the_writer_and_sends_only_text():
    from fakes import FRAME
    from je_server import prompts
    from je_server.claude import LIVE_OPTIONS
    from je_server.models import Frame, Issue

    fake = FakeAnthropic([["괜찮아요. ", "다시 해 볼까요?"]])
    issue = Issue(target="large", heard="launch", sound=("R", "N"), explain="")
    out = [d async for d in Claude(fake).aside(
        Frame(**FRAME), [("ryan", "What size?")], "A large one, please.", "A launch one, peace.", None,
        [issue], [("다시 할게요", "괜찮아요. 다시 해 볼까요?")])]
    assert out == ["괜찮아요. ", "다시 해 볼까요?"]
    req = fake.requests[0]
    assert req["model"] == "claude-sonnet-5-5" and req["system"] == prompts.ASIDE_SYSTEM
    assert req["output_config"]["effort"] == "low" and fake.options[-1] == LIVE_OPTIONS
    body = json.loads(req["messages"][0]["content"])
    assert body["대사"] == "A large one, please." and body["들린 말(영어 받아쓰기)"] == "A launch one, peace."
    assert body["들린 말(한국어 받아쓰기)"] == ""
    assert body["짚을 것"] == [{"대사 낱말": "large", "들린 낱말": "launch", "소리 내는 법": ""}]
    assert body["앞서 선생님에게 한 말"] == [{"들린 말": "다시 할게요", "라이언의 답": "괜찮아요. 다시 해 볼까요?"}]
    assert body["지금까지 대화"] == [{"speaker": "ryan", "text": "What size?"}]


async def test_aside_connection_error_is_unavailable():
    from fakes import FRAME
    from je_server.models import Frame

    fake = FakeAnthropic([connection_error()])
    with pytest.raises(ClaudeUnavailable):
        [d async for d in Claude(fake).aside(Frame(**FRAME), [], "a", "b", None, [], [])]


def test_aside_prompt_keeps_the_teacher_rules():
    from je_server import prompts

    p = prompts.ASIDE_SYSTEM
    for must in ("해요체", "읽는 법 보기", "처럼 들렸어요", "다시"):
        assert must in p
    # the app calls the roleplay 「대화」 (review-screens, user 2026-11-07); Ryan says it the same way
    assert "「역할극」이라고 하지 않고 「대화」라고 해요" in p


@pytest.mark.parametrize("error", ["read", "timeout"])
async def test_stream_cut_by_the_network_is_unavailable(error):
    # final review: the SDK raises transport errors met while reading the stream as they are, so a dropped
    # connection mid-answer broke the attempt instead of giving the fixed phrase
    import httpx2

    from fakes import FRAME
    from je_server.models import Frame

    req = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    cut = httpx2.ReadError("cut", request=req) if error == "read" else httpx2.ReadTimeout("slow", request=req)
    got = []
    with pytest.raises(ClaudeUnavailable):
        async for d in Claude(FakeAnthropic([["괜찮아요. ", cut]])).aside(Frame(**FRAME), [], "a", "b", None, [], []):
            got.append(d)
    assert got == ["괜찮아요. "]
    with pytest.raises(ClaudeUnavailable):
        [d async for d in Claude(FakeAnthropic([["좋아요. ", cut]])).feedback("a", "b", [], [])]
