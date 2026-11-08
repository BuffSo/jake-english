# 선생님 라이언 답: 앞서 짚은 것, 속 지시문, 지명 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 선생님 라이언이 같은 대사의 앞 시도에서 짚은 것을 알고 답하고, 지시문의 이름과 규칙을 학습자에게 말하지 않게 하고, 사전에 없는 이름(로마자 지명)을 음절로 견준다.

**Architecture:** 맥 서버만 바뀐다. `Engine._attempt`가 그 줄의 마지막 시도를 「이 대사의 앞 시도」에 더해 `Claude.aside`에 넘기고, `ASIDE_SYSTEM`이 그것을 묻는 말과 짚을 것이 빈 시도에 답하는 갈래를 얻는다. `Claude.aside`는 답을 문장마다 보고 지시문의 말이 든 문장을 버린다. `compare.py`는 사전에 없는 낱말을 음절로 견주고, 이름 자리의 한글을 한국어로 보지 않는다.

**Tech Stack:** Python(맥 서버, pytest, anthropic SDK). 새 꾸러미 없음.

**Spec:** `docs/superpowers/specs/2026-11-08-teacher-answer-context-design.md`. 할 일은 원래 폴더의 `docs/todo/20261108_40_todo_teacher_answer_context_and_leaks.md`.

## Global Constraints

- 시험 문장과 예는 지어낸 것만 쓴다. 맥의 기록(들린 말, 라이언 답, 그 기록의 지명)을 코드, 시험, 문서, 커밋에 옮기지 않는다(`REVIEW.md`).
- 커밋은 `/usr/bin/git`, `git commit -F - <<'EOF'`, 앞 커밋이 성공해야 다음이 돌게 `&&`로 잇는다. 첫 줄 72자 이내, scope `server`.
- 테스트: `cd server && uv run pytest -q`, 훅 `node --test 'scripts/**/*.test.mjs'`.
- 같이 도는 free-talk 카드가 `engine.py`, `claude.py`, `prompts.py`를 고친다. `Engine._attempt`의 선생님 답 부분, `Claude.aside`, `ASIDE_SYSTEM` 밖은 건드리지 않는다.
- 맥 스피커로 소리를 내지 않는다(main 세션이 알릴 때까지). 시험 서버는 `127.0.0.1:8797`, 받아쓰기 `8798`.

## 정한 것 (AI 판단)

- **실행 방식:** 이 세션이 직접 한다(executing-plans). 작업이 넷이고 모두 선생님 답의 한 흐름이라 작업마다 새 에이전트를 띄우면 같은 맥락을 다시 읽는 데 더 든다. 끝에 브랜치 리뷰와 pr-review를 돌린다.
- **앞 시도의 모양:** `earlier: list[tuple[str, list[Issue], str]]`(들린 말, 짚은 것, 라이언의 답). 보내는 글의 필드는 `"이 대사의 앞 시도"`, 항목은 `{"들린 말", "짚은 것": [{"대사 낱말", "들린 낱말"}], "라이언의 답"}`이다. 소리 설명은 라이언의 답에 이미 들어 있어 따로 넘기지 않는다.
- **거르는 말:** `claude.ASIDE_LEAKS`에 둔다. 검사 스크립트(`check_ryan_wording.py`)의 `NAMES`가 이것을 모두 담는지 시험이 본다.

## Review Focus

- 선생님에게 한 말이 셋을 넘을 때: 경계의 시도는 남고 선생님에게 한 말은 최근 세 번만 간다 → Task 1.
- 그 줄에 앞 시도가 없을 때(첫 녹음이 선생님에게 한 말): 앞 시도는 빈 목록이다 → Task 1.
- 거른 문장 뒤의 띄어쓰기: 버린 문장과 그 뒤 공백이 함께 빠져, 남은 글이 공백으로 시작하지 않는다 → Task 3.
- 거르는 중에 끊긴 답: 걸러지지 않은 조각은 내보낸 뒤 `ClaudeUnavailable`을 다시 낸다(엔진이 정해진 말을 잇는다) → Task 3.
- 모든 문장이 걸러진 답: 엔진이 빈 답처럼 정해진 말만 한다 → Task 3(엔진의 빈 답 시험이 이미 있다).

---

### Task 1: 같은 대사의 앞 시도를 넘긴다

**Files:**
- Modify: `server/je_server/engine.py` (`ASIDES_KEPT` 주석, `_attempt`의 `since`/`asides`)
- Modify: `server/je_server/claude.py` (`Claude.aside`의 `earlier`와 보내는 글)
- Modify: `server/je_server/prompts.py` (`ASIDE_SYSTEM`의 「받는 것」, 앞 시도를 묻는 갈래와 예)
- Modify: `server/tests/fakes.py` (`FakeClaude.aside`는 그대로 `earlier`를 담는다)
- Test: `server/tests/test_aside.py`, `server/tests/test_claude.py`

**Interfaces:**
- Produces: `Claude.aside(frame, history, line, heard, heard_ko, issues, earlier: list[tuple[str, list[Issue], str]])`.

- [x] **Step 1: 실패하는 시험.**
  - `test_aside.py::test_the_last_try_goes_with_the_asides`: practice로 near miss("It's light over hair.") 하나, 선생님에게 한 말 하나를 보낸 뒤, 마지막 호출의 `earlier[0]`이 `("It's light over hair.", [그 시도의 issues], 그 시도의 say_ko)`이고 `earlier[1][1] == []`.
  - `test_earlier_asides_stop_at_the_last_try_at_the_line`을 고친다: 경계 앞의 말은 가지 않고, `earlier[0]`이 경계의 시도다.
  - `test_earlier_asides_on_the_line_go_to_claude`: 넷을 보내면 `len(earlier) == 3`(경계 없음, 최근 셋), 항목 모양은 `(heard, [], answer)`.
  - `test_a_kept_try_stays_past_three_asides`: 경계 하나 뒤 선생님에게 한 말 넷이면 `len(earlier) == 4`, `earlier[0]`이 경계.
  - `test_claude.py::test_aside_streams_korean_on_the_writer_and_sends_only_text`: `body["이 대사의 앞 시도"] == [{"들린 말": …, "짚은 것": [{"대사 낱말": "large", "들린 낱말": "launch"}], "라이언의 답": …}]`, `"앞서 선생님에게 한 말" not in body`.
  - `test_aside_prompt_answers_about_an_earlier_point`: `ASIDE_SYSTEM`에 「이 대사의 앞 시도」, 「물을 때만」, 「이어서 빨리 말하면」이 있다.
- [x] **Step 2:** `uv run pytest -q tests/test_aside.py tests/test_claude.py` → 위 시험이 실패한다.
- [x] **Step 3: 고치기.** `since`는 마지막 aside가 아닌 시도의 자리(없으면 0), `kept = tries[since:since+1] if 그 시도가 있으면`, `asides = 그 뒤의 aside[-ASIDES_KEPT:]`. 지시문은 「받는 것」의 앞서 한 말 줄을 바꾸고, 「무엇이라고 답할지」 맨 앞에 앞서 짚은 것을 묻는 갈래를, 예에 지어낸 한 줄(bring, ring 같은 시험에 없는 낱말)을 더한다.
- [x] **Step 4:** `uv run pytest -q` → 모두 통과.
- [x] **Step 5: 커밋** `fix(server): send teacher Ryan the line's last try and its points`

### Task 2: 짚을 것이 빈 시도의 갈래와 맨 앞 규칙

**Files:**
- Modify: `server/je_server/prompts.py` (`ASIDE_SYSTEM`)
- Test: `server/tests/test_claude.py`

- [x] **Step 1: 실패하는 시험** `test_aside_prompt_covers_a_try_without_points`: 「짚을 것이 비어 있으면」 대신 학습자에게 쓰지 않을 낱말 없이, `ASIDE_SYSTEM`에 「대사와 조금 다르게 들렸어요」(예)와 「학습자에게 하는 말만」이 있고, 규칙 목록의 첫 줄이 「학습자에게 하는 말만」이다.
- [x] **Step 2:** 시험이 실패한다.
- [x] **Step 3: 고치기.** 「무엇이라고 답할지」의 첫 갈래 아래에 「대사를 따라 말하려 한 것 같은데 받은 짚을 것이 없으면」 갈래를 더하고, 규칙 맨 앞에 「답에는 학습자에게 하는 말만 써요. 지시를 어떻게 따를지, 받은 것이 비었는지 먼저 말하지 않아요」를 둔다.
- [x] **Step 4:** `uv run pytest -q` → 통과.
- [x] **Step 5: 커밋** `fix(server): give teacher Ryan a branch for a try with no points`

### Task 3: 지시문의 말이 든 문장을 서버가 거른다

**Files:**
- Modify: `server/je_server/claude.py` (`ASIDE_LEAKS`, `Claude.aside`)
- Modify: `server/scripts/check_ryan_wording.py` (`NAMES`는 `ASIDE_LEAKS`를 담는다)
- Test: `server/tests/test_claude.py`, `server/tests/test_check_ryan_wording.py`

**Interfaces:**
- Produces: `claude.ASIDE_LEAKS: tuple[str, ...]`, `claude.leaks(sentence: str) -> bool`.

- [x] **Step 1: 실패하는 시험.**
  - `test_aside_drops_sentences_that_name_its_materials`: 흘려 받은 `["「짚을 것」이 비어 있으니 말하지 ", "않을게요. 한 번 ", "더 해 볼까요?"]` → `aside()`가 낸 것을 이으면 `"한 번 더 해 볼까요?"`, 로그에 `aside sentence dropped`가 있고 문장 글은 없다.
  - `test_aside_with_every_sentence_dropped_yields_nothing`: `["짚을 곳이 없어요."]` → 빈 목록.
  - `test_aside_cut_keeps_the_clean_piece`: `["괜찮아요. ", "그런데 이", cut]` → `["괜찮아요. ", "그런데 이"]` 뒤 `ClaudeUnavailable`(지금 시험이 그대로 통과해야 한다).
  - `test_aside_keeps_a_sentence_about_an_earlier_point`: 「아까 짚은 곳은 late예요.」는 그대로 간다.
  - `test_check_ryan_wording.py::test_names_cover_the_servers_leak_words`: `set(claude.ASIDE_LEAKS) <= set(cw.NAMES)`.
- [x] **Step 2:** 시험이 실패한다.
- [x] **Step 3: 고치기.** `Claude.aside`가 `_stream`의 글을 모아 `(?<=[.?!])\s+` 뒤에서 문장으로 자르고(뒤 공백까지 한 덩어리), 문장마다 `leaks`를 보고 내보낸다. 끝과 `ClaudeUnavailable` 때 남은 조각도 같은 검사를 거친다.
- [x] **Step 4:** `uv run pytest -q` → 통과.
- [x] **Step 5: 커밋** `fix(server): drop teacher Ryan sentences that name his materials`

### Task 4: 사전에 없는 이름을 음절로 견준다

**Files:**
- Modify: `server/je_server/compare.py` (이름 음절 나누기와 견주기, `compare`의 맞대기, `korean_said`)
- Modify: `server/je_server/engine.py` (`followed`와 자동 받아쓰기의 한국어 판단이 `korean_said`를 쓴다)
- Test: `server/tests/test_compare.py`, `server/tests/test_aside.py`
- 예는 지어낸 것만 쓴다. 맥의 기록에서 이름이 어떻게 적혔는지는 옮기지 않는다(`REVIEW.md`).

**Interfaces:**
- Produces: `compare.is_name(word: str) -> bool`(소문자 낱말, 영어 글자만, CMUdict에 없음), `compare.syllables(word: str) -> list[tuple[str, str, str]] | None`(첫소리, 모음, 받침; 한글은 로마자로 옮긴 뒤), `compare.same_name(target: str, heard: str) -> bool`, `compare.korean_said(line: str, text: str) -> bool`.

- [x] **Step 1: 실패하는 시험** (`test_compare.py`, 지어낸 예와 목록 대본의 지명만)
  - `test_name_syllables`: `syllables("chungmuro") == [("ch","u","ng"),("m","u",""),("r","o","")]`, `len(syllables("gyeongbokgung")) == 3`, `len(syllables("itaewon")) == 3`, `len(syllables("haeundae")) == 3`, `syllables("홍대")`는 `syllables("hongdae")`와 같다.
  - `test_names_heard_alike_pass` (parametrize): (sinchon, sichon), (gyeongbokgung, kyongbokgung), (hongdae, hongde), (insadong, insa dong), (jamsil, chamsil), (sinchon, shinchon), (gyeongbokgung, 경복궁) → `compare(...).diffs == []`이고 `similarity == 1.0`.
  - `test_names_heard_differently_are_pointed` (parametrize): (chungmuro, chungmugong), (insadong, insa), (hongdae, hongik), (jamsil, jamsilsaenae), (itaewon, itaewan: 모음 무리 o와 a가 다름) → diffs가 하나, `explain == ""`.
  - `test_a_name_not_heard_is_pointed`: 대사의 이름이 들린 말에 없으면 지금처럼 「들리지 않았어요」.
  - `test_hangul_at_the_name_is_not_korean`: `korean_said("Get off at Hongdae.", "Get off at 홍대.") is False`, `korean_said("Get off at Hongdae.", "Get off at 홍대 아 뭐였지") is True`, `korean_said("Get off at Hongdae.", "아 몰라") is True`.
- [x] **Step 2:** 시험이 실패한다.
- [x] **Step 3: 고치기.** 스펙 3의 「정한 것」대로 나누고 견준다. `compare()`는 들린 말의 한글을 낱말로 남겨 맞대고, 한글이 모두 이름 자리에만 있을 때만 그대로 쓰고 아니면 지금처럼 한글을 빼고 다시 맞댄다. 같은 수로 바뀐 짝과 대사 쪽이 이름 하나인 덩어리를 `same_name`으로 본다.
- [x] **Step 4: 엔진 시험** (`test_aside.py`) `test_hangul_name_in_the_auto_transcript_is_a_try`: 영어 받아쓰기 "Get off at Hongdee, please."(가짜 대사에 맞춤)처럼 대사에 가까운 영어, 자동 받아쓰기가 korean으로 이름만 한글 → `heard_ko is None`, 맥의 짚을 것이 Claude에 간다.
- [x] **Step 5:** `uv run pytest -q` → 통과. 맥의 기록으로 옛 규칙과 새 규칙의 짚은 수를 숫자만 센다.
- [x] **Step 6: 커밋** `fix(server): compare names missing from the dictionary by syllable`

### Task 5: 실제 모델, 녹음 시험, 문서

- [x] **Step 1:** `check_ryan_wording.py`의 aside 호출에 `case.earlier`를 넘긴다. `--only aside --case "asks about" --runs 5`, `--case "try " --runs 5`, `--only aside --runs 1`을 돌려 고치기 전 결과와 견준다.
- [x] **Step 2:** 학습자 목소리 녹음 시험(`try_recordings.py`, 시험 서버 8797/8798): 짚을 것이 생기는 대사 녹음 뒤 그것을 묻는 한국어 녹음.
- [x] **Step 3:** 선생님 답 스펙 3과 「한계」에 이 스펙을 가리키는 줄, 가이드 `PRONUNCIATION_따라말하기_짚기`에 겪은 문제, devlog, 할 일 상태를 「완료」로.
