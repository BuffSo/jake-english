# 라이언의 섀도잉 한마디 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 그날 처음 앱을 켰을 때, 첫 화면에서 라이언이 인사 다음, 질문 앞에 섀도잉 한마디를 글과 목소리로 한다. 말 다섯을 차례로 돌린다.

**Architecture:** 말은 `server/je_server/phrases.py`의 `TIPS`이고, 서버가 켜질 때 정해진 말처럼 라이언 목소리로 미리 만든다. `/home?tip=1`로 물은 요청에만 맥이 「오늘 아직 말하지 않았으면」 다음 차례의 말을 `tip`으로 붙이고, 날짜와 차례를 기록 폴더의 `tip.json`에 쓴다. 앱은 `/home?tip=1`로 묻고, `homeLines`가 인사, 한마디, 질문 차례로 늘어놓는다.

**Tech Stack:** Python 3 + FastAPI(서버, `cd server && uv run pytest -q`), React Native + Expo + jest(앱, `cd app && npx jest && npx tsc --noEmit`). 새 꾸러미 없음.

**Spec:** `docs/superpowers/specs/2026-11-08-ryan-shadowing-tip-design.md`

**실행 방식:** 이 세션이 직접 한다(executing-plans). 서버, 앱, 확인 셋이 작고 서로의 이름을 이어 쓴다. 같은 PR의 버튼 계획(`docs/superpowers/plans/2026-11-08-button-colors.md`)과 함께 끝에 새 리뷰어 한 명이 브랜치 전체를 보고, PR을 열면 pr-review로 본다.

## Global Constraints

- 말(그대로 쓴다, 이 차례로):
  1. 섀도잉은 소리 내서 여러 번 해야 입에 붙어요.
  2. 섀도잉을 하면 듣기도 늘어요. 내가 낼 수 있는 소리는 귀에도 잘 들리거든요.
  3. 섀도잉은 따라 한 내 소리를 다시 들어 볼 때 더 늘어요.
  4. 같은 문장을 섀도잉으로 여러 번 말하다 보면, 실제로 말할 때 자신감이 붙어요.
  5. 섀도잉하기 전에, 어디를 세게 읽고 어디를 이어 읽는지 잘 들어 보세요.
- 차례: 인사(`greeting`) → 한마디 → 질문(`ask_mode`). 첫 화면에 돌아올 때는 `ask_again`만(한마디 없음).
- 「그날」은 맥의 날짜(`date.today()`). 다 돌면 1로.
- 한마디는 `/home`의 `lines`가 아니라 따로 `tip`. 앱이 `tip=1`로 묻지 않은 `/home`은 지금처럼 답하고 아무것도 쓰지 않는다.
- 옛 서버(`tip` 없음)와 옛 앱(`tip=1`을 묻지 않음) 어느 쪽과 붙어도 지금처럼 동작한다.
- 화면에 보이는 한국어는 `keepWords`를 거친다(첫 화면의 다른 라이언 말과 같은 자리, 같은 모양).
- 시험 서버는 `JE_HOST=127.0.0.1`, `JE_PORT=8793`, `JE_WHISPER_PORT=8794`, 기록은 복사본(녹음 `rec/`와 `tmp/` 빼고)이다. 원래 폴더 서버(launchd)는 멈추지 않는다.
- 커밋 메시지는 영어 Conventional Commits, 본문에 이유와 시험 결과, 끝에 `Refs: docs/superpowers/specs/2026-11-08-ryan-shadowing-tip-design.md`. AI 서명 줄 없음. git은 `/usr/bin/git`.

## Review Focus

1. **같은 날 두 번 말한다:** 서버를 다시 켜도(새 `Engine`) 같은 날이면 말하지 않는다. → Task 1 시험 `test_tip_once_a_day_even_after_a_restart`.
2. **`curl /home`이 그날 한마디를 쓴다:** → Task 1 시험 `test_home_without_asking_neither_gives_nor_uses_the_tip`.
3. **기록 파일이 깨지면 첫 화면이 멈춘다:** 읽을 수 없으면 첫 말부터, 오늘 아직 말하지 않은 것으로. → Task 1 시험 `test_unreadable_tip_file_starts_over`.
4. **두 요청이 동시에 와서 같은 날 두 번 준다:** `/home`은 스레드에서 돈다. 날짜를 보고 쓰는 것을 잠금 하나로 묶는다. → Task 1 Step 3(잠금), 시험 `test_tip_once_a_day_even_after_a_restart`가 차례를 본다.
5. **새 앱이 옛 서버에 붙는다:** `tip`이 없으면 인사와 질문만. → Task 2 시험 `an older server without a tip greets and asks as before`.

---

### Task 1: 맥 서버의 한마디

**Files:**
- Modify: `server/je_server/phrases.py`(`TIPS`), `server/je_server/store.py`(`load_tip`, `save_tip`), `server/je_server/engine.py`(`home_tip`, `warm`), `server/je_server/app.py`(`/home`의 `tip` 질의)
- Test: `server/tests/test_phrases.py`, `server/tests/test_engine.py`, `server/tests/test_api.py`

**Interfaces:**
- Produces: `TIPS: tuple[str, ...]`(Global Constraints의 다섯). `Store.load_tip() -> tuple[str | None, int]`(그날, 다음 차례). `Store.save_tip(day: str, next_: int) -> None`(`tip.json`, `{"day": "YYYY-MM-DD", "next": n}`). `Engine.home_tip(day: date | None = None) -> Said | None`. `GET /home?tip=1` → 응답에 `"tip": {"text", "audio"}`(그날 처음일 때만).

- [ ] **Step 1: 실패하는 시험을 쓴다**

`server/tests/test_phrases.py`:

```python
def test_tips_say_shadowing_and_are_not_fixed_lines():
    # spec ryan-shadowing-tip 1: each line has the word, five in this order, apart from the always-same lines
    from je_server.phrases import TIPS
    assert len(TIPS) == 5 and all("섀도잉" in t for t in TIPS)
    assert TIPS[4] == "섀도잉하기 전에, 어디를 세게 읽고 어디를 이어 읽는지 잘 들어 보세요."
    assert not set(TIPS) & set(PHRASES.values())
```

`server/tests/test_engine.py` (`from datetime import date`, `from je_server.phrases import TIPS`):

```python
def test_tip_comes_once_a_day_in_turn(engine):
    d1, d2 = date(2026, 11, 8), date(2026, 11, 9)
    assert engine.home_tip(d1).text == TIPS[0]
    assert engine.home_tip(d1) is None
    assert engine.home_tip(d2).text == TIPS[1]

def test_tip_wraps_after_the_last(engine):
    texts = [engine.home_tip(date(2026, 11, d)).text for d in range(1, 7)]
    assert texts == [*TIPS, TIPS[0]]

def test_tip_once_a_day_even_after_a_restart(engine_factory):
    day = date(2026, 11, 8)
    assert engine_factory().home_tip(day).text == TIPS[0]
    assert engine_factory().home_tip(day) is None
    assert engine_factory().home_tip(date(2026, 11, 9)).text == TIPS[1]

def test_unreadable_tip_file_starts_over(engine, tmp_path):
    (tmp_path / "data" / "tip.json").write_text("{not json", encoding="utf-8")
    assert engine.home_tip(date(2026, 11, 8)).text == TIPS[0]

def test_tip_is_ryans_korean_sound(engine, fake_voice):
    said = engine.home_tip(date(2026, 11, 8))
    assert said.audio == fake_voice.key("ryan", "korean", TIPS[0])

async def test_tips_are_made_ahead_and_checked(engine, fake_voice):
    await engine.warm()
    assert set(TIPS) <= set(fake_voice.checked)
```

`server/tests/test_api.py`:

```python
def test_home_without_asking_neither_gives_nor_uses_the_tip(client):
    # spec ryan-shadowing-tip 4: a card's `curl /home` must not use up the day's line
    assert "tip" not in client.get("/home").json()
    assert client.get("/home", params={"tip": 1}).json()["tip"]["text"] == TIPS[0]

def test_home_gives_the_tip_once_when_asked(client):
    first = client.get("/home", params={"tip": 1}).json()
    assert first["tip"]["text"] == TIPS[0] and len(first["tip"]["audio"]) == 64
    assert "tip" not in client.get("/home", params={"tip": 1}).json()
    assert "tip" not in first["lines"]
```

- [ ] **Step 2: 실패를 본다**

Run: `cd server && uv run pytest -q tests/test_phrases.py tests/test_engine.py tests/test_api.py`
Expected: FAIL, `ImportError: cannot import name 'TIPS'`

- [ ] **Step 3: 구현한다**

- `phrases.py`: `TIPS`(Global Constraints 그대로)와 주석(spec 경로, 「섀도잉」, 문구 기준 한 줄).
- `store.py`: `load_tip`은 파일이 없거나 읽을 수 없거나 모양이 틀리면 `(None, 0)`(깨진 것은 경고 한 줄, 글은 남기지 않음). `save_tip`은 `_write`로 통째로.
- `engine.py`: `__init__`에 `self.tip_lock = threading.Lock()`. `home_tip(day=None)`은 잠금 안에서 `load_tip` → 그날이면 `None`, 아니면 `TIPS[next % len(TIPS)]`를 고르고 `save_tip(day.isoformat(), next + 1)` → `Said`. `Said` 만들기는 `said(name)`과 같은 `self.voice.key("ryan", "korean", text)`를 쓰는 작은 도우미로 묶는다. `warm`은 `[*PHRASES.values(), *TIPS]`.
- `app.py`: `home(tip: bool = Query(False))`. `tip`이고 `e.home_tip()`이 있으면 응답에 `"tip"`을 더한다.

- [ ] **Step 4: 서버 시험을 모두 돌린다**

Run: `cd server && uv run pytest -q`
Expected: 모두 통과(새 시험 9개 포함)

- [ ] **Step 5: 커밋한다**

```bash
/usr/bin/git add server/je_server/phrases.py server/je_server/store.py server/je_server/engine.py server/je_server/app.py server/tests/test_phrases.py server/tests/test_engine.py server/tests/test_api.py
/usr/bin/git commit -F - <<'EOF'
feat(server): add Ryan's daily shadowing tip to the home lines
...(이유, 시험 결과, Refs)
EOF
```

### Task 2: 앱의 한마디

**Files:**
- Modify: `app/src/api/types.ts`(`Home.tip?`), `app/src/api/client.ts`(`getHome`), `app/src/flow/homeLines.ts`, `app/src/screens/HomeScreen.tsx`
- Test: `app/src/flow/homeLines.test.ts`, `app/src/api/client.test.ts`

**Interfaces:**
- Consumes: Task 1의 `GET /home?tip=1`과 `tip`.
- Produces: `Home.tip?: Said`(옛 서버는 없음). `homeLines(home: Pick<Home, "lines" | "tip">, returning: boolean): Said[]`.

- [ ] **Step 1: 실패하는 시험을 쓴다**

`homeLines.test.ts`의 지금 시험 셋을 `homeLines({ lines }, …)`로 바꾸고 더한다:

```ts
test("on the day's first start Ryan greets, says the shadowing tip, then asks", () => {
  expect(homeLines({ lines, tip: said("tip") }, false).map((l) => l.text)).toEqual(["greeting", "tip", "ask_mode"]);
});

test("coming back he does not say the tip again", () => {
  expect(homeLines({ lines, tip: said("tip") }, true).map((l) => l.text)).toEqual(["ask_again"]);
});

test("an older server without a tip greets and asks as before", () => {
  expect(homeLines({ lines }, false).map((l) => l.text)).toEqual(["greeting", "ask_mode"]);
});
```

`client.test.ts`의 「sends bearer token」: `expect(url).toBe(`${URL}/home?tip=1`)`.

- [ ] **Step 2: 실패를 본다**

Run: `cd app && npx jest src/flow/homeLines.test.ts src/api/client.test.ts`
Expected: FAIL(차례와 주소가 다름)

- [ ] **Step 3: 구현한다**

`types.ts`에 `tip?: Said`와 주석(그날 처음일 때만, 옛 서버는 없음). `client.ts`는 `get<Home>("/home?tip=1")`과 주석(물을 때만 맥이 그날 한마디를 쓴다). `homeLines`는 새 모양으로, `HomeScreen`의 세 곳(`load`, 돌아왔을 때, 화면 글)은 `homeLines(h, …)`, `homeLines(opened, true)`, `homeLines(home, returning)`.

- [ ] **Step 4: 앱 시험과 타입 검사를 돌린다**

Run: `cd app && npx jest && npx tsc --noEmit`
Expected: 모두 통과, 타입 오류 없음

- [ ] **Step 5: 커밋한다**

```bash
/usr/bin/git add app/src/api/types.ts app/src/api/client.ts app/src/flow/homeLines.ts app/src/flow/homeLines.test.ts app/src/api/client.test.ts app/src/screens/HomeScreen.tsx
/usr/bin/git commit -F - <<'EOF'
feat(app): play Ryan's shadowing tip between the greeting and the question
...(이유, 시험 결과, Refs)
EOF
```

### Task 3: 시험 서버와 폰에서 보기, 문서

**Files:**
- Modify: `docs/PRD.md`(머리의 「고침」, 「첫 화면」, 「독려」), `docs/guide/DEVENV_맥서버_저절로_띄우기_20261107.md`(「launchd 서버를 멈추지 않고 시험하기」에 한 줄)
- 할 일 상태: 원래 폴더의 `docs/todo/20261107_09_todo_ryan_shadowing_tip.md`를 이 worktree의 `docs/todo/`로 복사해 상태 줄을 완료로 고친다.

- [ ] **Step 1: 시험 서버를 띄운다**

`DEVENV_맥서버_저절로_띄우기_20261107.md` 「launchd 서버를 멈추지 않고 시험하기」대로. 포트 8793, 8794가 비었는지 먼저 본다. 기록은 scratchpad에 복사(녹음 빼고). 로그 끝의 `Uvicorn running on`과, `warm`이 한마디 다섯을 만들었는지(복사한 `audio/`에 다섯 소리 이름의 파일)를 본다.

- [ ] **Step 2: 한마디 소리를 받아써 본다**

다섯 소리를 시험 서버의 `/transcribe`에 보내(앱과 같은 토큰, 출력에 남기지 않음) 「섀도잉」이 들리게 읽혔는지 본다. 받아쓴 글은 말이 AI가 지은 것이라 PR에 적어도 된다.

- [ ] **Step 3: 폰에서 본다**

`app/.env`의 주소를 `http://127.0.0.1:8793`으로 한 APK를 빌드하고 `adb reverse tcp:8793 tcp:8793` 뒤 깐다(버튼 계획 Task 2의 화면 확인도 이 앱으로 한다). 깔기 전에 main 세션에 알린다. 볼 것: 앱을 처음 띄우면 인사, 한마디, 질문의 글과 소리(`logcat` 프레임 수), 상황 정하기에 갔다 돌아오면 질문만, 앱을 껐다 다시 띄우면 한마디 없음, 복사본의 `tip.json`의 날짜를 어제로 고치고 다시 띄우면 다음 말.

- [ ] **Step 4: 폰을 되돌리고 시험 서버를 정리한다**

원래 폴더의 `app/.env`로 이 브랜치 앱을 다시 빌드해 깐다(원래 폴더 서버는 `tip`이 없어 한마디 없이 지금처럼 동작한다). `adb reverse --remove tcp:8793`. 시험 서버를 끄고 두 포트가 비었는지 본 뒤 복사본을 지운다. main 세션에 폰의 앱이 이 브랜치 판이라는 것과, 머지 뒤 새 main 판으로 다시 깐다는 것을 알린다.

- [ ] **Step 5: PRD와 가이드를 고친다**

- PRD 머리 「고침」 끝에: 「같은 날 그날 처음 켰을 때 라이언이 인사 다음에 섀도잉 한마디를 하게 했다(ryan-shadowing-tip).」
- PRD 「첫 화면」 인사 줄 다음에: 그날 처음 앱을 켰을 때는 인사와 질문 사이에 섀도잉 한마디를 한다. 다섯 말을 차례로 돌리고, 글로도 보인다. 첫 화면에 돌아올 때는 하지 않는다(2026-11-08, 사용자와 AI 추천, 스펙 경로).
- PRD 「독려」에: **섀도잉이 왜 중요한지:** 라이언이 하루 한 번 첫 화면에서 짧게 말한다. 늘 보이는 글에는 넣지 않고, 알림과 연속 기록은 없다(「하지 않을 것」)(2026-11-07, 11-08 사용자, 스펙 경로).
- 서버 가이드 「launchd 서버를 멈추지 않고 시험하기」 4에: 앱처럼 `/home?tip=1`로 물으면 그날 한마디가 쓰인다. 서버가 떴는지만 볼 때는 `tip` 없이 `/home`을 부른다.

- [ ] **Step 6: 할 일 파일을 완료로 고쳐 넣고 커밋한다**

```bash
cp "$(/usr/bin/git worktree list | head -1 | cut -d" " -f1)/docs/todo/20261107_09_todo_ryan_shadowing_tip.md" docs/todo/   # 원래 폴더의 할 일
# 상태 줄: > 상태: **완료** (2026-11-08 first-screen-buttons 카드)
/usr/bin/git add docs/PRD.md docs/guide/DEVENV_맥서버_저절로_띄우기_20261107.md docs/todo/20261107_09_todo_ryan_shadowing_tip.md
/usr/bin/git commit -F - <<'EOF'
docs: note Ryan's shadowing tip in the PRD and the server guide
...(이유, 폰에서 본 것, Refs)
EOF
```
