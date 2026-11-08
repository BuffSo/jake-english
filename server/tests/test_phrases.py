from je_server.phrases import PHRASES


def test_jake_is_the_one_who_recommends():
    # 2026-11-05 the user: the recommendation comes from Jake, not Ryan, so Ryan says Jake will suggest one
    assert "제이크" in PHRASES["ask_situation"] and "제이크" in PHRASES["ask_recommend"]
    assert "추천해 드릴" not in PHRASES["ask_situation"] + PHRASES["ask_recommend"]


def test_greeting_does_not_name_the_learner():
    # 2026-11-05 the user: leave the name out (later it should be the signed-in person's name) and have Ryan
    # introduce himself instead
    assert "제이크" not in PHRASES["greeting"] and "라이언입니다" in PHRASES["greeting"]


def test_asking_again_neither_greets_nor_assumes_a_finished_roleplay():
    # 2026-11-06 the user: Ryan greets once, when the app starts; coming back to the first screen he only asks
    # again. The app cannot tell why the learner came back (done, or left halfway), so no 「수고했어요」.
    again = PHRASES["ask_again"]
    assert "안녕" not in again and "라이언입니다" not in again and "수고" not in again
    assert again != PHRASES["ask_mode"]


def test_topic_steps_have_ryans_lines():
    # spec situation-topics 6: topic, how to pick, the list, describing it
    assert PHRASES["ask_topic"] == "어떤 주제로 연습해 볼까요?"
    assert PHRASES["ask_how"] == "어떻게 상황을 정할까요?"
    assert PHRASES["ask_pick"] == "해 보고 싶은 상황을 골라 주세요."
    assert PHRASES["ask_describe"] == "어떤 상황인지 말하거나 써 주세요."


def test_first_screen_asks_what_to_practise():
    # spec review-screens 1: 「복습하기」 is not a way of talking, so Ryan asks what to practise
    assert PHRASES["ask_mode"] == "오늘은 무엇을 연습해 볼까요?"
    assert PHRASES["ask_again"] == "이번에는 무엇을 연습해 볼까요?"


def test_ryan_says_daehwa_not_roleplay():
    # spec review-screens 6: on screen and in Ryan's fixed lines the roleplay is 「대화」
    assert PHRASES["closing_retry"].startswith("대화 끝! 수고했어요.")
    assert PHRASES["closing_clean"].startswith("대화 끝! 수고했어요.")
    assert not [k for k, v in PHRASES.items() if "역할극" in v]


def test_plain_closing_does_not_praise():
    # spec record-cancel-skip 3: no line was said, so nothing the Mac heard to praise
    assert PHRASES["closing_plain"] == "대화 끝! 수고했어요."
    assert "잘했어요" not in PHRASES["closing_plain"]


def test_tips_say_shadowing_and_are_not_fixed_lines():
    # spec ryan-shadowing-tip 1: each line has the word, five in this order, apart from the always-same lines
    from je_server.phrases import TIPS

    assert len(TIPS) == 5 and all("섀도잉" in t for t in TIPS)
    assert TIPS[4] == "섀도잉하기 전에, 어디를 세게 읽고 어디를 이어 읽는지 잘 들어 보세요."
    assert not set(TIPS) & set(PHRASES.values())
