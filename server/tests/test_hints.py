"""Sohee chance: the Mac's checks on a hint and the conversation Claude is given (spec free-talk-design 9). The
talks and answers are made up."""
import pytest

from je_server import hints
from je_server.models import Hint, Said, ScriptLine
from fakes import talk_example

MEANING = "주말에 보통 뭐 하는지 물어요."
STARTERS = ["I usually…", "This weekend I…", "Not much, just…"]
FULL = "I usually stay home and watch movies."


def answer(**changes) -> dict:
    """What Claude gives for a hint (prompts.HINT_SCHEMA), with `changes`."""
    return {"meaning_ko": MEANING, "starters": list(STARTERS), "full": FULL, **changes}


def test_check_keeps_a_good_hint():
    assert hints.check(answer()) == Hint(meaning_ko=MEANING, starters=STARTERS, full=FULL)


def test_check_normalizes_spaces_and_dots():
    starters = ["I usually …", "This  weekend I...", "Not much, just…"]
    got = hints.check(answer(meaning_ko=f'"{MEANING}\n"', starters=starters, full=f"“{FULL}”"))
    assert got == Hint(meaning_ko=MEANING, starters=STARTERS, full=FULL)


def test_check_keeps_apostrophes_and_takes_two_to_six_words():
    got = hints.check(answer(starters=["I'm not…", "Yes, I go there every…"], full="I’m not sure yet."))
    assert got is not None and got.starters == ["I'm not…", "Yes, I go there every…"]
    assert got.full == "I’m not sure yet."  # matched with the straight apostrophe of its starter


def test_check_matches_the_full_sentence_without_the_comma_and_case():
    got = hints.check(answer(starters=["Not really,…", "Yes, I…"], full="not really. I was busy."))
    assert got is not None and got.full == "not really. I was busy."


def test_check_keeps_a_meaning_of_eighty_letters():
    meaning = "가" * 79 + "."
    assert hints.check(answer(meaning_ko=meaning)).meaning_ko == meaning


@pytest.mark.parametrize("bad", [
    pytest.param(answer(starters=["I usually…"]), id="one_starter"),
    pytest.param(answer(starters=["I usually…", "I usually go to the park with…"]),
                 id="four_word_limit_broken_7_words"),  # 7 words, over the 6
    pytest.param(answer(starters=["I usually…", "I usually 집에…"]), id="hangul_in_starter"),
    pytest.param(answer(starters=["I usually", "This weekend I…"]), id="starter_without_dots"),
    pytest.param(answer(starters=["Yes…", "This weekend I…"]), id="one_word_starter"),
    pytest.param(answer(meaning_ko=""), id="empty_meaning"),
    pytest.param(answer(meaning_ko="He asks what you do on weekends."), id="english_only_meaning"),
    pytest.param(answer(meaning_ko="가" * 81), id="meaning_over_80_chars"),
    pytest.param(answer(full="On weekends I stay home."), id="full_not_from_a_starter"),
    pytest.param(answer(full="I usually stay home and watch movies with my family on Saturday nights."),
                 id="full_over_12_words"),
    pytest.param(answer(full="I usually 집에 있어요."), id="hangul_in_full"),
    pytest.param(answer(starters="I usually…"), id="starters_not_a_list"),
    pytest.param(answer(starters=["I usually…", 3]), id="starter_not_text"),
    pytest.param({"meaning_ko": MEANING, "starters": STARTERS}, id="no_full"),
    pytest.param(None, id="not_json"),
    pytest.param([answer()], id="not_an_object"),
])
def test_check_drops_a_bad_hint(bad):
    assert hints.check(bad) is None


def test_check_keeps_the_first_three_starters():
    got = hints.check(answer(starters=[*STARTERS, "저는…"]))
    assert got is not None and got.starters == STARTERS
    # the full sentence starts with a starter the learner is shown
    assert hints.check(answer(starters=[*STARTERS, "On weekends I…"], full="On weekends I stay home.")) is None


def _talk(*lines: ScriptLine):
    rp = talk_example()
    rp.lines = [line.model_copy(update={"idx": i}) for i, line in enumerate(lines)]
    return rp


def _line(speaker: str, kind: str, text: str, **more) -> ScriptLine:
    return ScriptLine(idx=0, speaker=speaker, kind=kind, text=text, **more)


def test_conversation_is_text_only_and_stops_at_the_line():
    cut = ["Oh, nice!", "Who did you go with?"]
    rp = _talk(
        _line("ryan", "reply", "Hi! What did you do today?"),
        _line("user", "turn", "I go park."),
        _line("ryan", "help", "Could you try that in English?"),  # an old record's fixed line
        _line("user", "ask", "공원에 갔다고 어떻게 말해요?"),
        _line("ryan", "reply", " ".join(cut), parts=[Said(text=s, audio="a" * 64) for s in cut], heard_upto=1),
        _line("user", "turn", "My friend."),
        _line("ryan", "reply", "Cool! What did you eat?", audio="b" * 64),
        _line("user", "turn", "Pizza."),
        _line("ryan", "reply", "Yum! Was it good?"),
    )
    assert hints.conversation(rp, 6) == [
        {"말한 사람": "라이언", "말": "Hi! What did you do today?"},
        {"말한 사람": "학습자", "말": "I go park."},
        {"말한 사람": "학습자", "말": "공원에 갔다고 어떻게 말해요?"},  # my Korean turn as it was heard
        {"말한 사람": "라이언", "말": "Oh, nice!"},  # cut off: what I heard of it
        {"말한 사람": "학습자", "말": "My friend."},
        {"말한 사람": "라이언", "말": "Cool! What did you eat?"},
    ]


def test_conversation_leaves_out_fixes_and_a_reply_cut_before_a_word():
    rp = _talk(
        _line("ryan", "reply", "Hi! What did you do today?"),
        _line("user", "turn", "I go park."),
        _line("ryan", "reply", "Nice!", parts=[Said(text="Nice!", audio="a" * 64)], heard_upto=0),
        _line("user", "turn", "It was fun."),
        _line("ryan", "reply", "Great!"),
        _line("user", "fix", "I went to the park."),
    )
    assert [c["말"] for c in hints.conversation(rp, 5)] == ["Hi! What did you do today?", "I go park.", "It was fun.",
                                                           "Great!"]


def test_hide_unshown_drops_the_full_sentence_until_it_is_shown():
    unshown = {"meaning_ko": MEANING, "starters": STARTERS, "full": FULL, "audio": None, "full_shown": False,
               "full_three": None}
    shown = {**unshown, "full_shown": True}
    answer_ = {"roleplay": {"lines": [{"idx": 0, "hint": unshown}, {"idx": 1, "hint": None},
                                      {"idx": 2, "hint": shown}]},
               "summary": {"lines": [{"line": {"idx": 0, "hint": unshown}}]}}
    got = hints.hide_unshown(answer_)
    kept = {k: v for k, v in unshown.items() if k not in ("full", "full_three")}
    assert got["roleplay"]["lines"] == [{"idx": 0, "hint": kept}, {"idx": 1, "hint": None}, {"idx": 2, "hint": shown}]
    assert got["summary"]["lines"][0]["line"]["hint"] == kept
    assert answer_["roleplay"]["lines"][0]["hint"]["full"] == FULL  # the dump given is not changed
