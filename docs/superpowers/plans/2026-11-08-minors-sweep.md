# 쌓인 작은 할 일 정리 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 11월 5~8일 리뷰들이 미룬 작은 할 일 여덟 개 가운데 아직 해당하는 것을 고치고, 해당하지 않는 것과 할 일 하나를 닫는다.

**Architecture:** 기능은 더하지 않는다. 앱 PR(브랜치 `fix/minors-sweep`)과 서버 PR(브랜치 `fix/minors-sweep-server`, 이 계획 커밋에서 갈라진다) 둘로 나눈다. 서버는 소리 이름에 기준 녹음 지문을 넣는 것이 가장 크고, 나머지는 함수 하나씩 고친다.

**Tech Stack:** 서버 Python(FastAPI, pytest, uv), 앱 React Native + Expo(jest, tsc). 새 꾸러미 없음.

**Spec:** 원래 폴더 `docs/todo/`의 할 일 파일(아직 커밋하지 않았고, 끝내는 커밋에 「완료」로 넣는다): `20261105_11_todo_roleplay_mvp_review_minors.md`, `20261106_04_todo_practice_midway_review_minors.md`, `20261106_05_todo_follow_feedback_leftovers.md`, `20261105_13_todo_voice_reference_in_sound_key.md`, `20261108_08_todo_fixed_list_scripts_minors.md`, `20261108_09_todo_review_screens_minors_followup.md`, `20261108_10_todo_teacher_answer_cut_without_error.md`, `20261108_11_todo_line_notes_minors.md`. 닫는 것은 `20261104_05_todo_merge_checklist_gate.md`.

## Global Constraints

- 같이 도는 server-small-fixes 카드가 `server/je_server/claude.py`, `prompts.py`, `topics.py`, `tests/test_claude.py`, `tests/test_topics.py`, `scripts/check_ryan_wording.py`를 고친다. 이 파일을 건드리는 Task S8은 그 PR이 머지된 뒤 origin/main을 merge하고 한다.
- 테스트와 문서의 문장은 지어낸 것을 쓴다. 맥의 기록과 녹음에서 나온 낱말은 공개 파일에 옮기지 않는다. 기록으로 잰 것은 숫자만 적는다. 할 일 파일에 적힌 예문도 출처를 알 수 없으면 옮기지 않고 새로 지어낸다(PR #43 리뷰).
- 커밋은 `/usr/bin/git`, `git commit -F - <<'EOF'`, 앞 커밋이 성공해야 다음이 돌게 `&&`로 잇는다. `git add`는 파일을 지정한다.
- 테스트: 서버 `cd server && uv run pytest -q`, 앱 `cd app && npx jest && npx tsc --noEmit`.
- 시험 서버는 `JE_HOST=127.0.0.1 JE_PORT=8793 JE_WHISPER_PORT=8794`, 데이터는 복사본. 원래 폴더 서버(launchd)는 멈추지 않는다.

## 할 일별 판단

| 할 일 | 항목 | 지금 코드 | 판단 |
|---|---|---|---|
| 20261105_11 | 1 `_continue` | PR #29(offscript-aside)가 대본을 다시 만드는 일을 없애며 `_continue`를 지웠다 | 해당 없음, 닫는다 |
| | 2~6 | 이미 고쳤거나 생기지 않음(파일에 적힘), 4번은 `app.py` `/audio`가 `engine().voice`를 쓴다 | 닫는다 |
| 20261106_04 | 1 「뒤로」 두 번 | 남음 | Task A1 |
| | 2 최근 라이언 말풍선 | 남음. 지난 말풍선은 이제 접혀 있어(PR #31) 펼쳤을 때만 보인다 | Task A2 |
| | 3 첫 「다시 해 보기」의 본보기 | 남음(키가 `줄:turn`에서 `줄:retry`로 바뀜) | 사용자가 「다시 틀지 않는다」로 정함, Task A3 |
| 20261106_05 | 1 짧은 대사의 같은 정도 | 남음 | Task S5 |
| | 2 되풀이 | 남음 | Task S5 |
| | 3 조사, 소문자 | 남음 | 조사 꼴은 사용자가 「대사에 없는 「and」도 들렸어요」로 정함, Task S6 |
| | 4 「old rule flagged」 | 남음 | Task S6 |
| | 5 100만 이상, dollar 뺀 값 | 남음 | Task S6 |
| | 6 o'clock, 사용자가 할 것 | 받아쓰기 자료와 사용자 녹음이 있어야 한다 | 새 할 일로 옮긴다(Task S9) |
| 20261105_13 | 기준 녹음 지문 | 남음 | Task S4 |
| 20261108_08 | 1 `copy`의 `try` | 남음 | Task S3 |
| | 2, 5 목록 대본 | 남음, `topics.py`라 기다린다 | Task S8 |
| | 3 고를 때 기록 읽기 | 기록이 수백 개가 될 때의 일 | 새 할 일로 옮긴다(Task S9) |
| | 4 목록 회차가 옛 소리 키를 가져옴 | Task S4로 기준 녹음이 키에 들어가면 바로 생긴다 | Task S4 |
| 20261108_09 | 1, 2 | 남음 | Task A4, A5 |
| 20261108_10 | 1 `stop_reason` | 남음, `claude.py`라 기다린다 | Task S8 |
| | 2, 3 | 남음(`engine.py`, 테스트, `asr` 기록) | Task S7 |
| 20261108_11 | 1 콜백, 2 닿지 않는 `except` | 남음. 2의 주석은 이미 고쳐져 있다 | Task S1, S2 |
| | 3 「읽는 법 보기」 깜빡임 | 남음 | Task A6 |
| 20261104_05 | 체크리스트 강제 | PR #37이 사용자 몫의 빈 칸을 없앴다 | 닫는다(Task A7) |

## 정한 것 (AI 판단)

- **기준 녹음 지문(S4):** 작업 프로세스가 준비될 때 목소리와 언어마다 기준 녹음(`.wav`, `.txt`) 내용의 sha256 앞 16자를 알린다. 영어 소리는 영어 기준 녹음만 쓰므로 그것만, 한국어 소리는 영어 조각을 섞어 읽을 수 있어 그 목소리의 기준 녹음을 모두 넣는다. 그래서 라이언의 한국어 기준 녹음만 바꾸면 영어 대사 소리(가장 많다)는 그대로 쓴다. 지문이 없으면(옛 작업 프로세스, 시험 가짜) 지금 키와 같다. 처음 바꿀 때 모든 소리 키가 한 번 바뀌어 새로 만든다(맥에서만, 돈 들지 않음).
- **옛 키(08-4, S4):** 목록 회차와 「이 상황 다시 하기」는 앞 회차의 소리 키가 지금 키와 같을 때만 가져온다. 역할극 자기 기록의 키는 그대로 둔다(그때 들은 소리다).
- **같은 정도(S5):** `compare`가 맞춘 결과로 낸다. 맞은 낱말 수를 양쪽에서 세어 `(맞은 대사 낱말 + 맞은 들린 낱말) / (대사 낱말 + 들린 낱말)`. 군말과 되풀이는 양쪽 수에서 뺀다. 그냥 같은 글이면 지금 값과 같다.
- **되풀이(S5):** 바로 앞이나 뒤의 대사 낱말 덩어리를 여러 번 되풀이한 것(We, we, we need), 그 덩어리와 첫 낱말이 같고 반 넘게 같은 것(Could I sit the, could I see the)도 되풀이로 본다. 바꾼 뒤 맥의 기록으로 짚은 수를 다시 재 숫자만 적는다.
- **대소문자(S6):** 끝 화면 문구만 대사와 들린 말에 적힌 꼴로 되돌린다. 같은 낱말이 소문자로도 적혀 있으면 소문자로 둔다. 저장하는 `Issue`와 비교는 소문자 그대로다.
- **dollar 뺀 값(S6):** `$5.99`를 「five dollars ninety nine」, 「five ninety nine」, 「five dollars and ninety nine cents」 셋 다 맞게 본다(숫자 읽기 후보와 같은 방법).
- **끊긴 조각 끝(S7):** 닫는 괄호와 따옴표를 떼고 `.`, `?`, `!`, `…`로 끝나면 마침표를 더하지 않는다. 조각이 `.`, `?`, `!`로 끝나면 뒤 공백을 잡아 두지 않는다.
- **뒤로(A1):** 연습 중의 뒤로는 연습 밖에서 아무 일도 하지 않는 `endPractice`로 보낸다. 무엇을 보낼지는 `leaveAction(state)`가 정해 리듀서 시험으로 잡는다.
- **읽는 법(A6):** 받다 실패한 줄은 따로 적고, 아직 받으러 가기 전은 「받는 중」으로 본다. 실패한 줄은 「다시 해 보기」로 다시 받지 않는다(스펙 roleplay-practice 8의 「읽는 법 없이 글만」).
- 실행 방식은 직접 구현(executing-plans)이다. 작업이 서로 기대지 않고 작다.

## Review Focus

1. 기준 녹음을 바꾸지 않았는데 서버를 다시 띄울 때마다 소리를 새로 만들면 안 된다(지문이 같은 내용에서 늘 같아야 한다). Task S4 테스트.
2. 같은 정도를 바꾼 뒤 맞게 따라 말한 녹음이 「다르게 말함」으로, 다른 말이 「따라 말함」으로 넘어가면 안 된다. Task S5에서 맥의 기록으로 넘어가는 수를 잰다.
3. 연습에서 「뒤로」를 한 번만 누르면 지금처럼 연습만 빠져나가야 한다. Task A1 테스트.
4. 읽는 법을 받지 못한 줄에서 「읽는 법 보기」가 떴다가 사라지기를 되풀이하지 않아야 한다. Task A6 테스트.
5. 끊긴 답에 정해진 말을 붙일 때 공백이 둘이 되거나 빠지지 않아야 한다. Task S7 테스트.

---

## 앱 PR (`fix/minors-sweep`)

### Task A1: 연습에서 「뒤로」를 빨리 두 번 눌러도 묻지 않고 떠나지 않는다 (06_04-1)

**Files:** Modify `app/src/flow/state.ts`, `app/src/screens/RoleplayScreen.tsx` (`leave`). Test `app/src/flow/state.test.ts`.

**Interfaces:** Produces `Action` `{ type: "endPractice" }`, `leaveAction(s: State): Action`.

- [ ] 실패하는 테스트: `leaveAction(stale)`를 두 번 적용해도 연습 하나만 빠져나간다.

```ts
test("back pressed twice before a render leaves only the practice", () => {
  const midway = /* 역할극 중 연습(from "roleplay") 상태 */;
  const once = reduce(midway, leaveAction(midway));
  const twice = reduce(once, leaveAction(midway)); // the second tap still sees the practice
  expect(twice).toEqual(once);
  expect(twice.screen).toBe("roleplay");
  expect(twice.practice).toBeNull();
});
// 끝 화면에서 시작한 연습도 같다: twice.screen === "end"
// 연습 밖: leaveAction(s) 는 { type: "back" }
```

- [ ] `npx jest src/flow/state.test.ts` 실패 확인.
- [ ] `endPractice`: `s.screen === "roleplay" && s.practice ? leavePractice(s) : s`. `leaveAction`: 연습이면 `endPractice`, 아니면 `back`. `leave()`가 `dispatch(leaveAction(state))`.
- [ ] 테스트 통과, 커밋 `fix(app): leave only the practice when back is tapped twice`.

### Task A2: 막 끝난 라이언 말풍선에도 「따라 말하기」가 있다 (06_04-2)

**Files:** Modify `app/src/flow/state.ts` (`practiceFor`). Test `app/src/flow/state.test.ts`.

- [ ] 실패하는 테스트: `ryanDone` 뒤(phase `loading`, `line`은 아직 라이언 줄) `practiceFor(s, { kind: "ryan", idx: 그 줄 })`이 `"shadow"`. 내 말풍선이 화면의 줄이면 그대로 `null`.
- [ ] 「화면의 줄」 빼기를 `b.kind === "user"`에만 건다.
- [ ] 테스트 통과, 커밋 `fix(app): offer shadowing on ryan's newest bubble while the next line loads`.

### Task A3: 첫 「다시 해 보기」의 본보기 (06_04-3)

사용자가 스펙대로 다시 틀지 않기로 정했다(2026-11-08, main 세션을 거쳐). 들으려면 「🔊 다시 듣기」를 누른다.

- [ ] 실패하는 테스트: 같은 줄의 `turn`과 `retry`에서 `modelKey`가 같다. 연습 안의 키는 지금처럼 연습 번호를 담는다.
- [ ] 연습 밖의 키를 `${idx}`로 한다.
- [ ] 커밋 `fix(app): keep the model from playing again on the first retry`.

### Task A4, A5: 빼기 두 번 누르기 시험, 낱자 한글 잇기 (09)

**Files:** Test `app/src/flow/savedStore.test.ts`. Modify `app/src/ui/keepWords.ts`, test `app/src/ui/keepWords.test.ts`.

- [ ] A4 테스트: 첫 `remove`가 끝나기 전에 둘째 `remove`를 부르면 `set`이 한 번만 불린다. 이미 있는 막기를 지키는 시험이라, `remove`의 `busy` 확인을 잠시 빼서 실패하는 것을 보고 되돌린다.
- [ ] A5 실패하는 테스트: `keepWords("ㅋㅋ")`, `keepWords("좋아요ㅠㅠ")`의 글자 사이에 이음 문자가 든다. 영어 사이는 그대로.
- [ ] `HANGUL`을 `/[가-힣ㄱ-ㅎㅏ-ㅣ]/`로 넓힌다.
- [ ] 커밋 둘: `test(app): guard the second tap on remove in the saved store`, `fix(app): keep hangul jamo together on android`.

### Task A6: 「읽는 법 보기」가 늦게 생기거나 깜빡이지 않는다 (11-3)

**Files:** Modify `app/src/ui/notesView.ts`, `app/src/screens/RoleplayScreen.tsx` (`fetchThree`, 「읽는 법」 효과, `LineToSay`의 `three`). Test `app/src/ui/notesView.test.ts`.

**Interfaces:** `lineNotes(line, fetched, failed: boolean): ThreeLine | "loading" | null`, `needsNotes(line, fetched, failed: boolean): boolean`.

- [ ] 실패하는 테스트: `lineNotes(line, undefined, false)`는 `"loading"`(버튼이 처음부터 있다), `lineNotes(line, undefined, true)`는 `null`, `needsNotes(line, undefined, true)`는 `false`.
- [ ] 화면: `fetchThree`가 실패하면 그 줄을 `noNotes`에 적고, 시작할 때 지운다. 지난 말풍선의 「읽는 법 보기」는 지금처럼 다시 받는다.
- [ ] 커밋 `fix(app): show the notes button from the first frame and stop refetching failed notes`.

### Task A7: 시험, 닫는 할 일, PR

- [ ] 앱 전체 시험. 에뮬레이터(또는 폰)에서 A1(뒤로 두 번: `adb shell input keyevent 4 4`), A2, A3, A6을 본다(`docs/guide/DEVENV_폰을_adb로_시험하기_20261108.md`).
- [ ] `20261104_05`를 닫는 이유와 함께 docs 커밋. `20261106_04`, `20261108_09`는 끝내는 커밋에 「완료」로.
- [ ] PR, 리뷰(pr-review), 「머지 준비 됨」.

## 서버 PR (`fix/minors-sweep-server`)

### Task S1, S2: 읽는 법과 통역의 정리 콜백, 닿지 않는 `except` (11-1, 11-2)

**Files:** Modify `server/je_server/engine.py` (`_three_task`, `ko`), `server/je_server/app.py` (`line`). Test `server/tests/test_engine.py`.

- [ ] 실패하는 테스트: 첫 일이 실패로 끝나고 그 콜백이 돌기 전에 새 일이 들어오면, 콜백 뒤에도 `engine.threes[key]`가 새 일이다. asyncio의 차례(끝난 일의 콜백은 `call_soon`으로 뒤에 선다)를 써서 정확히 그 틈에 부른다. 통역(`kos`)도 같다.
- [ ] 콜백이 `d.get(key) is task`일 때만 지운다.
- [ ] `line` 경로의 `except ClaudeUnavailable`을 지운다.
- [ ] 커밋 `fix(server): let a finished notes task forget only itself`, `refactor(server): drop the unreachable claude error on the line route`.

### Task S3: 목록 회차의 오류를 삼키지 않는다 (08-1)

- [ ] 실패하는 테스트: 목록에 있는 줄의 `copy`에서 `create_pick`이 `KeyError`를 내면 그 오류가 올라오고 복사본을 만들지 않는다.
- [ ] `topics.pick`으로 먼저 찾고 `create_pick`은 `try` 밖에서 부른다.
- [ ] 커밋 `fix(server): look up the pick before copying a list run`.

### Task S4: 기준 녹음을 바꾸면 소리를 새로 만든다 (13, 08-4)

**Files:** Modify `server/je_server/tts_worker.py`, `server/je_server/tts.py`, `server/je_server/engine.py` (`said`, `_with_ko`, `_sohee_later`, `_prepared`, `copy`), `server/tests/fakes.py`, `server/tests/fake_tts_worker.py`. Test `server/tests/test_tts.py`, `test_tts_worker.py`, `test_picks.py`, `test_engine.py`.

**Interfaces:**
- `tts_worker.ref_prints(srv) -> dict[str, dict[str, str]]`: 작업 목소리 이름 → 언어 → 지문(16자). `{"ready": true, "refs": …}`로 알린다.
- `tts.audio_key(voice, lang, text, ref: str = "") -> str`: `ref`가 비면 지금 키와 같다.
- `Voice.refs: dict[str, dict[str, str]]`(뜰 때마다 받는다), `Voice.key(voice, lang, text) -> str`. `FakeVoice.key`도 둔다.

- [ ] 실패하는 테스트:
  - `ref_prints`: 가짜 모듈(임시 `REF_DIR`, `VOICES`, `ref_name`)에서 같은 파일이면 같은 지문, `.wav`를 바꾸면 그 목소리의 지문만 바뀐다. 라이언의 한국어 기준 녹음을 바꾸면 한국어 지문만 바뀌고 영어는 그대로. 기준 녹음이 없는 목소리는 빈 값.
  - `Voice`: 가짜 작업 프로세스가 `refs`를 알리면 `say`가 그 지문을 담은 키를 돌려주고 `key()`와 같다. 알리지 않으면 지금 키.
  - 엔진: 앞 회차의 `audio`가 지금 키와 다르면 목록 회차와 복사본은 그 소리를 가져오지 않고 새로 만든다. 같으면 가져온다.
- [ ] 구현, 엔진의 `audio_key` 호출을 `self.voice.key`로 바꾼다.
- [ ] 실제 TTS 모듈로 `ref_prints`만 돌려(모델을 불러오지 않는다) 세 목소리의 지문이 나오는지 본다(값은 찍지 않는다).
- [ ] 커밋 `feat(server): put the voice reference in the sound key`.

### Task S5: 같은 정도와 되풀이 (06_05-1, 2)

**Files:** Modify `server/je_server/compare.py` (`Comparison`, `compare`, `_restart`, `similarity`). Test `server/tests/test_compare.py`.

- [ ] 실패하는 테스트: `similarity("Downstairs, please.", "Down stairs, please.") >= FOLLOW_MIN`, `similarity("We need two tickets.", "We need, we need two tickets.") == 1.0`. `find_issues("We need two tickets.", "We, we, we need two tickets.")`와 `find_issues("Could I see the menu?", "Could I sit the, could I see the menu?")`가 빈 목록. 진짜 더한 낱말(`and`)은 그대로 짚는다.
- [ ] 바꾸기 전과 뒤에 맥의 기록으로 같은 정도가 문턱을 넘나드는 차례 수, 짚은 수를 잰다(숫자만).
- [ ] 커밋 `fix(server): judge following by the matched words`, `fix(server): skip stutters and garbled restarts as restarts`.

### Task S6: 끝 화면 문구, 시험 스크립트 이름, 숫자 (06_05-3, 4, 5)

- [ ] 실패하는 테스트: `issue_ko(Issue(target="", heard="and")) == "대사에 없는 「and」도 들렸어요"`(사용자가 고른 꼴, 2026-11-08. 「도」는 받침에 상관없이 붙는다). 대사 「Can I see the menu?」에서 짚은 `i`는 `I`로 보인다. `words("$5.99")`가 「five ninety nine」과도 맞는다(`similarity == 1.0`). `words("2,500,000")`가 「two million five hundred thousand」.
- [ ] `check_false_flags.py`의 「old rule flagged」를 「stored flagged」로.
- [ ] 커밋은 type마다 나눈다.

### Task S7: 선생님 라이언의 끊긴 답 다듬기 (10-2, 3)

- [ ] 실패하는 테스트(`test_aside.py`): 조각이 「…」, 「요.」」로 끝나면 마침표를 더하지 않는다. 조각이 「. 」로 끝나면 그 공백을 바로 보낸다(정해진 말 앞 공백이 둘이 되지 않는다). `test_auto_transcription_failing_goes_on_in_english`에 `fake_whisper.langs == ["en", "auto"]`.
- [ ] `auto transcription failed` 기록에 오류 종류를 붙이고, `fakes.py`, `test_asr.py`의 `WhisperError` 가져오기를 파일 위로.
- [ ] 커밋 `fix(server): end a cut aside answer cleanly`, `refactor(server): log why auto transcription failed`.

### Task S8: server-small-fixes 머지 뒤 (10-1, 08-2, 08-5)

- [ ] origin/main을 merge한다.
- [ ] 실패하는 테스트: `Claude.aside`의 스트림이 `max_tokens`나 `refusal`로 끝나면 `ClaudeUnavailable`. `feedback`은 그대로. 가짜 `_Stream`에 끝 이유를 더한다.
- [ ] 라이언 대사 셋을 한두 문장으로 다듬고(사실은 그대로, `test_topics.py`), 호텔 체크인 주석에 와이파이 비밀번호 자리를 더한다.
- [ ] 커밋 type마다.

### Task S9: 남은 할 일, 문서, 시험, PR

- [ ] 새 할 일: 따라 말하기의 o'clock과 사용자 녹음으로 잴 것, 목록 고를 때 기록 읽기(08-3). 쓰기 직전에 모든 worktree의 같은 날 번호를 본다.
- [ ] 가이드: `SPEECH_맥서버_받아쓰기와_목소리_20261105.md`(기준 녹음 지문), `PRONUNCIATION_따라말하기_짚기_20261106.md`(같은 정도, 되풀이, 숫자, 끝 화면 문구).
- [ ] 시험 서버(8793)에서 학습자 목소리 녹음으로 따라 말하기와 대사와 다른 말을 보내 본다.
- [ ] devlog, 할 일 파일 「완료」, PR, 리뷰, 「머지 준비 됨」.
