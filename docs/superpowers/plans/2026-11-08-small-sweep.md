# 지난 PR들이 남긴 작은 일 다섯 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 지난 PR들이 남긴 할 일 다섯(20, 25, 26, 27, 28)을 고치고 닫는다. 새 기능은 없다.

**Architecture:** 브랜치 `fix/small-sweep` 하나, PR 하나. 서버는 검사 스크립트와 지시문, 앱은 녹음 바의 게이트와 리듀서다. 지시문을 고치는 두 할 일(20, 27)은 검사부터 고치고(시험 먼저), 실제 모델로 잦기를 잰 뒤, 잦으면 지시문을 고치고 같은 수로 다시 잰다. 규칙 문서 할 일(18)은 PR #47로 따로 올렸다.

**Tech Stack:** 서버 Python(pytest, uv), 앱 React Native + Expo(jest, tsc). 새 꾸러미 없음.

**Spec:** 원래 폴더 `docs/todo/`의 할 일 파일(아직 커밋하지 않았다. 끝내는 커밋에 「완료」로 고쳐 넣는다): `20261108_20_todo_aside_tip_trimmed.md`, `20261108_25_todo_try_recordings_copy_line.md`, `20261108_26_todo_record_cancel_skip_minors.md`, `20261108_27_todo_jake_recommend_odd_start.md`, `20261108_28_todo_quick_model_review_minors.md`. 26은 스펙 `docs/superpowers/specs/2026-11-08-record-cancel-skip-design.md`(「5. 두 번 누름과 게이트」)를 따른다.

## Global Constraints

- 같이 도는 line-notes-degrade 카드가 `prompts.py`의 `THREE_SYSTEM`, `threeline.py`, `claude.py`의 `annotate`를 고친다. 이 계획은 그 셋을 건드리지 않는다. 먼저 머지되는 쪽이 있으면 다른 쪽이 origin/main을 merge한다.
- 시험과 문서의 문장은 지어낸다. 맥의 기록, 녹음, 받아쓰기, 할 일 파일의 실제 출력 예문을 옮기지 않는다.
- 지시문에는 모델이 쓰면 안 되는 낱말을 예로 넣지 않는다(`docs/guide/PROMPT_정해진_말투를_섞기_20261108.md`).
- 실제 모델 호출은 돌리기 전에 횟수와 어림 값을 main 세션에 알렸다(합쳐 1달러 안쪽). 몇 번 불렀고 얼마였는지 PR에 적는다.
- 커밋은 `/usr/bin/git`, `git commit -F - <<'EOF'`, 커밋 하나에 type 하나. 할 일을 끝내는 커밋에 그 할 일 파일(원래 폴더에서 복사해 상태 줄을 「완료」로)을 넣는다.
- 시험: 서버 `cd server && uv run pytest -q`, 앱 `cd app && npx jest && npx tsc --noEmit`.
- 시험 서버는 `JE_HOST=127.0.0.1 JE_PORT=8793 JE_WHISPER_PORT=8794`, 데이터는 녹음을 뺀 복사본. 원래 폴더 서버(launchd)는 멈추지 않는다.

## Review Focus

1. 소리 설명을 둘로 나눠 보는 검사가 같은 설명을 두 낱말에 붙인 경우(설명 한 번만 말함)를 「잘림」으로 세면 안 된다.
2. 추천의 「상황 아닌 시작」을 세는 검사가 상황 안의 「제가」(「제가 묵는 호텔에서 …」)를 세면 안 된다. 셈은 문장 맨 앞만 본다.
3. `rec_flags`의 되풀이 검사가 끝말이 없는 최근 상황(「…묻는 상황」)과 끝말이 붙은 답을 같은 것으로 봐야 한다. 끝말을 걷어 낸 것이 빈 글이면 모든 답에 걸리므로 건너뛴다.
4. 녹음 시험 스크립트가 복사본의 줄이 모드와 맞지 않아 멈출 때 복사본을 남기면, 사용자의 「지난 상황」에 시험 역할극이 보인다.
5. 마이크가 켜지는 동안 누른 「취소」를 기억했다가, 그 사이 뒤로 가서 화면을 떠났으면 취소가 아니라 떠날 때의 버림(`discard`)만 한다. 기억한 취소가 다음 녹음에 남으면 안 된다.

---

### Task 1: 추천 비교 스크립트와 시험의 작은 것 (할 일 28)

**Files:**
- Modify: `server/scripts/compare_quick_models.py` (`rec_flags`, `PRICE`)
- Modify: `server/je_server/claude.py:26-30` (주석만)
- Test: `server/tests/test_compare_quick_models.py`, `server/tests/test_claude.py`, `server/tests/test_check_jake_recommend.py`

**Interfaces:**
- Produces: `compare_quick_models._situation(text: str) -> str` (끝말과 끝의 「상황」, 낱말 아닌 글자를 뺀 비교용 줄기)

- [ ] **Step 1: 실패하는 시험**
  - `test_recommendation_flags`에 더한다: 최근 상황 「명동에서 환전소를 묻는 상황을 골라 봤어요.」를 받고 답이 「명동에서 환전소를 묻는 상황을 추천해요.」면 `"repeats a listed situation"`. 끝말 없는 「카페에서 주문하는 상황」과 KEPT도 그대로 걸린다. 끝말뿐인 「상황을 추천해요.」를 받으면 KEPT에 걸리지 않는다.
  - `test_claude.py`에 `test_every_message_label_is_dropped`: 목록이 있는 주제와 거절한 상황을 넘겨 `recommend`를 부르고, 보낸 메시지에서 `^([^\s:-][^:\n]*):\s*\S`(이름표 뒤에 같은 줄 값이 있는 줄)의 이름이 모두 `MESSAGE_LABELS`에 있는지 본다.
  - `test_check_jake_recommend.py`의 `>= 6`을 `== 10`으로.
- [ ] **Step 2:** `uv run pytest -q tests/test_compare_quick_models.py` → 새 단언이 실패(끝말만 다른 되풀이를 놓침). 이름표 시험과 `== 10`은 지금 코드로 통과한다(지키는 시험).
- [ ] **Step 3:** `rec_flags`의 되풀이 검사를 `_situation(s) in _situation(said)`(빈 줄기는 건너뜀)으로 바꾼다. `_situation`은 `strip_endings(x)`가 None이 아니면 그것, 아니면 `x`에서 낱말 아닌 글자를 빼고 끝의 「상황」을 뗀다. `PRICE = cjr.PRICE`.
- [ ] **Step 4:** `claude.py` 맨 위 주석에 `JE_CLAUDE_RECOMMEND`를 더한다(추천은 `QUICKS`에서 고르고 기본 Sonnet).
- [ ] **Step 5:** `uv run pytest -q` 통과.
- [ ] **Step 6: 커밋** — `fix(server): catch repeats that differ only in the ending in rec_flags`(스크립트와 그 시험), `test(server): pin message labels and the ten recent situations`(이름표 시험, `== 10`), `refactor(server): reuse the recommend price table and name JE_CLAUDE_RECOMMEND`(PRICE, 주석, 할 일 28 「완료」).

### Task 2: 소리 설명을 통째로 말했는지 보는 검사와 잦기 (할 일 20)

**Files:**
- Modify: `server/scripts/check_ryan_wording.py` (`TIP_MARK` → `TIP_HALVES`, `flags`)
- Test: `server/tests/test_check_ryan_wording.py`
- Maybe: `server/je_server/prompts.py` (`ASIDE_SYSTEM`, 잦을 때만), `server/tests/test_claude.py`, `docs/guide/PRONUNCIATION_따라말하기_짚기_20261106.md`

**Interfaces:**
- Produces: `TIP_HALVES: dict[str, tuple[str, str]]` — RL은 `("윗잇몸", "동그랗게")`, FP는 `("터뜨리", "아랫입술")`. 반쪽마다 다른 반쪽에 없는 낱말이다.

- [ ] **Step 1: 실패하는 시험** `test_a_tip_cut_in_half_is_flagged`: `near miss tip` 경우에 R 쪽 반만 말한 지어낸 답은 `"tip cut (room)"`, 설명을 통째로 말한 답은 tip 표시 없음, 설명이 없는 답은 `"tip dropped (room)"`. `same tip twice`(피드백)에서 설명을 한 번만 통째로 말하면 tip 표시 없음.
- [ ] **Step 2:** 실패 확인(지금은 「닿」이 두 반쪽 모두에 있어 잘린 것을 통과시킨다).
- [ ] **Step 3:** `flags`: 반쪽 표시가 하나도 없으면 `tip dropped`, 일부만 있으면 `tip cut`.
- [ ] **Step 4:** 통과 확인 후 커밋 `fix(server): flag a sound tip said only in half in check_ryan_wording`.
- [ ] **Step 5: 잰다(Sonnet 10번, 7센트쯤).** `uv run python scripts/check_ryan_wording.py --only aside --case "near miss tip" --runs 5`, 같은 것을 `"near miss F"`로. 잘림 수를 센다.
- [ ] **Step 6: 판단.** 열 번 중 둘 이상 잘리면 지시문을 고친다. 하나 이하면 고치지 않고 할 일에 잰 수를 적어 닫는다.
  - 고칠 때: `ASIDE_SYSTEM`의 「소리 내는 법이 있으면 받은 문장을 그대로 말해요」를, 받은 문장은 두 소리를 견주는 한 문장이라 앞뒤를 다 말한다는 것과 「그 문장 앞에 소리 설명을 더 붙이지 않는다」로 다진다. `test_claude.py`에 그 글이 있는지 보는 시험을 먼저 쓴다. 같은 두 경우를 5번씩 다시 재고(7센트쯤), aside 전체를 한 번(9번, 6센트쯤) 돌려 다른 규칙이 깨지지 않았는지 본다. 가이드 「라이언이 맥이 준 소리 설명을 버리고…」에 겪은 것을 더한다.
- [ ] **Step 7: 커밋** — 지시문을 고쳤으면 `fix(server): have teacher ryan say a given sound tip whole`(지시문, 시험, 가이드, 할 일 20 「완료」), 아니면 `docs: close the trimmed tip todo with its measured rate`(할 일 20만).

### Task 3: 추천이 상황 아닌 말로 시작하는 잦기와 고침 (할 일 27)

**Files:**
- Modify: `server/scripts/check_jake_recommend.py` (`odd_start`, 셈 줄), `server/scripts/compare_quick_models.py` (`ODD_START`를 `cjr`에서 가져옴)
- Test: `server/tests/test_check_jake_recommend.py`, `server/tests/test_claude.py`
- Maybe: `server/je_server/prompts.py` (`RECOMMEND_SYSTEM`), `docs/guide/PROMPT_정해진_말투를_섞기_20261108.md`

**Interfaces:**
- Produces: `check_jake_recommend.ODD_START: tuple[str, ...]`(compare의 것을 옮김), `check_jake_recommend.odd_start(text: str) -> bool`(맨 앞이 그 낱말 중 하나로 시작하면 참)

- [ ] **Step 1: 실패하는 시험** `test_odd_starts_are_counted_at_the_front_only`: 「제가 카페에서 주문하는 상황을 추천해요.」, 「제이크가 추천하는 상황은 카페에서 주문하는 상황이에요.」는 참. 「카페에서 제가 시킨 음료가 잘못 나와 바꿔 달라는 상황을 추천해요.」는 거짓.
- [ ] **Step 2:** 실패 확인(`odd_start` 없음). **Step 3:** 구현하고 `main`이 줄마다 `odd start`를 표시하고 끝에 수를 찍게 한다. compare는 `cjr.ODD_START`를 쓴다. **Step 4:** 통과 후 커밋 `test(server): count recommendations that open with the speaker in check_jake_recommend`.
- [ ] **Step 5: 잰다(Sonnet 63번, 20센트쯤).** `uv run python scripts/check_jake_recommend.py`를 세 번. 상황 아닌 시작을 센다.
- [ ] **Step 6: 고치는 길 견주기와 판단.**
  - 서버 걷기는 「제가 + 장소」(이상한 것)와 「제가 묵는 호텔에서 …」(상황 안의 학습자, 맞는 것)를 글자로 가를 수 없다. 걷을 꼴 목록도 모델마다 늘어난다. 그래서 하나라도 나오면 지시문을 고친다: request_ko는 상황(어디서, 무슨 일)으로 바로 시작하고, 말하는 사람이나 추천한다는 말을 쓰지 않는다. 「제가」는 예로 넣지 않는다.
  - `test_claude.py`에 `test_recommend_system_starts_with_the_situation`(지시문에 그 줄이 있고 「제가」, 「제이크」가 없는지)을 먼저 쓴다.
  - 고친 뒤 같은 세 번(63번, 20센트쯤)으로 다시 잰다. 끝말 셈(MISSED, swapped)이 나빠지지 않았는지도 본다.
  - 한 번도 안 나오면 고치지 않고 잰 수를 적어 닫는다.
- [ ] **Step 7: 커밋** `fix(server): have jake's recommendation open with the situation`(지시문, 시험, 가이드 「겪은 문제와 해결」, 할 일 27 「완료」).

### Task 4: 녹음 시험 스크립트가 복사본의 줄을 찍고 확인 (할 일 25)

**Files:**
- Modify: `server/scripts/try_recordings.py` (`run`, `list_roleplays`)
- Test: `server/tests/test_try_recordings.py`
- Modify: `docs/guide/DEVENV_폰없이_녹음_시험하기_20261108.md` 「명령」 2, 3, `docs/guide/PROMPT_일마다_모델_견주기_20261108.md` 「녹음 시험이 찍은 대사와…」 끝 줄

**Interfaces:**
- Produces: `try_recordings.copy_lines(rp: Roleplay) -> list[tuple[int, str, str]]` — 복사하면 나올 줄(idx, speaker, text). 목록 상황이 아직 목록에 있으면 `topics.pick(...).script`, 아니면 기록의 줄(`Engine.copy`와 같은 갈래).

- [ ] **Step 1: 실패하는 시험**
  - `test_the_copy_line_is_checked_and_printed`: 목록 상황(`POST /roleplays {"topic": "usa", "pick": "u-sneaker-size"}`)을 만들고 `topics.pick`을 첫 줄이 바뀐 대본으로 바꾼 뒤(`test_picks.changed_script`와 같은 방법) `run(..., 0, ...)`. 찍은 첫 줄이 `line 0: <바뀐 줄>`이다.
  - `test_a_copy_line_not_for_the_mode_stops_and_the_copy_is_deleted`: 바뀐 대본의 0번 줄을 라이언 줄로 두면 `Stop("Ryan's line")`이고 데이터 폴더에 원본만 남는다.
  - `test_list_shows_the_lines_a_copy_gets`: `list_roleplays`가 목록 상황이면 지금 대본의 줄을 찍는다.
  - 지금의 `test_a_line_not_for_the_mode_stops_before_copying`은 이름을 `..._stops_and_leaves_no_copy`로 바꾼다(이제 복사한 뒤 확인하고 지운다).
- [ ] **Step 2:** 실패 확인. **Step 3:** `run`은 먼저 복사하고, 복사본 응답의 줄로 `_check_line`을 하고, `Stop`이면 복사본을 지우고 다시 던진다. `list_roleplays`는 `copy_lines`를 찍고 목록 상황이면 머리 줄에 `(list: current script)`를 붙인다.
- [ ] **Step 4:** 통과. 가이드 두 곳을 고친다.
- [ ] **Step 5: 커밋** `fix(server): print and check the copy's line in try_recordings`(스크립트, 시험, 가이드, 할 일 25 「완료」).

### Task 5: 따라 말하기 연습의 건너뛰기를 묶는 시험 (할 일 26의 2)

**Files:** Test: `app/src/flow/state.test.ts` (「skip and cancel」 묶음)

- [ ] **Step 1:** `test("skip in shadow practice is taken on Ryan's line and goes where 다음 goes")`: `startPractice` shadow `order: [0]`, `lineLoaded` ryanLine → `canSkip` 참, `skip` → `[screen, practice] == ["end", null]`. `order: [0, 2]`면 `[practice.at, idx, phase] == [1, 2, "loading"]`.
- [ ] **Step 2:** 통과(지금 코드를 지키는 시험). 커밋 `test(app): pin skip in shadow practice`.

### Task 6: 건너뛴 말풍선에 `skipped` 필드 (할 일 26의 3)

**Files:** Modify `app/src/flow/state.ts:14, 370`, `app/src/screens/RoleplayScreen.tsx:496-497`; Test `app/src/flow/state.test.ts`

**Interfaces:** Produces `Bubble.skipped?: true`

- [ ] **Step 1:** 「skip in the roleplay…」와 「skip after teacher Ryan's answer…」의 기대 말풍선에 `skipped: true`를 넣는다. 따라 말한 말풍선(`exchange`)에는 `skipped`가 없다.
- [ ] **Step 2:** 실패 확인. **Step 3:** 건너뛸 때 `skipped: true`, 화면은 `!b.skipped`일 때 들린 말 줄을 보인다. `text`는 빈 글 그대로(다른 곳이 읽는 모양을 바꾸지 않음).
- [ ] **Step 4:** jest, tsc 통과. 커밋 `refactor(app): mark a skipped bubble with skipped`.

### Task 7: 마이크가 켜지는 동안의 「취소」 (할 일 26의 1)

main 세션에 물었다(추천 「가」: 화면은 그대로, 켜지는 동안 누른 「취소」를 기억했다가 켜지자마자 버림. 「■ 말하기 끝」은 「🎤 말하기」 자리라 두 번 누름으로 보고 지금처럼 버림). 답이 「나」면 이 Task를 「`rec.recording`이 참일 때만 「취소」를 보인다」로 바꾼다.

**Files:** Modify `app/src/flow/gate.ts`, `app/src/screens/RoleplayScreen.tsx` (`startRecording`, `cancelRecording`, `doStart`); Test `app/src/flow/gate.test.ts`

**Interfaces:**
- Produces: `createStartCancel()` → `{ begin(): void; ask(): boolean; end(): boolean }`. `begin`은 마이크를 켜기 시작할 때, `ask`는 「취소」가 왔을 때(켜는 중이면 기억하고 참, 아니면 거짓), `end`는 켜기가 끝났을 때 기억한 취소가 있었는지 돌려주고 지운다.

- [ ] **Step 1: 실패하는 시험** (`gate.test.ts`): 켜는 중이 아니면 `ask()`는 거짓. `begin` 뒤 `ask()`는 참이고 `end()`는 참, 다시 `end()`는 거짓. `begin` 뒤 `ask` 없이 `end()`는 거짓. 다음 `begin`은 앞의 기억을 지운다.
- [ ] **Step 2:** 실패 확인. **Step 3:** 구현. 화면: `cancelRecording`은 `startCancel.ask()`가 참이면 거기서 끝, 아니면 지금처럼 `runThenHold`. `doStart`는 `rec.start` 앞에서 `begin`, 뒤에서 `end()`를 부르고, 화면을 떠났으면 지금처럼 `discard`만, 아니고 기억한 취소가 있으면 `discard`, `recordCancel`, `tapHold.start()`. `rec.start`가 실패해도 `end()`를 부른다(`finally`).
- [ ] **Step 4:** jest, tsc 통과. 커밋 `fix(app): keep a cancel tapped while the mic is starting`.

### Task 8: 폰 시험, 녹음 시험, 마무리

- [ ] 앱: 릴리스 APK를 폰(USB)에 깔고 main 세션에 알린다. 대화 복사본에서 「건너뛰기」 뒤 말풍선(들린 말 줄이 없음), 끝 화면의 「따라 말하기」 연습에서 라이언 줄의 「건너뛰기」, 「🎤 말하기」와 「취소」를 adb로 한 명령에 이어 눌러 녹음이 맥에 가지 않고 말하기 전으로 돌아오는지(서버 로그에 시도가 없는지) 본다. 시험한 복사본은 지운다.
- [ ] 서버: 시험 서버(8793/8794, 데이터 복사본)에 `try_recordings.py`로 목록 상황 하나에 제이크 목소리 녹음을 보내 찍힌 줄이 복사본의 줄인지 본다. 20에서 지시문을 고쳤으면 낱말이 다르게 들릴 녹음도 하나 보낸다. 녹음과 데이터 복사본은 끝나면 지운다.
- [ ] `uv run pytest -q`, `npx jest`, `npx tsc --noEmit` 통과.
- [ ] push, PR, pr-review, 고칠 것 고침, devlog(`docs/devlog/2026-11-08-small-sweep.md`), 「머지 준비 됨」을 main 세션에.
