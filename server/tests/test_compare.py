from je_server.compare import FOLLOW_MIN, find_issues, praise_candidates, similarity, sound_pairs, word_pairs


def test_running_heard_as_learning_is_r_l():
    issues = find_issues("I'm running to the station.", "I'm learning to the station", limit=2)
    assert [(i.target, i.heard, set(i.sound)) for i in issues] == [("running", "learning", {"R", "L"})]
    assert "혀" in issues[0].explain


def test_unlisted_sound_change_is_not_flagged():
    assert find_issues("I want the red one.", "I want the bed one.", limit=2) == []


def test_limit_caps_issues_and_one_per_sound():
    issues = find_issues("Right, the river is very far.", "Light, the liver is belly par.", limit=2)
    assert len(issues) == 2 and len({frozenset(i.sound) for i in issues}) == 2


def test_same_words_no_issues_and_full_similarity():
    assert find_issues("Turn left here.", "turn left here", limit=2) == []
    assert similarity("Turn left here.", "turn left here") == 1.0


def test_different_answer_is_not_followed():
    assert similarity("It's right over there.", "Sorry, I don't know this area.") < FOLLOW_MIN


def test_one_misheard_word_still_followed():
    assert similarity("I'm running to the station.", "I'm learning to the station") >= FOLLOW_MIN


def test_empty_heard_is_zero():
    assert similarity("Hello there.", "") == 0.0


def test_unknown_word_has_no_sound_pairs():
    assert sound_pairs("namsan", "namsang") == []


def test_word_pairs_only_one_to_one():
    assert word_pairs("I'm running to the station.", "I'm learning to the station") == [("running", "learning")]
    assert word_pairs("go to the station", "go station") == []


def test_praise_names_a_listed_sound_heard_right():
    praise = praise_candidates("Turn right at the corner.", "turn right at the corner")
    assert any("right" in p and "R" in p for p in praise)


def test_praise_always_has_something():
    assert praise_candidates("Hello.", "Yellow.")
