from je_server.compare import (FOLLOW_MIN, compare, find_issues, issue_ko, praise_candidates, similarity, sound_pairs,
                                words)
from je_server.models import Issue


def test_running_heard_as_learning_is_r_l():
    issues = find_issues("I'm running to the station.", "I'm learning to the station", limit=2)
    assert [(i.target, i.heard, set(i.sound)) for i in issues] == [("running", "learning", {"R", "L"})]
    assert "혀" in issues[0].explain


def test_unlisted_sound_change_is_flagged_without_explain():
    assert find_issues("I want the red one.", "I want the bed one.", limit=2) == [Issue(target="red", heard="bed")]


def test_missing_and_added_words_are_flagged():
    assert find_issues("It's on the left.", "It's the left.", limit=2) == [Issue(target="on", heard="")]
    assert find_issues("Turn left, then go straight.", "Turn left and then go straight.", limit=2) == [
        Issue(target="", heard="and")]


def test_count_changed_span_is_one_issue():
    issues = find_issues("I'll grab a coffee.", "I will grab coffee.", limit=2)
    assert [(i.target, i.heard) for i in issues] == [("i'll", "i will"), ("a", "")]


def test_listed_sound_found_inside_count_changed_span():
    [i] = find_issues("Turn right here.", "Turn a light here.", limit=2)
    assert (i.target, i.heard, set(i.sound)) == ("right", "a light", {"R", "L"}) and "혀" in i.explain


def test_far_apart_words_in_a_span_get_no_sound():
    [i] = compare("We close at nine.", "We'll go so at nine.").diffs
    assert (i.target, i.heard, i.sound) == ("we close", "we'll go so", None)


def test_numbers_and_short_forms_are_not_differences():
    for line, heard in [("It's about ten minutes.", "It's about 10 minutes"),
                        ("I want to go at eleven a.m.", "I wanna go at 11 AM."),
                        ("That's five dollars.", "That's $5."),
                        ("OK, see you at five thirty.", "Okay, see you at 5:30.")]:
        assert compare(line, heard).diffs == [], (line, heard)


def test_joined_and_split_words_are_the_same():
    assert compare("Check-in is at noon.", "Checkin is at noon.").diffs == []
    assert compare("Where is the checkout?", "Where is the check out?").diffs == []


def test_i_am_is_a_real_difference():
    assert find_issues("I'm ready.", "I am ready.", limit=2) == [Issue(target="i'm", heard="i am")]


def test_restart_and_fillers_are_not_differences():
    assert compare("I'd like a cup of tea.", "I'd like a, um, I'd like a cup of tea.").diffs == []


def test_two_at_most_front_first():
    issues = find_issues("Go left, then right, then left again.", "Go lift, then light, then lift again.", limit=2)
    assert [i.target for i in issues] == ["left", "right"]


def test_all_issues_kept_when_within_limit_even_same_sound():
    issues = find_issues("The rock is on the right.", "The lock is on the light.", limit=2)
    assert [(i.target, set(i.sound)) for i in issues] == [("rock", {"R", "L"}), ("right", {"R", "L"})]


def test_comparison_counts_matched_words():
    c = compare("Go left, then right.", "Go lift, then light.")
    assert (c.matched, c.total, c.matched_words) == (2, 4, {"go", "then"})


def test_issue_ko_says_what_was_heard():
    assert issue_ko(Issue(target="right", heard="light")) == "「right」 → 「light」처럼 들렸어요"
    assert issue_ko(Issue(target="on", heard="")) == "「on」 → 들리지 않았어요"
    assert issue_ko(Issue(target="", heard="and")) == "대사에 없는 「and」 들렸어요"


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


def test_praise_only_what_was_checked():
    assert praise_candidates("Turn right at the corner.", "turn right at the corner", []) == ["대사를 빠짐없이 알아듣게 말했어요"]
    assert praise_candidates("Turn right at the corner.", "turn light at the corner", []) == ["나머지 낱말은 다 알아들었어요"]


def test_praise_when_not_every_difference_was_named():
    line = "Go left, then right, then left again."
    assert praise_candidates(line, "Go lift, then light, then lift again.", []) == ["대사의 낱말 대부분을 알아들었어요"]
    assert praise_candidates("Red and blue and green.", "Bed an glue and green.", []) == ["대사 5낱말 가운데 2낱말을 알아들었어요"]


def test_improvement_names_the_listed_sound_or_the_word():
    before = [Issue(target="right", heard="light", sound=("R", "L"), explain="…")]
    assert praise_candidates("Turn right here.", "Turn right here.", before)[0] == "이번에는 right의 R 소리가 제대로 났어요"
    before = [Issue(target="on", heard="")]
    assert praise_candidates("It's on the left.", "It's on the left.", before)[0] == "이번에는 on, 대사대로 들렸어요"


def test_improvement_needs_the_same_issue_gone():
    line = "This is for you. This is for you."
    before = [Issue(target="for", heard="")]
    assert not any(p.startswith("이번에는") for p in praise_candidates(line, "This is for you. This is you.", before))


def test_praise_can_be_empty():
    assert praise_candidates("Hello.", "Yellow.", []) == []


def test_improvement_skipped_when_the_word_is_inside_a_current_difference():
    before = [Issue(target="to", heard="")]
    praise = praise_candidates("I need to go to the bank.", "I need to goat the bank.", before)
    assert not any(p.startswith("이번에는") for p in praise)


def test_clock_times_are_not_differences():
    for line, heard in [("Let's meet at nine.", "Let's meet at 9:00."),
                        ("See you at nine o'clock.", "See you at 9:00."),
                        ("Check-in starts at ten a.m.", "Check-in starts at 10:00 AM."),
                        ("The bus leaves at five oh five.", "The bus leaves at 5:05.")]:
        assert compare(line, heard).diffs == [], (line, heard)
    assert "zero" not in words("It costs $1,000.")
