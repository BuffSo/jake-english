"""scripts/check_ryan_wording.py: the live wording check's own bookkeeping (PR #32 review)."""
import importlib.util
import sys
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "check_ryan_wording", Path(__file__).resolve().parent.parent / "scripts" / "check_ryan_wording.py")
cw = importlib.util.module_from_spec(_spec)
sys.modules["check_ryan_wording"] = cw  # dataclasses look the module up while the script loads
_spec.loader.exec_module(cw)


def test_every_model_the_server_can_pick_has_a_price():
    # with JE_CLAUDE_WRITER=opus the run made every paid call and then died on the cost sum (KeyError)
    from je_server.claude import QUICKS, WRITERS

    assert {m["model"] for m in (*WRITERS.values(), *QUICKS.values())} <= set(cw.PRICE)


def test_double_quotes_are_checked_on_the_model_answer():
    # the server drops double quotes from what the learner sees, so the check looks at the model's own text
    case = cw.Case("q", "Can I get a room?", "Can I get a loom?", [cw.issue("room", "loom")], [cw.REST])
    shown = "나머지 낱말은 다 알아들었어요. 그런데 room이 loom처럼 들렸어요. 한 번 더 해 볼까요?"
    said = shown.replace("room이 loom", '"room"이 "loom"')
    assert "double quotes" in cw.flags(case, shown, aside=False, raw=said)
    assert cw.flags(case, shown, aside=False, raw=shown) == []


def test_aside_flags_the_sorting_and_a_missing_retry():
    # phone test 2026-11-08: teacher Ryan told the learner how the server had sorted the recording, and stopped there
    case = next(c for c in cw.ASIDE if c.name == "off app wish")
    bad = "대사와 상관없는 말로 들려서 따로 짚을 곳이 없어요."
    assert {"names '짚을'", "names '상관없는'", "does not ask to try again"} <= set(cw.flags(case, bad, aside=True))
    # the prompt before this fix, live: the sort's own words, which the check first missed
    assert "names '혼잣말'" in cw.flags(case, "대사와 상관없는 혼잣말로 들렸어요. 한 번 더 해 볼까요?", aside=True)
    good = "그렇군요, 그런 게 있으면 편하겠어요. 다시 해 볼까요?"
    assert cw.flags(case, good, aside=True) == []
    # spec record-cancel-skip 6: a line can be skipped now, so the old example's 「대사를 말해야 넘어가요」 is wrong
    old = "그렇군요, 그런 게 있으면 편하겠어요. 지금은 대사를 말해야 다음으로 넘어가요. 다시 해 볼까요?"
    assert cw.flags(case, old, aside=True) == ["says '말해야'"]


def test_aside_flags_a_skip_wish_without_the_skip_button():
    # spec record-cancel-skip 6: wanting to move past the line gets 「건너뛰기」 named
    case = next(c for c in cw.ASIDE if c.name == "off skip wish")
    assert cw.flags(case, "괜찮아요. 다시 해 볼까요?", aside=True) == ["does not say '건너뛰기'"]
    good = "「건너뛰기」를 누르면 녹음하지 않고 다음으로 넘어가요. 아니면 한 번 더 해 볼까요?"
    assert cw.flags(case, good, aside=True) == []


def test_a_tip_cut_in_half_is_flagged():
    # todo 20: teacher Ryan said only the R half of the R and L tip; the check looked for 「닿」, which both halves have
    case = next(c for c in cw.ASIDE if c.name == "near miss tip")
    point = "room이 loom처럼, tenth가 tent처럼 들렸어요. "
    half = point + "R은 혀가 어디에도 닿지 않게 하고 입술을 살짝 동그랗게 모아요. 한 번 더 해 볼까요?"
    assert "tip cut (room)" in cw.flags(case, half, aside=True)
    whole = point + cw.RL + " 한 번 더 해 볼까요?"
    assert not [f for f in cw.flags(case, whole, aside=True) if f.startswith("tip")]
    assert "tip dropped (room)" in cw.flags(case, point + "한 번 더 해 볼까요?", aside=True)
    # one tip for two words is said once, whole: nothing cut
    twice = next(c for c in cw.FEEDBACK if c.name == "same tip twice")
    once = "나머지 낱말은 다 알아들었어요. 그런데 fried가 flied처럼, rice가 lice처럼 들렸어요. " + cw.RL + " 한 번 더 해 볼까요?"
    assert cw.flags(twice, once, aside=False) == []


def test_a_reworded_tip_is_flagged():
    # todo 29: Haiku said both halves of the R and L tip but in another order and its own words; the halves check let it by
    case = next(c for c in cw.FEEDBACK if c.name == "tip")
    point = "나머지 낱말은 다 알아들었어요. 그런데 room이 loom처럼 들렸어요. "
    swapped = point + "R은 혀가 어디에도 닿지 않게 하고 입술을 살짝 동그랗게 모으지만, L은 혀끝이 윗잇몸에 닿아요. 한 번 더 해 볼까요?"
    assert cw.flags(case, swapped, aside=False) == ["tip reworded (room)"]


def test_spacing_does_not_count_as_rewording():
    case = next(c for c in cw.FEEDBACK if c.name == "tip")
    spaced = "그런데 room이 loom처럼 들렸어요.\n" + cw.RL.replace(" ", "  ", 1) + " 한 번 더 해 볼까요?"
    assert not [f for f in cw.flags(case, spaced, aside=False) if f.startswith("tip")]


def test_a_tip_said_twice_is_flagged():
    # todo 29: the R half first in Ryan's own words, then the whole tip
    case = next(c for c in cw.FEEDBACK if c.name == "tip")
    point = "그런데 room이 loom처럼 들렸어요. "
    own = point + "R은 입술을 동그랗게 모아야 해요. " + cw.RL + " 한 번 더 해 볼까요?"
    assert "tip repeated (room)" in cw.flags(case, own, aside=False)
    assert "tip repeated (room)" in cw.flags(case, point + cw.RL + " " + cw.RL + " 한 번 더 해 볼까요?", aside=False)
    # one tip for two words, said once: clean
    twice = next(c for c in cw.FEEDBACK if c.name == "same tip twice")
    once = "나머지 낱말은 다 알아들었어요. 그런데 fried가 flied처럼, rice가 lice처럼 들렸어요. " + cw.RL + " 한 번 더 해 볼까요?"
    assert cw.flags(twice, once, aside=False) == []


def test_a_made_up_tip_is_flagged():
    # todo 29: a word that was not heard, with no tip from the Mac, got an F tip anyway
    case = next(c for c in cw.FEEDBACK if c.name == "dropped")
    point = "나머지 낱말은 다 알아들었어요. 그런데 by가 들리지 않았어요. "
    made = point + "F는 윗니를 아랫입술에 대고 바람을 내보내요. 한 번 더 해 볼까요?"
    assert cw.flags(case, made, aside=False) == ["tip made up"]
    assert cw.flags(case, point + "한 번 더 해 볼까요?", aside=False) == []
    # a given tip beside a word without one is not made up
    second = next(c for c in cw.FEEDBACK if c.name == "tip second")
    ok = "나머지 낱말은 다 알아들었어요. 그런데 on이 들리지 않았고, red가 led처럼 들렸어요. " + cw.RL + " 한 번 더 해 볼까요?"
    assert cw.flags(second, ok, aside=False) == []


def test_a_sound_named_outside_the_tip_is_flagged():
    # todo 29: 「두 낱말 모두 R이 L로 들린 것이에요」 put before the tip
    case = next(c for c in cw.FEEDBACK if c.name == "same tip twice")
    framed = "그런데 fried가 flied처럼, rice가 lice처럼 들렸어요. 두 낱말 모두 R이 L로 들린 것이에요. " + cw.RL + " 한 번 더 해 볼까요?"
    assert cw.flags(case, framed, aside=False) == ["sound named (fried)"]
    # a praise that names a sound, with no tip given, is fine
    improved = next(c for c in cw.FEEDBACK if c.name == "improved")
    said = "이번에는 right의 R 소리가 제대로 났어요. 그런데 on이 들리지 않았어요. 한 번 더 해 볼까요?"
    assert cw.flags(improved, said, aside=False) == []


def test_every_listed_tip_has_halves_and_cases():
    # a tip changed in data/sounds.json leaves the halves check looking for words that are gone
    from je_server import sounds

    for s in sounds.SOUNDS:
        first, second = s.explain.split("지만, ", 1)
        a, b = cw.TIP_HALVES[s.explain]
        assert a in first and a not in second and b in second and b not in first, s.name
        for cases in (cw.FEEDBACK, cw.ASIDE):
            assert any(i.explain == s.explain for c in cases for i in c.issues), s.name
