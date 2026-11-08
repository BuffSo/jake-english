# 라이언의 소리 설명 고치기 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 따라 말한 뒤의 피드백(Haiku)이 받은 소리 설명을 그대로 한 번만 말하고 받지 않은 설명을 지어내지 않게 하고, 소리 설명 목록 여섯 쌍을 사람이 검토한 글로 바꾼다.

**Architecture:** 실제 모델 검사 스크립트(`check_ryan_wording.py`)가 먼저 「그대로인지」까지 보게 고친 뒤 잰다. 잦으면 `FEEDBACK_SYSTEM`에 할 일 20의 고침(`ASIDE_SYSTEM`)을 같은 말로 옮긴다. 소리 목록은 카드가 쌍마다 초안을 만들어 main 세션을 거쳐 사용자가 정하고, 정한 글을 `sounds.json`에 넣은 뒤 두 라이언이 그 글을 그대로 말하는지 실제 모델로 본다.

**Tech Stack:** Python 3(서버), pytest, Anthropic API(Haiku 5.5 피드백, Sonnet 5.5 선생님 라이언)

**Spec:** `docs/superpowers/specs/2026-11-05-speaking-practice-design.md` 「평가」 4, 7과 「소리 설명 목록」. 할 일(원래 폴더, untracked): `docs/todo/20261108_29_todo_feedback_tip_reworded.md`, `docs/todo/20261105_08_todo_sound_list_review.md`. 앞선 고침: `docs/devlog/2026-11-08-small-sweep.md`(할 일 20).

## Global Constraints

- 시험 문장과 예는 지어낸다. 맥의 기록, 받아쓰기, 사용자가 연습한 대사, 그것으로 모델이 만든 문장을 공개 파일과 커밋에 쓰지 않는다(`REVIEW.md` 「공개 저장소 노출」).
- 라이언은 받은 소리 설명을 그대로 말하고 새로 지어내지 않는다(스펙 「소리 설명 목록」).
- 설명은 몸으로 따라 할 수 있는 한 가지를 헷갈린 소리와 맞대어 쓴다. 예: 「L은 혀끝이 윗잇몸에 닿지만, R은 혀가 어디에도 닿지 않게 하고 입술을 살짝 동그랗게 모은다.」(스펙 「소리 설명 목록」)
- 실제 모델 호출은 돌리기 전에 횟수와 어림 값을 main 세션에 한 줄로 알린다. 합쳐 1달러 안쪽이면 기다리지 않는다.
- 피드백 지시문을 고치면 고치기 전과 뒤를 같은 경우로 견준다(`docs/guide/PRONUNCIATION_따라말하기_짚기_20261106.md` 「라이언의 말을 고칠 때」).
- `sounds.json`의 글은 사용자가 main 세션에서 정한 대로만 바꾼다.

## Review Focus

- 받은 설명을 띄어쓰기나 줄바꿈만 다르게 말한 답: 그대로 말한 것으로 본다(Task 1 `test_spacing_does_not_count_as_rewording`).
- 같은 설명을 받은 짚을 것 둘(same tip twice): 설명을 한 번 말하면 깨끗하고, 두 번 말하면 「tip repeated」다(Task 1 `test_a_tip_said_twice_is_flagged`).
- 소리 설명이 없는 짚을 것과 있는 짚을 것이 섞인 경우(tip second): 받은 설명은 「made up」으로 세지 않는다(Task 1 `test_a_made_up_tip_is_flagged`).
- 칭찬 후보에 소리 이름이 든 경우(improved의 「R 소리」): 설명이 없는 경우라 「sound named」로 세지 않는다(Task 1 `test_a_sound_named_outside_the_tip_is_flagged`).
- 목록 글을 바꾸면 검사의 반쪽 낱말이 낡는다: 시험이 막는다(Task 1 `test_every_listed_tip_has_halves`).

---

### Task 1: 검사가 설명을 그대로 말했는지 본다

**Files:**
- Modify: `server/scripts/check_ryan_wording.py`
- Test: `server/tests/test_check_ryan_wording.py`

**Interfaces:**
- Produces: `RL`, `FP`(목록에서 읽은 글), `TIP_HALVES: dict[str, tuple[str, str]]`(목록의 여섯 설명 모두, 앞 반쪽에만 있는 낱말과 뒤 반쪽에만 있는 낱말), `MOUTH`(입 모양 낱말), `tip_flags(case: Case, text: str) -> list[str]`, `issue(target, heard, explain="", sound=("R", "L"))`, 피드백 경우 `dropped`와 `sound <이름>` 다섯 개, 선생님 라이언 경우 `sound <이름>` 넷(F는 `near miss F`가 있다).

- [ ] **Step 1: 시험을 먼저 쓴다.** 띄어쓰기는 `" ".join(s.split())`로 맞춘 뒤 본다.

```python
def test_a_reworded_tip_is_flagged():
    case = next(c for c in cw.FEEDBACK if c.name == "tip")
    point = "나머지 낱말은 다 알아들었어요. 그런데 room이 loom처럼 들렸어요. "
    swapped = point + "R은 혀가 어디에도 닿지 않게 하고 입술을 살짝 동그랗게 모으지만, L은 혀끝이 윗잇몸에 닿아요. 한 번 더 해 볼까요?"
    assert cw.flags(case, swapped, aside=False) == ["tip reworded (room)"]

def test_spacing_does_not_count_as_rewording():
    case = next(c for c in cw.FEEDBACK if c.name == "tip")
    spaced = "그런데 room이 loom처럼 들렸어요.\n" + cw.RL.replace(" ", "  ", 1) + " 한 번 더 해 볼까요?"
    assert not [f for f in cw.flags(case, spaced, aside=False) if f.startswith("tip")]

def test_a_tip_said_twice_is_flagged():
    # todo 29: the R half first in its own words, then the whole tip
    case = next(c for c in cw.FEEDBACK if c.name == "tip")
    point = "그런데 room이 loom처럼 들렸어요. "
    own = point + "R은 입술을 동그랗게 모아야 해요. " + cw.RL + " 한 번 더 해 볼까요?"
    assert "tip repeated (room)" in cw.flags(case, own, aside=False)
    assert "tip repeated (room)" in cw.flags(case, point + cw.RL + " " + cw.RL + " 한 번 더 해 볼까요?", aside=False)
    twice = next(c for c in cw.FEEDBACK if c.name == "same tip twice")  # one tip for two words, said once: clean
    once = "나머지 낱말은 다 알아들었어요. 그런데 fried가 flied처럼, rice가 lice처럼 들렸어요. " + cw.RL + " 한 번 더 해 볼까요?"
    assert cw.flags(twice, once, aside=False) == []

def test_a_made_up_tip_is_flagged():
    # todo 29: a dropped word with no tip got an F tip the Mac never sent
    case = next(c for c in cw.FEEDBACK if c.name == "dropped")
    made = "나머지 낱말은 다 알아들었어요. 그런데 by가 들리지 않았어요. F는 윗니를 아랫입술에 대고 바람을 내보내요. 한 번 더 해 볼까요?"
    assert cw.flags(case, made, aside=False) == ["tip made up"]
    assert cw.flags(case, "나머지 낱말은 다 알아들었어요. 그런데 by가 들리지 않았어요. 한 번 더 해 볼까요?", aside=False) == []
    second = next(c for c in cw.FEEDBACK if c.name == "tip second")  # a given tip beside a word without one
    ok = "나머지 낱말은 다 알아들었어요. 그런데 on이 들리지 않았고, red가 led처럼 들렸어요. " + cw.RL + " 한 번 더 해 볼까요?"
    assert cw.flags(second, ok, aside=False) == []

def test_a_sound_named_outside_the_tip_is_flagged():
    # todo 29: 「두 낱말 모두 R이 L로 들린 것이에요」 put before the tip
    case = next(c for c in cw.FEEDBACK if c.name == "same tip twice")
    framed = "그런데 fried가 flied처럼, rice가 lice처럼 들렸어요. 두 낱말 모두 R이 L로 들린 것이에요. " + cw.RL + " 한 번 더 해 볼까요?"
    assert cw.flags(case, framed, aside=False) == ["sound named (fried)"]
    improved = next(c for c in cw.FEEDBACK if c.name == "improved")  # a praise that names a sound, no tip given
    said = "이번에는 right의 R 소리가 제대로 났어요. 그런데 on이 들리지 않았어요. 한 번 더 해 볼까요?"
    assert cw.flags(improved, said, aside=False) == []

def test_every_listed_tip_has_halves_and_cases():
    from je_server import sounds

    for s in sounds.SOUNDS:
        first, second = s.explain.split("지만, ", 1)
        a, b = cw.TIP_HALVES[s.explain]
        assert a in first and a not in second and b in second and b not in first, s.name
        for cases in (cw.FEEDBACK, cw.ASIDE):
            assert any(i.explain == s.explain for c in cases for i in c.issues), s.name
```

기존 `test_a_tip_cut_in_half_is_flagged`는 그대로 통과해야 한다.

- [ ] **Step 2: 실패를 본다.** `cd server && uv run pytest -q tests/test_check_ryan_wording.py` → 새 시험 여섯이 FAIL(`dropped` 경우 없음, `tip reworded` 없음 등).

- [ ] **Step 3: 고친다.**
  - `RL`, `FP`는 `je_server.sounds.find(...)`의 `explain`에서 읽는다. `TIP_HALVES`는 목록의 여섯 설명 모두를 손으로 고른 낱말 짝으로 둔다(지금 R과 L, F와 P의 짝은 그대로).
  - `tip_flags(case, text)`: 경우의 짚을 것에서 받은 설명을 겹치지 않게 모은다(처음 짚을 것의 낱말로 표시). 받은 설명을 그대로 든 곳을 모두 지운 나머지 글을 `rest`라 한다.
    - 그대로 들어 있으면: 두 번 넘게 들었거나 `rest`에 그 설명의 반쪽 낱말이 있으면 「tip repeated」.
    - 그대로가 아니면: 반쪽 낱말이 하나도 없으면 「tip dropped」, 하나면 「tip cut」, 둘 다면 「tip reworded」.
    - 받은 설명이 모두 그대로였고 위 표시가 없는데 `rest`에 `MOUTH`(혀, 입술, 윗니, 아랫니, 잇몸, 입천장, 목을 울, 바람)가 있으면 「tip made up」.
    - 받은 설명을 그대로 한 번 말했고 위 표시가 없는데, 그 설명에 든 소리 이름(영어 대문자 낱말, R과 L 같은 것)이 `rest`에 따로 서 있으면 「sound named」. 고쳐 말한 설명은 소리 이름이 들어 있는 것이 당연해 따로 세지 않는다.
  - `flags`는 지금의 반쪽 검사 대신 `tip_flags`를 쓴다. 독스트링 맨 위 목록에 새 표시를 적는다.
  - 경우를 더한다(문장은 지어낸 것). 조사 검사를 위해 새 낱말을 `BATCHIM`에 넣는다(fork, pork, very, berry, think, sink, there, dare는 받침 없음, zone, joan, by는 각각 있음과 없음).
    - 피드백 `dropped`: 「Can I pay by card?」, 들린 말 「Can I pay card?」, 짚을 것 by(설명 없음), 후보 `[REST]`.
    - 피드백 `sound F`(fork, pork), `sound V`(very, berry), `sound TH S`(think, sink), `sound TH D`(there, dare), `sound Z`(zone, joan): 짚을 것 하나에 목록의 설명, 후보 `[REST]`.
    - 선생님 라이언 `sound V`, `sound TH S`, `sound TH D`, `sound Z`: 같은 대사와 들린 말.
  - `issue()`에 `sound` 인자를 더한다(기본 R, L).

- [ ] **Step 4: 통과를 본다.** `uv run pytest -q tests/test_check_ryan_wording.py` → 모두 PASS. `uv run pytest -q` 전체도 PASS.

- [ ] **Step 5: 커밋.** `fix(server): flag a reworded, repeated or made-up tip in check_ryan_wording`

### Task 2: 피드백을 재고, 잦으면 지시문을 고친다

**Files:**
- Modify: `server/je_server/prompts.py`(`FEEDBACK_SYSTEM`)
- Test: `server/tests/test_claude.py`
- Docs: `docs/guide/PRONUNCIATION_따라말하기_짚기_20261106.md`, `docs/guide/README.md`, `docs/todo/20261108_29_todo_feedback_tip_reworded.md`(원래 폴더에서 가져와 상태를 완료로)

**Interfaces:**
- Consumes: Task 1의 표시(tip reworded, tip repeated, tip made up, sound named).

- [ ] **Step 1: 고치기 전을 잰다.** main 세션에 횟수와 값을 알린 뒤 `uv run python scripts/check_ryan_wording.py --only feedback --runs 5`(Haiku 90번쯤, 3센트쯤). 경우마다 설명 표시 수를 적는다.
- [ ] **Step 2: 판단.** 설명이 있거나 빠진 낱말이 있는 경우의 답 가운데 설명 표시가 10% 이상이면 고친다(할 일 20과 같은 기준). 아니면 고치지 않고 할 일을 「고치지 않고 닫음(잰 값)」으로 닫는다.
- [ ] **Step 3: 시험을 먼저 쓴다.** `test_feedback_prompt_keeps_a_given_tip_whole`: `FEEDBACK_SYSTEM`에 `"처음부터 끝까지 그대로 말해요"`, `"한쪽 소리만"`, `"앞에 설명을 더 붙이지 않아요"`가 있다. 지어낸 설명이 나왔으면 그 금지 줄도 시험에 넣는다. → FAIL을 본다.
- [ ] **Step 4: 고친다.** `FEEDBACK_SYSTEM`의 「소리 내는 법은 받은 문장을 …」 줄을 `ASIDE_SYSTEM`의 같은 줄과 같은 말로 바꾼다: 왜 통째로 말하는지(들린 소리와 내야 할 소리를 견주는 한 문장, 한쪽만 말하면 무엇이 다른지 알 수 없음), 반만, 순서 바꾸기, 자기 말로 고치기, 앞에 설명 붙이기 금지. 「맞는지 따지지 않고」와 「짚을 것 둘의 소리 내는 법이 같으면 한 번만」은 남긴다. 잰 것에 지어낸 설명이 있으면 「소리 내는 법이 비어 있으면 …」 줄에 입 모양(혀, 입술, 이, 바람)을 말하지 않는다고 더한다.
- [ ] **Step 5: 고친 뒤를 같은 명령으로 잰다.** 표시가 줄었는지 보고, 답을 직접 읽어 뜻이 맞는지 본다. `uv run pytest -q` PASS.
- [ ] **Step 6: 가이드.** 「선생님 라이언이 받은 소리 설명을 반만 말했다」 뒤에 「따라 말한 뒤 피드백도 설명을 고쳐 말하거나 지어냈다」(증상, 원인, 고친 것, 막는 법)를 쓰고, 「라이언의 말을 고칠 때」의 표시 목록에 새 표시를 더한다. 색인 줄을 고친다.
- [ ] **Step 7: 커밋.** 할 일 29 상태를 완료로 고쳐 함께. `fix(server): have feedback ryan say a given sound tip whole`(고치지 않으면 `docs: close the feedback tip todo after measuring`)

### Task 3: 소리 설명 목록 검토

**Files:**
- Modify: `server/je_server/data/sounds.json`, `server/je_server/sounds.py`(독스트링의 「초안」), `server/scripts/check_ryan_wording.py`(`TIP_HALVES`, 글이 바뀐 쌍)
- Docs: 스펙 「소리 설명 목록」에 검토한 날과 바꾼 것 한 줄, `docs/todo/20261105_08_todo_sound_list_review.md`(완료)

- [ ] **Step 1: 초안을 main 세션에 보낸다(Task 1 전에 보내 사용자가 그동안 고르게 한다).** 쌍마다 지금 글, 고친 초안(또는 「그대로」), 이유 한 줄. R과 L은 스펙 문장과 같은지만. 「ㅇㅋ」 한 번으로 받거나 쌍마다 고를 수 있게.
- [ ] **Step 2: 사용자가 정한 대로 `sounds.json`을 고친다.** `test_every_listed_tip_has_halves_and_cases`가 깨지면 `TIP_HALVES`의 낱말을 새 글에 맞춘다. `uv run pytest -q` PASS(`test_compare.py`의 「혀」 검사 포함).
- [ ] **Step 3: 바뀐 쌍마다 두 라이언을 한 번씩 본다.** `--case sound --runs 1`(피드백 Haiku 다섯 번, 선생님 라이언 Sonnet 네 번, 4센트쯤) 그리고 F가 바뀌었으면 `--case "near miss F" --runs 1`. 설명 표시가 없고, 답에 새 글이 그대로 있는지 읽는다.
- [ ] **Step 4: 커밋.** 할 일 8 상태를 완료로 고쳐 함께. `fix(server): use the reviewed sound tips`

### Task 4: 녹음 시험, PR, 리뷰, devlog

- [ ] **Step 1: 옆 시험 서버**(8791, 8792, 녹음을 뺀 데이터 복사본, `DEVENV_맥서버_저절로_띄우기_20261107.md` 「launchd 서버를 멈추지 않고 시험하기」)에 제이크 목소리로 지어낸 녹음 둘을 보낸다: 대사 낱말 하나를 빼고 읽은 것(지어낸 설명이 없어야 한다), 대사 그대로 읽은 것. 끝나면 서버, 복사본, 녹음 파일을 지운다.
- [ ] **Step 2: push, PR(본문 한국어, 실제 모델 호출 횟수와 값), pr-review, 확인된 문제 고치기.**
- [ ] **Step 3: devlog**(`docs/devlog/2026-11-08-ryan-sound-tips.md`)를 커밋하고 main 세션에 「머지 준비 됨」.
