# 하던 대화 이어 하기 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 상황 정하기의 주제 고르기 단계 맨 아래 「하던 대화 이어 하기」 한 줄로, 가장 최근 대화를 마친 내 대사의 다음 줄에서 다시 시작한다. 대화를 나갈 때 묻지 않고, 대화 중 뒤로는 주제 고르기 단계로 온다.

**Architecture:** 맥이 이어 할 대화를 고른다. 가장 최근 `roleplay.json`에 `pos`나 그 뒤의 내 대사가 있으면 그 대화다(`review.to_resume`). 앞의 대화에 쓸 들린 말과 녹음 번호(`review.said_before`)를 함께 `GET /resume`으로 준다. 건너뛰기는 `POST …/skip`으로 `pos`만 움직인다. 앱은 받은 기록으로 대화 상태를 만든다(`flow/resume.ts`, 리듀서 `resumed`). 대화 화면이 맥에 보내고 아직 끝나지 않은 평가와 건너뛰기 알림은 `flow/pending.ts`가 세고, 상황 정하기 화면은 그것이 끝난 뒤에 묻는다.

**Tech Stack:** Python 3 + FastAPI(서버, `cd server && uv run pytest -q`), React Native + Expo + jest(앱, `cd app && npx jest && npx tsc --noEmit`). 새 꾸러미 없음.

**Spec:** `docs/superpowers/specs/2026-11-08-resume-roleplay-design.md`

**실행 방식:** 이 세션이 직접 한다(executing-plans). 작업마다 앞 작업의 이름과 모양을 바로 쓰고 `state.ts`, `RoleplayScreen.tsx`, `SituationScreen.tsx` 둘레라, 작업마다 새 에이전트를 띄우면 같은 맥락을 다시 읽는 데 더 든다. 끝에 새 리뷰어 한 명이 브랜치 전체를 보고, PR을 열면 pr-review로 본다. 이 저장소는 머지 전까지 묻지 않으므로(`AGENTS.md` 「PR과 머지」) 고르는 것을 묻지 않았다.

## Global Constraints

- 화면 글귀(그대로 쓴다): 윗줄 「하던 대화 이어 하기」, 아랫줄 `${상황 제목} · 내 대사 ${no}/${total}`, 앞에 ▶(`"▶︎"`, 글자 모양으로), 끝에 「›」.
- 한 줄의 모양: 흰 바탕(`colors.bg`), 파란 테두리 두께 `BUTTON_BORDER`(`colors.primary`), 둥근 모서리 12, 윗줄 파란 굵은 글자, 아랫줄 `colors.sub` 작은 글자. 주제 고르기 단계에서만, 화면 맨 아래에 붙인다.
- 첫 화면(`HomeScreen.tsx`)은 바꾸지 않는다. `/home`은 앱을 띄울 때 한 번만 받는다.
- 이어 하는 것은 맥의 가장 최근 대화(`created`가 가장 늦은 것) 하나다. 그 대화에 `pos`나 그 뒤의 내 대사가 없으면 없다.
- 맥의 기록 모양(`Roleplay`)은 바꾸지 않는다. 건너뛰기는 `pos`만 움직이고 `attempts`와 녹음을 만들지 않는다.
- 상황 정하기 화면은 남겨 둔 평가와 건너뛰기 알림을 길어야 `RESUME_WAIT_MS = 30_000`(앱 요청의 `TIMEOUT`과 같다) 기다린 뒤 묻는다.
- 화면에 보이는 한국어는 `keepWords`를 거친다(APP 가이드).
- 시험 문장과 예는 지어낸다(`REVIEW.md` 「공개 저장소 노출」). 실제 모델 호출은 따라 말한 녹음 몇 개(한 번에 0.03센트쯤), 횟수와 값을 PR에 적는다.
- 커밋 메시지는 영어 Conventional Commits, 본문에 이유와 시험 결과, 끝에 `Refs: docs/superpowers/specs/2026-11-08-resume-roleplay-design.md`. AI 서명 줄 없음. git은 `/usr/bin/git`, 커밋은 `[ $? -eq 0 ] &&`로 잇는다.

## Review Focus

1. **평가 중에 나가 곧바로 「대화 연습하기」:** 맥이 아직 위치를 옮기기 전이다. 한 줄은 그 평가가 끝난 뒤에 나와야 하고, 방금 말한 줄을 다시 하라고 하면 안 된다. → Task 5 시험 `settled waits for what was tracked`, Task 7에서 대화 안의 시도(`turn`)를 `pending.track`으로 보낸다.
2. **가장 최근 대화는 끝났고 더 옛날 대화가 끝나지 않았을 때:** 한 줄이 없어야 한다. → Task 2 시험 `test_no_resume_when_the_newest_is_done`.
3. **내가 대화를 끝내는 상황(마지막 줄이 내 대사):** 그 줄을 따라 말하면 `pos`가 줄 수와 같아진다. 한 줄이 없어야 한다. → Task 2 시험 `test_no_resume_after_the_last_line_is_mine_and_done`.
4. **한 줄을 빠르게 두 번 누름:** 대화가 한 번만 열린다. → Task 6 시험 `a second resumed does nothing`.
5. **건너뛰기 알림이 실패(맥 연결 끊김):** 화면은 그대로 다음 줄로 가고 오류를 보이지 않는다. 남겨 둔 것 세기는 실패도 끝난 것으로 친다. → Task 5 시험 `a failed promise counts as settled`, Task 7에서 알림의 실패를 삼킨다.

---

### Task 1: 맥이 건너뛰기를 받아 위치를 움직인다

**Files:**
- Modify: `server/je_server/engine.py`(`Engine.skip` 더함), `server/je_server/app.py`(경로 더함)
- Test: `server/tests/test_resume.py`(새 파일)

**Interfaces:**
- Produces: `async def Engine.skip(self, rp_id: str, idx: int) -> int` — 그 줄이 내 대사면 `self.lock(rp_id)` 안에서 `pos = max(pos, idx + 1)`로 저장하고 새 `pos`를 돌려준다. 줄이 없거나 라이언 대사면 `NotFound`. `POST /roleplays/{rp_id}/lines/{idx}/skip` → `{"pos": int}`, 없으면 404 `not_found`.

- [ ] **Step 1: 실패하는 시험을 쓴다**

```python
async def test_skip_moves_pos_past_my_line(engine_with_rp):
    engine, rp_id, user_idx = engine_with_rp
    assert await engine.skip(rp_id, user_idx) == user_idx + 1
    assert engine.load(rp_id).pos == user_idx + 1 and engine.load(rp_id).attempts == {}

async def test_skip_never_moves_pos_back(engine_with_rp):
    engine, rp_id, _ = engine_with_rp
    mine = [l.idx for l in engine.load(rp_id).lines if l.speaker == "user"]
    await engine.skip(rp_id, mine[1])
    assert await engine.skip(rp_id, mine[0]) == mine[1] + 1
    assert await engine.skip(rp_id, mine[1]) == mine[1] + 1  # the same skip twice

async def test_skip_on_ryans_line_is_not_found(engine_with_rp):
    engine, rp_id, _ = engine_with_rp
    with pytest.raises(NotFound):
        await engine.skip(rp_id, 0)  # line 0 is Ryan's in the fake script

def test_skip_route(client):
    rp = client.post("/roleplays", json={"situation": "길 묻기"}).json()
    mine = next(l["idx"] for l in rp["lines"] if l["speaker"] == "user")
    assert client.post(f"/roleplays/{rp['id']}/lines/{mine}/skip").json() == {"pos": mine + 1}
    assert client.post(f"/roleplays/{rp['id']}/lines/0/skip").status_code == 404
```

- [ ] **Step 2: 실패를 본다** — `cd server && uv run pytest tests/test_resume.py -q` → `AttributeError: 'Engine' object has no attribute 'skip'`

- [ ] **Step 3: `Engine.skip`과 경로를 쓴다.** 줄 찾기는 `get_line`, 저장은 `save_attempt`처럼 잠금 안에서 다시 읽어 쓴다. 경로는 `three` 경로처럼 `PathParam(pattern=ID)`, `PathParam(ge=0)`.

- [ ] **Step 4: 통과를 본다** — 같은 명령 → 4 passed

- [ ] **Step 5: 커밋한다** — `feat(server): move a roleplay's place on a skipped line`

### Task 2: 맥이 이어 할 대화를 고른다

**Files:**
- Modify: `server/je_server/review.py`, `server/je_server/engine.py`, `server/je_server/app.py`
- Create: `contract/resume.json`
- Test: `server/tests/test_review.py`, `server/tests/test_resume.py`, `server/tests/test_contract.py`

**Interfaces:**
- Produces:
  - `def to_resume(rps: list[Roleplay]) -> Roleplay | None` (`review.py`) — `max(rps, key=lambda r: (r.created, r.id))`가 `pos`나 그 뒤에 내 대사를 가지면 그것, 아니면(기록이 없어도) `None`.
  - `def said_before(rp: Roleplay, upto: int) -> list[dict]` (`review.py`) — `idx < upto`인 내 대사마다 대화 안 시도(`a.mode in ROLEPLAY_MODES and not a.aside`)의 마지막 것을 `{"idx": int, "heard": str, "n": int}`로, 줄 순서대로. 시도가 없는 줄(건너뜀)은 넣지 않는다.
  - `def progress_of(rp: Roleplay, idx: int) -> dict[str, int]` (`engine.py` 모듈 함수) — 지금 `Engine.progress`의 몸통. `Engine.progress`는 이것을 부른다.
  - `def Engine.resume(self) -> dict | None` — `{"roleplay": rp.model_dump(mode="json"), "at": rp.pos, "progress": progress_of(rp, rp.pos), "said": said_before(rp, rp.pos)}`. Claude를 부르지 않는다.
  - `GET /resume` → `{"resume": <위 dict> | null}`.
  - `contract/resume.json`: `{"resume": {...}}`. `roleplay`는 `contract/roleplay.json`의 대화를 줄 다섯(라이언, 나, 라이언, 나, 라이언)으로 늘리고 `pos` 2로 둔 것, `at` 2, `progress` `{"no": 2, "total": 2}`, `said`는 줄 1의 시도 하나.

- [ ] **Step 1: 실패하는 시험을 쓴다** (`test_review.py`는 지금의 `make`와 `LINES`(라이언, 나, 라이언)를 쓴다. `make`에 `pos` 인자를 더한다.)

```python
def test_to_resume_is_the_newest_roleplay_with_my_line_left():
    old, new = make(A, "2026-11-05T10:00:00"), make(B, "2026-11-06T10:00:00", pos=1)
    assert to_resume([new, old]).id == B

def test_no_resume_when_the_newest_is_done():
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
```

  `test_resume.py`에 더한다.

```python
async def test_resume_after_a_followed_turn(engine_with_rp, speech_bytes, fake_whisper):
    engine, rp_id, user_idx = engine_with_rp
    fake_whisper.text = engine.load(rp_id).lines[user_idx].text
    [e async for e in engine.attempt(rp_id, user_idx, speech_bytes, "turn")]
    r = engine.resume()
    assert r["roleplay"]["id"] == rp_id and r["at"] == user_idx + 1
    assert [s["idx"] for s in r["said"]] == [user_idx] and r["progress"]["no"] == 2

async def test_resume_skips_an_unreadable_record(engine_with_rp):
    engine, rp_id, _ = engine_with_rp
    bad = engine.store.roleplays / ("f" * 12)
    bad.mkdir()
    (bad / "roleplay.json").write_text("{", encoding="utf-8")
    assert engine.resume()["roleplay"]["id"] == rp_id

def test_resume_route(client):
    assert client.get("/resume").json() == {"resume": None}
    rp = client.post("/roleplays", json={"situation": "길 묻기"}).json()
    r = client.get("/resume").json()["resume"]
    assert r["roleplay"]["id"] == rp["id"] and r["at"] == 0 and r["said"] == []
```

  `test_contract.py`: `test_resume_example_has_the_engine_shape` — 키가 `{"roleplay", "at", "progress", "said"}`, `Roleplay.model_validate(raw["resume"]["roleplay"])`가 그대로 돌아오고, `said`의 키가 `{"idx", "heard", "n"}`.

- [ ] **Step 2: 실패를 본다** — `cd server && uv run pytest tests/test_review.py tests/test_resume.py tests/test_contract.py -q` → `ImportError: cannot import name 'to_resume'`

- [ ] **Step 3: 위 Interfaces대로 쓴다.** `Engine.resume`는 `self.store.all()`을 한 번 읽는다(읽을 수 없는 기록은 거기서 이미 건너뛴다).

- [ ] **Step 4: 통과를 본다** — 같은 명령, 그리고 `uv run pytest -q` 전체가 통과한다.

- [ ] **Step 5: 커밋한다** — `feat(server): tell the app which conversation to resume`

### Task 3: 앱의 요청과 모양

**Files:**
- Modify: `app/src/api/types.ts`, `app/src/api/client.ts`, `app/src/api/contract.test.ts`

**Interfaces:**
- Produces:
  - `export type HeardTry = { idx: number; heard: string; n: number };`
  - `export type Resume = { roleplay: Roleplay; at: number; progress: Progress; said: HeardTry[] };`
  - `export const RESUME_KEYS = ["roleplay", "at", "progress", "said"] as const; export const HEARD_TRY_KEYS = ["idx", "heard", "n"] as const;` (아래의 키 목록과 타입을 맞추는 검사도 지금 것처럼 더한다)
  - `api.resume(): Promise<Resume | null>` — `GET /resume`의 `resume`.
  - `api.skipLine(id: string, idx: number): Promise<{ pos: number }>` — `POST /roleplays/${id}/lines/${idx}/skip`.

- [ ] **Step 1: 실패하는 시험을 쓴다** (`contract.test.ts`)

```ts
import resume from "../../../contract/resume.json";

test("resume example has the keys the situation screen reads", () => {
  expect(sorted(Object.keys(resume.resume))).toEqual(sorted(RESUME_KEYS));
  expect(sorted(Object.keys(resume.resume.roleplay))).toEqual(sorted(ROLEPLAY_KEYS));
  for (const s of resume.resume.said) expect(sorted(Object.keys(s))).toEqual(sorted(HEARD_TRY_KEYS));
});
```

- [ ] **Step 2: 실패를 본다** — `cd app && npx jest src/api/contract.test.ts` → `RESUME_KEYS`가 없다는 오류

- [ ] **Step 3: 타입, 키 목록, 두 요청을 쓴다.** 요청은 `getRoleplay`, `setSaved` 옆에 지금 `get`, `post`로.

- [ ] **Step 4: 통과를 본다** — `npx jest src/api && npx tsc --noEmit`

- [ ] **Step 5: 커밋한다** — `feat(app): add the resume and skip requests`

### Task 4: 받은 기록으로 앞의 대화를 만든다

**Files:**
- Create: `app/src/flow/resume.ts`, `app/src/flow/resume.test.ts`

**Interfaces:**
- Consumes: `Resume`, `HeardTry`(Task 3), `Bubble`(`state.ts`)
- Produces:
  - `resumeHistory(r: Resume): Bubble[]` — `idx < r.at`인 줄을 차례로. 라이언 줄은 `{ kind: "ryan", text, idx }`. 내 줄은 `said`에 있으면 `{ kind: "user", text: heard, script: line.text, idx, rec: { rp_id: r.roleplay.id, idx, n } }`, 없으면 `{ kind: "user", text: "", script: line.text, idx, skipped: true }`.
  - `resumeSeen(r: Resume): Record<number, ScriptLine>` — `idx < r.at`인 줄.
  - `resumeLabel(r: Resume): string` — `${r.roleplay.frame.title_ko} · 내 대사 ${r.progress.no}/${r.progress.total}`.

- [ ] **Step 1: 실패하는 시험을 쓴다.** 지어낸 대화 다섯 줄(라이언 0, 나 1, 라이언 2, 나 3, 라이언 4)로 만든다.
  - `the lines before the start, with what was heard`: `at` 2, `said` `[{idx:1, heard:"Yes, two nights.", n:2}]` → 말풍선 둘, 둘째의 `rec`가 `{ rp_id, idx: 1, n: 2 }`.
  - `a skipped line keeps its script only`: `at` 4, `said`에 줄 3이 없으면 넷째 말풍선이 `{ kind: "user", text: "", script, idx: 3, skipped: true }`.
  - `nothing before the first line`: `at` 0 → `[]`, `resumeSeen` → `{}`.
  - `the label says the situation and my line`: `"호텔 체크인하기 · 내 대사 2/2"`.

- [ ] **Step 2: 실패를 본다** — `npx jest src/flow/resume.test.ts` → 모듈이 없다

- [ ] **Step 3: 세 함수를 쓴다.**

- [ ] **Step 4: 통과를 본다** — 같은 명령

- [ ] **Step 5: 커밋한다** — `feat(app): rebuild a resumed conversation from the Mac's record`

### Task 5: 남겨 두고 나온 요청 세기

**Files:**
- Create: `app/src/flow/pending.ts`, `app/src/flow/pending.test.ts`

**Interfaces:**
- Produces:
  - `export function createPending(): { track<T>(p: Promise<T>): Promise<T>; settled(maxMs: number): Promise<void> }` — `track`은 `p`를 그대로 돌려주고(실패도 그대로 부른 쪽에 간다), 끝날 때까지 센다. `settled`는 부른 때 세고 있던 것이 모두 끝나거나(실패도 끝) `maxMs`가 지나면 풀린다.
  - `export const pending = createPending();` — 대화 화면과 상황 정하기 화면이 함께 쓰는 하나.
  - `export const RESUME_WAIT_MS = 30_000;`

- [ ] **Step 1: 실패하는 시험을 쓴다** (jest 가짜 타이머)
  - `settled is at once with nothing tracked`
  - `settled waits for what was tracked`: 풀리지 않은 약속 하나를 `track` → `settled(30_000)`이 아직 안 풀림 → 약속을 풀면 풀린다.
  - `a failed promise counts as settled`: 거부된 약속을 `track`(부른 쪽에서 `.catch`) → `settled`가 풀린다.
  - `settled gives up after maxMs`: 풀리지 않는 약속 → 30초를 돌리면 풀린다.

- [ ] **Step 2: 실패를 본다** — `npx jest src/flow/pending.test.ts`

- [ ] **Step 3: 쓴다.** 세는 것은 `Set<Promise<unknown>>`, 끝나면(`finally`) 뺀다.

- [ ] **Step 4: 통과를 본다** — 같은 명령

- [ ] **Step 5: 커밋한다** — `feat(app): wait for what the roleplay screen left running`

### Task 6: 리듀서: 이어 하기, 뒤로, 묻지 않기

**Files:**
- Modify: `app/src/flow/state.ts`, `app/src/flow/state.test.ts`

**Interfaces:**
- Consumes: `resumeHistory`, `resumeSeen`(Task 4), `Resume`(Task 3)
- Produces:
  - 동작 `{ type: "resumed"; resume: Resume }` — `s.screen === "situation"`일 때만. `{ ...initial, screen: "roleplay", roleplay, idx: at, history: resumeHistory(r), seen: resumeSeen(r), progress, phase: "loading" }`(`situationFrom` null, `jake` null, `mode` `"turn"`).
  - `back`: 대화 화면(연습이 아니고 `returnTo`가 없을 때)에서는 `{ ...initial, screen: "situation" }`(주제 고르기). 끝 화면은 지금처럼 `situationFrom`.
  - `askFirst`를 지운다.

- [ ] **Step 1: 시험을 고치고 더한다**
  - `situation topics` 묶음의 `back from a roleplay returns to the step the situation came from`를 `back from a roleplay mid-way goes to the topics; from its end screen to where it was picked`로 바꾼다. 대화 화면 뒤로 → `["situation", null, null]`, 끝 화면 뒤로 → `["situation", from]`.
  - `restarting keeps where back leads`: 끝 화면에서 뒤로를 본다(지금 시험이 대화 화면에서 보면 null로 바꾼다).
  - 새 묶음 `resume (spec resume-roleplay)`:
    - `resuming opens the roleplay at its line with what was said before`: `reduce(situation, { type: "resumed", resume })` → `screen` `"roleplay"`, `idx` `at`, `phase` `"loading"`, `history` `resumeHistory(resume)`, `progress`, `situationFrom` null, `jake` null.
    - `resumed is taken only on the situation screen`: `home`이나 대화 화면에서는 `toBe(그 상태)`.
    - `a second resumed does nothing`: 두 번 보내면 첫 번째 결과와 같다(`toBe`).
    - `a past line of a resumed roleplay can be practised`: `practiceFor(s, s.history[1])` → `"mine"`.
    - `back from a resumed roleplay goes to the topics`.
  - `asks first only when a roleplay would be lost`와 `askFirst` 가져오기를 지운다.

- [ ] **Step 2: 실패를 본다** — `npx jest src/flow/state.test.ts`

- [ ] **Step 3: 고친다.** `back`의 주석에 이 스펙과 사용자 결정을 적는다.

- [ ] **Step 4: 통과를 본다** — `npx jest && npx tsc --noEmit` (`RoleplayScreen.tsx`가 `askFirst`를 가져와 tsc가 깨지면 Task 7의 묻기 지우기를 여기서 함께 한다)

- [ ] **Step 5: 커밋한다** — `feat(app): resume a conversation and go back to the topics without asking`

### Task 7: 화면: 한 줄, 묻지 않는 뒤로, 알림

**Files:**
- Create: `app/src/ui/ResumeRow.tsx`
- Modify: `app/src/screens/SituationScreen.tsx`, `app/src/screens/RoleplayScreen.tsx`, `app/App.tsx`

**Interfaces:**
- Consumes: `api.resume`, `api.skipLine`(Task 3), `resumeLabel`(Task 4), `pending`, `RESUME_WAIT_MS`(Task 5), 동작 `resumed`(Task 6)
- Produces: `ResumeRow({ line, onPress }: { line: string; onPress: () => void })`. `SituationScreen`의 새 prop `onResume: (r: Resume) => void`.

- [ ] **Step 1: `ResumeRow`를 쓴다.** Global Constraints의 모양과 글귀. `accessibilityRole="button"`, `accessibilityLabel`은 두 줄을 이은 것. 눌린 동안 투명도 0.7(버튼 가이드). ▶는 소스에 `"▶︎"`로 쓰고, 파일에 역슬래시 글자 그대로 들어갔는지 `grep -n 'u25B6' app/src/ui/ResumeRow.tsx`로 본다(도구가 이스케이프를 풀어 넣는 일이 있었다).

- [ ] **Step 2: `SituationScreen`.** 화면이 열릴 때 한 번 `pending.settled(RESUME_WAIT_MS)` 뒤 `api.resume()`. 화면을 떠났으면 버리고, 실패하면 한 줄 없이 둔다. `step === "topic"`이고 받은 것이 있으면 주제 버튼 아래에 늘어나는 빈칸(`flex: 1`)을 두고 `ResumeRow`를 둔다. 누르면 `sounds.clear()` 뒤 `onResume`.

- [ ] **Step 3: `RoleplayScreen`.**
  - `askLeave`와 `Alert`를 지우고, 「‹ 뒤로」와 폰의 뒤로 키가 `leave()`를 바로 부른다. `leave`의 주석에서 「이어 하기가 없어 묻는다」를 고친다.
  - `sendRec`: `state.mode === "turn"`이면 `api.attempt(...)`를 `pending.track`으로 감싼다.
  - `doSkip`: 연습이 아니면 `dispatch` 전에 `pending.track(api.skipLine(rp.id, state.line.idx)).catch(() => {})`.

- [ ] **Step 4: `App.tsx`.** `SituationScreen`에 `onResume={(resume) => dispatch({ type: "resumed", resume })}`.

- [ ] **Step 5: 확인한다** — `cd app && npx tsc --noEmit && npx jest` → 오류 없음, 모두 통과

- [ ] **Step 6: 커밋한다** — `feat(app): show the resume row on the topic step and stop asking on leave`

### Task 8: 문서

**Files:**
- Modify: `docs/PRD.md`, `docs/superpowers/specs/2026-11-05-speaking-practice-design.md`, `docs/superpowers/specs/2026-11-08-record-cancel-skip-design.md`, `docs/superpowers/specs/2026-11-07-situation-topics-design.md`, `docs/superpowers/specs/2026-11-07-review-screens-design.md`, `docs/guide/APP_버튼_색과_모양_20261108.md`

- [ ] **Step 1: 스펙 「6. 고칠 문서」대로 고친다.**
  - PRD: 머리말 「고침」에 이 날의 줄, 「첫 화면」의 「맨 앞 선택지」와 「버튼은 넷」, 「상황 정하기」, 「독려」의 「바로 이어 하기」. 사용자의 말 「이어 하기 버튼은 메인에 없는 게 좋을 것 같은데, 메인이 복잡해진다」를 적는다.
  - 버튼 가이드 「버튼이 아닌 것」 위에: 이어 하기 줄은 두 줄짜리 덜 주된 버튼 모양이다.
- [ ] **Step 2: 커밋한다** — `docs: write resuming a conversation into the PRD and earlier specs`

### Task 9: 끝에서 끝까지 확인

- [ ] **Step 1: 전체 시험** — `cd server && uv run pytest -q`, `cd app && npx jest && npx tsc --noEmit`
- [ ] **Step 2: 시험 서버.** `DEVENV_맥서버_저절로_띄우기_20261107.md` 「카드가 서버를 시험할 때」대로 데이터 복사본(녹음 뺌)으로 `JE_HOST=127.0.0.1 JE_PORT=8791 JE_WHISPER_PORT=8792`에 띄운다. 목록 상황을 만들고 `GET /resume`(at 0) → 제이크 목소리 녹음으로 첫 내 대사를 따라 말함(`try_recordings.py`처럼 같은 요청) → `GET /resume`(at 다음 라이언 줄, said 하나) → 다음 내 대사 `skip` → `GET /resume`(그 다음, 남은 내 대사가 없으면 null).
- [ ] **Step 3: 에뮬레이터(AVD `jake-english`, 360dp도).** 앱을 깔고 시험 서버에 붙인다. 첫 화면이 카드 둘 그대로인지 → 「대화 연습하기」(하던 대화가 있으면 맨 아래 한 줄) → 목록 상황으로 대화를 시작해 라이언 말 중 「뒤로」(묻지 않고 주제 고르기 단계, 맨 아래 한 줄) → 한 줄 누르기(라이언이 맞는 대사부터) → 내 차례에서 「건너뛰기」 → 「뒤로」 → 다시 한 줄(건너뛴 다음부터, 앞의 말풍선) → 앱을 껐다 켜 같은지 → 끝까지 하면 한 줄이 없는지. 녹음 버튼 시험 전에 `emu avd hostmicoff`. 스크린샷은 저장소 밖.
- [ ] **Step 4: 시험 데이터와 녹음 파일을 지우고 서버와 에뮬레이터를 끈다.**
