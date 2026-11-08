# 선생님 라이언의 답: 마지막 리뷰가 미룬 작은 것 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 선생님 라이언의 답(PR #29)의 마지막 리뷰가 미룬 작은 것 여섯(할 일 1~6)을 고친다. 할 일 7(0.3 기준)은 폰에서 써 봐야 정하므로 새 할 일 파일로 옮긴다.

**Architecture:** 기능은 바꾸지 않는다. 맥 서버의 `Engine._aside`가 빈 답과 끊긴 답을 정해진 말로 메우고, 두 번째 받아쓰기(`Whisper.transcribe_auto`)가 실패해도 영어 글로 이어 가며, Claude에 넘기는 앞서 한 말을 그 줄의 마지막 시도 뒤로 좁힌다. 쓰지 않는 코드와 대본 다시 쓰기를 말하는 낡은 주석을 지우고, 빠진 서버 시험을 채운다.

**Tech Stack:** Python(맥 서버, pytest), React Native + Expo(앱, 주석만). 새 꾸러미 없음.

**Spec:** `docs/superpowers/specs/2026-11-07-offscript-aside-design.md`. 할 일은 원래 폴더의 `docs/todo/20261107_10_todo_offscript_aside_minors.md`(아직 커밋하지 않은 파일, 마지막 커밋에 「완료」로 넣는다).

## Global Constraints

- 새로 설치하는 것이 없다. 테스트 문장은 지어낸 것을 쓴다(공개 저장소, ADR-0005). 녹음을 받아쓴 글을 옮기지 않는다.
- 커밋은 `/usr/bin/git`, `git commit -F - <<'EOF'`, 앞 커밋이 성공해야 다음이 돌게 `&&`로 잇는다. 첫 줄 72자 이내.
- 테스트: 서버 `cd server && uv run pytest -q`, 앱 `cd app && npx jest && npx tsc --noEmit`, 훅 `node --test 'scripts/**/*.test.mjs'`.
- 같이 도는 카드(fixed-list-scripts, review-screens-minors)가 `engine.py`의 `ready`, `line`, `three`, 앱 `RoleplayScreen.tsx`를 고친다. 그 부분은 주석 한 줄 말고는 건드리지 않는다.

## 정한 것 (AI 판단)

- **실행 방식:** 이 세션이 직접 고친다(executing-plans). 작업이 작고 대부분 `engine.py`의 한 함수 둘레라, 작업마다 새 에이전트를 띄우면 같은 맥락을 다시 읽는 데 더 든다. 끝에 브랜치 전체를 pr-review로 본다. 사용자는 자는 중이라 묻지 않고 골랐다.
- **빈 답(할 일 1):** 스트림이 오류 없이 끝났는데 공백 말고 글이 없으면 `retry_offscript`를 낸다. 거절(`stop_reason` refusal)을 따로 읽지 않는다. 글 없이 끝나면 다 같은 경우다.
- **끊긴 답(할 일 4):** 끊긴 조각이 `.`, `?`, `!`로 끝나지 않으면 마침표를 넣고 한 칸 띄어 정해진 말을 잇는다. `sentences.SentenceBuffer`가 문장을 자르는 부호와 같게 해서, 목소리도 두 문장으로 읽는다. 조각 끝의 공백은 다음 글이 올 때까지 내보내지 않는다. 공백 뒤에 마침표가 붙지 않게 하려는 것이다(「말이 . 이번에는」).
- **두 번째 받아쓰기 실패(할 일 2):** `asr.py`에 `WhisperError`를 두고 `Whisper._infer`가 whisper-server의 HTTP 오류, 연결 오류, JSON이 아닌 답을 그것으로 바꾼다. `Engine.attempt`는 자동 받아쓰기의 `WhisperError`만 잡고 영어 글로 이어 간다. 첫 번째(영어) 받아쓰기가 실패하는 것은 지금처럼 그 시도가 실패한다(할 일 범위 밖).
- **앞서 한 말의 범위(할 일 3):** 그 줄의 시도 가운데 마지막으로 `aside`가 아닌 시도(따라 말한 시도, 짚을 것이 있던 시도, 옛 기록의 시도) 뒤의 것만, 많아야 세 개(`ASIDES_KEPT`) 넘긴다. 따라 말하지 않고 연습을 그만둔 뒤 다른 날 같은 줄을 연습하면 그때의 말이 아직 넘어간다. 시도의 날짜로 자르면 막을 수 있지만, 할 일이 정한 방법을 따르고 PR 「한계」에 적는다.
- **할 일 7:** 원래 폴더의 `docs/todo/20261108_07_todo_near_min_threshold.md`로 옮긴다(untracked).

## Review Focus

- 공백만 흘려 받은 답: 빈 답처럼 정해진 말만 나와야 한다 → Task 2.
- 공백으로 끝난 조각에서 끊긴 답: 「말이. 이번에는」처럼 마침표가 글 바로 뒤에 붙어야 한다 → Task 2.
- whisper-server가 200인데 JSON이 아닌 답을 줄 때: 오류 화면이 아니라 영어 글로 이어 가야 한다 → Task 3.
- 대사에 가까운 영어인데 자동 받아쓰기가 실패할 때: 맥이 찾은 짚을 것은 그대로 가고 「다음」으로 넘어가야 한다 → Task 3.
- 앞선 시도가 짚을 것이 있던 시도일 때: 따라 말한 시도처럼 앞서 한 말의 경계가 되어야 한다 → Task 4.

---

### Task 1: 한국어로 한 말 뒤 첫 차례를 따라 말하면 다음 줄로 (할 일 6)

빠진 시험을 채운다. 지금 코드로 통과해야 한다. 뒤 작업이 `attempt`를 고치는 동안 이 흐름을 지킨다.

**Files:** Test `server/tests/test_aside.py`.

- [ ] **Step 1: 시험 `test_first_turn_after_a_korean_aside_moves_on`**
  - 영어 받아쓰기 `""`, 자동 받아쓰기 `("잠깐만요, 다시 할게요", "korean")`로 `turn`을 보낸다: `ev[0] == {"type": "heard", "text": "잠깐만요, 다시 할게요", "followed": False}`, `ev[-1] == {"type": "done", "next": user_idx, "issues": 0}`, 저장한 `pos`는 그대로, 마지막 시도의 `aside is True`.
  - 이어서 영어 받아쓰기를 그 줄의 대사로 바꿔 다시 `turn`을 보낸다: `ev[-1]["next"] == user_idx + 1`, `rp.pos == user_idx + 1`.
- [ ] **Step 2:** `cd server && uv run pytest -q tests/test_aside.py` → 통과.
- [ ] **Step 3: 커밋** `test(server): pin the first turn moving on after a Korean aside`

### Task 2: 빈 답과 끊긴 답을 정해진 말로 메우기 (할 일 1, 4)

**Files:** Modify `server/je_server/engine.py`(`Engine._aside`). Test `server/tests/test_aside.py`.

**Interfaces:** `Engine._aside(text: AsyncIterator[str]) -> AsyncIterator[str]`는 그대로다. 부르는 곳(`attempt`)도 그대로.

- [ ] **Step 1: 실패하는 시험**
  - `test_aside_empty_answer_says_the_fixed_phrase`(`aside_pieces`가 `[]`와 `["  "]` 둘로 parametrize): `said(ev) == engine.said("retry_offscript").text`, 오류 이벤트 없음, 끝은 `done`, 저장한 `say_ko`도 정해진 말.
  - `test_aside_cut_midsentence_ends_it_before_the_fixed_phrase`(parametrize): `aside_pieces=["괜찮아요, 말이 ", "꼬일 수", " 있어요."]`(셋째는 오지 않는다), `aside_fail_after=2` → `said(ev) == "괜찮아요, 말이 꼬일 수. " + fixed`. 같은 조각에 `aside_fail_after=1` → `"괜찮아요, 말이. " + fixed`. 목소리에 간 라이언의 한국어 문장(`fake_voice.calls`)의 마지막 둘이 조각과 정해진 말로 나뉜다.
  - 있는 `test_aside_claude_cut_midway_ends_with_fixed_phrase`는 `said(ev) == "괜찮아요, 말이 꼬일 수 있어요. " + fixed`(한 칸)로 좁힌다.
- [ ] **Step 2:** `uv run pytest -q tests/test_aside.py` → 새 시험이 실패한다(빈 답은 글이 없고, 끊긴 조각에는 마침표가 없다).
- [ ] **Step 3: `_aside` 고치기.** 받은 조각마다 끝의 공백을 떼어 두었다가 다음 조각 앞에 붙여 낸다. 끝까지 낸 글이 없으면 정해진 말을 낸다. `ClaudeUnavailable`이면 낸 글이 `.`, `?`, `!`로 끝나지 않을 때 `"."`을 붙이고 `" "`와 정해진 말을 낸다. 낸 글이 없으면 정해진 말만. 기록에는 빈 답이면 `aside answer empty`, 끊기면 지금처럼 `aside answer unavailable`(글은 남기지 않는다).
- [ ] **Step 4:** `uv run pytest -q` → 모두 통과.
- [ ] **Step 5: 커밋** `fix(server): fill an empty or cut teacher answer with the fixed phrase`

### Task 3: 두 번째 받아쓰기가 실패해도 영어 글로 (할 일 2)

**Files:** Modify `server/je_server/asr.py`, `server/je_server/engine.py`(`attempt`). Test `server/tests/test_asr.py`, `server/tests/test_aside.py`, `server/tests/fakes.py`(`FakeWhisper`).

**Interfaces:**
- Produces: `asr.WhisperError(Exception)`. `Whisper._infer`(그래서 `transcribe`, `transcribe_auto`, `hear`)가 whisper-server가 답하지 못하면 이것을 던진다.
- `FakeWhisper.auto_fail: bool = False`. 참이면 `transcribe_auto`가 `WhisperError("fake")`를 던진다(부른 기록 `langs`에는 `"auto"`가 남는다).

- [ ] **Step 1: 실패하는 시험**
  - `test_asr.py`의 `test_whisper_failures_are_whisper_errors`(parametrize): 500 답, 200인데 JSON이 아닌 글(`"oops"`), 처리기가 `httpx.ConnectError`를 던질 때 모두 `transcribe_auto`가 `WhisperError`를 던진다.
  - `test_aside.py`의 `test_auto_transcription_failing_goes_on_in_english`: `fake_whisper.text = "Wait, let me try that again."`, `auto_fail = True` → `ev[0]["text"]`가 영어 글, 라이언의 답이 나오고(`aside_calls[-1]["heard_ko"] is None`), 끝은 `done`.
  - `test_auto_transcription_failing_keeps_the_macs_points`: `fake_whisper.text = "It's light over hair."`, `auto_fail = True` → `ev[-1] == {"type": "done", "next": user_idx + 1, "issues": 2}`.
- [ ] **Step 2:** `uv run pytest -q tests/test_asr.py tests/test_aside.py` → 새 시험이 실패한다.
- [ ] **Step 3: 고치기.** `_infer`가 `httpx.HTTPError`와 `ValueError`(JSON이 아님)를 `WhisperError`로 바꿔 던진다(`from e`). `attempt`는 `transcribe_auto`의 `WhisperError`를 잡아 `auto transcription failed`를 기록하고 `heard_ko`를 비운 채 간다. `asr.py` 머리글에 실패하면 영어 글로 간다는 것을 한 줄 더한다.
- [ ] **Step 4:** `uv run pytest -q` → 모두 통과.
- [ ] **Step 5: 커밋** `fix(server): go on in English when the auto transcription fails`

### Task 4: 앞서 한 말은 그 줄의 마지막 시도 뒤의 것만 (할 일 3)

**Files:** Modify `server/je_server/engine.py`(`attempt`의 `asides`). Test `server/tests/test_aside.py`.

- [ ] **Step 1: 실패하는 시험** `test_earlier_asides_stop_at_the_last_try_at_the_line`(경계 시도의 영어 받아쓰기를 `"It's right over there."`(따라 말함)와 `"It's light over hair."`(짚을 것이 있음)로 parametrize, 모두 `practice`): 선생님에게 한 말(`"Wait, let me try that again."`) 하나, 경계 시도 하나, 선생님에게 한 말(`"What does this mean?"`) 둘을 보낸다. 마지막 `aside_calls[-1]["earlier"] == [("What does this mean?", "괜찮아요, 말이 꼬일 수 있어요. 다시 해 볼까요?")]`.
- [ ] **Step 2:** `uv run pytest -q tests/test_aside.py` → 실패한다(경계 앞의 말도 넘어간다).
- [ ] **Step 3: 고치기.** 그 줄의 시도에서 마지막으로 `aside`가 아닌 시도의 뒤만 남기고, 그 끝 `ASIDES_KEPT`개를 넘긴다. `ASIDES_KEPT` 옆 주석을 「the asides after the line's last try at it」으로 고친다.
- [ ] **Step 4:** `uv run pytest -q` → 모두 통과(있는 `test_earlier_asides_on_the_line_go_to_claude`도).
- [ ] **Step 5: 커밋** `fix(server): send only the asides since the line's last try`

### Task 5: 쓰지 않는 코드와 낡은 주석 (할 일 5)

**Files:** Modify `server/je_server/engine.py`, `server/je_server/app.py`, `server/je_server/claude.py`, `app/src/flow/state.ts`, `app/src/screens/RoleplayScreen.tsx`.

- [ ] **Step 1:** `engine.py`의 `_one`을 지운다(`grep -rn "_one" server`로 부르는 곳이 없는지 먼저 본다).
- [ ] **Step 2: 주석 고치기.** 대본 다시 쓰기는 2026-11-07에 없앴으니, 지금 하는 일처럼 말하는 곳을 고친다.
  - `app.py` 줄 받기: 「waits for a rebuild, so the count is of the whole script」 → 그 줄의 노트와 본보기 소리를 기다린다는 말.
  - `engine.py`의 `ko`: 「nor for a rebuild of the rest of the script」를 지운다.
  - `claude.py`의 `LIVE_OPTIONS` 주석: 「off-script reply」 → 「teacher Ryan's answer」.
  - `state.ts`의 `practiseLine`: 「asking the server could wait for a rebuild …」 → 앱이 이미 가진 줄이라 서버를 기다리지 않는다는 말.
  - `RoleplayScreen.tsx`의 `canPractise` 주석: 「his reply」 → 「teacher Ryan's answer」.
  - `engine.py`에서 옛 기록에만 해당하는 설명(`_make_ko`의 「Ryan's reply answers …」, `summary`의 「Ryan's reply to a line said differently」와 `point_ko` 주석, `saved`의 「rebuilt」)에 「records from before 2026-11-07」을 밝힌다.
- [ ] **Step 3:** 서버 `uv run pytest -q`, 앱 `npx jest && npx tsc --noEmit` → 모두 통과. `grep -rn -i "rebuild\|off-script" server/je_server app/src`에 옛 기록을 말하는 것만 남는다.
- [ ] **Step 4: 커밋** `refactor: drop _one and comments about the removed script rewrite`

### Task 6: 문서

**Files:** Modify `docs/superpowers/specs/2026-11-07-offscript-aside-design.md`, `docs/guide/SPEECH_맥서버_받아쓰기와_목소리_20261105.md`.

- [ ] 스펙 2: 자동 받아쓰기가 실패하면 한국어 글 없이 영어 글로 간다. 스펙 3: 「앞서 선생님에게 한 말」은 그 줄의 마지막 시도 뒤의 것, 많아야 세 번. Claude가 글 없이 끝나도 정해진 말, 끊긴 조각에는 마침표를 넣고 잇는다. 각각 날짜(2026-11-08)와 이유를 짧게.
- [ ] SPEECH 가이드의 「고친 것」에 자동 받아쓰기가 실패하면 영어 글로 간다는 것 한 줄.
- [ ] 커밋 `docs: record the teacher-answer fallbacks and the asides range`

## 마무리

1. 할 일 7을 원래 폴더의 `docs/todo/20261108_07_todo_near_min_threshold.md`로 옮긴다(untracked). 20261107_10을 worktree에 복사해 상태를 「완료」로 고치고(7을 어디로 옮겼는지 적는다) 마지막 커밋에 넣는다.
2. 실제 서버 시험: worktree 서버를 `JE_HOST=127.0.0.1 JE_PORT=8795 JE_WHISPER_PORT=8796`으로 원래 서버 옆에 띄운다. 제이크 목소리로 지어낸 녹음 둘(한국어로 묻는 말, 그 줄의 대사)을 `scripts/try_recordings.py`로 `turn`에 차례로 보낸다. 첫째는 선생님의 답과 같은 줄, 둘째는 다음 줄. 소넷 한 번, 하이쿠 한 번(1센트 안쪽). 복사본과 녹음을 지우고 서버를 끈다.
3. push, PR, pr-review, devlog. 앱은 주석만 바뀌어 APK를 빌드하지 않는다. 머지 뒤 원래 폴더 서버를 다시 띄운다.
