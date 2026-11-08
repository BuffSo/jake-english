# 녹음 취소와 건너뛰기 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 녹음하는 동안 「취소」로 녹음을 버리고, 내 차례에 녹음 없이 「건너뛰기」로 「다음」과 같은 곳으로 간다. 한 줄도 말하지 않은 대화의 끝인사는 칭찬을 빼고, 선생님 라이언은 넘어가고 싶다는 말에 「건너뛰기」를 알려 준다.

**Architecture:** 앱만으로 취소와 건너뛰기를 한다. 녹음 시작, 멈춤, 취소, 건너뛰기는 역할극 화면의 게이트 하나를 지나고, 취소와 건너뛰기는 한 뒤 게이트를 잠깐 닫아 둔다(`runThenHold`). 건너뛰기를 받을 때와 가는 곳은 리듀서(`canSkip`, `skip`)가 정한다. 맥 서버는 끝인사 고르기(`Engine.summary`)와 선생님 라이언 지시문(`ASIDE_SYSTEM`)만 바꾸고, API와 기록 모양은 그대로다.

**Tech Stack:** Python 3 + FastAPI(서버, `cd server && uv run pytest -q`), React Native + Expo + jest(앱, `cd app && npx jest && npx tsc --noEmit`). 새 꾸러미 없음.

**Spec:** `docs/superpowers/specs/2026-11-08-record-cancel-skip-design.md`

**실행 방식:** 이 세션이 직접 한다(executing-plans). 앱 작업이 `RoleplayScreen.tsx`와 `flow/` 둘레라, 작업마다 새 에이전트를 띄우면 같은 맥락을 다시 읽는 데 더 든다. 끝에 새 리뷰어 한 명이 브랜치 전체를 보고, PR을 열면 pr-review로 본다. 이 저장소는 머지 전까지 묻지 않으므로(`AGENTS.md` 「PR과 머지」) 고르는 것을 묻지 않았다.

## Global Constraints

- 버튼 글귀(그대로 쓴다): 「취소」, 「건너뛰기」. 큰 버튼 글귀는 지금 그대로(「🎤 말하기」, 「🎤 따라 말하기」, 「■ 말하기 끝」, 「평가하고 있어요」, 「다시 해 보기」, 「다음」, 「대화로 돌아가기」).
- 둘째 줄은 왼쪽 회색(`kind="plain"`) 버튼, 오른쪽 파란 버튼이고, 파란 버튼이 남은 너비를 채운다. 선생님 라이언이 답한 뒤의 「다시 해 보기」는 파랑 그대로.
- 끝인사 글귀: 「대화 끝! 수고했어요.」(정해진 말 `closing_plain`).
- 맥 서버의 API, 기록 모양, 계약 예시(`contract/`)는 바꾸지 않는다. 앱은 맥에 건너뛰기를 알리지 않는다.
- 화면에 보이는 한국어는 `keepWords`를 거친다(APP 가이드). 버튼 글귀처럼 짧은 것은 지금처럼 그대로 둔다.
- 시험 문장과 예는 지어낸다(`REVIEW.md` 「공개 저장소 노출」). 실제 Sonnet 확인은 선생님 라이언 답 5번쯤(한 번에 0.7센트쯤, 다 합해 5센트 안쪽), 횟수와 값을 PR에 적는다.
- 커밋 메시지는 영어 Conventional Commits, 본문에 이유와 시험 결과, 끝에 `Refs: docs/superpowers/specs/2026-11-08-record-cancel-skip-design.md`. AI 서명 줄 없음. git은 `/usr/bin/git`.

## Review Focus

1. **「취소」 두 번:** 취소한 자리에 「건너뛰기」가 나온다. 두 번째 누름이 그 줄을 건너뛰거나 녹음을 다시 시작하면 안 된다. → Task 1 시험 `the gate stays shut a moment after a cancel`, Task 3에서 화면이 건너뛰기와 시작을 같은 게이트로 보낸다.
2. **연습에서 「건너뛰기」 두 번:** 다음 연습 줄의 같은 자리에 「건너뛰기」가 다시 나온다. 한 줄만 넘어가야 한다. → Task 1 같은 시험(건너뛰기도 `runThenHold`로 돈다), Task 2 시험 `two skips from one old state move one line`.
3. **이미 말한 줄을 건너뛰기:** 따라 말해 「다시 해 보기」를 누른 뒤 건너뛰면 대화에 그 줄 말풍선이 둘이 되면 안 된다. → Task 2 시험 `skipping a line already said adds no bubble`.
4. **마지막 줄 건너뛰기:** 끝 화면으로 간다(「다음」과 같다). 그 대화의 끝인사는 말한 줄이 있으면 지금처럼, 없으면 「대화 끝! 수고했어요.」. → Task 2 시험 `skip in the roleplay ...`(다음 줄 번호), 앱 화면에서 `lineMissing`이 끝 화면으로 보낸다(지금 시험 `a missing line ends the roleplay`). Task 4 시험.
5. **선생님에게 한 말만 하고 끝난 대화:** 끝인사가 칭찬하면 안 된다. → Task 4 시험 `test_closing_after_asides_only_has_no_praise`.

---

### Task 1: 게이트를 잠깐 닫아 두는 `runThenHold`

**Files:**
- Modify: `app/src/flow/gate.ts`
- Test: `app/src/flow/gate.test.ts`

**Interfaces:**
- Produces: `export const TAP_HOLD_MS = 400;` 그리고 `export async function runThenHold(gate: ReturnType<typeof createGate>, fn: () => Promise<boolean>, wait: () => Promise<void>): Promise<boolean>` — 게이트가 비어 있으면 그 안에서 `fn`을 돌리고, `fn`이 `true`면 `wait`가 끝날 때까지 게이트를 닫아 둔다. 게이트가 바쁘면 `fn`을 부르지 않고 `false`.

- [ ] **Step 1: 실패하는 시험을 쓴다** (`gate.test.ts`에 더함)

```ts
test("a cancel while a stop runs does nothing, and the stop sends", async () => {
  const gate = createGate();
  const send = jest.fn(async () => {});
  let finish!: (v: string) => void;
  const stop = stopThenSend(gate, () => new Promise<string>((r) => (finish = r)), send);
  const cancel = jest.fn(async () => true);
  expect(await runThenHold(gate, cancel, async () => {})).toBe(false);
  expect(cancel).not.toHaveBeenCalled();
  finish("file:///rec.m4a");
  await stop;
  expect(send).toHaveBeenCalledWith("file:///rec.m4a");
});

test("a stop while a cancel runs sends nothing", async () => {
  const gate = createGate();
  const send = jest.fn(async () => {});
  let finish!: () => void;
  const cancel = runThenHold(gate, () => new Promise<boolean>((r) => (finish = () => r(true))), async () => {});
  await stopThenSend(gate, async () => "file:///rec.m4a", send);
  finish();
  expect(await cancel).toBe(true);
  expect(send).not.toHaveBeenCalled();
});

test("the gate stays shut a moment after a cancel", async () => {
  const gate = createGate();
  let release!: () => void;
  const held = runThenHold(gate, async () => true, () => new Promise<void>((r) => (release = r)));
  await new Promise((r) => setTimeout(r, 0));
  expect(gate.busy).toBe(true); // the second tap of a double tap finds it shut
  const second = jest.fn(async () => true);
  expect(await runThenHold(gate, second, async () => {})).toBe(false);
  expect(second).not.toHaveBeenCalled();
  release();
  await held;
  expect(gate.busy).toBe(false);
});

test("nothing done keeps the gate open at once", async () => {
  const gate = createGate();
  const wait = jest.fn(async () => {});
  expect(await runThenHold(gate, async () => false, wait)).toBe(false);
  expect(wait).not.toHaveBeenCalled();
  expect(gate.busy).toBe(false);
});
```

- [ ] **Step 2: 돌려서 실패를 본다**

Run: `cd app && npx jest src/flow/gate.test.ts`
Expected: FAIL, `runThenHold`가 없다.

- [ ] **Step 3: `runThenHold`와 `TAP_HOLD_MS`를 `gate.ts`에 쓴다**

`gate.run` 안에서 `fn()`을 기다리고, 참이면 `wait()`도 기다린 뒤 참을 돌려준다. `gate.run`이 `undefined`면 `false`. 주석에 왜 닫아 두는지(누른 자리에 다른 버튼이 나온다, 스펙 5)를 쓴다.

- [ ] **Step 4: 돌려서 통과를 본다**

Run: `cd app && npx jest src/flow/gate.test.ts`
Expected: PASS(9개)

- [ ] **Step 5: 커밋**

```bash
/usr/bin/git add app/src/flow/gate.ts app/src/flow/gate.test.ts
/usr/bin/git commit -F - <<'EOF'
feat(app): hold the recording gate a moment after a cancel or skip
...
EOF
```

### Task 2: 리듀서의 건너뛰기

**Files:**
- Modify: `app/src/flow/state.ts`
- Test: `app/src/flow/state.test.ts`

**Interfaces:**
- Consumes: 지금의 `advance`, `freshTurn`, `recordCancel`(녹음 중 → `ready`, 방식 그대로).
- Produces:
  - `export function canSkip(s: State): boolean` — 역할극 화면이고, 줄이 내가 말할 줄(내 줄, 또는 따라 말하기 연습의 라이언 줄)이고, `phase`가 `ready`이거나 `evaluated`이면서 `aside`일 때 참. 화면은 이것으로 「건너뛰기」를 보인다.
  - `Action`에 `{ type: "skip" }`.
  - `Bubble.text`가 `""`이면 말하지 않고 건너뛴 내 줄이다(주석으로 적는다). 새 필드는 두지 않는다.

- [ ] **Step 1: 실패하는 시험을 쓴다** (`state.test.ts`에 `describe("skip and cancel (spec record-cancel-skip)", …)`로 더함. 아래 이름과 단언을 쓴다)

  - `cancel while recording goes back to ready and keeps the mode`: `at("ready", { mode: "retry" })`에 `recordStart`, `recordCancel` → `phase` `"ready"`, `mode` `"retry"`, `history` 그대로.
  - `skip is taken before recording and after teacher Ryan's answer only`: `canSkip`이 `ready` 참, `aside: true`인 `evaluated` 참. `recording`, `evaluating`, `aside: false`인 `evaluated`, `error`, `loading` 거짓. 라이언 줄의 `ryan` 거짓. 끝 화면(`screen: "end"`) 거짓. 거짓인 상태에 `skip`을 보내면 같은 객체(`toBe(s)`).
  - `skip in the roleplay leaves my line as its script and moves on`: `at("ready")`(idx 1)에 `skip` → `history.at(-1)`이 `{ kind: "user", text: "", script: userLine.text, idx: 1 }`, `idx` 2, `phase` `"loading"`, `line` null, `mode` `"turn"`, `heard` null.
  - `skip after teacher Ryan's answer leaves nothing of the answer`: `evaluating`에 `heard`(`followed: false`), `text`, `done`(`issues: 0`) → `skip` → 대화에 `feedback` 말풍선이 없고, 더한 말풍선은 대본만 있는 내 줄 하나.
  - `skipping a line already said adds no bubble`: 따라 말한 `done`(`next: 2`) → `again` → `skip` → `idx` 1의 `user` 말풍선이 하나뿐이고 그것은 들린 말이 있는 것, `idx` 2.
  - `two skips from one old state move one line`: `const s = at("ready"); const a = reduce(s, skip); expect(reduce(a, skip)).toBe(a)`.
  - `skip in a practice goes where 다음 goes`: 끝 화면에서 `startPractice` `mine` `[1, 3]` → 줄 받고 `skip` → `practice.at` 1, `idx` 3, `history` `[]`. 다시 줄 받고 `skip` → `screen` `"end"`. 한 줄 연습(`practiseLine`)에서 `skip` → 떠나기 전 역할극 그대로(`resume`과 같은 `idx`, `history`, `line`). 모아 둔 문장 한 줄(`startSaved`)에서 `skip` → `screen` `"saved"`.
  - `a skipped line keeps its practice button`: 건너뛴 뒤 다음 줄을 받은 상태에서 `practiceFor(s, 그 말풍선)`이 `"mine"`.

- [ ] **Step 2: 돌려서 실패를 본다**

Run: `cd app && npx jest src/flow/state.test.ts`
Expected: FAIL, `canSkip`이 없고 `skip`이 상태를 바꾸지 않는다.

- [ ] **Step 3: `canSkip`과 `skip`을 쓴다**

`skip`은 `canSkip`이 거짓이면 그대로 돌려준다. 연습이면 `advance(s)`. 역할극이면 「다음」(`next`)처럼 `{ ...freshTurn, idx: s.nextIdx ?? s.idx + 1, nextIdx: null, mode: "turn", phase: "loading", line: null }`로 가고, 대화에는 그 줄의 `user` 말풍선이 아직 없을 때만 `{ kind: "user", text: "", script: line.text, idx: line.idx }`를 더한다(선생님에게 한 말은 더하지 않는다).

- [ ] **Step 4: 돌려서 통과를 본다**

Run: `cd app && npx jest src/flow/state.test.ts`
Expected: PASS

- [ ] **Step 5: 커밋** (`feat(app): skip my line without a recording`)

### Task 3: 화면의 「취소」와 「건너뛰기」

**Files:**
- Modify: `app/src/screens/RoleplayScreen.tsx`
- Modify: `app/src/ui/Button.tsx`

**Interfaces:**
- Consumes: Task 1의 `runThenHold`, `TAP_HOLD_MS`. Task 2의 `canSkip`, `{ type: "skip" }`, 빈 `Bubble.text`. `useRecorder`의 `discard()`, `isRecording()`.
- Produces: `Button`의 선택 prop `grow?: boolean` — 참이면 줄에서 남은 너비를 채운다(`flexGrow: 1`, `flexBasis: 0`쯤).

- [ ] **Step 1: `Button`에 `grow`를 더한다**

- [ ] **Step 2: 화면에 취소와 건너뛰기를 단다**
  - `const hold = () => new Promise<void>((r) => setTimeout(r, TAP_HOLD_MS));`
  - `cancelRecording = () => runThenHold(gate, doCancel, hold)`. `doCancel`은 `rec.isRecording()`이 거짓이면 `false`. 참이면 `await rec.discard()` 뒤 `dispatch({ type: "recordCancel" })`, `true`.
  - `skipLine = () => runThenHold(gate, doSkip, hold)`. `doSkip`은 `canSkip(state)`가 거짓이면 `false`, 참이면 `dispatch({ type: "skip" })` 뒤 `true`. 시작(`startRecording`)이 같은 게이트라 건너뛴 뒤 곧바로 누른 「🎤 말하기」는 막힌다(스펙 5).
  - 아래 버튼 줄: `evaluated`가 아닐 때 한 줄에 `canSkip(state)`면 「건너뛰기」(plain), 녹음 중이면 「취소」(plain), 그리고 지금의 큰 버튼(`grow`). 선생님 라이언이 답한 뒤는 「건너뛰기」(plain) + 「다시 해 보기」(`grow`). 따라 말한 뒤 줄은 그대로.
  - `myBubble`: `b.text`가 비면 「들린 말」 줄을 그리지 않는다(「🔊 내 녹음」도 없다. `b.rec`이 없다).
  - 주석에 스펙 경로와 절(1, 2, 5)을 적는다. `epoch`, `mounted`, `leave()`는 바꾸지 않는다.

- [ ] **Step 3: 형과 시험을 돌린다**

Run: `cd app && npx tsc --noEmit && npx jest`
Expected: 오류 없음, 모두 PASS

- [ ] **Step 4: 커밋** (`feat(app): add cancel and skip buttons to the turn bar`)

### Task 4: 한 줄도 말하지 않은 대화의 끝인사

**Files:**
- Modify: `server/je_server/phrases.py`, `server/je_server/engine.py` (`Engine.summary`)
- Test: `server/tests/test_summary.py`, `server/tests/test_phrases.py`

**Interfaces:**
- Produces: `PHRASES["closing_plain"] = "대화 끝! 수고했어요."`. `Engine.summary`의 `say`가 내 줄 어디에도 역할극 안의 시도(`turn`, `retry`, 선생님에게 한 말 뺌)가 없으면 `closing_plain`, 있으면 지금 규칙(`closing_retry`/`closing_clean`).

- [ ] **Step 1: 실패하는 시험을 쓴다**
  - `test_summary.py`의 `test_closing_without_any_line_said_has_no_praise`: 시도 없는 `engine_with_rp` → `s["say"] == engine.said("closing_plain").model_dump()`.
  - `test_closing_after_asides_only_has_no_praise`: `save_attempt(... Attempt(..., aside=True, mode="turn", followed=False, issues=[]))` 뒤 같은 단언.
  - `test_closing_after_practice_only_has_no_praise`: `mode="practice"`로 따라 말한 시도만 있으면 같은 단언(연습은 역할극 안의 시도가 아니다).
  - `test_phrases.py`의 `test_plain_closing_does_not_praise`: `"잘했어요" not in PHRASES["closing_plain"]`, `PHRASES["closing_plain"].startswith("대화 끝!")`.

- [ ] **Step 2: 돌려서 실패를 본다**

Run: `cd server && uv run pytest -q tests/test_summary.py tests/test_phrases.py`
Expected: FAIL(`closing_plain` KeyError, 끝인사가 `closing_clean`)

- [ ] **Step 3: `phrases.py`에 한 줄, `Engine.summary`에 「말한 줄이 있는지」를 더한다**

`tries`를 모으는 지금 반복에서 `said = said or bool(tries)`. 정해진 말은 맥 서버가 켜질 때 `warm()`이 만든다(지금 시험 `test_engine.py`의 PHRASES 확인이 새 말도 덮는다).

- [ ] **Step 4: 돌려서 통과를 본다**

Run: `cd server && uv run pytest -q`
Expected: 모두 PASS

- [ ] **Step 5: 커밋** (`feat(server): drop the praise from closing words when no line was said`)

### Task 5: 선생님 라이언이 「건너뛰기」를 알려 주기

**Files:**
- Modify: `server/je_server/prompts.py` (`ASIDE_SYSTEM`)
- Modify: `server/scripts/check_ryan_wording.py`
- Test: `server/tests/test_claude.py`

**Interfaces:**
- Produces: `ASIDE_SYSTEM`에 넘어가고 싶다는 말의 갈래. 「앱에 바라는 것」 갈래와 그 예에서 「대사를 말해야 다음으로 넘어간다」를 뺀다. 마지막은 늘 같은 대사를 다시 해 보자는 말이라는 규칙은 그대로.

- [ ] **Step 1: 실패하는 시험을 쓴다** (`test_claude.py`)

```python
def test_aside_prompt_points_to_skip():
    # spec record-cancel-skip 6: the line can be skipped now, so Ryan says how instead of 「대사를 말해야 넘어가요」
    from je_server import prompts

    p = prompts.ASIDE_SYSTEM
    assert "「건너뛰기」" in p
    assert "대사를 말해야 다음으로 넘어가" not in p and "말해야 다음으로 넘어간다" not in p
```

- [ ] **Step 2: 돌려서 실패를 본다**

Run: `cd server && uv run pytest -q tests/test_claude.py -k skip`
Expected: FAIL

- [ ] **Step 3: 지시문을 고친다**

「무엇이라고 답할지」에 갈래 하나: 이 줄을 넘기고 싶다(넘어가고 싶다, 말하기 어렵다, 녹음하기 싫다)는 말이면 「건너뛰기」를 누르면 다음으로 넘어간다고 알려 주고, 같은 대사를 다시 해 보자는 말로 끝낸다. 예: 「건너뛰기를 누르면 다음으로 넘어가요. 아니면 한 번 더 해 볼까요?」 「앱에 바라는 것」 갈래와 예에서 「지금은 대사를 말해야 다음으로 넘어가요」를 뺀다. 버튼 이름은 「다시 듣기」, 「읽는 법 보기」처럼 「」로 쓴다.

- [ ] **Step 4: 돌려서 통과를 본다**

Run: `cd server && uv run pytest -q`
Expected: 모두 PASS

- [ ] **Step 5: 지시문 확인 스크립트에 경우를 더한다**

`Case`에 `must: tuple[str, ...] = ()`, `never: tuple[str, ...] = ()`를 더하고 `flags`가 빠진 `must`와 들어간 `never`를 알린다. `ASIDE`에 지어낸 경우 하나: `Case("off skip wish", "Here is your key card.", "I want to just skip this line.", [], heard_ko="이 줄은 그냥 넘어가고 싶어요.", must=("건너뛰기",))`. 「off app wish」에 `never=("말해야",)`.

- [ ] **Step 6: 실제 Sonnet으로 돌린다** (선생님 라이언 답 5번쯤, 5센트 안쪽)

Run: `cd server && uv run python scripts/check_ryan_wording.py --only aside --case "off skip wish" --runs 3` 그리고 `--case "off app wish" --runs 2`
Expected: 표시된 규칙 어김 없음. 「off skip wish」의 답에 「건너뛰기」가 있고 다시 해 보자는 말로 끝남. 찍힌 비용을 적어 둔다(PR).

- [ ] **Step 7: 커밋** (`feat(server): have teacher ryan point to the skip button`)

### Task 6: 문서

**Files:**
- Modify: `docs/PRD.md`, `docs/superpowers/specs/2026-11-07-offscript-aside-design.md`, `docs/superpowers/specs/2026-11-05-roleplay-practice-design.md`

- [ ] **Step 1:** 스펙 8대로 PRD 「사용자 차례(역할극)」에 취소와 건너뛰기 한 줄, 「상황 역할극」의 다시 하게 하는 곳에 건너뛸 수 있다는 한 줄, 맨 위 「고침」 줄에 2026-11-08 이 일을 더한다. 선생님 답 스펙 3의 「앱에 바라는 것」 예와 역할극 뒤 연습 스펙 3의 「한 번도 말하지 않은 줄」에 이 스펙으로 바뀌었다는 줄을 단다.
- [ ] **Step 2: 커밋** (`docs: note record cancel and skip in the prd and earlier specs`)

### Task 7: 시험 서버, 제이크 목소리 녹음, 에뮬레이터 화면

- [ ] **Step 1: 시험 서버를 띄운다.** 원래 폴더 서버(launchd)는 그대로 두고, `docs/guide/DEVENV_맥서버_저절로_띄우기_20261107.md` 「카드가 서버를 시험할 때」대로 데이터 복사본으로 `JE_HOST=127.0.0.1 JE_PORT=8795 JE_WHISPER_PORT=8796`에 띄운다.
- [ ] **Step 2: 제이크 목소리 녹음을 보낸다.** `docs/guide/DEVENV_폰없이_녹음_시험하기_20261108.md`대로 지어낸 한국어 녹음(이 줄을 넘어가고 싶다는 말) 하나를 시험 역할극 복사본의 내 줄에 보낸다. 라이언 답에 「건너뛰기」가 나오는지 본다. 복사본은 끝나면 지운다.
- [ ] **Step 3: 에뮬레이터(AVD `jake-english`)에 이 브랜치 앱을 깐다.** `docs/guide/DEVENV_폰을_adb로_시험하기_20261108.md`대로. 시험 서버를 보게 한다. 녹음 버튼을 누르기 전에 `emu avd hostmicoff`.
- [ ] **Step 4: 화면을 본다.** 녹음 중 「취소」(맥 시험 데이터에 녹음 파일이 생기지 않는다), 「■ 말하기 끝」과 「취소」 빠르게 같이, 「취소」 빠르게 두 번(건너뛰지 않음), 말하기 전 「건너뛰기」(대본만 있는 내 말풍선, 라이언 다음 대사), 마지막 줄 건너뛰기(끝 화면, 대본만 있는 줄, 끝인사), 모든 줄을 건너뛴 대화의 끝인사, 끝 화면 「내 대사 다시 연습」에서 건너뛰기 두 번 빠르게(한 줄만), 아래 버튼 줄의 모양. 받아쓰기가 들어간 화면 캡처는 공개 파일에 넣지 않는다.
- [ ] **Step 5:** 에뮬레이터를 끄고, 시험 서버를 멈추고, 시험 데이터 복사본을 지운다. main 세션에 에뮬레이터를 다 썼다고 알린다.
