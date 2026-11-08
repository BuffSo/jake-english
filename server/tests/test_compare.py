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


def test_far_apart_word_pair_gets_no_sound():
    # a number written as an unrelated word swaps several sounds; one of them (F, P) is on the list, but it is not a
    # sound the learner changed (guide 「남은 것」, 2026-11-07). Same limit as inside a span whose word count changed.
    [i] = compare("It's fifteen dollars.", "It's pity dollars.").diffs  # three sounds apart
    assert (i.target, i.heard, i.sound, i.explain) == ("fifteen", "pity", None, "")
    [i] = compare("I'm running late.", "I'm learning late.").diffs  # two sounds apart (R/L, AH/ER): still a tip
    assert set(i.sound) == {"R", "L"} and "혀" in i.explain


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
    # 「도」 fits every word: 이 or 가 would depend on how the word ends in Korean (the user's choice, 2026-11-08)
    assert issue_ko(Issue(target="", heard="and")) == "대사에 없는 「and」도 들렸어요"


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


def test_numbers_past_ninety_nine_are_not_differences():
    for line, heard in [("It is one thousand dollars.", "It is $1,000."),
                        ("That's one hundred twenty.", "That's 120."),
                        ("We sold two thousand five hundred cups.", "We sold 2,500 cups.")]:
        assert compare(line, heard).diffs == [], (line, heard)
    assert compare("Room 305, please.", "Room 305, please.").diffs == []


def test_fillers_written_in_the_line_are_not_points():
    assert compare("Um, can I pay by card?", "Can I pay by card?").diffs == []
    assert praise_candidates("Hmm, I think I'll have the soup.", "I think I'll have the soup.", []) == [
        "대사를 빠짐없이 알아듣게 말했어요"]


def test_a_hundred_a_dollar_and_ordinals_are_notation():
    for line, heard in [("It costs a hundred dollars.", "It costs $100."),
                        ("Do you take a dollar fifty?", "Do you take $1.50?"),
                        ("We waited a thousand years.", "We waited 1,000 years."),
                        ("It's on the 2nd floor.", "It's on the second floor."),
                        ("My room is on the twenty-first floor.", "My room is on the 21st floor."),
                        ("Turn left at the 3rd light.", "Turn left at the third light.")]:
        assert compare(line, heard).diffs == [], (line, heard)


def test_added_word_left_out_this_time_is_praised():
    before = [Issue(target="", heard="and")]
    praise = praise_candidates("Wait here, then come in.", "Wait here, then come in.", before)
    assert praise[0] == "이번에는 and 없이 대사대로 들렸어요"
    still = praise_candidates("Wait here, then come in.", "Wait here, and then come in.", before)
    assert not any(p.startswith("이번에는") for p in still)


def test_a_number_said_in_pairs_matches_its_digits():
    # the voice read the shoe size 270 as "two seventy" and the learner followed it (phone test, 2026-11-07)
    for line, heard in [("I wear 270 in Korea.", "I wear two seventy in Korea."),
                        ("I wear two seventy in Korea.", "I wear 270 in Korea."),
                        ("I wear 270 in Korea.", "I wear two hundred seventy in Korea."),
                        ("I wear 270 in Korea.", "I wear 270 in Korea."),
                        ("Room 305, please.", "Room three oh five, please."),
                        ("I was born in 1990.", "I was born in nineteen ninety."),
                        ("It was 2017.", "It was twenty seventeen."),
                        ("It costs 1500 won.", "It costs fifteen hundred won.")]:
        assert compare(line, heard).diffs == [], (line, heard)
    assert similarity("I wear 270 in Korea.", "I wear two seventy in Korea.") == 1.0
    assert words("I wear 270.") == ["i", "wear", "two", "hundred", "seventy"]  # read one way when nothing to fit


def test_a_real_point_next_to_a_number_has_no_hundred_in_it():
    # the phone test: "hundred" was part of the point though no one said or heard it
    issues = compare("I wear 270 in Korea.", "I well two seventy in Korea.").diffs
    assert [(i.target, i.heard, set(i.sound or ())) for i in issues] == [("wear", "well", {"R", "L"})]


def test_words_that_sound_the_same_are_notation():
    # the transcriber may write "to" for "two": they sound the same, so there is nothing to say
    assert compare("I wear two seventy.", "I wear to seventy.").diffs == []
    assert compare("Is this for me?", "Is this four me?").diffs == []


# --- following by the matched words, and restarts (todo follow-feedback leftovers 1, 2) ------------------------

def test_a_short_line_split_into_two_words_is_still_followed():
    # the Mac matches joined words, fillers and restarts, so following is judged on that match too: a two-word line
    # written as three words by the transcriber fell under FOLLOW_MIN before
    assert similarity("Downstairs, please.", "Down stairs, please.") == 1.0
    assert similarity("We need two tickets.", "We need, we need two tickets.") == 1.0
    assert similarity("We need two tickets.", "Um, we need two tickets.") == 1.0


def test_similarity_of_plain_differences_is_as_before():
    # one word out of four: (3 + 3) / (4 + 4), what the word match gave before
    assert similarity("We need two tickets.", "We need three tickets.") == 0.75
    assert similarity("Turn left here.", "Sorry, I am new here.") < FOLLOW_MIN


def test_a_word_said_again_and_again_is_a_restart():
    assert find_issues("We need two tickets.", "We, we, we need two tickets.", limit=2) == []
    assert find_issues("We need two tickets.", "We need, we need, we need two tickets.", limit=2) == []


def test_a_start_that_went_wrong_and_was_said_again_is_a_restart():
    # the words before the restart came out wrong, but the learner said them again as written
    assert find_issues("Could I see the menu?", "Could I sit the, could I see the menu?", limit=2) == []


def test_a_word_added_inside_the_line_is_still_a_point():
    assert find_issues("We need two tickets.", "We need two more tickets.", limit=2) == [
        Issue(target="", heard="more")]
    # not a try at the words after it: another first word
    assert find_issues("Could I see the menu?", "Please, could I see the menu?", limit=2) == [
        Issue(target="", heard="please")]


# --- the end screen's words, and notation (todo follow-feedback leftovers 3, 5) --------------------------------

def test_issue_ko_shows_the_words_as_written():
    # the Mac compares in lowercase; the end screen shows a word the way the line or the transcript writes it
    assert issue_ko(Issue(target="i", heard="eye"), "Can I see the menu?", "Can eye see the menu?") == (
        "「I」 → 「eye」처럼 들렸어요")
    assert issue_ko(Issue(target="", heard="boston"), "We need two tickets.", "We need two Boston tickets.") == (
        "대사에 없는 「Boston」도 들렸어요")
    # written both ways in the line, or not written at all (a number read out): left as compared
    assert issue_ko(Issue(target="please", heard=""), "Please, please wait.", "Please wait.") == (
        "「please」 → 들리지 않았어요")
    assert issue_ko(Issue(target="ten", heard="tin"), "Wait 10 minutes.", "Wait tin minutes.") == (
        "「ten」 → 「tin」처럼 들렸어요")


def test_numbers_of_a_million_and_more_are_notation():
    assert words("2,500,000") == "two million five hundred thousand".split()
    assert compare("It sold 1,000,000 copies.", "It sold one million copies.").diffs == []


def test_a_price_read_without_dollars_is_notation():
    # people read $5.99 as "five ninety-nine" too; the voice and the learner may do either
    for heard in ("It's five ninety-nine.", "It's five dollars ninety-nine.", "It's five dollars and ninety-nine cents.",
                  "It's $5.99."):
        assert similarity("It's $5.99.", heard) == 1.0, heard
    assert compare("That's $2.05.", "That's two oh five.").diffs == []
    assert compare("It's five ninety-nine.", "It's $5.99.").diffs == []
    assert compare("It's $5.99.", "It's five forty-nine.").diffs != []  # another price is still a point


# Names the dictionary does not have, compared by syllable (spec teacher-answer-context 3). The examples are made up or
# from the list scripts; none is how a name was written in the Mac's records (REVIEW.md).
import pytest  # noqa: E402

from je_server.compare import is_name, korean_said, romanize, same_name, syllables  # noqa: E402


def test_name_syllables():
    assert syllables("chungmuro") == [("ch", "u", "ng"), ("m", "u", ""), ("r", "o", "")]
    assert syllables("gyeongbokgung") == [("g", "yeo", "ng"), ("b", "o", "k"), ("g", "u", "ng")]
    assert [len(syllables(w)) for w in ("itaewon", "haeundae", "hangang", "yeouido")] == [3, 3, 2, 3]
    assert romanize("홍대") == "hongdae" and syllables(romanize("경복궁")) == syllables("gyeongbokgung")


def test_only_words_missing_from_the_dictionary_are_names():
    assert is_name("hongdae") and is_name("chungmuro")
    assert not is_name("palace") and not is_name("seoul") and not is_name("i'm") and not is_name("4")


@pytest.mark.parametrize("line,heard", [
    ("Get off at Sinchon.", "Get off at Sichon."),  # a final consonant left out
    ("Get off at Jamsil.", "Get off at Chamsil."),
    ("Get off at Hongdae.", "Get off at Hongde."),
    ("Get off at Hongdae.", "Get off at Hong Day."),
    ("Get off at Gyeongbokgung.", "Get off at Kyongbokkung."),
    ("Get off at Chungmuro.", "Get off at Choongmuro."),
    ("Let's go to Sinchon.", "Let's go to Shinchon."),
    ("Get off at Hapjeong.", "Get off at Habjung."),
    ("Let's meet at Jamsil.", "Let's meet at Jangsil."),  # one nasal final heard as another
    ("Meet me at Insadong.", "Meet me at Insa Dong."),
    ("Get off at Hongdae.", "Get off at 홍대."),
    ("Get off at Jongno.", "Get off at 종로."),  # written in Hangul as spelled, said with the sound change
])
def test_names_heard_alike_pass(line, heard):
    assert compare(line, heard).diffs == [] and similarity(line, heard) == 1.0
    assert not korean_said(line, heard)


@pytest.mark.parametrize("line,heard,said", [
    ("Get off at Chungmuro.", "Get off at Chungmugong.", "chungmugong"),  # a syllable more (the user's example)
    ("Meet me at Insadong.", "Meet me at Insa.", "insa"),  # a syllable less
    ("Get off at Jamsil.", "Get off at Jamsilsaenae.", "jamsilsaenae"),
    ("Get off at Hongdae.", "Get off at Hongik.", "hongik"),  # a syllable changed
    ("Meet me in Itaewon.", "Meet me in Itaewan.", "itaewan"),
    ("Get off at Chungmuro.", "Get off at 충무공.", "충무공"),
])
def test_names_heard_differently_are_pointed(line, heard, said):
    diffs = compare(line, heard).diffs
    assert len(diffs) == 1 and diffs[0].heard == said and diffs[0].explain == "" and diffs[0].sound is None
    assert not korean_said(line, heard)


def test_a_name_not_heard_is_pointed():
    assert [(d.target, d.heard) for d in compare("Get off at Hongdae.", "Get off at.").diffs] == [("hongdae", "")]


def test_hangul_at_the_name_is_not_korean():
    assert not korean_said("Get off at Hongdae.", "Get off at Hongdae.")
    assert not korean_said("Get off at Hongdae.", "Get off at 홍대.")
    assert korean_said("Get off at Hongdae.", "Get off at Hongdae 아 뭐였지")
    assert korean_said("Get off at Hongdae.", "아 몰라")
    assert korean_said("Get off here.", "Get off 여기")  # no name in the line
    # next to other words heard wrong, word for word
    assert not korean_said("Get off at Hongdae, please.", "Get of a 홍대 peace")
    assert korean_said("Get off at Hongdae, please.", "Get 아 a 홍대 peace")


@pytest.mark.parametrize("line,heard", [
    ("Get off at Hongdae.", "Get off at 홍대 맞나요?"),  # the name, then a question (PR #62 review)
    ("Take Line 2 and get off at Hongdae.", "Take line 2 and get off at 홍대 근데 이거 맞아요?"),
    ("Get off at Hongdae.", "Get off at 네"),  # Korean where the name goes
    ("Get off at Chungmuro.", "Get off at 어디였지"),
])
def test_korean_at_the_name_is_still_korean(line, heard):
    # the engine then treats the try as not followed, however close the English words are
    assert korean_said(line, heard)


@pytest.mark.parametrize("line,heard", [
    ("Get off at Chungmuro.", "Get off at 충무공."),  # a syllable changed: still a try at the name
    ("Get off at Chungmuro.", "Get off at 충무."),  # a syllable dropped
])
def test_hangul_like_the_name_is_a_try_at_it(line, heard):
    assert not korean_said(line, heard) and len(compare(line, heard).diffs) == 1
    # Korean outside the name: compared as before, without the Hangul
    assert compare("Get off at Hongdae.", "Get off at Hongdae 아 뭐였지").diffs == []
