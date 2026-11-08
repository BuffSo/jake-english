# 녹음 안 한 내 대사도 이어 하기 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 가장 최근 대화에 대화 안에서 녹음하지 않은 내 대사가 남아 있으면 「하던 대화 이어 하기」 줄에 남긴다. 끝까지 간 대화는 녹음 안 한 줄만 앞에서부터 하고, 아랫줄에 「녹음 안 한 줄 N개」를 쓴다.

**Architecture:** 맥이 「녹음한 줄」을 한 규칙으로 정한다(`review.kept_tries`, 끝 화면과 지난 상황도 같은 규칙을 쓴다). `to_resume`은 녹음 안 한 줄이 있는 가장 최근 대화를 고르고, `resume_start`가 시작 줄과 「끝까지 간 대화인지」를 셈한다. `GET /resume`에 `ended`를 더하고 `said`는 녹음한 모든 내 대사로 넓힌다. 앱은 이어 한 대화의 녹음한 줄을 상태(`recorded`)에 두고, 「다음」과 「건너뛰기」 뒤에 녹음한 줄을 말풍선으로 지나간다(`flow/resume.ts`의 `passRecorded`).

**Tech Stack:** Python 3 + FastAPI(서버, `cd server && uv run pytest -q`), React Native + Expo + jest(앱, `cd app && npx jest && npx tsc --noEmit`). 새 꾸러미 없음.

**Spec:** `docs/superpowers/specs/2026-11-08-resume-unrecorded-design.md`(앞선 스펙 `docs/superpowers/specs/2026-11-08-resume-roleplay-design.md`와 함께 읽는다)

**실행 방식:** 이 세션이 직접 한다(executing-plans). 작업이 넷이고 서로의 이름과 모양을 바로 쓴다. 끝에 새 리뷰어 한 명이 브랜치 전체를 보고, PR을 열면 pr-review로 본다. 이 저장소는 머지 전까지 묻지 않으므로(`AGENTS.md` 「PR과 머지」) 고르는 것을 묻지 않았다.

## Global Constraints

- 녹음한 줄: 내 대사의 대화 안 시도(`mode`가 `turn`이나 `retry`) 가운데 `aside`가 아닌 것이 하나라도 있는 줄. 연습(`practice`, `shadow`)은 치지 않는다.
- 이어 할 대화는 맥의 가장 최근 대화(`(created, id)`가 가장 큰 것) 하나다. 녹음 안 한 내 대사가 없으면 없다.
- 시작 줄: 진행 위치(`pos`)나 그 뒤의 녹음 안 한 내 대사가 있으면 그 첫 줄, 없으면 녹음 안 한 첫 내 대사를 고른다(`ended`는 뒤의 경우). 시작 줄은 고른 줄 앞의 마지막 내 대사 다음 줄(없으면 0)이다.
- 화면 글귀(그대로): 중간에 나간 대화 `${title_ko} · 내 대사 ${no}/${total}`(지금 그대로), 끝까지 간 대화 `${title_ko} · 녹음 안 한 줄 ${N}개`. 윗줄, ▶, 「›」, 모양과 자리는 바꾸지 않는다(`ResumeRow.tsx` 그대로).
- 맥의 기록 모양(`Roleplay`, `Attempt`)은 바꾸지 않는다. 건너뛰기 알림과 `pos`는 지금과 같다.
- `RoleplayScreen.tsx`는 고치지 않는다(record-feedback 카드와 겹친다). 바뀌는 것은 리듀서와 `flow/resume.ts`뿐이다.
- 시험 문장과 예는 지어낸다(`REVIEW.md` 「공개 저장소 노출」). 실제 모델 호출은 제이크 목소리 녹음 몇 개(평가 한 번에 0.03센트쯤), 횟수와 값을 PR에 적는다.
- 커밋 메시지는 영어 Conventional Commits, 본문에 이유와 시험 결과, 끝에 `Refs: docs/superpowers/specs/2026-11-08-resume-unrecorded-design.md`. AI 서명 줄 없음. git은 `/usr/bin/git`, 커밋은 `[ $? -eq 0 ] &&`로 잇는다.

## Review Focus

1. **중간에 나간 대화의 앞에 건너뛴 줄이 있을 때:** 나간 자리(`pos`)부터여야 하고, 아랫줄은 「내 대사 n/N」이다. 건너뛴 줄로 먼저 데려가면 안 된다. → Task 1 시험 `test_midway_resumes_at_pos_past_an_earlier_skip`, Task 2 시험 `the label of a conversation left mid-way`.
2. **내가 대화를 끝내는 상황(마지막 줄이 내 대사)에서 그 줄을 건너뜀:** 그 줄부터 하고, 마친 뒤 곧바로 끝 화면이다(남은 줄이 없으니 `idx`가 줄 수가 되어 `lineMissing`). → Task 3 시험 `after the last unrecorded line, the ending or the end screen`.
3. **연습으로만 말한 줄, 선생님 라이언에게 한국어로만 말한 줄:** 녹음 안 한 줄로 남는다. → Task 1 시험 `test_practice_and_asides_are_not_recorded`.
4. **진행 위치 뒤에 이미 대화 안 시도가 있는 드문 기록(라이언 목소리가 끊겨 `pos`가 움직이지 않음):** 그 줄을 다시 하라고 하지 않는다. → Task 1 시험 `test_start_passes_a_recorded_line_after_pos`.
5. **이어 한 대화에서 또 건너뜀:** 다음 녹음 안 한 줄로 가고, 건너뛴 줄은 대본만 남는다. → Task 3 시험 `a skip in a resumed conversation passes recorded lines too`.

---

### Task 1: 맥이 녹음 안 한 줄로 이어 할 대화와 시작 줄을 정한다

**Files:**
- Modify: `server/je_server/review.py`(`spoken`, `to_resume`, `said_before` → `said_on`, 새 `kept_tries`, `unrecorded`, `resume_start`), `server/je_server/engine.py`(`resume`, `summary`가 `kept_tries`를 씀), `contract/resume.json`(`ended` 더함, `said` 예를 녹음한 모든 줄로)
- Test: `server/tests/test_review.py`, `server/tests/test_resume.py`, `server/tests/test_contract.py`

**Interfaces:**
- Produces:
  - `kept_tries(rp: Roleplay, line: ScriptLine) -> list[Attempt]` — 내 대사의 대화 안 시도(`turn`, `retry`, `aside` 아님). 라이언 대사면 `[]`. `spoken`, `said_on`, `unrecorded`, `Engine.summary`가 이것을 쓴다.
  - `unrecorded(rp: Roleplay) -> list[int]` — `kept_tries`가 빈 내 대사의 `idx`, 오름차순.
  - `to_resume(rps: list[Roleplay]) -> Roleplay | None` — 가장 최근 대화에 `unrecorded`가 있으면 그 대화.
  - `resume_start(rp: Roleplay) -> tuple[int, bool]` — `(at, ended)`. Global Constraints의 시작 줄 규칙.
  - `said_on(rp: Roleplay) -> list[dict]` — 녹음한 모든 내 대사의 `{"idx", "heard", "n"}`(마지막 `kept_tries`). `said_before`를 대신한다.
  - `GET /resume` → `{"roleplay", "at", "progress", "said", "ended"}`(`progress = progress_of(rp, at)`).

- [ ] **Step 1: 실패하는 시험을 쓴다** (`test_review.py`의 `make`를 쓴다. `LINES`는 라이언, 나, 라이언이라, 내 대사가 여럿인 대화는 시험 안에서 `lines`를 늘린다)

```python
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
    rp = make(A, "2026-11-05T10:00:00", pos=2, tries=SAID)
    assert to_resume([rp]) is None

# R0 U1 R2 U3 R4 U5 R6 (spec 3 example)
def test_gone_to_the_end_starts_at_the_ryan_line_before_the_first_unrecorded():
    rp = seven(pos=6, said=[3])  # U1, U5 unrecorded
    assert resume_start(rp) == (0, True)
    rp = seven(pos=6, said=[1])  # U3, U5 unrecorded
    assert resume_start(rp) == (2, True)

def test_midway_resumes_at_pos_past_an_earlier_skip():
    rp = seven(pos=4, said=[3])  # U1 skipped, U3 said, left before U5
    assert resume_start(rp) == (4, False)

def test_start_passes_a_recorded_line_after_pos():
    rp = seven(pos=2, said=[1, 3])  # U3's try stayed under pos (Ryan's voice cut)
    assert resume_start(rp) == (4, False)

def test_said_on_takes_every_recorded_line():
    rp = seven(pos=6, said=[1, 5])
    assert [s["idx"] for s in said_on(rp)] == [1, 5]
```

`seven(pos, said)`는 이 파일에 더하는 도우미다. 대사 일곱 줄(라이언과 나가 번갈아, 라이언이 처음과 끝)을 만들고, `said`의 줄에 `turn` 따라 말한 시도 하나를 둔다. `test_said_before_*` 둘은 `said_on`으로 바꾼다. `test_no_resume_after_the_last_line_is_mine_and_done`은 시도 없이 `pos`만 넘긴 줄을 「마친 줄」로 보던 시험이라, 그 줄에 `SAID`를 두어 다 녹음한 경우로 바꾼다(시도가 없으면 이제 이어 한다). `said_on`은 시작 줄 앞이 아니라 모든 줄을 본다. `test_resume.py`의 `test_resume_after_a_followed_turn`에는 `r["ended"] is False`를 더하고, `test_resume_route`에는 `"ended"`가 있는지 본다. `test_contract.py`의 열쇠 집합에 `"ended"`를 더한다.

- [ ] **Step 2: 시험이 실패하는지 본다**

Run: `cd server && uv run pytest -q tests/test_review.py tests/test_resume.py tests/test_contract.py`
Expected: FAIL(`unrecorded`, `resume_start`, `said_on`을 가져올 수 없음).

- [ ] **Step 3: `review.py`에 위 Interfaces를 만들고, `spoken`과 `Engine.summary`가 `kept_tries`를 쓰게 한다. `Engine.resume`은 `resume_start`, `said_on`을 쓰고 `ended`를 더한다. `contract/resume.json`에 `"ended": false`를 더한다**

`resume_start`의 셈은 이렇다. `left = unrecorded(rp)`, `ahead = [i for i in left if i >= rp.pos]`, `target = (ahead or left)[0]`, `at = max((l.idx for l in rp.lines if l.speaker == "user" and l.idx < target), default=-1) + 1`, `ended = not ahead`.

- [ ] **Step 4: 시험이 통과하는지 본다**

Run: `cd server && uv run pytest -q`
Expected: 모두 통과(기준선 527개와 새 시험).

- [ ] **Step 5: 커밋한다**

```bash
/usr/bin/git add server/je_server/review.py server/je_server/engine.py contract/resume.json server/tests/test_review.py server/tests/test_resume.py server/tests/test_contract.py
/usr/bin/git commit -F - <<'EOF'
feat(server): resume the newest conversation while a line of mine is unrecorded
...
EOF
```

### Task 2: 앱이 `ended`를 받고 한 줄의 아랫줄을 두 꼴로 쓴다

**Files:**
- Modify: `app/src/api/types.ts`(`Resume`에 `ended: boolean`, `RESUME_KEYS`에 `"ended"`, `HeardTry`와 `Resume` 주석), `app/src/flow/resume.ts`(`resumeLabel`)
- Test: `app/src/flow/resume.test.ts`, `app/src/api/contract.test.ts`(열쇠 목록이 이미 `RESUME_KEYS`를 본다), `app/src/flow/state.test.ts`의 `Resume` 값에 `ended: false`

**Interfaces:**
- Consumes: Task 1의 `/resume` 모양.
- Produces: `type Resume = { roleplay: Roleplay; at: number; progress: Progress; said: HeardTry[]; ended: boolean }`, `resumeLabel(r: Resume): string`.

- [ ] **Step 1: 실패하는 시험을 쓴다** (`resume.test.ts`의 `resume(at, said)`에 `ended` 인자를 더한다)

```ts
test("the label of a conversation left mid-way", () => {
  expect(resumeLabel(resume(2, [], false))).toBe("호텔 체크인하기 · 내 대사 2/2");
});

test("the label of a conversation gone to the end: how many lines of mine are unrecorded", () => {
  const said = [{ idx: 3, heard: "Sure, here you go.", n: 1 }];
  expect(resumeLabel(resume(0, said, true))).toBe("호텔 체크인하기 · 녹음 안 한 줄 1개");
  expect(resumeLabel(resume(0, [], true))).toBe("호텔 체크인하기 · 녹음 안 한 줄 2개");
});
```

- [ ] **Step 2: 시험이 실패하는지 본다**

Run: `cd app && npx jest src/flow/resume.test.ts src/api/contract.test.ts`
Expected: FAIL(아랫줄이 「내 대사」, 계약 열쇠에 `ended`가 없음).

- [ ] **Step 3: `types.ts`와 `resumeLabel`을 고친다.** 녹음 안 한 줄 수는 `roleplay.lines` 가운데 내 대사이면서 `said`에 없는 줄의 수다.

- [ ] **Step 4: 시험과 타입 검사가 통과하는지 본다**

Run: `cd app && npx jest && npx tsc --noEmit`
Expected: 모두 통과, 타입 오류 없음.

- [ ] **Step 5: 커밋한다** (`feat(app): name unrecorded lines on the resume row`)

### Task 3: 이어 한 대화가 녹음한 줄을 말풍선으로 지나간다

**Files:**
- Modify: `app/src/flow/resume.ts`(`passRecorded`, 말풍선 만들기를 `resumeHistory`와 함께 씀), `app/src/flow/state.ts`(`State.recorded`, `initial`, `resumed`, `next`, `skip`)
- Test: `app/src/flow/resume.test.ts`, `app/src/flow/state.test.ts`

**Interfaces:**
- Consumes: Task 2의 `Resume`.
- Produces:
  - `passRecorded(rp: Roleplay, recorded: Record<number, HeardTry>, from: number): { idx: number; passed: Bubble[]; seen: Record<number, ScriptLine> }` — `from`부터 다음 녹음 안 한 내 대사(없으면 대본 끝)의 앞 라이언 대사까지 건너간다. `idx = max(from, (그 줄 앞의 마지막 내 대사) + 1)`이고, 대본 끝이면 마지막 내 대사 다음 줄이다. `[from, idx)` 줄을 `resumeHistory`와 같은 말풍선(녹음한 내 대사는 들린 말과 `rec`)으로 돌려준다.
  - `State.recorded: Record<number, HeardTry> | null` — 이어 한 대화가 받은 녹음한 내 대사(`said`를 `idx`로). 이어 하지 않은 대화는 `null`이고, 그때 `next`와 `skip`은 지금과 똑같다.

- [ ] **Step 1: 실패하는 시험을 쓴다**

`resume.test.ts`(대사 다섯 줄 R0 U1 R2 U3 R4):

```ts
test("passing recorded lines to the Ryan line before the next unrecorded one", () => {
  const rec = { 1: { idx: 1, heard: "Yes, I booked a room.", n: 1 } };
  const p = passRecorded(roleplay, rec, 2);
  expect(p.idx).toBe(2); // R2 leads to U3, which is unrecorded: nothing passed
  expect(p.passed).toEqual([]);
});

test("after the last unrecorded line, the ending or the end screen", () => {
  const rec = { 3: { idx: 3, heard: "Sure, here you go.", n: 2 } };
  const p = passRecorded(roleplay, rec, 2); // U1 done: U3 is recorded, so on to R4, the ending
  expect(p.idx).toBe(4);
  expect(p.passed.map((b) => b.idx)).toEqual([2, 3]);
  expect(p.passed[1]).toMatchObject({ kind: "user", text: "Sure, here you go.", rec: { rp_id: RP, idx: 3, n: 2 } });
  const mineLast = { ...roleplay, lines: lines.slice(0, 4) }; // I end the conversation
  expect(passRecorded(mineLast, {}, 4).idx).toBe(4); // = line count: lineMissing, the end screen
});
```

`state.test.ts`의 `describe("resume")`에, 대사 다섯 줄(R0 U1 R2 U3 R4)인 대화를 U1만 녹음 안 한 채 끝까지 간 것으로 이어 한다(`at: 0`, `ended: true`, `said`는 U3).

```ts
test("resuming keeps the lines recorded before", () => {
  expect(resumedEnded().recorded).toEqual({ 3: said3 });
  expect(resumed().recorded).toEqual({ 1: resume.said[0] });
  expect(initial.recorded).toBeNull();
});

test("「다음」 in a resumed conversation passes recorded lines as bubbles", () => {
  const s = reduce(evaluatedAt(resumedEnded(), 1), { type: "next" });
  expect([s.idx, s.phase]).toEqual([4, "loading"]);
  expect(s.history.slice(-2).map((b) => b.idx)).toEqual([2, 3]);
  expect(s.seen[3]).toEqual(lines5[3]);
});

test("a skip in a resumed conversation passes recorded lines too", () => {
  const s = reduce(readyAt(resumedEnded(), 1), { type: "skip" });
  expect(s.idx).toBe(4);
  expect(s.history.map((b) => [b.idx, !!b.skipped])).toEqual([[1, true], [2, false], [3, false]]);
});

test("a conversation not resumed goes line by line as before", () => {
  // the existing 「next」 and 「skip」 tests keep passing with recorded null
});
```

`evaluatedAt(s, idx)`와 `readyAt(s, idx)`는 이 describe 안의 도우미다. `lineLoaded`로 그 줄을 싣고, 따라 말한 `heard`와 `done`(`next: idx + 1`)을 보낸다. 마지막 시험은 새로 쓰지 않는다. 지금 있는 `next`와 `skip` 시험이 그대로 통과하는지로 본다.

- [ ] **Step 2: 시험이 실패하는지 본다**

Run: `cd app && npx jest src/flow`
Expected: FAIL(`passRecorded`가 없음, `recorded`가 `undefined`).

- [ ] **Step 3: `passRecorded`를 만들고 `resumeHistory`와 말풍선 만들기를 함께 쓴다. `state.ts`에 `recorded`를 더한다.** `resumed`는 `said`로 `recorded`를 채운다. `next`와 `skip`(연습이 아닐 때)은 `idx = s.nextIdx ?? s.idx + 1`을 구한 뒤, `s.recorded`가 있으면 `passRecorded`로 `idx`, `history`(뒤에 `passed`), `seen`(`seen`에 더함)을 정한다.

- [ ] **Step 4: 시험과 타입 검사가 통과하는지 본다**

Run: `cd app && npx jest && npx tsc --noEmit`
Expected: 모두 통과, 타입 오류 없음.

- [ ] **Step 5: 커밋한다** (`feat(app): pass recorded lines when resuming a conversation`)

### Task 4: 문서를 고친다

**Files:**
- Modify: `docs/PRD.md`(맨 위 「고침」, 「상황 정하기」의 하던 대화 이어 하기, 「사용자 차례(역할극)」의 건너뛰기), `docs/superpowers/specs/2026-11-08-resume-roleplay-design.md`(「실패로 볼 것」 1, 2, 「정한 것」 1, 2, 4, 5에 바뀐 것과 이 스펙 경로), `docs/superpowers/specs/2026-11-08-record-cancel-skip-design.md`(「한계」의 이어 하기 줄)
- 할 일 파일: 원래 폴더의 `docs/todo/20261108_36_todo_resume_unrecorded_lines.md`를 이 worktree로 복사해 상태 줄을 「완료」로 고치고, 끝내는 커밋에 넣는다.

- [ ] **Step 1: 스펙 「고칠 문서」(6)의 줄마다 고친다.** 사용자의 말(「녹음까지 해야 완료로 봐야 하는데」)과 이 스펙 경로를 PRD에 적는다.
- [ ] **Step 2: 옛 동작을 말하는 주석과 문서를 찾는다.** `/usr/bin/grep -rn "건너뛴 줄\|마친 내 대사\|said_before\|line of mine left" docs/PRD.md docs/superpowers/specs server/je_server app/src`로 찾아, 이 스펙과 어긋나는 것을 고친다.
- [ ] **Step 3: 커밋한다** (`docs(prd): keep unrecorded lines on the resume row`. 할 일 파일은 끝내는 커밋에 함께 넣는다)

### 확인 (작업 뒤, 커밋 없음)

- 시험 서버(`JE_HOST=127.0.0.1 JE_PORT=8791 JE_WHISPER_PORT=8792`, 녹음을 뺀 데이터 복사본): 목록 상황을 만들고, 첫 내 대사를 건너뛰고, 둘째 줄을 제이크 목소리 녹음으로 따라 말하고(`docs/guide/DEVENV_폰없이_녹음_시험하기_20261108.md`), 남은 줄을 건너뛰어 끝까지 간다. `/resume`의 `at`, `ended`, `said`를 본다. 남은 줄을 녹음으로 채우면 `null`인지 본다.
- 화면(AVD `jake-english`, 360dp, `docs/guide/DEVENV_폰을_adb로_시험하기_20261108.md`): 아랫줄 「녹음 안 한 줄 N개」 → 누르면 맞는 라이언 대사 → 한 줄 뒤 녹음한 줄을 말풍선으로 지나감 → 끝 화면 → 줄이 없어짐. 중간에 나간 대화는 「내 대사 n/N」. 녹음 버튼 시험 전에 `emu avd hostmicoff`.
