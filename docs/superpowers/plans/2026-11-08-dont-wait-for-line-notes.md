# 내 대사를 보여 주기 전에 읽는 법을 기다리지 않기 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 내 대사는 본보기 소리만 준비되면 나오고, 읽는 법은 뒤에서 만들어 앱이 따로 받아 온다.

**Architecture:** 맥 서버의 줄 준비를 소리 일과 읽는 법 일로 나눈다. 줄 받기는 소리만 기다리고, 읽는 법은 `Engine.three`의 한 줄 한 번 길을 내 대사도 쓴다. 앱은 지금 말할 줄에 읽는 법이 없으면 따라 말하기처럼 받아 온다.

**Tech Stack:** Python 3 + FastAPI(서버, `cd server && uv run pytest -q`), React Native + jest(앱, `cd app && npx jest && npm run typecheck`).

**Spec:** `docs/superpowers/specs/2026-11-08-dont-wait-for-line-notes-design.md`

## Global Constraints

- 줄 받기는 소리만 기다린다. 내 대사의 읽는 법은 대본이 생길 때 바로 뒤에서 만들기 시작한다.
- 한 줄의 읽는 법은 한 번만 만든다(뒤에서 만드는 것과 앱이 받는 것이 한 부름을 나눈다).
- Claude가 안 될 때 줄 받기는 오류를 내지 않는다.
- 화면 글귀는 바꾸지 않는다.
- git은 `/usr/bin/git`, 커밋은 `git commit -F - <<'EOF'`, Conventional Commits 영어, 본문에 이유와 시험 결과, AI 서명 없음.

## Review Focus

1. **읽는 법을 만드는 중에 앱이 받으러 온다:** Claude 부름은 한 번이다. 시험: Task 1 `test_notes_asked_while_made_in_the_background_share_one_call`.
2. **소리가 먼저 실패한다:** 줄은 소리 없이 오고, 읽는 법은 뒤에서 계속 만들어진다. 시험: Task 1 `test_a_line_whose_sound_failed_still_gets_its_notes`.
3. **서버가 다시 켜졌다:** 만들다 만 읽는 법은 그 줄을 받을 때 다시 시작한다. 시험: Task 1 `test_prep_survives_restart`.
4. **Claude가 안 된다:** 줄 받기는 오고, 읽는 법 받기만 오류, 다음에 다시 받으면 된다. 시험: Task 1 `test_claude_down_while_preparing_is_retried_next_time`.
5. **읽는 법을 받지 못한 줄:** 앱은 「읽는 법 보기」를 숨기고 대사와 말하기를 그대로 둔다. 시험: Task 2 `lineNotes` 시험.

---

### Task 1: 서버는 소리만 기다린다

**Files:**
- Modify: `server/je_server/engine.py` (`ready`, 새 `prepared`, `schedule`, `_prepare`를 소리 일로, `line`, `three`, `create`, `copy`, `create_pick`)
- Test: `server/tests/test_engine.py`, `server/tests/test_picks.py`, `server/tests/test_api.py`

**Interfaces:**
- Produces:
  - `Engine.ready(line) -> bool`: 보여 줄 수 있다(소리가 있다). 말하는 사람과 상관없다.
  - `Engine.prepared(line) -> bool`: 준비가 다 됐다(소리가 있고, 내 대사면 읽는 법도 있다). 뒤에서 만들 일을 정할 때 쓴다.
  - `Engine.schedule(rp_id, idx) -> asyncio.Task`: 소리 일을 돌려준다. 내 대사에 읽는 법이 없으면 읽는 법 일도 시작한다(`self.threes`, `Engine.three`와 같은 일).
  - `Engine.line`은 준비가 다 되지 않았으면 `schedule`하고, 소리가 없으면 소리 일만 기다린다.

- [ ] **Step 1: 시험을 새 약속으로 고치고 더한다**
  - `test_create_then_lines_are_prepared` → 내 대사는 `line()`에서 소리가 있고, 읽는 법은 `await engine.three(...)`로 오며 기록에 남는다.
  - `test_prep_survives_restart` → 두 번째 엔진에서 `line()`이 소리를 주고, `three()`가 읽는 법을 준다.
  - `test_claude_down_while_preparing_is_retried_next_time` → `line()`은 오류 없이 오고, 첫 `three()`가 `ClaudeUnavailable`, 다음 `three()`가 읽는 법을 준다.
  - `test_model_audio_starts_before_notes_finish` → 읽는 법이 막혀 있는 동안 `line(1)`이 소리와 함께 `three is None`으로 온다. 막힘을 풀면 `three()`가 읽는 법을 준다.
  - `test_a_line_whose_sound_failed_still_has_its_notes` → 이름을 `test_a_line_whose_sound_failed_still_gets_its_notes`로, 줄은 소리 없이 오고(읽는 법을 기다리지 않음) `three()`가 읽는 법을 준다.
  - 새 `test_notes_asked_while_made_in_the_background_share_one_call`: 읽는 법을 막은 채 대본을 만들고, `three()`를 두 번 부른 뒤 풀면 그 줄의 `annotate` 부름은 한 번이다.
  - `test_picks.py`의 도우미 `ready(engine, rp)`는 내 대사마다 `engine.three`도 기다리게 하고, `engine.ready(l)`로 「준비가 다 됐다」를 보던 곳은 `engine.prepared(l)`로 바꾼다.
  - 새 `test_api.py` `test_learner_line_comes_while_claude_is_down`: 읽는 법이 실패하게 하고 줄 받기는 200, 읽는 법 받기는 503 `claude_down`.
- [ ] **Step 2: 실패를 본다** — `cd server && uv run pytest -q`, 위 시험들이 FAIL
- [ ] **Step 3: 구현** — `_prepare`는 소리만 만든다. 읽는 법 일은 `three()`에서 꺼낸 `_three_task(rp_id, idx)`로 시작한다. `create`, `copy`, `create_pick`은 `prepared`로 뒤에서 만들 줄을 고른다.
- [ ] **Step 4: 통과를 본다** — `cd server && uv run pytest -q` 모두 PASS
- [ ] **Step 5: 커밋** (`feat(server): hand out a learner line before its notes are made`)

### Task 2: 앱은 지금 말할 줄의 읽는 법을 받아 온다

**Files:**
- Modify: `app/src/ui/notesView.ts` (새 순수 함수), `app/src/screens/RoleplayScreen.tsx`(읽는 법 받기 효과와 `LineToSay`의 `three`)
- Test: `app/src/ui/notesView.test.ts`(있으면 더하고, 없으면 만든다)

**Interfaces:**
- Produces: `lineNotes(line: ScriptLine, fetched: ThreeLine | "loading" | undefined): ThreeLine | "loading" | null` — 줄에 온 읽는 법, 없으면 받아 온 것(받는 중이면 `"loading"`), 둘 다 없으면 `null`. `needsNotes(line: ScriptLine, fetched: ThreeLine | "loading" | undefined): boolean` — 줄에 읽는 법이 없고 아직 받으러 가지 않았으면 참.

- [ ] **Step 1: 시험** — `lineNotes`: 줄의 것이 먼저, 그다음 받아 온 것, 받는 중은 `"loading"`, 없으면 `null`. `needsNotes`: 줄에 있으면 거짓, 받는 중이거나 받았으면 거짓, 아니면 참. `notesView(lineNotes(...), false)`가 받는 중에도 `"closed"`(버튼이 보임).
- [ ] **Step 2: 실패를 본다** — `cd app && npx jest src/ui/notesView.test.ts`
- [ ] **Step 3: 구현** — 따라 말하기에만 걸던 읽는 법 받기 효과를 지금 말할 줄 모두(`myTurn`인 줄)에 건다(`needsNotes`, `state.phase === "ready"`). `LineToSay`에는 모드와 상관없이 `lineNotes(line, threes[line.idx])`를 넘긴다.
- [ ] **Step 4: 통과를 본다** — `cd app && npx jest && npm run typecheck`
- [ ] **Step 5: 커밋** (`feat(app): fetch the notes of the line to say when they come later`)

### Task 3: 시간을 재고, 문서와 APK

- [ ] **Step 1: 시간** — PR #34 devlog와 같은 방법(빈 포트 확인, 기록은 세 항목만 복사, `127.0.0.1:8791`/`8792`)으로 운동화와 경복궁을 각각 처음 고르고, 첫 내 대사까지와 그 줄의 `three`가 돌아오기까지를 잰다. Expected: 첫 내 대사까지 1초 안팎(소리는 같은 글이면 바로 나온다). 시험 서버를 끄고 복사본을 지운다.
- [ ] **Step 2: 문서** — 역할극 뒤 연습 스펙 8의 「펼쳤는데 세 줄이 아직 없으면」 줄에 새 스펙을 가리키는 한 줄을 더한다. 원래 폴더의 할 일 03을 이 worktree로 옮겨 상태를 완료로 하고 1~3이 어떻게 끝났는지 적는다.
- [ ] **Step 3: APK** — `app/README.md`대로 빌드한다(JDK 17, `-PreactNativeArchitectures=arm64-v8a`). 폰에는 사용자가 깨어 있을 때 깐다(다른 카드의 앱을 덮는다).
- [ ] **Step 4: 커밋** (`docs: point the roleplay-practice spec at the notes that come later`)
