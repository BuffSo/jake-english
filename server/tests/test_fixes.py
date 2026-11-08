"""The corrections after a free talk: what the Mac keeps of what Claude picked (spec free-talk-design 7)."""
from fakes import talk_example
from je_server import sounds
from je_server.fixes import MAX_FIXES, Found, check, line_before

TURNS = {1: "I walked to the park with my dog.", 3: "Yesterday I go to the market.",
         5: "I turned light at the bank.", 7: "I had a cat on my finger."}


def item(idx, said, fixed, why="바꿔요.", heard="", meant="", say=""):
    return {"idx": idx, "said": said, "fixed": fixed, "why_ko": why,
            "sound": {"heard": heard, "meant": meant, "say_ko": say}}


def test_items_beyond_three_are_dropped():
    items = [item(7, "I had a cat on my finger.", "I had a cat on my finger now."),
             item(1, "I walked to the park with my dog.", "I went to the park with my dog."),
             item(3, "Yesterday I go to the market.", "Yesterday I went to the market."),
             item(5, "I turned light at the bank.", "I turned at the bank.")]
    assert MAX_FIXES == 3
    assert [f.of for f in check(items, TURNS)] == [1, 3, 5]


def test_an_item_on_a_line_that_is_not_my_english_turn_is_dropped():
    items = [item(2, "I walked to the park with my dog.", "I went to the park with my dog."),
             item(9, "Yesterday I go to the market.", "Yesterday I went to the market.")]
    assert check(items, TURNS) == []


def test_one_item_per_turn():
    items = [item(3, "Yesterday I go to the market.", "Yesterday I went to the market.", why="첫째예요."),
             item(3, "Yesterday I go to the market.", "I went to the market yesterday.", why="둘째예요.")]
    assert check(items, TURNS) == [Found(3, "Yesterday I go to the market.", "Yesterday I went to the market.", "첫째예요.")]


def test_said_must_be_in_the_turn():
    assert check([item(3, "I eat lunch.", "I ate lunch.")], TURNS) == []
    assert check([item(3, "", "I ate lunch.")], TURNS) == []
    [f] = check([item(3, "yesterday, I GO to the market", "Yesterday I went to the market.")], TURNS)
    assert f.of == 3


def test_fixed_over_twelve_words_or_unchanged_is_dropped():
    long = "Yesterday I went to the market and bought some fresh apples and pears there"  # 14 words
    assert check([item(3, "Yesterday I go to the market.", long)], TURNS) == []
    assert check([item(3, "Yesterday I go to the market.", "yesterday i go to the market")], TURNS) == []
    assert check([item(3, "Yesterday I go to the market.", "")], TURNS) == []


def test_a_listed_sound_guess_adds_the_list_words():
    [f] = check([item(5, "I turned light at the bank.", "I turned right at the bank.", why="",
                      heard="light", meant="right", say="right가 light처럼 들렸어요.")], TURNS)
    assert f.why_ko == "right가 light처럼 들렸어요. " + sounds.find("R", "L").explain
    assert f.fixed == "I turned right at the bank."


def test_an_unlisted_guess_is_dropped_and_its_item_too_without_other_fixes():
    guess = dict(heard="cat", meant="cut", say="cut가 cat처럼 들렸어요.")
    assert check([item(7, "I had a cat on my finger.", "I had a cut on my finger.", why="", **guess)], TURNS) == []
    [f] = check([item(7, "I had a cat on my finger.", "I had a cut on my finger.", why="다른 낱말이에요.", **guess)], TURNS)
    assert "처럼 들렸" not in f.why_ko and f.why_ko == "다른 낱말이에요."


def test_a_guess_that_says_what_was_said_is_dropped():
    assert check([item(5, "I turned light at the bank.", "I turned right at the bank.", why="",
                       heard="light", meant="right", say="light라고 말했어요.")], TURNS) == []


def test_a_guess_whose_heard_word_is_not_in_the_sentence_is_dropped():
    assert check([item(5, "I turned light at the bank.", "I turned right at the bank.", why="",
                       heard="late", meant="rate", say="rate가 late처럼 들렸어요.")], TURNS) == []


def test_line_before_a_fix_is_ryans_line_before_the_turn():
    rp = talk_example()
    assert line_before(rp, 7).idx == 4  # the fix's turn is 5; the line before it is 4, not 6
    assert line_before(rp, 3).idx == 2
    assert line_before(rp, 0) is None


def test_line_before_skips_ryans_help_line():
    rp = talk_example()
    assert rp.lines[2].kind == "help"
    moved = rp.lines[3].model_copy(update={"fix": rp.lines[7].fix.model_copy(update={"of": 3})})
    rp.lines[7] = moved.model_copy(update={"idx": 7})
    # the turn it fixes (3) comes right after Ryan's help line (2): the line before is Ryan's opener (0)
    assert line_before(rp, 7).idx == 0


def test_a_guess_whose_say_is_the_unfilled_template_is_dropped():
    guess = dict(heard="light", meant="right", say="meant가 heard처럼 들렸어요.")
    assert check([item(5, "I turned light at the bank.", "I turned right at the bank.", why="", **guess)], TURNS) == []
    [f] = check([item(5, "I turned light at the bank.", "I turned right at the bank.", why="방향이에요.", **guess)], TURNS)
    assert f.why_ko == "방향이에요."
