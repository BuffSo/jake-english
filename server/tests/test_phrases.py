from je_server.phrases import PHRASES


def test_jake_is_the_one_who_recommends():
    # 2026-11-05 the user: the recommendation comes from Jake, not Ryan, so Ryan says Jake will suggest one
    assert "제이크" in PHRASES["ask_situation"] and "제이크" in PHRASES["ask_recommend"]
    assert "추천해 드릴" not in PHRASES["ask_situation"] + PHRASES["ask_recommend"]


def test_greeting_does_not_name_the_learner():
    # 2026-11-05 the user: leave the name out (later it should be the signed-in person's name) and have Ryan
    # introduce himself instead
    assert "제이크" not in PHRASES["greeting"] and "라이언입니다" in PHRASES["greeting"]
