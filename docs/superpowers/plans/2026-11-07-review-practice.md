# 다시 연습(지난 상황, 모아 둔 문장) 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 첫 화면의 「다시 연습」에서 지난 상황을 같은 대본으로 다시 하고, 직접 모은 문장만 연습하게 한다. 지나간 말풍선과 주고받은 말의 줄은 눌러야 버튼이 펼쳐진다.

**Architecture:** 맥 서버가 `roleplay.json` 기록을 읽어 지난 상황 목록, 묶음의 최근 회차, 처음 녹음, 모아 둔 문장 목록을 만든다(Claude를 부르지 않는다, ADR-0011). 판정은 순수 함수 모듈 `server/je_server/review.py`에 모으고, `Engine`은 기록을 읽고 쓰기만 한다. 앱은 화면 흐름을 지금처럼 리듀서(`app/src/flow/state.ts`)에 두고, 새 화면 셋(다시 연습, 지난 상황, 모아 둔 문장)을 더한다. 지난번 대화는 끝 화면을, 모아 둔 문장 연습은 역할극 화면의 연습을 다시 쓴다.

**Tech Stack:** FastAPI, pydantic(pytest, anyio), Expo SDK 58 / React Native 0.88(jest-expo, tsc). 새 패키지는 없다.

**Spec:** `docs/superpowers/specs/2026-11-07-review-practice-design.md` (함께 읽을 것: `docs/adr/0011-review-from-stored-records.md`, `docs/superpowers/specs/2026-11-05-roleplay-practice-design.md`)

## Global Constraints

- 새 패키지를 설치하지 않는다.
- 지난 상황 목록, 지난번 대화, 처음 녹음, 모아 두기와 빼기, 모아 둔 문장 목록은 Claude를 부르지 않는다.
- 지난번 대화 화면은 열릴 때 라이언 줄의 읽는 법을 미리 만들지 않는다(끝 화면의 `getThree` 미리 부르기를 건너뛴다).
- 같은 문장 기준(`sentence_key`, `sentenceKey`): 소문자로 바꾸고 `’`를 `'`로 바꾼 뒤, `[a-z0-9']+` 조각만 남겨 빈칸 하나로 잇는다. 서버와 앱이 `contract/sentence-keys.json`으로 같은 결과를 확인한다.
- 녹음은 지금의 경로 `/roleplays/{id}/lines/{idx}/attempts/{n}/recording`로만 내준다. 새 녹음 경로를 열지 않는다.
- 새 경로의 ID는 지금처럼 `ID = r"^[0-9a-f]{12}$"`로 검사하고 토큰이 있어야 열린다.
- 화면 글귀(바꾸지 않는다): 「다시 연습」, 「지난 상황」, 「했던 상황을 같은 대본으로 다시」, 「모아 둔 문장 (n)」, 「모아 둔 문장만 집중해서」, 「처음 한 날 M월 D일」, 「아직 해 본 상황이 없어요」, 「☆ 모아 두기」, 「★ 모아 둠」, 「빼기 ✕」, 「M월 D일에 모음」, 「처음부터 차례로 연습(n)」, 「아직 모아 둔 문장이 없어요. 역할극이나 연습에서 ☆를 누르면 여기에 모여요.」, 「모아 둔 문장 a/b」, 「앞 대화 보기 ›」/「앞 대화 접기」, 「이 상황 다시 하기」, 「▶ 처음 녹음」, 「모아 두지 못했어요. 맥 연결을 확인해 주세요.」, 「준비하고 있어요」.
- 끝 화면의 「같은 대본으로 처음부터」는 「이 상황 다시 하기」로 바꾼다.
- 시험 문장과 계약 예시는 지어낸 것을 쓴다. 지난 기록의 대사, 들린 말, 상황을 옮기지 않는다(ADR-0005, `AGENTS.md` 「공개 저장소」).
- git은 `/usr/bin/git`으로 부르고, `git add`는 파일을 지정한다. 커밋은 `git commit -F - <<'EOF'`로, Conventional Commits 영어, scope는 `server`, `app`(둘 다 걸치면 생략), AI 서명 없이 쓰고 끝에 `Refs: docs/superpowers/specs/2026-11-07-review-practice-design.md`를 단다.
- 시험 명령: 서버 `cd server && uv run pytest -q`, 앱 `cd app && npx jest` 와 `cd app && npx tsc --noEmit`.

## Review Focus

- **줄이 바뀐 모아 둔 문장:** 모은 뒤 다르게 말해 남은 대본이 새로 만들어지면 `idx`가 다른 글을 가리킨다. 목록은 같은 문장 기준으로 그 역할극에서 다시 찾고, 없으면 그 항목만 빼고 보여 준다(Task 4 `test_saved_list_finds_moved_line`, `test_saved_list_skips_lost_line`).
- **옛 기록:** `origin`, `at`이 없는 `roleplay.json`도 그대로 읽히고, 처음 녹음은 `at` 대신 그 역할극을 만든 때로 가른다(Task 1 `test_old_record_loads`, Task 3 `test_first_try_falls_back_to_created`).
- **☆ 두 번 누르기:** 두 요청이 가도 항목은 하나다. 서버는 같은 글을 두 번 넣지 않고, 앱은 요청 중인 문장의 누름을 무시한다(Task 4 `test_save_twice_keeps_one`, Task 7 `pendingKeys` 시험).
- **다시 한 뒤 돌아오기:** 지난번 대화에서 「이 상황 다시 하기」로 한 역할극을 그만두거나 끝내고 「뒤로」 하면 지난번 대화로 돌아오고, 방금 한 회차가 보인다(Task 3 `test_latest_is_newest_spoken_run`, Task 6 `restarted from a past view returns there`).
- **두 역할극에 걸친 모아 둔 문장:** 차례로 할 때 줄 번호가 같은 다른 역할극의 줄로 넘어가도 앞 줄의 읽는 법, 통역, 본보기 기록이 섞이지 않는다. 리듀서는 역할극을 바꾸고(Task 6 시험), 앱은 역할극 화면을 역할극 ID로 다시 띄운다(Task 8 `key`).

---

### Task 1: 기록에 원본 ID와 녹음한 때를 남긴다

**Files:**
- Modify: `server/je_server/models.py` (`Attempt`, `Roleplay`)
- Modify: `server/je_server/engine.py` (`Engine.copy`, `Engine.attempt`의 `Attempt(...)`)
- Modify: `contract/roleplay.json` (`origin`, 시도마다 `at`)
- Modify: `app/src/api/types.ts` (`Attempt.at`, `Roleplay.origin`, `ROLEPLAY_KEYS`)
- Test: `server/tests/test_engine.py`, `server/tests/test_store.py`, `server/tests/test_contract.py`, `app/src/api/contract.test.ts`

**Interfaces:**
- Produces: `Attempt.at: str | None = None`(초까지의 ISO 시각, `datetime.now().isoformat(timespec="seconds")`), `Roleplay.origin: str | None = None`(묶음의 첫 역할극 ID). 앱 `Attempt.at: string | null`, `Roleplay.origin: string | null`, `ROLEPLAY_KEYS`에 `"origin"`.

- [ ] **Step 1: 시험을 쓴다.** `test_engine.py`:
  - `test_copy_points_at_the_first_roleplay`: `rp = await engine.create("길 묻기")`, `c1 = await engine.copy(rp.id)`, `c2 = await engine.copy(c1.id)` → `rp.origin is None`, `c1.origin == rp.id`, `c2.origin == rp.id`, `engine.load(c2.id).origin == rp.id`.
  - `test_attempt_records_when`: `engine_with_rp`로 한 번 말한 뒤 `engine.load(rp_id).attempts[user_idx][0].at`가 `re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d", at)`.
  - `test_store.py`의 `test_old_record_loads`: `origin`과 시도의 `at` 키가 없는 `roleplay.json`(지어낸 대사)을 써 두고 `Store.load` → `origin is None`, `at is None`.
  - 계약: `contract/roleplay.json`에 `"origin": null`을 `pos` 다음에, 시도마다 `"at": "2026-11-07T10:00:00"`을 `timings` 다음에 더한다.
- [ ] **Step 2: 실패를 본다.** `cd server && uv run pytest tests/test_engine.py tests/test_store.py tests/test_contract.py -q` → 새 시험과 계약이 FAIL. `cd app && npx jest src/api/contract.test.ts` → 키가 달라 FAIL.
- [ ] **Step 3: 구현한다.** 두 칸을 모델에 더하고(주석에 ADR-0011), `copy`는 `origin=old.origin or old.id`, `attempt`는 `Attempt(..., at=datetime.now().isoformat(timespec="seconds"))`. 앱 타입과 `ROLEPLAY_KEYS`를 맞춘다.
- [ ] **Step 4: 통과를 본다.** 서버 전체 `uv run pytest -q` PASS, `npx jest` PASS, `npx tsc --noEmit` 오류 없음.
- [ ] **Step 5: Commit** `feat: record the origin of copied roleplays and when each try was made`

---

### Task 2: 같은 문장 기준을 서버와 앱에 둔다

**Files:**
- Create: `server/je_server/review.py` (이 Task에서는 `sentence_key`만)
- Create: `app/src/flow/review.ts` (이 Task에서는 `sentenceKey`만)
- Create: `contract/sentence-keys.json`
- Test: `server/tests/test_review.py`, `app/src/flow/review.test.ts`

**Interfaces:**
- Produces: 서버 `sentence_key(text: str) -> str`, 앱 `sentenceKey(text: string): string`. 규칙은 Global Constraints.

- [ ] **Step 1: 계약 예시와 시험을 쓴다.** `contract/sentence-keys.json`은 `[[입력, 기대값], ...]`이다. 적어도 다음을 넣는다: `["Can I have a small latte, please?", "can i have a small latte please"]`, `["I’m  fine.", "i'm fine"]`, `["It's 10 o'clock!", "it's 10 o'clock"]`, `["Sure.", "sure"]`, `["...", ""]`. 서버 `test_sentence_keys_match_contract`와 앱 `"sentence keys match the contract"`가 파일의 모든 쌍을 확인한다.
- [ ] **Step 2: 실패를 본다.** `uv run pytest tests/test_review.py -q`, `npx jest src/flow/review.test.ts` → 함수가 없어 FAIL.
- [ ] **Step 3: 두 함수를 구현한다.** 서버는 `re.findall(r"[a-z0-9']+", text.lower().replace("’", "'"))`, 앱은 같은 정규식의 `match`.
- [ ] **Step 4: 통과를 본다.** 위 두 명령 PASS.
- [ ] **Step 5: Commit** `feat: add one sentence key shared by the server and the app`

---

### Task 3: 지난 상황 목록, 묶음의 최근 회차, 처음 녹음 (서버)

**Files:**
- Modify: `server/je_server/review.py`
- Modify: `server/je_server/store.py` (`Store.all`)
- Modify: `server/je_server/engine.py` (`Engine.past`, `Engine.latest`, `Engine.summary`)
- Modify: `server/je_server/app.py` (`GET /roleplays/{rp_id}`, `GET /past`, `GET /groups/{group}/latest`)
- Modify: `contract/summary.json` (내 줄마다 `first`)
- Create: `contract/past.json`
- Test: `server/tests/test_review.py`, `server/tests/test_summary.py`, `server/tests/test_api.py`, `server/tests/test_contract.py`

**Interfaces:**
- Consumes: Task 1의 `Roleplay.origin`, `Attempt.at`; Task 2의 `sentence_key`.
- Produces:
  - `review.group_of(rp: Roleplay) -> str` (`rp.origin or rp.id`)
  - `review.spoken(rp: Roleplay) -> bool` (내 줄에 `turn` 또는 `retry` 시도가 하나라도 있다)
  - `review.past_items(rps: list[Roleplay]) -> list[dict]`: 말한 회차가 있는 묶음마다 `{"group": str, "title_ko": str, "first": "YYYY-MM-DD", "latest": "<ISO>"}`. `first`는 말한 회차 중 가장 이른 `created`의 날짜, `latest`와 `title_ko`는 말한 회차 중 가장 늦은 것. `latest`가 늦은 묶음부터.
  - `review.latest_run(rps: list[Roleplay], group: str) -> Roleplay | None`: 그 묶음의 말한 회차 중 `created`가 가장 늦은 것.
  - `review.first_try(group_runs: list[Roleplay], rp: Roleplay, idx: int) -> dict | None`: `{"rp_id": str, "idx": int, "n": int}`. 규칙은 스펙 4: 묶음의 모든 회차에서 `speaker == "user"`이고 `sentence_key`가 같은 줄의 `followed` 시도 중 `(a.at or run.created, run.created, a.n)`이 가장 작은 것. 그것이 `rp`의 그 줄의 `turn`/`retry` 시도이면 `None`. 라이언 줄이면 `None`.
  - `Store.all() -> list[Roleplay]`: 읽히는 모든 `roleplay.json`. 읽지 못하는 파일은 로그 한 줄(ID만)을 남기고 건너뛴다. `recent_situations`도 이것을 쓴다.
  - `Engine.past() -> list[dict]`, `Engine.latest(group: str) -> dict` (`{"roleplay": Roleplay JSON, "summary": summary(그 회차)}`, 없으면 `NotFound`), `Engine.summary(rp_id)`의 각 줄에 `"first": dict | None`.
  - 경로: `GET /roleplays/{rp_id}` → `Roleplay` JSON, `GET /past` → `{"items": [...]}`, `GET /groups/{group}/latest` → `Engine.latest`. 없는 ID는 404 `not_found`.

- [ ] **Step 1: 판정 시험을 쓴다(`test_review.py`, 기록은 지어낸 `Roleplay`를 직접 만든다).**
  - `test_unspoken_roleplays_are_left_out`: 시도가 없는 역할극과 라이언 줄만 `shadow`로 따라 한 역할극 → `past_items == []`.
  - `test_copies_make_one_row`: 원본(11-05 created, 말함)과 복사본 둘(11-06 말함, 11-07 말하지 않음) → 한 줄, `first == "2026-11-05"`, `latest`는 11-06 회차의 `created`, `group`은 원본 ID.
  - `test_same_title_other_script_is_another_row`: `title_ko`가 같고 `origin`이 없는 두 역할극 → 두 줄.
  - `test_rows_newest_first`.
  - `test_latest_is_newest_spoken_run`: 위 묶음에서 `latest_run`은 11-06 회차(11-07은 말하지 않아 아님).
  - `test_first_try_is_from_the_earlier_run`: 원본의 그 줄 `turn` n=1(`at` 11-05), 복사본의 `turn` n=1(`at` 11-06) → 복사본 기준 `first_try == {"rp_id": 원본, "idx": i, "n": 1}`; 원본 기준 `None`.
  - `test_first_try_skips_offscript_and_ryan`: 원본의 그 줄 시도가 `followed=False`뿐이면 복사본 기준 `None`. 라이언 줄의 `shadow` 시도는 세지 않는다.
  - `test_first_try_by_time_not_run_order`: 원본의 그 줄에 시도가 없다가 11-08에 `practice` n=1이 쌓이고, 복사본(11-06 created)의 `turn` n=1(`at` 11-06) → 복사본 기준 `None`(복사본의 것이 가장 이르다), 원본 기준 복사본의 시도.
  - `test_first_try_falls_back_to_created`: `at`이 없는 옛 시도는 그 회차의 `created`로 가른다.
- [ ] **Step 2: 경로와 끝 화면 시험을 쓴다.**
  - `test_summary.py`의 `test_summary_first_points_at_earlier_run`: `engine_with_rp`에서 대사대로 말하고(`fake_whisper.text = "It's right over there."`), `copy`한 회차에서 같은 줄을 말한 뒤 `summary(copy)`의 그 줄 `first == {"rp_id": rp_id, "idx": user_idx, "n": 1}`, `summary(rp_id)`의 그 줄 `first is None`, 라이언 줄 `first is None`.
  - `test_api.py`: `test_past_and_latest_routes`(만들고 한 번 말한 뒤 `/past`에 한 줄, `/groups/{id}/latest`의 `roleplay.id`와 `summary.lines` 수), `test_get_roleplay_route`, `test_latest_unknown_or_unspoken_is_404`, `test_new_routes_need_token`(`/past`, `/groups/000000000000/latest`, `/roleplays/000000000000`이 토큰 없이 401), `test_bad_group_id_rejected`(`/groups/..%2Fx/latest`가 404나 422).
  - 계약: `contract/summary.json`의 모든 줄에 `"first": null`, 내 줄 하나는 `{"rp_id": "a1b2c3d4e5f6", "idx": 1, "n": 1}`. `test_summary_example_has_the_engine_shape`의 줄 키를 `{"line", "tries", "first"}`로. `contract/past.json`은 `{"items": [{"group", "title_ko", "first", "latest"}]}` 예시 하나, `test_past_example_has_the_engine_shape`가 키를 확인한다.
- [ ] **Step 3: 실패를 본다.** `uv run pytest tests/test_review.py tests/test_summary.py tests/test_api.py tests/test_contract.py -q` → FAIL.
- [ ] **Step 4: 구현한다.** 판정은 `review.py`에만 둔다. `Engine.summary`는 `group_runs = [r for r in self.store.all() if group_of(r) == group_of(rp)]`를 한 번 읽어 내 줄마다 `first_try`를 부른다. 끝 화면의 `say`와 `tries`는 바꾸지 않는다.
- [ ] **Step 5: 통과를 본다.** 서버 전체 `uv run pytest -q` PASS.
- [ ] **Step 6: Commit** `feat(server): list past situations and find the first recording of a line`

---

### Task 4: 모아 둔 문장 (서버)

**Files:**
- Modify: `server/je_server/models.py` (`Saved`)
- Modify: `server/je_server/store.py` (`Store.load_saved`, `Store.save_saved`)
- Modify: `server/je_server/engine.py` (`Engine.saved`, `Engine.set_saved`, `self.saved_lock`)
- Modify: `server/je_server/app.py` (`GET /saved`, `POST /saved`, 본문 `SavedChange`)
- Create: `contract/saved.json`
- Test: `server/tests/test_saved.py`, `server/tests/test_api.py`, `server/tests/test_contract.py`

**Interfaces:**
- Consumes: Task 2의 `sentence_key`.
- Produces:
  - `class Saved(BaseModel): key: str; rp_id: str; idx: int; at: str`
  - `Store.load_saved() -> list[Saved]` (파일 `root / "saved.json"`, 없으면 `[]`), `Store.save_saved(items: list[Saved]) -> None` (`Store.save`처럼 임시 파일에 쓰고 `os.replace`)
  - `Engine.saved() -> list[dict]`: `{"key", "rp_id", "idx", "speaker", "text", "title_ko", "at"}`, `at`이 늦은 것부터. 줄은 `rp.lines[idx]`의 글이 같은 문장이면 그것, 아니면 그 역할극에서 같은 문장인 첫 줄. 둘 다 없거나 역할극을 읽지 못하면 그 항목은 목록에서 빠진다(파일에는 남는다).
  - `async Engine.set_saved(rp_id: str, idx: int, on: bool) -> dict`: `{"key": str, "on": bool}`. 없는 역할극이나 줄은 `NotFound`. `on`이면 같은 `key`가 없을 때만 더한다(있으면 그대로). 끄면 그 `key`를 모두 뺀다. `self.saved_lock`(`asyncio.Lock`) 안에서 읽고 쓴다.
  - 경로: `GET /saved` → `{"items": Engine.saved()}`, `POST /saved` 본문 `{"rp_id": str(pattern=ID), "idx": int(ge=0), "on": bool}` → `Engine.set_saved`. 404 `not_found`, 본문 오류 422.

- [ ] **Step 1: 시험을 쓴다(`test_saved.py`, 지어낸 대사).**
  - `test_save_and_list_newest_first`: 두 줄을 차례로 모으면 목록은 나중 것부터, 항목에 `speaker`, `text`, `title_ko`.
  - `test_save_twice_keeps_one`: 같은 줄을 `on=True`로 두 번 → 한 항목. 같은 문장인 다른 역할극의 줄을 모아도 한 항목.
  - `test_unsave_removes_by_sentence`: 다른 역할극의 같은 문장 줄로 `on=False` → 빠진다.
  - `test_saved_survives_restart`: 모은 뒤 같은 폴더로 새 `Engine`(`engine_factory()`)을 만들어 `saved()`에 남아 있다.
  - `test_saved_list_finds_moved_line`: 모은 줄의 `idx` 자리를 다른 글로 바꾸고 같은 문장을 다른 `idx`에 둔 기록 → 목록의 `idx`가 새 자리.
  - `test_saved_list_skips_lost_line`: 같은 문장이 그 역할극에 없으면 목록에서 빠지고 `store.load_saved()`에는 남는다.
  - `test_save_unknown_line_is_not_found`: 없는 역할극 ID, 범위 밖 `idx` → `NotFound`.
- [ ] **Step 2: 경로 시험을 쓴다(`test_api.py`).** `test_saved_routes`(POST 뒤 GET에 한 항목, 끄면 빈 목록), `test_saved_bad_body_rejected`(`rp_id: "../x"`, `idx: -1`이 422), `test_saved_routes_need_token`(GET과 POST가 401). 계약 `contract/saved.json`과 `test_saved_example_has_the_engine_shape`.
- [ ] **Step 3: 실패를 본다.** `uv run pytest tests/test_saved.py tests/test_api.py tests/test_contract.py -q` → FAIL.
- [ ] **Step 4: 구현한다.**
- [ ] **Step 5: 통과를 본다.** 서버 전체 PASS.
- [ ] **Step 6: Commit** `feat(server): keep saved sentences in one file on the Mac`

---

### Task 5: 앱의 API와 타입

**Files:**
- Modify: `app/src/api/types.ts`
- Modify: `app/src/api/client.ts`
- Test: `app/src/api/client.test.ts`, `app/src/api/contract.test.ts`

**Interfaces:**
- Consumes: Task 3, 4의 경로와 `contract/summary.json`, `contract/past.json`, `contract/saved.json`.
- Produces:
  - 타입: `TryRef = { rp_id: string; idx: number; n: number }`, `TranscriptLine = { line: ScriptLine; tries: Try[]; first: TryRef | null }`, `PastItem = { group: string; title_ko: string; first: string; latest: string }`, `PastRun = { roleplay: Roleplay; summary: Summary }`, `SavedItem = { key: string; rp_id: string; idx: number; speaker: Speaker; text: string; title_ko: string; at: string }`. 키 목록 `TRANSCRIPT_KEYS`, `PAST_KEYS`, `SAVED_KEYS`와 `KEYS_MATCH` 항목.
  - `api.getRoleplay(id: string): Promise<Roleplay>`, `api.past(): Promise<PastItem[]>`, `api.pastRun(group: string): Promise<PastRun>`, `api.saved(): Promise<SavedItem[]>`, `api.setSaved(rpId: string, idx: number, on: boolean): Promise<{ key: string; on: boolean }>`.

- [ ] **Step 1: 시험을 쓴다.** `client.test.ts`: 다섯 함수가 부르는 주소와 방법(`setSaved`는 POST `/saved`, 본문 `{"rp_id":"a1b2c3d4e5f6","idx":2,"on":true}`), `past`와 `saved`가 `items`를 풀어 돌려주는지. `contract.test.ts`: summary의 줄 키가 `TRANSCRIPT_KEYS`, past와 saved 예시의 항목 키.
- [ ] **Step 2: 실패를 본다.** `npx jest src/api` → FAIL.
- [ ] **Step 3: 구현한다.**
- [ ] **Step 4: 통과를 본다.** `npx jest` PASS, `npx tsc --noEmit` 오류 없음.
- [ ] **Step 5: Commit** `feat(app): add API calls for past situations and saved sentences`

---

### Task 6: 화면 흐름 (리듀서)

**Files:**
- Modify: `app/src/flow/state.ts`
- Test: `app/src/flow/state.test.ts`

**Interfaces:**
- Consumes: Task 5의 `Roleplay`.
- Produces:
  - `Screen`에 `"review" | "past" | "saved"`.
  - `Practice = { kind: "mine" | "shadow"; order: number[]; at: number; from: "end" | "roleplay" | "saved"; runs?: Roleplay[] }` (`from: "saved"`일 때 `runs[i]`가 `order[i]`의 역할극).
  - `State`에 `past: { group: string; title: string } | null`(끝 화면이 지난번 대화일 때), `returnTo: State | null`(「다시 연습」에서 시작한 역할극이 돌아갈 화면), `beforeOpen: boolean`(모아 둔 문장 연습의 앞 대화).
  - `Action`에 `{ type: "openReview" }`, `{ type: "openPast" }`, `{ type: "openSaved" }`, `{ type: "openPastRun"; group: string; title: string }`, `{ type: "pastLoaded"; roleplay: Roleplay }`, `{ type: "startSaved"; runs: Roleplay[]; order: number[] }`, `{ type: "toggleBefore" }`. `restarted`는 끝 화면과 모아 둔 문장 연습에서 받는다.
  - `kindOf(line: ScriptLine): "mine" | "shadow"` (라이언 줄은 `shadow`).

- [ ] **Step 1: 시험을 쓴다(이름은 그대로 쓴다).**
  - `home opens review, review back goes home`
  - `review opens past and saved; back from them returns to review`
  - `openPastRun shows the end screen as a past view without closing words`: `screen === "end"`, `past` 설정, `roleplay === null`, `closingPlayed === true`. `pastLoaded`는 그때만 `roleplay`를 넣고 다른 화면에서는 무시된다.
  - `back from a past view returns to the past list`
  - `practice from a past view comes back to it`: `startPractice` → 마지막 `next` 뒤 `screen === "end"`, `past`가 남는다.
  - `restarted from a past view returns there`: 지난번 대화에서 `restarted` → `screen === "roleplay"`, `returnTo`가 그 지난번 대화 상태. 역할극에서 `back` → 그 상태로(`screen === "end"`, `past` 같음). 그 역할극이 끝 화면까지 간 뒤 `back`도 같다. 그 끝 화면에서 또 `restarted`해도 `returnTo`는 처음 것 그대로.
  - `restarted from a normal end keeps going to the situation screen`: `returnTo === null`, 역할극에서 `back` → `screen === "situation"`.
  - `saved practice walks lines across roleplays`: `runs = [rpA, rpB]`, `order = [1, 0]`(rpA의 1은 내 줄, rpB의 0은 라이언 줄) → 처음 `roleplay === rpA`, `idx === 1`, `mode === "practice"`, `practice.kind === "mine"`. 평가 뒤 `next` → `roleplay === rpB`, `idx === 0`, `mode === "shadow"`, `practice.kind === "shadow"`, `phase === "loading"`, `history` 빔. 마지막 `next` → `screen === "saved"`.
  - `back from saved practice returns to the saved list`
  - `a missing line in saved practice moves on`: `lineMissing` → 다음 줄로, 마지막이면 `screen === "saved"`(끝 화면으로 가지 않는다).
  - `restarted from saved practice returns to the same line`: `returnTo`가 그 연습 상태. 돌아오면 같은 `practice.at`, `roleplay`, `idx`이고 `phase === "loading"`, `line === null`, `history` 빔, `practiceNo`가 하나 늘었다.
  - `toggleBefore opens the previous line and a new line closes it`
  - `saved practice offers no midway practice`: `practiceFor`가 `null`.
- [ ] **Step 2: 실패를 본다.** `npx jest src/flow/state.test.ts` → FAIL.
- [ ] **Step 3: 구현한다.** 돌아가기는 함수 하나 `restore(rt: State): State`로: `rt.screen === "roleplay"`이면 `{ ...rt, ...freshTurn, phase: "loading", line: null, history: [], practiceNo: rt.practiceNo + 1 }`, 아니면 `rt` 그대로. `restarted`의 `returnTo`는 `s.returnTo ?? (s.past || s.practice?.from === "saved" ? s : null)`. `leavePractice`는 `from: "saved"`이면 `{ ...initial, screen: "saved" }`.
- [ ] **Step 4: 통과를 본다.** `npx jest` PASS, `npx tsc --noEmit` 오류 없음.
- [ ] **Step 5: Commit** `feat(app): add review screens and saved practice to the screen flow`

---

### Task 7: 앱 도우미와 모아 둔 문장 상태

**Files:**
- Modify: `app/src/flow/review.ts`
- Create: `app/src/flow/savedStore.ts` (순수 상태), `app/src/ui/useSaved.tsx` (React와 서버에 잇기), `app/src/ui/Star.tsx`
- Test: `app/src/flow/review.test.ts`, `app/src/flow/savedStore.test.ts`

**Interfaces:**
- Consumes: Task 2 `sentenceKey`, Task 5 `api.saved`, `api.setSaved`, `SavedItem`, `TranscriptLine`, `TryRef`.
- Produces:
  - `dayKo(iso: string): string` (`"2026-11-05"`나 `"2026-11-05T10:00:00"` → `"11월 5일"`)
  - `toggleRow(open: string | null, key: string): string | null` (같은 것이면 `null`, 아니면 `key`)
  - `comparePair(rpId: string, l: TranscriptLine): { first: TryRef; then: TryRef | null } | null` (`first`가 없으면 `null`; `then`은 `l.tries` 중 `followed`인 마지막 것의 `{ rp_id: rpId, idx: l.line.idx, n }`)
  - `createSavedStore(deps: { list: () => Promise<SavedItem[]>; set: (rpId: string, idx: number, on: boolean) => Promise<unknown>; onFail: () => void; changed: () => void })` → `{ items(): SavedItem[] | null; has(text: string): boolean; pending(text: string): boolean; refresh(): Promise<void>; toggle(rpId: string, idx: number, text: string): Promise<void> }`. `toggle`은 같은 문장이 요청 중이면 아무것도 하지 않고, 성공하면 `refresh`, 실패하면 상태를 바꾸지 않고 `onFail`.
  - `SavedProvider`, `useSaved(): ReturnType<typeof createSavedStore>`(바뀌면 다시 그린다). 실패 알림은 `ToastAndroid.show("모아 두지 못했어요. 맥 연결을 확인해 주세요.", ToastAndroid.SHORT)`.
  - `StarButton({ saved, onPress, disabled })` 글귀 「☆ 모아 두기」/「★ 모아 둠」, `StarMark()` 「★」.

- [ ] **Step 1: 시험을 쓴다.** `review.test.ts`: `dayKo` 두 형식, `toggleRow` 세 경우, `comparePair`(first 없음 → `null`; 시도 둘 중 마지막이 `followed=false`이면 앞의 것; 따라 말한 시도가 없으면 `then === null`). `savedStore.test.ts`: `pendingKeys`(요청이 끝나기 전 같은 문장 두 번째 `toggle`은 `set`을 부르지 않는다), 성공하면 `has`가 바뀐다, 실패하면 `has`가 그대로이고 `onFail` 한 번, `has`는 `sentenceKey`로 비교한다(`"Sure."`를 모으면 `"sure"`도 참).
- [ ] **Step 2: 실패를 본다.** `npx jest src/flow` → FAIL.
- [ ] **Step 3: 구현한다.**
- [ ] **Step 4: 통과를 본다.** `npx jest` PASS, `npx tsc --noEmit` 오류 없음.
- [ ] **Step 5: Commit** `feat(app): add saved-sentence state, star button and review helpers`

---

### Task 8: 첫 화면, 다시 연습, 지난 상황, 모아 둔 문장 화면

**Files:**
- Modify: `app/src/screens/HomeScreen.tsx` (`onReview`, 버튼 「다시 연습」)
- Create: `app/src/screens/ReviewScreen.tsx`, `app/src/screens/PastScreen.tsx`, `app/src/screens/SavedScreen.tsx`
- Modify: `app/App.tsx` (새 화면, `SavedProvider`, `RoleplayScreen`에 `key={state.roleplay?.id}`)

**Interfaces:**
- Consumes: Task 5 API, Task 6 액션, Task 7 `useSaved`, `dayKo`, `StarButton`.
- Produces: 화면 컴포넌트 `ReviewScreen({ dispatch })`, `PastScreen({ dispatch })`, `SavedScreen({ dispatch })`. 셋 다 왼쪽 위 「뒤로」와 폰의 뒤로가기 키(`useBackKey`)가 `back`을 보낸다.

- [ ] **Step 1: 첫 화면.** 「상황 역할극」 아래에 「다시 연습」. 다른 것은 바꾸지 않는다(돌아왔을 때의 말 포함).
- [ ] **Step 2: 다시 연습 화면.** 버튼 둘과 한 줄 설명(Global Constraints 글귀). 모아 둔 수는 `useSaved().items()?.length`이고, 화면이 열릴 때 `refresh()`. 라이언 그림과 목소리는 없다.
- [ ] **Step 3: 지난 상황 화면.** 열릴 때 `api.past()`. 줄마다 상황 이름과 「처음 한 날 {dayKo(first)}」. 누르면 `openPastRun`. 비었으면 「아직 해 본 상황이 없어요」. 오류는 `messageOf`와 「다시 시도」.
- [ ] **Step 4: 모아 둔 문장 화면.** 줄마다 이름표(「라이언」/「나」, `Named`의 색), 문장, 「{title_ko} · {dayKo(at)}에 모음」, 「빼기 ✕」(묻지 않고 `toggle`). 줄을 누르면 그 줄만, 맨 아래 「처음부터 차례로 연습(n)」은 모두. 시작할 때 필요한 역할극을 `api.getRoleplay`로 한 번씩 받아(「준비하고 있어요」) `startSaved`를 보낸다. 게이트로 두 번 누름을 막는다. 비었으면 Global Constraints의 안내 한 줄.
- [ ] **Step 5: `App.tsx`를 잇는다.** `RoleplayScreen`에 `key={state.roleplay?.id}`를 주어, 모아 둔 문장을 차례로 하다 역할극이 바뀌면 화면의 읽는 법, 통역, 본보기 기록이 새로 시작되게 한다(Review Focus 5).
- [ ] **Step 6: 확인한다.** `npx tsc --noEmit` 오류 없음, `npx jest` PASS.
- [ ] **Step 7: Commit** `feat(app): add the review, past situation and saved sentence screens`

---

### Task 9: 끝 화면: 지난번 대화, 눌러서 펼치기, 처음 녹음, 모아 두기

**Files:**
- Modify: `app/src/screens/EndScreen.tsx`

**Interfaces:**
- Consumes: Task 5 `api.pastRun`, `TranscriptLine.first`; Task 6 `past`, `pastLoaded`, `restarted`; Task 7 `toggleRow`, `comparePair`, `dayKo`, `useSaved`, `StarButton`, `StarMark`.

- [ ] **Step 1: 지난번 대화.** `state.past`가 있으면 `api.pastRun(state.past.group)`으로 받고 `pastLoaded`를 보낸다(`roleplay`가 올 때까지 기다림 표시). 맨 위는 상황 이름과 `dayKo(roleplay.created)`. 마무리 말은 보이지도 틀지도 않는다. 라이언 줄의 읽는 법을 미리 부르지 않는다. 아래 버튼은 「이 상황 다시 하기」(주 버튼), 「내 대사 다시 연습(n줄)」, 「라이언 대사 따라 말하기(n줄)」.
- [ ] **Step 2: 이름을 바꾼다.** 보통 끝 화면의 「같은 대본으로 처음부터」를 「이 상황 다시 하기」로. 순서는 그대로.
- [ ] **Step 3: 줄을 접고 펼친다.** 평소: 이름표, 문장, 내 줄은 시도마다 「들린 말」과 짚은 것, 모은 줄은 `StarMark`. 줄을 누르면 `toggleRow`로 한 줄만 펼친다. 라이언 줄: 「▶ 듣기」, 「통역」, 「따라 말하기 ›」, `StarButton`. 내 줄: 「▶ 내 녹음」(시도마다), 「▶ 처음 녹음」(`comparePair`가 있을 때), 「통역」, 「이 줄 다시 ›」, `StarButton`. 닫으면 그 줄의 통역(`koOpen[idx]`)도 닫는다.
- [ ] **Step 4: 처음 녹음.** 누르면 `sounds.clear()` 뒤 `first`의 녹음, 이어서 `then`의 녹음을 `api.recordingSource(rp_id, idx, n)`로 넣는다.
- [ ] **Step 5: 확인한다.** `npx tsc --noEmit`, `npx jest` PASS.
- [ ] **Step 6: Commit** `feat(app): open past conversations on the end screen and fold its lines`

---

### Task 10: 역할극 화면: 눌러서 펼치기, 지금 말할 줄의 모아 두기, 모아 둔 문장 연습

**Files:**
- Modify: `app/src/screens/RoleplayScreen.tsx`
- Modify: `app/src/ui/LineToSay.tsx` (`star?: { saved: boolean; onPress: () => void }`)

**Interfaces:**
- Consumes: Task 6 `practice.from === "saved"`, `beforeOpen`, `toggleBefore`, `restarted`; Task 7 `toggleRow`, `useSaved`, `StarButton`, `StarMark`.

- [ ] **Step 1: 지나간 말풍선을 접는다.** 라이언 말풍선: 평소 대사만(모은 줄은 `StarMark`). 누르면 「읽는 법 보기」, 「통역」, 「따라 말하기 ›」, `StarButton`. 내 말풍선: 대본을 크게, 「들린 말: …」을 작게 한 줄. 누르면 「통역」, 「이 줄 다시 ›」, `StarButton`. 한 번에 하나(`toggleRow`), 닫으면 그 줄의 `open[idx]`와 `koOpen[idx]`도 닫는다. 「따라 말하기」, 「이 줄 다시」가 눌리는 때(`canPractise`)는 그대로. 라이언이 지금 말하는 대사, 평가, 제이크 말풍선, 앞 라이언 대사는 그대로.
- [ ] **Step 2: 지금 말할 줄.** `LineToSay`의 「읽는 법 보기」, 「통역」 옆에 `StarButton`(늘 보임).
- [ ] **Step 3: 모아 둔 문장 연습.** 제목 「모아 둔 문장」, 숫자 「{at+1}/{n}」(한 줄이면 없음), 아래 줄은 상황 이름. 앞 줄(`rp.lines[line.idx - 1]`)이 있으면 「앞 대화 보기 ›」/「앞 대화 접기」(`toggleBefore`), 펼치면 작은 말풍선(누르면 그 줄 소리). 위쪽에 「이 상황 다시 하기」: `canReplay(phase)`이고 소리가 나오지 않을 때만 눌리고, 게이트로 한 번만 `api.copyRoleplay(rp.id)` 뒤 `restarted`.
- [ ] **Step 4: 확인한다.** `npx tsc --noEmit`, `npx jest` PASS.
- [ ] **Step 5: Commit** `feat(app): fold past bubbles, star the line to say and practise saved sentences`

---

### Task 11: 문서와 전체 확인

**Files:**
- Modify: `docs/guide/APP_Expo_앱_뼈대와_서버_연결_20261105.md` (구현하며 겪은 문제가 있을 때만, 「문제:」 절 양식), `docs/guide/README.md` (그때 목록 줄)
- Modify: `app/README.md` 또는 `server/README.md` (새 경로를 적는 곳이 있으면 그 목록)

- [ ] **Step 1: 전체 시험.** `cd server && uv run pytest -q`, `cd app && npx jest`, `cd app && npx tsc --noEmit`, `node --test 'scripts/**/*.test.mjs'` 모두 PASS. 통과 개수를 적어 둔다(PR 본문에 쓴다).
- [ ] **Step 2: 공개 검사.** `/usr/bin/git diff origin/main --stat`로 바뀐 파일을 보고, 시험과 계약 예시에 지난 기록의 글이 없는지 본다.
- [ ] **Step 3: 문서.** 겪은 문제가 있었으면 가이드에 쓴다. 원래 폴더(`git worktree list`의 첫 줄)의 `docs/todo/20261105_09_todo_speaking_practice_next.md` 상태 줄을 「**진행 중**(목표 8 중 주고받은 말의 처음 녹음과 지난 역할극 다시 하기는 review-practice에서 함)」으로 고친다. 커밋하지 않는 파일이다.
- [ ] **Step 4: Commit**(문서를 고쳤을 때만) `docs(guide): ...`
