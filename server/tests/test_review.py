import json
from pathlib import Path

from je_server.review import sentence_key

CONTRACT = Path(__file__).resolve().parents[2] / "contract"


def test_sentence_keys_match_contract():
    for text, key in json.loads((CONTRACT / "sentence-keys.json").read_text(encoding="utf-8")):
        assert sentence_key(text) == key, text


# --- past situations and the first recording (spec 2, 4) -------------------------------------------------------

from je_server.models import Attempt, Frame, Roleplay, ScriptLine
from je_server.review import first_try, group_of, latest_run, past_items, spoken

LINES = [("ryan", "What can I get for you?"), ("user", "A small latte, please."), ("ryan", "Sure.")]


def make(rid, created, title="카페에서 주문하기", origin=None, tries=None, pos=0):
    """A made-up roleplay. tries: {idx: [(n, mode, followed, at), ...]}"""
    return Roleplay(
        id=rid, created=created, situation="카페", origin=origin, pos=pos,
        frame=Frame(title_ko=title, user_role_ko="손님", ryan_role_ko="점원", place_ko="카페", goal_ko="주문"),
        lines=[ScriptLine(idx=i, speaker=s, text=t) for i, (s, t) in enumerate(LINES)],
        attempts={idx: [Attempt(n=n, mode=m, heard="x", followed=f, issues=[], say_ko="", audio=[], timings={}, at=at)
                        for n, m, f, at in ts] for idx, ts in (tries or {}).items()})


A = "aaaaaaaaaaaa"
B = "bbbbbbbbbbbb"
C = "cccccccccccc"
SAID = {1: [(1, "turn", True, None)]}


def test_unspoken_roleplays_are_left_out():
    quiet = make(A, "2026-11-05T10:00:00")
    shadow_only = make(B, "2026-11-05T11:00:00", tries={0: [(1, "shadow", True, None)]})
    practice_only = make(C, "2026-11-05T12:00:00", tries={1: [(1, "practice", True, None)]})
    assert not spoken(quiet) and not spoken(shadow_only) and not spoken(practice_only)
    assert past_items([quiet, shadow_only, practice_only]) == []


def test_copies_make_one_row():
    rps = [make(A, "2026-11-05T10:00:00", tries=SAID), make(B, "2026-11-06T10:00:00", origin=A, tries=SAID),
           make(C, "2026-11-07T10:00:00", origin=A)]
    assert group_of(rps[1]) == A and group_of(rps[0]) == A
    assert past_items(rps) == [{"group": A, "title_ko": "카페에서 주문하기", "first": "2026-11-05",
                                "latest": "2026-11-06T10:00:00"}]


def test_same_title_other_script_is_another_row():
    rps = [make(A, "2026-11-05T10:00:00", tries=SAID), make(B, "2026-11-05T11:00:00", tries=SAID)]
    assert [i["group"] for i in past_items(rps)] == [B, A]


def test_rows_newest_first():
    rps = [make(A, "2026-11-06T10:00:00", title="길 묻기", tries=SAID),
           make(B, "2026-11-05T10:00:00", tries=SAID), make(C, "2026-11-07T10:00:00", origin=B, tries=SAID)]
    assert [i["group"] for i in past_items(rps)] == [B, A]


def test_latest_is_newest_spoken_run():
    rps = [make(A, "2026-11-05T10:00:00", tries=SAID), make(B, "2026-11-06T10:00:00", origin=A, tries=SAID),
           make(C, "2026-11-07T10:00:00", origin=A)]
    assert latest_run(rps, A).id == B
    assert latest_run(rps, "dddddddddddd") is None and latest_run([rps[2]], A) is None


def test_first_try_is_from_the_earlier_run():
    first = make(A, "2026-11-05T10:00:00", tries={1: [(1, "turn", True, "2026-11-05T10:01:00")]})
    again = make(B, "2026-11-06T10:00:00", origin=A, tries={1: [(1, "turn", True, "2026-11-06T10:01:00")]})
    assert first_try([first, again], again, 1) == {"rp_id": A, "idx": 1, "n": 1}
    assert first_try([first, again], first, 1) is None


def test_first_try_skips_offscript_and_ryan():
    first = make(A, "2026-11-05T10:00:00", tries={1: [(1, "turn", False, "2026-11-05T10:01:00")],
                                                  2: [(1, "shadow", True, "2026-11-05T10:02:00")]})
    again = make(B, "2026-11-06T10:00:00", origin=A, tries={1: [(1, "turn", True, "2026-11-06T10:01:00")]})
    assert first_try([first, again], again, 1) is None
    assert first_try([first, again], again, 2) is None


def test_first_try_by_time_not_run_order():
    # the first run's line was saved and practised on 11-08, after the copy's turn on 11-06
    first = make(A, "2026-11-05T10:00:00", tries={1: [(1, "practice", True, "2026-11-08T10:00:00")]})
    again = make(B, "2026-11-06T10:00:00", origin=A, tries={1: [(1, "turn", True, "2026-11-06T10:01:00")]})
    assert first_try([first, again], again, 1) is None
    assert first_try([first, again], first, 1) == {"rp_id": B, "idx": 1, "n": 1}


def test_first_try_falls_back_to_created():
    first = make(A, "2026-11-05T10:00:00", tries={1: [(1, "turn", True, None)]})
    again = make(B, "2026-11-06T10:00:00", origin=A, tries={1: [(1, "turn", True, "2026-11-06T10:01:00")]})
    assert first_try([first, again], again, 1) == {"rp_id": A, "idx": 1, "n": 1}


def test_first_try_never_from_this_run():
    """「처음 하는 회차에는 나오지 않는다」 (spec 4): an off-script turn, then a practice in the same run (final review)."""
    run = make(A, "2026-11-05T10:00:00", tries={1: [(1, "turn", False, "2026-11-05T10:01:00"),
                                                (2, "practice", True, "2026-11-05T10:05:00")]})
    assert first_try([run], run, 1) is None


def test_first_try_not_from_the_same_sentence_in_this_run():
    twice = make(A, "2026-11-05T10:00:00", tries={1: [(1, "turn", True, "2026-11-05T10:01:00")]})
    twice.lines.append(ScriptLine(idx=3, speaker="user", text="A small latte, please!"))
    twice.attempts[3] = [Attempt(n=1, mode="turn", heard="x", followed=True, issues=[], say_ko="", audio=[],
                                 timings={}, at="2026-11-05T10:03:00")]
    assert first_try([twice], twice, 3) is None


def test_aside_only_run_is_not_a_past_situation():
    run = make(A, "2026-11-05T10:00:00", tries={1: [(1, "turn", False, None)]})
    run.attempts[1][0].aside = True
    assert not spoken(run) and past_items([run]) == []


# --- the conversation to resume (spec resume-roleplay 1, 2) -----------------------------------------------------

from je_server.review import said_before, to_resume


def test_to_resume_is_the_newest_roleplay_with_my_line_left():
    old, new = make(A, "2026-11-05T10:00:00"), make(B, "2026-11-06T10:00:00", pos=1)
    assert to_resume([new, old]).id == B


def test_no_resume_when_the_newest_is_done():
    # an older conversation left midway is not looked for (spec 1)
    old, new = make(A, "2026-11-05T10:00:00"), make(B, "2026-11-06T10:00:00", pos=2, tries=SAID)
    assert to_resume([old, new]) is None


def test_no_resume_without_records():
    assert to_resume([]) is None


def test_no_resume_after_the_last_line_is_mine_and_done():
    rp = make(A, "2026-11-05T10:00:00", pos=2)
    rp.lines = rp.lines[:2]  # Ryan, me: I end the conversation
    assert to_resume([rp]) is None and to_resume([rp.model_copy(update={"pos": 1})]).id == A


def test_said_before_takes_the_last_roleplay_try():
    rp = make(A, "2026-11-05T10:00:00", tries={1: [(1, "turn", True, None), (2, "retry", True, None),
                                                   (3, "practice", True, None)]})
    assert said_before(rp, 2) == [{"idx": 1, "heard": "x", "n": 2}]
    assert said_before(rp, 1) == [] and said_before(make(B, "2026-11-05T10:00:00"), 2) == []  # skipped: no try


def test_said_before_leaves_out_asides():
    rp = make(A, "2026-11-05T10:00:00", tries={1: [(1, "turn", True, None)]})
    rp.attempts[1].append(rp.attempts[1][0].model_copy(update={"n": 2, "aside": True, "followed": False}))
    assert said_before(rp, 2) == [{"idx": 1, "heard": "x", "n": 1}]
