# 역할극 뒤 반복 연습과 주고받은 말 보기 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 역할극 중 진행 표시와 대본·들린 말 말풍선, 끝 화면의 주고받은 말과 다시 듣기, 끝난 뒤 연습 셋(내 대사 다시, 라이언 대사 따라 말하기, 같은 대본으로 처음부터)을 만든다.

**Architecture:** 맥 서버(FastAPI)는 시도 종류 두 개(`practice`, `shadow`), 줄 응답의 진행 숫자, 끝 화면용 요약, 녹음 내주기, 역할극 복사를 더한다. 폰 앱(Expo)은 reducer에 연습 상태를 더하고, 역할극 화면을 연습에도 다시 쓰며, 끝 화면을 새로 그린다.

**Tech Stack:** 서버 Python 3 + FastAPI + pytest(`uv`), 앱 React Native + Expo SDK 58 + Jest + TypeScript. 새 의존성 없음.

**Spec:** `docs/superpowers/specs/2026-11-05-roleplay-practice-design.md` (함께 읽을 것: `docs/superpowers/specs/2026-11-05-speaking-practice-design.md`, `docs/PRD.md`)

## Global Constraints

- 이 worktree에서 git은 `/usr/bin/git`으로 부른다. `git add`는 파일을 지정한다(`-A`, `.` 금지). 커밋은 `git commit -F - <<'EOF'`, Conventional Commits 영어, scope는 `server`, `app`(둘에 걸치면 생략). AI 서명 줄을 넣지 않는다.
- 커밋 본문에 왜, 어떻게 확인했는지(명령과 결과)를 쓰고, 끝에 `Refs: docs/superpowers/specs/2026-11-05-roleplay-practice-design.md`를 단다.
- 테스트 문장은 지어낸 것만 쓴다(`REVIEW.md`, ADR-0005). 녹음, 받아쓴 실제 글, 홈 폴더 경로를 코드, 테스트, 문서에 쓰지 않는다.
- 녹음은 폰에 파일로 남기지 않는다. 녹음 경로는 토큰이 있어야 열리고, 형식 검사한 ID와 정수로만 파일을 찾는다(`REVIEW.md` 「녹음 처리」, 「맥 서버 보안」).
- 연습(`practice`, `shadow`)은 역할극의 진행 위치(`pos`)와 대본을 바꾸지 않고, 라이언의 대답(`offscript`)을 부르지 않는다.
- 서버 시험: `cd server && uv run pytest -q`. 앱 시험: `cd app && npm test && npx tsc --noEmit`. 둘 다 매 작업 끝에 통과해야 한다.
- 문서(가이드, devlog, PR 본문)는 한국어, 코드와 주석은 영어.

## Review Focus

1. **역할극 화면의 닫는 줄에서 진행 숫자:** 다르게 말한 뒤 남은 대본을 못 만들어 라이언이 인사로 끝내면, 「내 대사 n/m」의 n이 m을 넘지 않아야 한다 → Task 2 `test_progress_never_passes_total`.
2. **녹음 경로의 없는 시도와 남의 경로:** 없는 시도 번호, 없는 역할극, 형식이 틀린 ID는 404/422이고 rec 폴더를 만들지 않는다 → Task 4 `test_recording_missing_is_404_and_creates_nothing`.
3. **연습 줄에 라이언 소리가 없을 때:** 소리 만들기가 실패해 `audio`가 없는 라이언 줄도 따라 말하기에서 녹음할 수 있어야 한다(`ready`) → Task 7 `test_shadow_line_without_audio_is_ready`.
4. **다르게 말한 역할극을 복사:** 대답 줄(`kind="reply"`)과 다시 만든 줄이 그대로, 번호가 0부터 이어져야 한다 → Task 5 `test_copy_keeps_reply_lines_in_order`.
5. **말한 적 없는 줄의 요약:** 앱 오류로 건너뛴 내 줄은 `tries`가 빈 목록이어야 한다(오류가 아니다) → Task 3 `test_line_without_attempts_has_no_tries`.

---

## 파일 지도

| 파일 | 맡는 것 | 작업 |
|---|---|---|
| `server/je_server/models.py` | `Mode` 타입, `Attempt.mode` | 1 |
| `server/je_server/engine.py` | `target_line`, `attempt`의 연습 종류, `progress`, `summary`, `recording`, `copy` | 1~5 |
| `server/je_server/store.py` | `find_rec` | 4 |
| `server/je_server/app.py` | 시도 경로의 종류, 줄 응답의 `progress`, 녹음 경로, 복사 경로, `/audio`의 `engine()` 검사 | 1, 2, 4, 5 |
| `contract/summary.json` | 끝 화면 요약의 예시(서버와 앱이 함께 시험) | 3 |
| `app/src/api/types.ts`, `app/src/api/client.ts` | 새 타입과 호출 | 6 |
| `app/src/flow/state.ts` | 진행, 말풍선 대본, 연습 상태, 복사 뒤 다시 시작 | 7 |
| `app/src/screens/RoleplayScreen.tsx` | 진행 표시, 대본·들린 말 말풍선, 연습 화면 | 8 |
| `app/src/screens/EndScreen.tsx` | 주고받은 말, 다시 듣기, 연습 버튼 | 9 |

시험 파일: `server/tests/test_attempt.py`, `test_engine.py`, `test_summary.py`, `test_api.py`, `test_store.py`, `test_contract.py`, `app/src/api/client.test.ts`, `contract.test.ts`, `app/src/flow/state.test.ts`.

가짜 대본(`server/tests/fakes.py`)은 줄 7개다: 라이언 0, 2, 4, 6과 사용자 1, 3, 5. 사용자 1은 `"It's right over there."`, 라이언 0은 `"Excuse me, where is the subway station?"`.

---

### Task 1: 서버, 연습 시도 종류 (`practice`, `shadow`)

**Files:**
- Modify: `server/je_server/models.py` (`Attempt`)
- Modify: `server/je_server/engine.py` (`user_line` → `target_line`, `attempt`)
- Modify: `server/je_server/app.py` (`attempt` 경로)
- Test: `server/tests/test_attempt.py`, `server/tests/test_api.py`

**Interfaces:**
- Produces: `Mode = Literal["turn", "retry", "practice", "shadow"]` (models.py), `Attempt.mode: Mode`.
- Produces: `Engine.target_line(rp_id: str, idx: int, mode: Mode) -> ScriptLine`. `shadow`는 라이언 줄, 나머지는 사용자 줄이어야 하고, 아니면 `NotFound`.
- Produces: `POST /roleplays/{id}/lines/{idx}/attempts?mode=turn|retry|practice|shadow` (그 밖의 값은 422, 종류와 말하는 사람이 맞지 않으면 404).
- `user_line`은 지운다(부르는 곳은 `app.py`의 시도 경로와 `attempt`뿐).

- [ ] **Step 1: 실패하는 시험을 쓴다** (`server/tests/test_attempt.py` 끝에)

```python
async def test_shadow_on_ryan_line_is_evaluated_like_a_followed_line(engine_with_rp, speech_bytes, fake_whisper,
                                                                    fake_claude):
    engine, rp_id, _ = engine_with_rp
    ryan = engine.store.load(rp_id).lines[0]
    fake_whisper.text = ryan.text
    ev = await run(engine, rp_id, 0, speech_bytes, "shadow")
    assert ev[0] == {"type": "heard", "text": ryan.text, "followed": True}
    assert ev[-1] == {"type": "done", "next": 0, "issues": 0}
    assert fake_claude.feedback_calls[0]["line"] == ryan.text
    saved = engine.store.load(rp_id)
    assert saved.attempts[0][0].mode == "shadow" and saved.pos == 0


async def test_shadow_said_differently_asks_to_follow(engine_with_rp, speech_bytes, fake_whisper, fake_claude):
    engine, rp_id, _ = engine_with_rp
    before = engine.store.load(rp_id).lines
    fake_whisper.text = "I have no idea at all."
    ev = await run(engine, rp_id, 0, speech_bytes, "shadow")
    assert [e["delta"] for e in ev if e["type"] == "text"] == [engine.said("retry_offscript").text]
    assert fake_claude.offscript_calls == [] and engine.store.load(rp_id).lines == before


async def test_practice_keeps_pos_and_script(engine_with_rp, speech_bytes, fake_whisper, fake_claude):
    engine, rp_id, user_idx = engine_with_rp
    before = engine.store.load(rp_id).lines
    fake_whisper.text = "I have no idea at all."
    ev = await run(engine, rp_id, user_idx, speech_bytes, "practice")
    assert ev[-1] == {"type": "done", "next": user_idx, "issues": 0}
    assert fake_claude.offscript_calls == []
    saved = engine.store.load(rp_id)
    assert saved.lines == before and saved.pos == 0 and saved.attempts[user_idx][0].mode == "practice"


async def test_mode_must_match_the_speaker(engine_with_rp):
    from je_server.engine import NotFound

    engine, rp_id, user_idx = engine_with_rp
    with pytest.raises(NotFound):
        engine.target_line(rp_id, 0, "turn")
    with pytest.raises(NotFound):
        engine.target_line(rp_id, user_idx, "shadow")
```

`server/tests/test_api.py` 끝에:

```python
def test_attempt_route_modes(client, speech_bytes):
    rp = client.post("/roleplays", json={"situation": "길 묻기"}).json()
    client.get(f"/roleplays/{rp['id']}/lines/0")
    ok = client.post(f"/roleplays/{rp['id']}/lines/0/attempts?mode=shadow", content=speech_bytes)
    assert ok.status_code == 200 and ok.text.strip().splitlines()
    assert client.post(f"/roleplays/{rp['id']}/lines/1/attempts?mode=shadow", content=speech_bytes).status_code == 404
    assert client.post(f"/roleplays/{rp['id']}/lines/1/attempts?mode=bogus", content=speech_bytes).status_code == 422
```

(`speech_bytes`가 `test_api.py`에서 안 보이면 conftest 고정물이라 인자로 받기만 하면 된다.)

- [ ] **Step 2: 실패를 본다**

Run: `cd server && uv run pytest -q tests/test_attempt.py tests/test_api.py`
Expected: 새 시험 5개 FAIL(`target_line` 없음, `mode` 값 검증 오류, 404 대신 422 등).

- [ ] **Step 3: 구현한다**

- `models.py`: `Mode`를 정의하고 `Attempt.mode: Mode`.
- `engine.py`: `target_line`을 만들고 `attempt`가 쓴다. 다르게 말했을 때 `mode != "turn"`이면 지금의 `retry`처럼 `retry_offscript`를 말하고 대답하지 않는다. `nxt`는 `turn`만 `idx + 1`(따라 말함) 또는 `idx + 2`(다르게 말함), 나머지는 `idx`. `pos`는 지금처럼 `turn`일 때만 바꾼다.
- `app.py`: 시도 경로의 `mode` 타입을 `Mode`로, `engine().user_line(...)`을 `engine().target_line(rp_id, idx, mode)`로.

- [ ] **Step 4: 통과를 본다**

Run: `cd server && uv run pytest -q`
Expected: 모두 PASS.

- [ ] **Step 5: 커밋한다**

`feat(server): add practice and shadow attempt modes` — 본문에 연습은 `pos`, 대본, 라이언 대답을 건드리지 않는다는 것과 시험 결과.

---

### Task 2: 서버, 줄 응답의 진행 숫자

**Files:**
- Modify: `server/je_server/engine.py` (`progress`)
- Modify: `server/je_server/app.py` (`GET /roleplays/{id}/lines/{idx}`)
- Test: `server/tests/test_engine.py`, `server/tests/test_api.py`

**Interfaces:**
- Produces: `Engine.progress(rp_id: str, idx: int) -> dict[str, int]` = `{"no": n, "total": t}`. `t`는 대본의 사용자 줄 수, `n`은 `1 + (idx보다 앞에 있는 사용자 줄 수)`를 `t`로 자른 값(`t`가 0이면 0). 라이언 줄에서는 다음 내 차례의 번호가 된다.
- Produces: 줄 경로의 응답 = `ScriptLine` JSON에 `"progress": {"no", "total"}`를 더한 것. `Engine.line`이 다시 만들기를 기다린 뒤에 센다.

- [ ] **Step 1: 실패하는 시험을 쓴다** (`server/tests/test_engine.py` 끝에)

```python
async def test_progress_counts_the_learners_lines(engine):
    rp = await engine.create("길 묻기")  # lines: ryan 0, user 1, ryan 2, user 3, ryan 4, user 5, ryan 6
    assert [engine.progress(rp.id, i) for i in (0, 1, 2, 3, 5, 6)] == [
        {"no": 1, "total": 3}, {"no": 1, "total": 3}, {"no": 2, "total": 3},
        {"no": 2, "total": 3}, {"no": 3, "total": 3}, {"no": 3, "total": 3}]


async def test_progress_never_passes_total(engine, fake_claude, fake_whisper, speech_bytes):
    # a rebuild that fails closes with Ryan's goodbye: lines become ryan 0, user 1, reply 2, closing 3
    fake_claude.fail_continue = True
    rp = await engine.create("길 묻기")
    await engine.line(rp.id, 1)
    fake_whisper.text = "I have no idea at all."
    [e async for e in engine.attempt(rp.id, 1, speech_bytes, "turn")]
    await engine.line(rp.id, 3)
    assert engine.progress(rp.id, 3) == {"no": 1, "total": 1}
```

`server/tests/test_api.py`의 `test_create_roleplay_and_get_lines`에 한 줄 더한다:

```python
    assert line["progress"] == {"no": 1, "total": 3}
```

- [ ] **Step 2: 실패를 본다**

Run: `cd server && uv run pytest -q tests/test_engine.py tests/test_api.py`
Expected: 3개 FAIL(`progress` 없음, 응답에 `progress` 없음).

- [ ] **Step 3: `Engine.progress`를 만들고 줄 경로가 응답에 더한다**

- [ ] **Step 4: 통과를 본다** — `cd server && uv run pytest -q` 모두 PASS.

- [ ] **Step 5: 커밋한다** — `feat(server): send the learner's line number with each line`.

---

### Task 3: 서버, 끝 화면 요약(주고받은 말)

**Files:**
- Modify: `server/je_server/engine.py` (`summary`)
- Create: `contract/summary.json`
- Test: `server/tests/test_summary.py`, `server/tests/test_contract.py`

**Interfaces:**
- Produces: `GET /roleplays/{id}/summary` → `{"say": Said, "lines": [{"line": ScriptLine, "tries": [Try]}]}`. `retry` 목록은 없앤다(앱은 Task 9부터 `lines`를 쓴다).
- `Try` = `{"n": int, "mode": "turn" | "retry", "heard": str, "followed": bool, "issues": [{"target": str, "heard": str}], "point_ko": str}`.
  - 사용자 줄의 시도 가운데 `mode`가 `turn`, `retry`인 것만 시도 순서대로. 라이언 줄은 빈 목록.
  - `point_ko`: 다르게 말한 시도(`followed=False`)는 `say_ko`, 따라 말한 시도는 `""`.
- `say`: 사용자 줄 가운데 마지막 역할극 시도(`turn`, `retry`)에 `issues`가 있는 줄이 하나라도 있으면 `closing_retry`, 아니면 `closing_clean`. 연습 시도는 세지 않는다.
- `contract/summary.json`: 위 모양의 예시. 라이언 줄 하나(`tries: []`), 따라 말한 시도 하나(issues 하나), 다르게 말한 시도 하나(`point_ko` 있음)를 지어낸 문장으로 넣는다. `line`은 `contract/roleplay.json`의 줄과 같은 키를 쓴다.

- [ ] **Step 1: 실패하는 시험을 쓴다** (`server/tests/test_summary.py`)

기존 시험의 `retry` 단언을 바꾼다. `test_summary_lists_lines_with_issues_left`는 `s["retry"] == [user_idx]` 대신 아래 `tries(s, user_idx)[-1]["issues"]`가 비지 않았는지 본다. `test_fixed_on_retry_drops_from_summary`는 `retry`가 역할극 시도라 `closing_clean` 단언을 그대로 두고 `s["retry"] == []`만 지운다. `test_summary_route`는 `j["retry"] == []` 대신 `len(j["lines"]) == 7`을 본다. 그리고 새 시험을 더한다.

```python
def tries(s, idx):
    return next(l["tries"] for l in s["lines"] if l["line"]["idx"] == idx)


async def test_summary_shows_roleplay_tries_not_practice(engine_with_rp, speech_bytes, fake_whisper):
    engine, rp_id, user_idx = engine_with_rp
    fake_whisper.text = "It's light over there."
    await run(engine, rp_id, user_idx, speech_bytes)
    fake_whisper.text = "It's right over there."
    await run(engine, rp_id, user_idx, speech_bytes, "practice")
    s = engine.summary(rp_id)
    assert tries(s, user_idx) == [{"n": 1, "mode": "turn", "heard": "It's light over there.", "followed": True,
                                   "issues": [{"target": "right", "heard": "light"}], "point_ko": ""}]
    assert s["say"] == engine.said("closing_retry").model_dump()  # the practice fix does not count
    assert [l["line"]["idx"] for l in s["lines"]] == list(range(7)) and tries(s, 0) == []


async def test_offscript_try_carries_ryans_point(engine_with_rp, speech_bytes, fake_whisper, fake_claude):
    engine, rp_id, user_idx = engine_with_rp
    fake_whisper.text = "I have no idea at all."
    await run(engine, rp_id, user_idx, speech_bytes)
    [t] = tries(engine.summary(rp_id), user_idx)
    assert t["followed"] is False and t["issues"] == [] and t["point_ko"] == fake_claude.offscript_out.point_ko


async def test_line_without_attempts_has_no_tries(engine_with_rp):
    engine, rp_id, user_idx = engine_with_rp
    assert tries(engine.summary(rp_id), user_idx) == []
```

`server/tests/test_contract.py` 끝에:

```python
def test_summary_example_has_the_engine_shape():
    raw = json.loads((CONTRACT / "summary.json").read_text(encoding="utf-8"))
    assert set(raw) == {"say", "lines"}
    for l in raw["lines"]:
        assert set(l) == {"line", "tries"} and ScriptLine.model_validate(l["line"]).model_dump(mode="json") == l["line"]
        for t in l["tries"]:
            assert set(t) == {"n", "mode", "heard", "followed", "issues", "point_ko"}
            assert all(set(i) == {"target", "heard"} for i in t["issues"])
```

- [ ] **Step 2: 실패를 본다** — `cd server && uv run pytest -q tests/test_summary.py tests/test_contract.py`, 새 시험 FAIL.

- [ ] **Step 3: `Engine.summary`를 새 모양으로 바꾸고 `contract/summary.json`을 쓴다**

- [ ] **Step 4: 통과를 본다** — `cd server && uv run pytest -q` 모두 PASS.

- [ ] **Step 5: 커밋한다** — `feat(server): return the conversation with roleplay tries in the summary`.

---

### Task 4: 서버, 녹음 내주기 경로

**Files:**
- Modify: `server/je_server/store.py` (`find_rec`)
- Modify: `server/je_server/engine.py` (`recording`)
- Modify: `server/je_server/app.py` (녹음 경로, `/audio`의 `engine()` 검사)
- Test: `server/tests/test_store.py`, `server/tests/test_api.py`

**Interfaces:**
- Produces: `Store.find_rec(rp_id: str, idx: int, n: int) -> Path | None`. 폴더를 만들지 않는다. ID가 틀리면 `None`.
- Produces: `Engine.recording(rp_id: str, idx: int, n: int) -> Path`, 없으면 `NotFound`.
- Produces: `GET /roleplays/{rp_id}/lines/{idx}/attempts/{n}/recording` (`rp_id`는 `ID` 패턴, `idx >= 0`, `n >= 1`) → `FileResponse(..., media_type="audio/mp4")`. 토큰이 필요하다(라우터에 둔다).
- `/audio/{key}`: `services.voice`를 바로 쓰지 말고 `engine().voice`를 쓴다(`docs/todo/20261105_11_todo_roleplay_mvp_review_minors.md` 4번). 서비스 없이 띄우면 503 `not_ready`.

- [ ] **Step 1: 실패하는 시험을 쓴다**

`server/tests/test_store.py`:

```python
def test_find_rec_does_not_create_folders(tmp_path):
    s = Store(tmp_path)
    r = rp(s)
    s.save(r)
    assert s.find_rec(r.id, 1, 1) is None and not (s.roleplays / r.id / "rec").exists()
    assert s.find_rec("../etc", 1, 1) is None
    s.rec_path(r.id, 1, 1).write_bytes(b"m4a")
    assert s.find_rec(r.id, 1, 1).read_bytes() == b"m4a"
```

`server/tests/test_api.py`:

```python
def test_recording_is_served_after_an_attempt(client, speech_bytes):
    rp = client.post("/roleplays", json={"situation": "길 묻기"}).json()
    client.get(f"/roleplays/{rp['id']}/lines/1")
    client.post(f"/roleplays/{rp['id']}/lines/1/attempts?mode=turn", content=speech_bytes)
    r = client.get(f"/roleplays/{rp['id']}/lines/1/attempts/1/recording")
    assert r.status_code == 200 and r.headers["content-type"] == "audio/mp4" and r.content == speech_bytes


def test_recording_missing_is_404_and_creates_nothing(client, settings):
    rp = client.post("/roleplays", json={"situation": "길 묻기"}).json()
    assert client.get(f"/roleplays/{rp['id']}/lines/1/attempts/9/recording").status_code == 404
    assert client.get("/roleplays/000000000000/lines/1/attempts/1/recording").status_code == 404
    assert client.get(f"/roleplays/{rp['id']}/lines/1/attempts/0/recording").status_code == 422
    assert client.get("/roleplays/..%2Fx/lines/1/attempts/1/recording").status_code in (404, 422)
    assert not (settings.data_dir / "roleplays" / rp["id"] / "rec").exists()


def test_recording_needs_token(settings, engine, fake_voice, fake_whisper):
    from fastapi.testclient import TestClient

    from je_server.app import Services, create_app

    c = TestClient(create_app(settings, Services(engine=engine, voice=fake_voice, whisper=fake_whisper)))
    assert c.get("/roleplays/000000000000/lines/1/attempts/1/recording").status_code == 401


def test_audio_without_services_is_not_ready(settings, auth):
    from fastapi.testclient import TestClient

    from je_server.app import create_app

    c = TestClient(create_app(settings, None), headers=auth)
    r = c.get("/audio/" + "a" * 64)
    assert r.status_code == 503 and r.json()["code"] == "not_ready"
```

- [ ] **Step 2: 실패를 본다** — `cd server && uv run pytest -q tests/test_store.py tests/test_api.py`, 새 시험 FAIL.

- [ ] **Step 3: 구현한다** — `find_rec`는 `_dir`의 `KeyError`를 `None`으로 바꾸고 `is_file()`인 경로만 돌려준다. `/audio`와 녹음 경로 모두 `engine()`을 거친다.

- [ ] **Step 4: 통과를 본다** — `cd server && uv run pytest -q` 모두 PASS.

- [ ] **Step 5: 커밋한다** — `feat(server): serve a learner's recording to the app for replay`. 본문에 녹음은 폰에 저장하지 않고 받아 틀기만 한다는 것, minors todo 4번을 함께 고친 것.

---

### Task 5: 서버, 같은 대본으로 새 역할극 만들기

**Files:**
- Modify: `server/je_server/engine.py` (`copy`)
- Modify: `server/je_server/app.py` (`POST /roleplays/{rp_id}/copy`)
- Test: `server/tests/test_engine.py`, `server/tests/test_api.py`

**Interfaces:**
- Produces: `Engine.copy(rp_id: str) -> Roleplay`. 다시 만들기가 도는 중이면 `line()`처럼 기다린다. 새 ID, 지금 시각, 같은 `situation`, `frame`, `lines`(세 줄과 소리 키까지), `attempts={}`, `pos=0`. 저장하고, 준비가 덜 된 줄(`ready()`가 아닌 줄)만 `schedule`한다.
- Produces: `POST /roleplays/{rp_id}/copy` → 새 `Roleplay` JSON. 없는 ID는 404.

- [ ] **Step 1: 실패하는 시험을 쓴다** (`server/tests/test_engine.py`)

```python
async def test_copy_starts_fresh_with_the_same_script(engine_with_rp, speech_bytes, fake_claude):
    engine, rp_id, user_idx = engine_with_rp
    for i in range(7):  # let background preparation finish, so the record stops changing
        await engine.line(rp_id, i)
    [e async for e in engine.attempt(rp_id, user_idx, speech_bytes, "turn")]
    old = engine.store.load(rp_id)
    calls = len(fake_claude.calls)
    new = await engine.copy(rp_id)
    assert new.id != rp_id and new.lines == old.lines and new.attempts == {} and new.pos == 0
    assert new.situation == old.situation and new.frame == old.frame
    assert engine.store.load(rp_id) == old  # the old record is untouched
    assert ("make_script", (old.situation,)) not in fake_claude.calls[calls:]


async def test_copy_keeps_reply_lines_in_order(engine_with_rp, speech_bytes, fake_whisper):
    engine, rp_id, user_idx = engine_with_rp
    fake_whisper.text = "I have no idea at all."
    [e async for e in engine.attempt(rp_id, user_idx, speech_bytes, "turn")]
    new = await engine.copy(rp_id)  # waits for the rebuild
    assert [l.idx for l in new.lines] == list(range(len(new.lines)))
    assert new.lines[user_idx + 1].kind == "reply"
    # text only: background preparation may still add notes and sounds to either record
    shape = lambda lines: [(l.idx, l.speaker, l.text, l.kind) for l in lines]  # noqa: E731
    assert shape(new.lines) == shape(engine.store.load(rp_id).lines)
```

`server/tests/test_api.py`:

```python
def test_copy_route(client):
    rp = client.post("/roleplays", json={"situation": "길 묻기"}).json()
    new = client.post(f"/roleplays/{rp['id']}/copy").json()
    assert new["id"] != rp["id"] and [l["text"] for l in new["lines"]] == [l["text"] for l in rp["lines"]]
    assert client.post("/roleplays/000000000000/copy").status_code == 404
```

- [ ] **Step 2: 실패를 본다** — `cd server && uv run pytest -q tests/test_engine.py tests/test_api.py`, 새 시험 FAIL.

- [ ] **Step 3: 구현한다**

- [ ] **Step 4: 통과를 본다** — `cd server && uv run pytest -q` 모두 PASS.

- [ ] **Step 5: 커밋한다** — `feat(server): copy a roleplay to play the same script again`.

---

### Task 6: 앱, API 타입과 호출

**Files:**
- Modify: `app/src/api/types.ts`, `app/src/api/client.ts`
- Test: `app/src/api/client.test.ts`, `app/src/api/contract.test.ts`

**Interfaces:**
- Produces (types.ts):
  - `AttemptMode = "turn" | "retry" | "practice" | "shadow"`, `Attempt.mode: AttemptMode`.
  - `Progress = { no: number; total: number }`, `LineWithProgress = ScriptLine & { progress: Progress }`.
  - `Try = { n: number; mode: "turn" | "retry"; heard: string; followed: boolean; issues: { target: string; heard: string }[]; point_ko: string }`.
  - `TranscriptLine = { line: ScriptLine; tries: Try[] }`, `Summary = { say: Said; lines: TranscriptLine[] }`(옛 `retry`는 없앤다).
  - `SUMMARY_KEYS = ["say", "lines"]`, `TRY_KEYS = ["n", "mode", "heard", "followed", "issues", "point_ko"]`와 `KEYS_MATCH`에 맞춘 `Same` 검사 두 개.
- Produces (client.ts):
  - `getLine(id, idx): Promise<LineWithProgress>`.
  - `attempt(id, idx, fileUri, mode: AttemptMode, onEvent)`.
  - `copyRoleplay(id: string): Promise<Roleplay>` → `POST /roleplays/{id}/copy`(LONG 시간 제한).
  - `recordingSource(id: string, idx: number, n: number): { uri: string; headers: { Authorization: string } }` → `${base}/roleplays/${id}/lines/${idx}/attempts/${n}/recording`.

- [ ] **Step 1: 실패하는 시험을 쓴다**

`app/src/api/client.test.ts`:

```ts
test("copy posts to the roleplay's copy route", async () => {
  const f = jest.fn(async () => json(200, { id: "b".repeat(12) }));
  await makeApi(URL, TOKEN, f as never, noFile).copyRoleplay("a".repeat(12));
  const [url, init] = f.mock.calls[0] as unknown as [string, RequestInit];
  expect(url).toBe(`${URL}/roleplays/${"a".repeat(12)}/copy`);
  expect(init.method).toBe("POST");
});

test("recording source carries the token and the attempt number", () => {
  const src = makeApi(URL, TOKEN, jest.fn() as never, noFile).recordingSource("a".repeat(12), 3, 2);
  expect(src).toEqual({
    uri: `${URL}/roleplays/${"a".repeat(12)}/lines/3/attempts/2/recording`,
    headers: { Authorization: `Bearer ${TOKEN}` },
  });
});

test("attempt sends the shadow mode", async () => {
  const f = jest.fn(async () => streamOf(['{"type":"done","next":0,"issues":0}\n']));
  await makeApi(URL, TOKEN, f as never, noFile).attempt("a".repeat(12), 0, "file://x.m4a", "shadow", () => {});
  expect((f.mock.calls[0] as unknown as [string])[0]).toBe(`${URL}/roleplays/${"a".repeat(12)}/lines/0/attempts?mode=shadow`);
});
```

`app/src/api/contract.test.ts`:

```ts
import summary from "../../../contract/summary.json";
// …
test("summary example has the keys the end screen reads", () => {
  expect(sorted(Object.keys(summary))).toEqual(sorted(SUMMARY_KEYS));
  for (const l of summary.lines) {
    expect(sorted(Object.keys(l.line))).toEqual(sorted(LINE_KEYS));
    for (const t of l.tries) expect(sorted(Object.keys(t))).toEqual(sorted(TRY_KEYS));
  }
});
```

- [ ] **Step 2: 실패를 본다** — `cd app && npm test`, 새 시험 FAIL. `npx tsc --noEmit`도 오류.

- [ ] **Step 3: 타입과 호출을 더한다.** `EndScreen.tsx`가 옛 `summary.retry`를 써서 타입 오류가 나면, 이 작업에서는 `summary.lines`에서 짚은 것이 남은 내 줄을 골라 같은 버튼을 그리게 최소한으로 고친다(화면은 Task 9에서 다시 쓴다). `retryFromEnd`는 Task 7까지 남는다.

- [ ] **Step 4: 통과를 본다** — `cd app && npm test && npx tsc --noEmit` 모두 통과.

- [ ] **Step 5: 커밋한다** — `feat(app): add API calls for practice, replay and copy`.

---

### Task 7: 앱, 화면 흐름(reducer)

**Files:**
- Modify: `app/src/flow/state.ts`
- Test: `app/src/flow/state.test.ts`

**Interfaces:**
- Consumes: Task 6의 `AttemptMode`, `Progress`.
- Produces (state.ts):
  - `State.mode: AttemptMode`, `State.progress: Progress | null`, `State.practice: Practice | null`(`Practice = { kind: "mine" | "shadow"; order: number[]; at: number }`), `State.closingPlayed: boolean`. `returnToEnd`는 없앤다(`practice !== null`이 대신한다).
  - `Bubble = { kind: "ryan" | "user" | "feedback"; text: string; idx?: number; script?: string }`. 사용자 말풍선의 `script`는 그 차례의 대사(`s.line.text`).
  - Actions: `{ type: "lineLoaded"; line: ScriptLine; progress?: Progress }`, `{ type: "startPractice"; kind: "mine" | "shadow"; order: number[] }`(옛 `retryFromEnd`를 대신한다), `{ type: "restarted"; roleplay: Roleplay }`, `{ type: "closingPlayed" }`.
- 규칙:
  - `lineLoaded`: 라이언 줄이고 `mode !== "shadow"`이면 `ryan`, 아니면 `ready`. `progress`가 오면 담는다.
  - `startPractice`: 끝 화면에서만, `order`가 비지 않았을 때만. `screen="roleplay"`, `mode`는 `shadow` 또는 `practice`, `idx=order[0]`, `practice={kind, order, at: 0}`, `history=[]`, `line=null`, `phase="loading"`, `progress=null`.
  - 연습 중 `again`: 말풍선을 쌓고 `ready`로, `mode`는 그대로.
  - 연습 중 `next`: 다음 줄이 있으면 `at+1`, `idx=order[at+1]`, `history=[]`, `phase="loading"`. 마지막이면 `screen="end"`, `practice=null`, `mode="turn"`.
  - 연습 중 `back`: `screen="end"`, `practice=null`, `mode="turn"`.
  - `restarted`: 끝 화면에서만. `{ ...initial, screen: "roleplay", roleplay, jake: s.jake, phase: "loading" }`.
  - `closingPlayed`: `closingPlayed=true`. `created`, `restarted`, `home`은 `initial`에서 `false`.

- [ ] **Step 1: 실패하는 시험을 쓴다** (`app/src/flow/state.test.ts`). 옛 `retryFromEnd`, `returnToEnd` 시험은 `startPractice`로 바꾼다.

```ts
const end = (extra: Partial<State> = {}): State => ({ ...at("evaluated"), screen: "end", ...extra });

test("line progress is kept for the header", () => {
  const s = reduce(reduce(situation, { type: "created", roleplay: rp }), {
    type: "lineLoaded", line: ryanLine, progress: { no: 1, total: 3 } });
  expect(s.progress).toEqual({ no: 1, total: 3 });
});

test("the learner's bubble keeps the script line and what was heard", () => {
  let s = at("evaluating");
  s = reduce(s, { type: "event", e: { type: "heard", text: "I like a cup of copy", followed: true } });
  s = reduce(s, { type: "event", e: { type: "done", next: 2, issues: 0 } });
  s = reduce(s, { type: "next" });
  expect(s.history[0]).toEqual({ kind: "user", text: "I like a cup of copy", script: userLine.text });
});

test("practice of my lines goes through the order and back to the end", () => {
  let s = reduce(end(), { type: "startPractice", kind: "mine", order: [1, 3] });
  expect([s.screen, s.mode, s.idx, s.phase, s.history]).toEqual(["roleplay", "practice", 1, "loading", []]);
  s = reduce(reduce(s, { type: "lineLoaded", line: userLine }), { type: "recordStart" });
  s = reduce(reduce(s, { type: "recordStop" }), { type: "event", e: { type: "done", next: 1, issues: 0 } });
  s = reduce(s, { type: "again" });
  expect([s.mode, s.phase]).toEqual(["practice", "ready"]);
  s = { ...s, phase: "evaluated" };
  s = reduce(s, { type: "next" });
  expect([s.idx, s.practice?.at, s.history]).toEqual([3, 1, []]);
  s = reduce({ ...s, phase: "evaluated" }, { type: "next" });
  expect([s.screen, s.practice, s.mode]).toEqual(["end", null, "turn"]);
});

test("back from practice returns to the end screen", () => {
  const s = reduce(reduce(end(), { type: "startPractice", kind: "shadow", order: [0, 2] }), { type: "back" });
  expect([s.screen, s.practice, s.mode]).toEqual(["end", null, "turn"]);
});

test("a Ryan line in shadow practice is the learner's to say", () => {
  const s = reduce(reduce(end(), { type: "startPractice", kind: "shadow", order: [0] }), { type: "lineLoaded", line: ryanLine });
  expect([s.mode, s.phase]).toEqual(["shadow", "ready"]);
});

test("shadow line without audio is ready", () => {
  const s = reduce(reduce(end(), { type: "startPractice", kind: "shadow", order: [0] }), {
    type: "lineLoaded", line: { ...ryanLine, audio: null } });
  expect(s.phase).toBe("ready");
});

test("practice starts only from the end screen with lines", () => {
  const s = at("ready");
  expect(reduce(s, { type: "startPractice", kind: "mine", order: [1] })).toBe(s);
  const e = end();
  expect(reduce(e, { type: "startPractice", kind: "mine", order: [] })).toBe(e);
});

test("restarted opens the copied roleplay and keeps Jake's line", () => {
  const jake = { text: "카페에서 주문하는 상황으로 연습해 보면 어때요?", audio: "a".repeat(64) };
  const copy = { ...rp, id: "b".repeat(12) };
  const s = reduce(end({ jake, closingPlayed: true }), { type: "restarted", roleplay: copy });
  expect([s.screen, s.roleplay?.id, s.jake, s.idx, s.closingPlayed]).toEqual(["roleplay", copy.id, jake, 0, false]);
  const playing = at("ready");
  expect(reduce(playing, { type: "restarted", roleplay: copy })).toBe(playing); // only from the end screen
});

test("closing is marked as played", () => {
  expect(reduce(end(), { type: "closingPlayed" }).closingPlayed).toBe(true);
});
```

- [ ] **Step 2: 실패를 본다** — `cd app && npm test`, 새 시험 FAIL.

- [ ] **Step 3: reducer를 바꾼다.** `RoleplayScreen.tsx`, `EndScreen.tsx`의 `returnToEnd`, `retryFromEnd`는 같은 동작의 새 이름(`practice`, `startPractice`)으로 바꿔 타입 오류만 없앤다(화면은 Task 8, 9).

- [ ] **Step 4: 통과를 본다** — `cd app && npm test && npx tsc --noEmit`.

- [ ] **Step 5: 커밋한다** — `feat(app): add practice, progress and restart to the screen flow`.

---

### Task 8: 앱, 역할극 화면(진행 표시, 말풍선, 연습)

**Files:**
- Modify: `app/src/screens/RoleplayScreen.tsx`

**Interfaces:**
- Consumes: Task 6 `api.getLine`(진행 숫자), `api.attempt(…, state.mode, …)`, `api.getThree`. Task 7 `State.progress`, `State.practice`, `Bubble.script`.

- [ ] **Step 1: 화면을 바꾼다** (스펙 1, 2, 4, 5)
  - 머리: 연습이 아니면 제목 옆에 `내 대사 {no}/{total}`(`progress`가 있을 때). 연습이면 제목을 「내 대사 다시 연습」 또는 「라이언 대사 따라 말하기」로, 옆에 `{at+1}/{order.length}`.
  - 사용자 말풍선: `script`가 있으면 「대본」 줄과 「들린 말」 줄 두 줄.
  - `getLine` 결과의 `progress`를 `lineLoaded`에 넘긴다.
  - 내 차례 조건에 `mode === "shadow"`인 라이언 줄을 넣는다. 따라 말하기의 줄은 영어 대사를 크게 보여 주고, 세 줄은 `line.three`가 없으면 `api.getThree`로 받아 보여 준다(받는 동안 「세 줄을 만들고 있어요」). 녹음 버튼 글은 「🎤 따라 말하기」.
  - 내 대사 다시 연습: `state.seen[idx - 1]`이 라이언 줄이면 그 대사를 작은 글씨로 위에 보여 주고, 누르면 그 소리를 튼다.
  - 연습 중에는 쌓인 대화 대신 지금 줄만 보인다(`history`는 연습 줄마다 비워진다).
  - 「뒤로」와 폰 뒤로가기: 연습 중이면 묻지 않고 떠난다(옛 `returnToEnd` 자리).
- [ ] **Step 2: 확인한다** — `cd app && npm test && npx tsc --noEmit` 통과. 화면은 Task 10에서 폰으로 본다.
- [ ] **Step 3: 커밋한다** — `feat(app): show progress, script lines and practice on the roleplay screen`.

---

### Task 9: 앱, 끝 화면(주고받은 말, 다시 듣기, 연습 버튼)

**Files:**
- Modify: `app/src/screens/EndScreen.tsx`

**Interfaces:**
- Consumes: Task 6 `api.summary`, `api.recordingSource`, `api.audioSource`, `api.copyRoleplay`, `api.getThree`. Task 7 `startPractice`, `restarted`, `closingPlayed`.

- [ ] **Step 1: 화면을 다시 쓴다** (스펙 3, 6)
  - 맨 위: 뒤로, 역할극 제목, 마무리 말 글. 마무리 말 소리는 `state.closingPlayed`가 아닐 때만 틀고 `closingPlayed`를 보낸다(연습에서 돌아올 때 다시 말하지 않는다).
  - 요약을 받으면 `line.three`가 없는 라이언 줄마다 `api.getThree`를 뒤에서 부른다(결과는 쓰지 않는다, 실패는 무시).
  - 주고받은 말(스크롤): 라이언 줄은 대사와 「▶」(`line.audio`가 있을 때). 내 줄은 대본, 시도마다 「들린 말: …」, 「▶ 내 녹음」(`recordingSource(id, line.idx, try.n)`), 짚은 것(`issues`는 「「right」 → 「light」처럼 들렸어요」 꼴로 하나씩, `point_ko`는 그대로), 그리고 「이 줄 다시」(`startPractice mine [line.idx]`).
  - 아래 고정: 「내 대사 다시 연습(n줄)」(사용자 줄 번호들), 「라이언 대사 따라 말하기(n줄)」(라이언 줄 번호들), 「같은 대본으로 처음부터」(`copyRoleplay` → `restarted`, 기다리는 동안 버튼을 막아 두 번 누르기를 막고, 실패하면 오류 글), 「처음으로」.
  - 어떤 버튼이든 누르면 먼저 `sounds.clear()`.
- [ ] **Step 2: 확인한다** — `cd app && npm test && npx tsc --noEmit` 통과.
- [ ] **Step 3: 커밋한다** — `feat(app): show the conversation and practice buttons on the end screen`.

---

### Task 10: 폰에서 확인하고 마무리

- [ ] **Step 1: 서버를 이 worktree에서 다시 띄운다.** 끄기 전에 사용자에게 알린다(다른 카드도 서버를 쓴다). 로그 `~/Library/Logs/jake-english/server.log`에서 `ready`를 본다.
- [ ] **Step 2: APK를 빌드해 깐다** — `app/README.md`대로(`JAVA_HOME`은 JDK 17, `ANDROID_HOME`은 SDK, `-PreactNativeArchitectures=arm64-v8a`), `adb install -r`.
- [ ] **Step 3: 사용자와 폰에서 본다** (PR 본문의 테스트 체크리스트로 옮긴다)
  - 역할극 중 「내 대사 n/m」, 지나간 내 말풍선의 대본과 들린 말.
  - 끝 화면: 주고받은 말, 라이언 ▶, 내 녹음 ▶, 「이 줄 다시」.
  - 내 대사 다시 연습, 라이언 대사 따라 말하기(세 줄 표시, 빠르기, 평가), 같은 대본으로 처음부터(바로 시작, 제이크 말풍선).
  - 마무리 말 소리가 연습에서 돌아올 때 다시 나오지 않는지, 버튼을 두 번 눌러도 역할극이 둘 생기지 않는지.
  - 이 PR에 먼저 들어간 것: 라이언 사진(첫 화면, 상황 화면), 말 빠르기, 문장 안 쉼과 끝소리, 제이크 추천과 첫 인사.
- [ ] **Step 4: 마무리는 `AGENTS.md`대로 한다** — PR(본문 한국어, 「한계」에 평가 고치기 카드와 6의 어긋남), pr-review, 고친 뒤 devlog. 끝내는 커밋에 `docs/todo/20261105_10_todo_roleplay_practice_and_transcript.md` 상태를 완료로, `docs/todo/20261105_11_todo_roleplay_mvp_review_minors.md`에 4번을 고친 것을 적는다(두 파일은 원래 폴더에 untracked로 있다. worktree로 옮겨 커밋한다).
