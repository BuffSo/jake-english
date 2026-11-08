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

from je_server.review import resume_start, said_on, to_resume, unrecorded


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
    rp = make(A, "2026-11-05T10:00:00", pos=2, tries=SAID)
    rp.lines = rp.lines[:2]  # Ryan, me: I end the conversation
    assert to_resume([rp]) is None and to_resume([rp.model_copy(update={"attempts": {}})]).id == A


def test_said_on_takes_the_last_roleplay_try():
    rp = make(A, "2026-11-05T10:00:00", tries={1: [(1, "turn", True, None), (2, "retry", True, None),
                                                   (3, "practice", True, None)]})
    assert said_on(rp) == [{"idx": 1, "heard": "x", "n": 2}]
    assert said_on(make(B, "2026-11-05T10:00:00")) == []  # skipped: no try


def test_said_on_leaves_out_asides():
    rp = make(A, "2026-11-05T10:00:00", tries={1: [(1, "turn", True, None)]})
    rp.attempts[1].append(rp.attempts[1][0].model_copy(update={"n": 2, "aside": True, "followed": False}))
    assert said_on(rp) == [{"idx": 1, "heard": "x", "n": 1}]


# --- lines of mine left unrecorded (spec resume-unrecorded 1, 3) ---------------------------------------------------


def seven(pos, said):
    """Ryan and me in turn, Ryan first and last: R0 U1 R2 U3 R4 U5 R6. `said`: my lines with a followed turn."""
    rp = make(A, "2026-11-05T10:00:00", pos=pos, tries={i: [(1, "turn", True, None)] for i in said})
    rp.lines = [ScriptLine(idx=i, speaker="ryan" if i % 2 == 0 else "user", text=f"Line number {i}.")
                for i in range(7)]
    return rp


def test_practice_and_asides_are_not_recorded():
    rp = make(A, "2026-11-05T10:00:00", pos=2, tries={1: [(1, "practice", True, None)]})
    assert unrecorded(rp) == [1] and to_resume([rp]).id == A
    rp.attempts[1].append(Attempt(n=2, mode="turn", heard="x", followed=False, issues=[], say_ko="", audio=[],
                                  timings={}, aside=True))
    assert unrecorded(rp) == [1]


def test_a_conversation_gone_to_the_end_with_a_skipped_line_is_resumed():
    rp = make(A, "2026-11-05T10:00:00", pos=2)  # my only line skipped: the place moved past it
    assert to_resume([rp]).id == A and resume_start(rp) == (0, True)


def test_no_resume_when_every_line_of_mine_was_recorded():
    assert to_resume([make(A, "2026-11-05T10:00:00", pos=2, tries=SAID)]) is None
    assert to_resume([seven(pos=2, said=[1, 3, 5])]) is None  # recorded, whatever the place says


def test_gone_to_the_end_starts_at_the_ryan_line_before_the_first_unrecorded():
    assert resume_start(seven(pos=6, said=[3])) == (0, True)  # U1, U5 unrecorded
    assert resume_start(seven(pos=6, said=[1])) == (2, True)  # U3, U5 unrecorded


def test_midway_resumes_at_pos_past_an_earlier_skip():
    assert resume_start(seven(pos=4, said=[3])) == (4, False)  # U1 skipped, U3 said, left before U5


def test_start_passes_a_recorded_line_after_pos():
    assert resume_start(seven(pos=2, said=[1, 3])) == (4, False)  # U3's try stayed under pos (Ryan's voice cut)


def test_i_speak_first_from_my_first_line():
    # U0 R1 U2 R3: a skipped first line of mine has no Ryan line before it (spec resume-unrecorded 3)
    rp = seven(pos=4, said=[1])
    rp.lines = [ScriptLine(idx=i, speaker="user" if i % 2 == 0 else "ryan", text=f"Line number {i}.") for i in range(4)]
    rp.attempts = {2: rp.attempts[1]}
    assert resume_start(rp) == (0, True)
    rp.pos, rp.attempts = 1, {}  # U0 skipped, left before U2
    assert resume_start(rp) == (1, False)


def test_said_on_takes_every_recorded_line():
    assert [s["idx"] for s in said_on(seven(pos=6, said=[1, 5]))] == [1, 5]


def test_a_talk_is_not_a_past_situation():
    from fakes import talk_example

    talk = talk_example()
    assert past_items([talk]) == []
    assert latest_run([talk], talk.id) is None


def test_resume_skips_a_newer_talk():
    from fakes import talk_example

    rp = make(A, "2026-11-08T09:00:00")
    talk = talk_example().model_copy(update={"created": "2026-11-08T10:00:00"})
    assert to_resume([talk, rp]).id == A
    assert to_resume([talk]) is None
