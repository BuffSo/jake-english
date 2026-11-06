# 대사 통역(소희) 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 대본의 줄이 영어로 보이는 곳마다 「통역」을 두고, 누르면 「소희」 이름표가 붙은 한국어 한 줄이 나오고 소희 목소리로 들리게 한다.

**Architecture:** 맥 서버가 줄마다 통역 글(짧은 말 모델)과 소희 소리(목소리 작업 프로세스, 복제 소희)를 누를 때 만들어 대본 줄(`ScriptLine.ko`, `ko_audio`)에 저장한다. 글과 소리는 경로가 따로라 앱은 글을 먼저 보여 주고 소리를 기다린다. 앱은 보일 모양과 소리를 틀어도 되는지를 순수 함수(`flow/interpret.ts`)로 정하고, 가져오기와 틀기를 훅(`ui/useInterpret.ts`) 하나에 모아 역할극 화면과 끝 화면이 같이 쓴다.

**Tech Stack:** FastAPI, pydantic, anthropic SDK(pytest, anyio), Expo SDK 58 / React Native 0.88(jest-expo, tsc). 새 패키지는 없다.

**Spec:** `docs/superpowers/specs/2026-11-06-korean-translation-design.md`

## Global Constraints

- 새 패키지를 설치하지 않는다.
- 통역 글은 짧은 말 모델(`Claude.quick`, `JE_CLAUDE_QUICK`)로 만든다. 새 설정을 만들지 않는다.
- 소희 목소리: 서버 이름 `"sohee"`, 작업 프로세스에 넘기는 이름 `"sohee_clone"`, 빠르기 `("sohee", "korean"): 1.0`. `sohee`, `sohee_basic`(다른 모델)을 작업 프로세스에 넘기지 않는다.
- 소희 소리는 급한 차례(`urgent=True`)로, 끝소리 확인을 켜고(`check=True`) 만든다.
- 통역과 소리는 누를 때만 만든다. 대본을 만들 때나 끝 화면이 열릴 때 미리 만들지 않는다.
- 통역 호출은 `Engine.sem`을 쓰지 않고, 남은 대본 다시 만들기(`Engine.continuing`)를 기다리지 않는다.
- 문맥의 앞뒤 대사는 `Engine.history`(다르게 말한 차례는 받아쓴 글)로 만든다. `Engine.context`는 바꾸지 않는다.
- 화면 글귀: 버튼 「통역 ›」(접힘), 「통역 접기」(펼침), 이름표 「소희」, 기다림 「소희가 통역하고 있어요…」, 실패 「지금은 통역할 수 없어요」.
- 역할극 화면에서 저절로 틀기는 소리가 도착한 그때 `canReplay(phase)`이고 아무 소리도 나오지 않을 때만이다. 소희 줄을 눌러 다시 듣기는 `canReplay(phase)`일 때만 되고, 나오던 소리를 멈추고 튼다. 끝 화면은 둘 다 늘 되고, 나오던 소리를 멈추고 튼다.
- `RoleplayScreen.tsx`, `EndScreen.tsx`의 `wrap`, `controls` 스타일과 그 바깥 배치는 건드리지 않는다(bottom-buttons 카드와 겹친다).
- 시험 문장은 지어낸 것을 쓴다(ADR-0005). 실제 Claude 호출은 Task 8에서만, 사용자에게 알린 뒤 한두 번 한다.
- git은 `/usr/bin/git`으로 부른다. `git add`는 파일을 지정한다.

## Review Focus

- **열자마자 접음:** 「통역」을 누르고 소리가 오기 전에 접으면 소리가 나오지 않아야 한다. 훅은 소리가 도착할 때 `stillOpen()`을 다시 본다(Task 6의 화면 쪽 `stillOpen`, Task 5의 `mayAutoPlay` 시험).
- **소리가 늦게 도착:** 누를 때는 조용했는데 소리가 오기 전에 녹음을 시작했거나 라이언이 말하기 시작했으면 틀지 않는다. 훅이 도착 시점에 `allow(true)`를 부르고, 역할극 화면은 최신 상태를 담은 ref로 답한다(Task 6).
- **역할극 중 연습으로 떠남:** 지난 줄 연습으로 가면 역할극 화면은 그대로 남아 `mounted`가 참이다. 떠나기 전에 연 통역의 소리가 연습 화면에서 나오면 안 된다. 화면의 `stillOpen`이 `epoch`도 본다(Task 6).
- **다르게 말한 뒤의 대답:** 대답 줄의 앞 대사가 받아쓴 글로 가야 하고, 다시 만들기를 기다리지 않아야 한다(Task 4 시험 둘).
- **같은 줄을 두 화면에서:** 역할극에서 만든 통역이 끝 화면과 「같은 대본으로 처음부터」에서 다시 만들어지지 않는다. 서버가 줄에 저장하고 `copy`가 줄을 옮긴다(Task 4 시험).

---

### Task 1: 줄에 통역 칸을 더한다 (서버 모델, 앱 타입, 계약 예시)

**Files:**
- Modify: `server/je_server/models.py` (`ScriptLine`)
- Modify: `app/src/api/types.ts` (`ScriptLine`, `LINE_KEYS`)
- Modify: `contract/roleplay.json`, `contract/line-user.json`, `contract/summary.json` (모든 줄)
- Test: `server/tests/test_contract.py`, `app/src/api/contract.test.ts` (고치지 않고 그대로 돌린다)

**Interfaces:**
- Produces: 서버 `ScriptLine.ko: str | None = None`(소희가 옮긴 한국어), `ScriptLine.ko_audio: str | None = None`(그 소리 키, sha256 hex). 앱 `ScriptLine`에 `ko: string | null; ko_audio: string | null`. `LINE_KEYS`에 `"ko"`, `"ko_audio"`.

- [ ] **Step 1: 계약 예시를 먼저 고친다.** 세 파일의 모든 줄에 `"ko": null, "ko_audio": null`을 더한다(`audio` 다음 자리). `contract/line-user.json`만 `"ko": "커피 한 잔 주세요."`, `"ko_audio": null`로 둔다(지어낸 문장).
- [ ] **Step 2: 실패를 본다.** `cd server && uv run pytest tests/test_contract.py -q` → 줄 예시가 모델과 달라 FAIL. `cd app && npx jest src/api/contract.test.ts` → 키가 달라 FAIL.
- [ ] **Step 3: 서버 `ScriptLine`과 앱 타입, `LINE_KEYS`에 두 칸을 더한다.** 서버 칸에는 한 줄 주석으로 「누를 때 만든다(스펙 korean-translation 5)」를 단다.
- [ ] **Step 4: 통과를 본다.** 위 두 명령이 PASS, `cd app && npx tsc --noEmit` 오류 없음. 서버 전체 `uv run pytest -q`도 PASS(옛 `roleplay.json`은 기본값으로 읽힌다).
- [ ] **Step 5: Commit** `feat: add Sohee's interpretation fields to script lines`

---

### Task 2: 서버에 소희 목소리를 더한다

**Files:**
- Modify: `server/je_server/tts.py` (`SPEAK_RATE`, 새 `WORKER_VOICE`, `Voice.say`의 `voice` 타입, `_render`)
- Test: `server/tests/test_tts.py`

**Interfaces:**
- Produces: `Voice.say(text, "sohee", "korean", urgent, rank=0, check=False) -> str`. 키는 `audio_key("sohee", "korean", text)`.

- [ ] **Step 1: 실패하는 시험을 쓴다.**

```python
async def test_sohee_is_the_cloned_voice(voice, tmp_path):
    # the voice setup falls back to its default voice for a name it does not know, and its plain "sohee" is
    # another model: the worker must get the cloned voice by name (spec korean-translation 「제약」)
    key = await voice.say("커피 한 잔 주세요.", "sohee", "korean", urgent=True)
    rates = (tmp_path / ".tmp" / "rates.txt").read_text(encoding="utf-8").splitlines()
    assert rates == ["sohee_clone korean 1.0"] and key == audio_key("sohee", "korean", "커피 한 잔 주세요.")
```

- [ ] **Step 2: 실패를 본다.** `cd server && uv run pytest tests/test_tts.py::test_sohee_is_the_cloned_voice -q` → `KeyError: ('sohee', 'korean')`.
- [ ] **Step 3: 구현한다.** `SPEAK_RATE`에 `("sohee", "korean"): 1.0`(주석: 폰에서 들어 보고 정한다, 2026-11-06). `WORKER_VOICE: dict[str, str] = {"sohee": "sohee_clone"}`를 두고 `_render`의 요청에 `WORKER_VOICE.get(voice, voice)`를 넣는다. 키(`audio_key`)는 서버 이름 그대로다. `say`의 `voice` 타입에 `"sohee"`를 더하고, 모듈 첫 줄 설명에 소희를 더한다.
- [ ] **Step 4: 통과를 본다.** `uv run pytest tests/test_tts.py -q` 전체 PASS.
- [ ] **Step 5: Commit** `feat(server): add Sohee's cloned voice to the voice worker`

---

### Task 3: Claude가 대사를 소희의 한국어로 옮긴다

**Files:**
- Modify: `server/je_server/prompts.py` (새 `INTERPRET_SYSTEM`, `INTERPRET_SCHEMA`)
- Modify: `server/je_server/claude.py` (새 `Claude.interpret`, `INTERPRET_TRIES = 2`)
- Modify: `server/tests/fakes.py` (`FakeClaude.interpret`)
- Test: `server/tests/test_claude.py`

**Interfaces:**
- Produces: `async def interpret(self, frame: Frame, line: tuple[Speaker, str], before: tuple[Speaker, str] | None, after: tuple[Speaker, str] | None) -> str` — 한 줄로 다듬은 한국어. 못 만들면 `ClaudeUnavailable`.
- Produces(시험용): `FakeClaude.interpret` — `self.interpret_calls`에 `{"frame", "line", "before", "after"}`를 남기고, `self.interpret_gate`(asyncio.Event)가 있으면 기다리고, `fail_next`를 따르고, `"소희: " + line[1]`을 돌려준다.

- [ ] **Step 1: 실패하는 시험을 쓴다.** `from je_server.models import Frame`과 `fakes.FRAME`을 쓴다.

```python
async def test_interpret_uses_the_quick_model_with_roles_and_neighbors():
    fake = FakeAnthropic([json.dumps({"ko": "역까지 어떻게 가요?"})])
    ko = await Claude(fake).interpret(Frame(**FRAME), ("ryan", "How do I get there?"),
                                      ("user", "It's right over there."), None)
    req = fake.requests[0]
    assert ko == "역까지 어떻게 가요?" and req["model"] == "claude-haiku-5-5"
    body = req["messages"][0]["content"]
    assert "How do I get there?" in body and "It's right over there." in body
    assert FRAME["ryan_role_ko"] in body and FRAME["user_role_ko"] in body
    assert fake.options and fake.options[0]["timeout"] == 12.0  # the learner waits: fail fast (LIVE_OPTIONS)


async def test_interpret_keeps_one_line_without_quotes():
    fake = FakeAnthropic([json.dumps({"ko": "「역까지\n어떻게 가요?」"})])
    assert await Claude(fake).interpret(Frame(**FRAME), ("ryan", "How do I get there?"), None, None) == "역까지 어떻게 가요?"


async def test_interpret_asks_again_without_korean_then_gives_up():
    fake = FakeAnthropic([json.dumps({"ko": "How do I get there?"}), json.dumps({"ko": "역까지 어떻게 가요?"})])
    assert await Claude(fake).interpret(Frame(**FRAME), ("ryan", "How do I get there?"), None, None) == "역까지 어떻게 가요?"
    fake = FakeAnthropic([json.dumps({"ko": ""}), "not json"])
    with pytest.raises(ClaudeUnavailable):
        await Claude(fake).interpret(Frame(**FRAME), ("ryan", "How do I get there?"), None, None)
```

- [ ] **Step 2: 실패를 본다.** `cd server && uv run pytest tests/test_claude.py -q -k interpret` → `AttributeError: 'Claude' object has no attribute 'interpret'`.
- [ ] **Step 3: 프롬프트를 쓴다.** `INTERPRET_SCHEMA = _obj({"ko": STR})`. `INTERPRET_SYSTEM`(영어 지시, 기존 프롬프트처럼)은 스펙 「3. 통역 글」을 담는다: 통역사 소희가 한 대사를 자연스러운 한국어로 옮긴다, 낱말대로가 아니라 그 상황에서 한국 사람이 실제로 할 말로, 말하는 사람의 역할과 상황에 맞는 말투(손님에게 말하는 점원은 존댓말), 설명·낱말 풀이·영어 병기·따옴표·머리말 없음, 소리 내 읽을 한 줄, 앞뒤 대사는 문맥으로만 쓰고 옮기지 않는다. 예시 하나는 지어낸 문장으로 둔다.
- [ ] **Step 4: `Claude.interpret`를 구현한다.** 보낼 글은 `json.dumps({"상황": frame.model_dump(), "앞 대사": …, "옮길 대사": …, "뒤 대사": …}, ensure_ascii=False)`이고, 대사마다 `{"말하는 사람": <역할>, "text": …}`로 둔다. 역할은 `"ryan"`이면 `frame.ryan_role_ko`, `"user"`면 `frame.user_role_ko`, 없는 대사는 `None`. `self._json(self.quick, …, 300, live=True)`를 `INTERPRET_TRIES`번까지 부른다. 답은 공백과 줄바꿈을 한 칸으로 줄이고, 앞뒤의 `"'“”「」` 따옴표를 떼고, `[가-힣]`이 없으면 다시 부른다. 다 실패하면 `ClaudeUnavailable("bad interpretation")`. 걸린 시간과 시도 수를 `log.info`로 남긴다(옮긴 글은 찍지 않는다).
- [ ] **Step 5: `FakeClaude.interpret`를 더한다.** 위 Interfaces대로. `__init__`에 `self.interpret_calls: list[dict] = []`, `self.interpret_gate = None`.
- [ ] **Step 6: 통과를 본다.** `uv run pytest tests/test_claude.py -q` 전체 PASS.
- [ ] **Step 7: Commit** `feat(server): interpret a script line into Sohee's Korean`

---

### Task 4: 서버가 통역 글과 소리를 누를 때 만들어 저장한다

**Files:**
- Modify: `server/je_server/engine.py` (새 `Engine.ko`, `Engine._make_ko`, `Engine.ko_audio`, `self.kos`)
- Modify: `server/je_server/app.py` (새 경로 둘)
- Test: `server/tests/test_engine.py`, `server/tests/test_api.py`

**Interfaces:**
- Consumes: `Claude.interpret`(Task 3), `Voice.say(…, "sohee", "korean", …)`(Task 2), `ScriptLine.ko`, `ko_audio`(Task 1).
- Produces:
  - `async def ko(self, rp_id: str, idx: int) -> str` — 있으면 그대로, 없으면 만들어 `update_line(…, ko=…)`. 같은 줄을 동시에 물으면 `self.kos[(rp_id, idx)]` 작업 하나를 나눈다(`Engine.three`와 같은 모양). `self.sem`을 쓰지 않고 `self.continuing`을 기다리지 않는다. 문맥은 `hist = self.history(rp, len(rp.lines))`의 `idx - 1`, `idx + 1`(없으면 `None`).
  - `async def ko_audio(self, rp_id: str, idx: int) -> str` — 통역 글이 없으면 `NotFound`. `line.ko_audio`가 있고 `self.voice.path(key).is_file()`이면 그대로. 아니면 `self.voice.say(line.ko, "sohee", "korean", urgent=True, check=True)` 뒤 `update_line(…, ko_audio=key)`.
  - `GET /roleplays/{rp_id}/lines/{idx}/ko` → `{"text": str}`. 404 `not_found`, 503 `claude_unavailable`(`claude_down()`).
  - `GET /roleplays/{rp_id}/lines/{idx}/ko/audio` → `{"audio": str}`. 404 `not_found`(줄이 없거나 통역 글이 아직 없음), 503 `voice_unavailable`(`VoiceError`). 경로 값은 지금 경로처럼 `PathParam(pattern=ID)`, `PathParam(ge=0)`로 검사한다.

- [ ] **Step 1: 실패하는 엔진 시험을 쓴다.** `test_engine.py`에 넣는다. 다르게 말한 차례는 `engine.save_attempt`로 `Attempt(n=1, mode="turn", heard="Do you have oat milk?", followed=False, issues=[], say_ko="", audio=[], timings={})`를 남기고, 대답은 `engine.add_reply(rp.id, 1, "Do you have oat milk?", ScriptLine(idx=2, speaker="ryan", text="Yes, we do!", kind="reply"))`로 넣는다(`fake_claude.continue_gate = asyncio.Event()`로 다시 만들기를 붙잡아 둔다).

```python
async def test_ko_made_once_and_kept_on_the_line(engine, fake_claude):
    rp = await engine.create("길 묻기")
    a, b = await asyncio.gather(engine.ko(rp.id, 0), engine.ko(rp.id, 0))
    assert a == b == "소희: " + rp.lines[0].text and len(fake_claude.interpret_calls) == 1
    assert engine.store.load(rp.id).lines[0].ko == a
    assert await engine.ko(rp.id, 0) == a and len(fake_claude.interpret_calls) == 1
    copy = await engine.copy(rp.id)
    assert copy.lines[0].ko == a  # 「같은 대본으로 처음부터」 does not make it again


async def test_ko_of_a_reply_sees_what_was_said_and_does_not_wait_for_the_rebuild(engine, fake_claude):
    # 위 설명대로 다르게 말한 차례와 대답을 넣고 continue_gate를 열지 않는다
    ...
    ko = await asyncio.wait_for(engine.ko(rp.id, 2), 1)
    call = fake_claude.interpret_calls[-1]
    assert ko == "소희: Yes, we do!" and call["before"] == ("user", "Do you have oat milk?")


async def test_ko_does_not_queue_behind_three_line_notes(engine, fake_claude):
    fake_claude.annotate_gate = asyncio.Event()  # every note waits: Engine.sem is full
    rp = await engine.create("길 묻기")
    await asyncio.sleep(0)
    assert await asyncio.wait_for(engine.ko(rp.id, 0), 1)
    fake_claude.annotate_gate.set()


async def test_ko_audio_is_sohee_urgent_checked_and_kept(engine, fake_voice):
    rp = await engine.create("길 묻기")
    with pytest.raises(NotFound):
        await engine.ko_audio(rp.id, 0)  # no text yet
    text = await engine.ko(rp.id, 0)
    key = await engine.ko_audio(rp.id, 0)
    assert (text, "sohee", "korean", True) in fake_voice.calls and text in fake_voice.checked
    assert engine.store.load(rp.id).lines[0].ko_audio == key
    n = len(fake_voice.calls)
    assert await engine.ko_audio(rp.id, 0) == key and len(fake_voice.calls) == n
```

- [ ] **Step 2: 실패하는 API 시험을 쓴다.** `test_api.py`: 역할극을 만든 뒤 `GET …/lines/0/ko/audio`가 404, `GET …/lines/0/ko`가 200 `{"text": "소희: …"}`, 이어 `…/ko/audio`가 200이고 `len(audio) == 64`. `fake_claude.fail_next = True`이면 `…/lines/1/ko`가 503 `claude_unavailable`. `fake_voice.fail_text`를 그 통역 글로 두면 `…/ko/audio`가 503 `voice_unavailable`. `test_routes_need_token`의 경로 목록에 `/roleplays/000000000000/lines/0/ko`를 더한다.
- [ ] **Step 3: 실패를 본다.** `cd server && uv run pytest tests/test_engine.py tests/test_api.py -q` → `AttributeError: 'Engine' object has no attribute 'ko'`, 404.
- [ ] **Step 4: 엔진과 경로를 구현한다.** 위 Interfaces대로. `ko` 문서 문자열에 「세마포어와 다시 만들기를 기다리지 않는다(스펙 5, 빌더 검토)」를 적는다.
- [ ] **Step 5: 통과를 본다.** `uv run pytest -q` 전체 PASS.
- [ ] **Step 6: Commit** `feat(server): make and keep Sohee's interpretation on demand`

---

### Task 5: 앱이 통역을 받아 오고, 보일 모양과 틀 때를 정한다

**Files:**
- Modify: `app/src/api/client.ts` (`getKo`, `getKoAudio`)
- Create: `app/src/flow/interpret.ts`
- Modify: `app/src/flow/state.ts` (`State.interpreting`, 액션 `interpret`)
- Test: `app/src/api/client.test.ts`, `app/src/flow/interpret.test.ts`(새로), `app/src/flow/state.test.ts`

**Interfaces:**
- Produces(`client.ts`): `getKo(id: string, idx: number): Promise<{ text: string }>`(기본 30초), `getKoAudio(id: string, idx: number): Promise<{ audio: string }>`(기본 30초). 경로는 Task 4.
- Produces(`flow/interpret.ts`):
  - `type Ko = { text: string; audio: string | null }`, `type KoEntry = Ko | "loading" | "failed"`
  - `koOf(line: ScriptLine | undefined): Ko | undefined` — `line.ko`가 있으면 `{ text: line.ko, audio: line.ko_audio }`
  - `type KoView = "closed" | "loading" | "failed" | "open"`; `koView(entry: KoEntry | undefined, open: boolean): KoView` — `"failed"`이면 열림과 관계없이 `"failed"`, 닫혔으면 `"closed"`, 열렸는데 없거나 `"loading"`이면 `"loading"`, 아니면 `"open"`
  - `mayAutoPlay(where: "roleplay" | "end", phase: Phase, playing: boolean): boolean` — 끝 화면은 `true`, 역할극은 `canReplay(phase) && !playing`
  - `mayReplay(where: "roleplay" | "end", phase: Phase): boolean` — 끝 화면은 `true`, 역할극은 `canReplay(phase)`
- Produces(`state.ts`): `State.interpreting: boolean`(지금 말할 줄의 통역이 펼쳐져 있다), 액션 `{ type: "interpret"; open: boolean }`(줄이 있을 때만 바꾼다). `reading: false`로 돌리는 모든 곳(`lineLoaded`, `startPractice`, `practiseLine`, `initial`)에서 `interpreting: false`. `again`과 `leavePractice`(돌아오면 그대로)는 그대로 둔다.

- [ ] **Step 1: 실패하는 시험을 쓴다.**
  - `client.test.ts`: `getKo("abcdef012345", 2)`가 `${URL}/roleplays/abcdef012345/lines/2/ko`를 부르고 `{ text }`를 돌려준다. `getKoAudio`는 `…/lines/2/ko/audio`.
  - `interpret.test.ts`: `koView`의 네 경우(`"failed"`가 열림·닫힘 모두 `"failed"`, 닫힌 Ko는 `"closed"`, 열린 `undefined`와 `"loading"`은 `"loading"`, 열린 Ko는 `"open"`). `koOf`가 `ko: null`이면 `undefined`. `mayAutoPlay("roleplay", p, false)`가 `"ready"`, `"evaluated"`에서만 참이고 `playing`이 참이면 모두 거짓, `"end"`는 늘 참. `mayReplay("roleplay", "recording")`이 거짓.
  - `state.test.ts`: `interpret`로 열고 닫는다. 다음 줄(`lineLoaded`)에서 접힌다. `again`에서는 열린 채다. 역할극 중 지난 줄 연습(`practiseLine`)은 접힌 채 시작하고, 끝나고 돌아오면(`next` → `leavePractice`) 떠나기 전처럼 열린 채다. 줄이 없으면 바뀌지 않는다.
- [ ] **Step 2: 실패를 본다.** `cd app && npx jest src/api src/flow` → 없는 함수와 키로 FAIL.
- [ ] **Step 3: 구현한다.** 위 Interfaces대로. `interpret.ts` 머리 주석에 스펙 경로와 「소리는 도착할 때 다시 본다」를 쓴다.
- [ ] **Step 4: 통과를 본다.** `npx jest` 전체 PASS, `npx tsc --noEmit` 오류 없음.
- [ ] **Step 5: Commit** `feat(app): fetch Sohee's interpretation and decide when it shows and plays`

---

### Task 6: 통역 훅과 소희 줄, 역할극 화면에 붙이기

**Files:**
- Create: `app/src/ui/useInterpret.ts`, `app/src/ui/Interpret.tsx`
- Modify: `app/src/ui/theme.ts` (`colors.sohee`), `app/src/ui/LineToSay.tsx`, `app/src/screens/RoleplayScreen.tsx`

**Interfaces:**
- Consumes: Task 5 전부, `SoundQueue`, `api.audioSource`.
- Produces(`useInterpret.ts`):

```ts
export type Interpret = {
  entry: (idx: number, line?: ScriptLine) => KoEntry | undefined; // 이 화면에서 받은 것, 없으면 koOf(line)
  // 글이 없으면 받아 오고, 이어서 소리가 없으면 받아 온다. 소리가 오면 stillOpen()과 allow(true)를 그때 보고 튼다.
  open: (idx: number, line: ScriptLine | undefined, stillOpen: () => boolean) => void;
  // allow(false)일 때만. 소리가 없으면 받아 온 뒤 튼다(소리를 못 만들었던 줄을 다시 만들어 본다).
  replay: (idx: number, line?: ScriptLine) => void;
};
export function useInterpret(rpId: string, sounds: SoundQueue, allow: (auto: boolean) => boolean): Interpret;
```

  틀 때는 늘 `sounds.clear()` 뒤 `sounds.enqueue(api.audioSource(audio))`. 글을 받는 중에 같은 줄을 또 열면 새로 부르지 않는다. 글을 못 받으면 그 줄은 `"failed"`, 소리를 못 받으면 글은 남기고 `audio: null`. 화면이 사라진 뒤 도착한 것은 버린다(훅 안의 `mounted` ref).
- Produces(`Interpret.tsx`): `KoButton({ view, onPress })` — `"closed"`, `"failed"`이면 「통역 ›」, 아니면 「통역 접기」. `KoLine({ view, entry, onReplay })` — `"loading"`이면 「소희가 통역하고 있어요…」, `"failed"`면 「지금은 통역할 수 없어요」, `"open"`이면 「소희」 이름표(`colors.sohee` 바탕의 작은 흰 글자)와 한국어 한 줄을 담은 `Pressable`(`onReplay`), `"closed"`면 아무것도 그리지 않는다. `colors.sohee = "#2F9E44"`.
- Produces(`LineToSay` 새 props): `ko: { view: KoView; entry: KoEntry | undefined; onToggle: () => void; onReplay: () => void }`. 소희 줄은 평범한 대사나 세 줄 아래, 버튼 줄 위. 버튼 줄은 「읽는 법 보기 ›」와 「통역 ›」를 나란히 둔다. 세 줄이 없어(`"plain"`) 읽는 법 버튼이 없어도 통역 버튼은 있다.

- [ ] **Step 1: 훅과 `Interpret.tsx`, `colors.sohee`를 만든다.** 위 Interfaces대로. 순수한 판단은 Task 5 함수를 부른다.
- [ ] **Step 2: `LineToSay`에 `ko`를 받는다.**
- [ ] **Step 3: 역할극 화면을 잇는다.**
  - 최신 상태 ref: `const now = useRef(state); now.current = state;`. 훅의 `allow`는 `(auto) => mounted.current && (auto ? mayAutoPlay("roleplay", now.current.phase, sounds.isPlaying()) : mayReplay("roleplay", now.current.phase))`.
  - 지난 말풍선의 펼침은 화면 안의 `koOpen: Record<number, boolean>`(ref로도 들고 있는다). 열 때 `const my = epoch.current`를 잡고 `stillOpen = () => epoch.current === my && koOpenRef.current[idx] === true`로 넘긴다. 「내 차례」는 `dispatch({ type: "interpret", open })`이고 `stillOpen = () => epoch.current === my && now.current.interpreting && now.current.line?.idx === idx`. 「실패」를 누르면 다시 연다(`open`을 다시 부른다).
  - `RyanBubble`: 말풍선을 `Pressable`에서 `View`로 바꾸고 「눌러서 읽는 법 보기」 안내를 뺀다. 아래 버튼 줄에 「읽는 법 보기 ›」/「읽는 법 접기」(지금 `toggleThree`)와 `KoButton`을 두고, `PractiseLink`는 그대로 둔다. `KoLine`은 영어 대사(와 펼친 세 줄) 아래.
  - 지나간 「나」 말풍선: 「대본」 글 아래에 `KoButton`과 `KoLine`, 그다음 「들린 말」.
  - 앞 라이언 대사(내 대사 다시 연습): 말풍선 `Pressable`(듣기)은 그대로 두고 안에 `KoButton`, `KoLine`.
  - 「내 차례」: `LineToSay`의 `ko`. 줄은 `line`(따라 말하기에서는 라이언 줄)이다.
  - 다르게 말해 나온 대답(`state.reply`)은 `RyanBubble`이라 그대로 붙는다. 줄 객체는 `state.seen[idx]`나 `state.reply`, 지금 줄은 `line`에서 찾는다.
  - 접을 때 나오던 소희 목소리를 멈추지 않는다(스펙 2). 「다시 해 보기」와 연습에서 돌아올 때는 `open`을 부르지 않는다(다시 틀지 않는다).
- [ ] **Step 4: 확인한다.** `cd app && npx tsc --noEmit` 오류 없음, `npx jest` 전체 PASS.
- [ ] **Step 5: Commit** `feat(app): show Sohee's interpretation in the roleplay bubbles`

---

### Task 7: 끝 화면에 통역을 붙인다

**Files:**
- Modify: `app/src/screens/EndScreen.tsx` (`RyanLine`, `MyLine`, 화면의 펼침 상태)

**Interfaces:**
- Consumes: `useInterpret`(`allow` = `() => mounted.current`), `KoButton`, `KoLine`, `koView`.

- [ ] **Step 1: 구현한다.** 화면 안의 `koOpen: Record<number, boolean>`과 그 ref. `RyanLine`의 `actions` 줄에 「▶ 듣기」, 「따라 말하기 ›」 옆으로 `KoButton`, `MyLine`의 「이 줄 다시 ›」 옆에 `KoButton`. `KoLine`은 대사(`styles.text`) 바로 아래, 시도(`TryView`) 위. 줄 객체는 `summary.lines`의 `l.line`(서버가 저장한 통역이 들어 있다). 끝 화면을 열 때 통역을 미리 받지 않는다.
- [ ] **Step 2: 확인한다.** `npx tsc --noEmit` 오류 없음, `npx jest` 전체 PASS.
- [ ] **Step 3: Commit** `feat(app): show Sohee's interpretation on the end screen`

---

### Task 8: 문서 고치기와 실제로 재기

**Files:**
- Modify: `docs/PRD.md` (「통역」), `docs/superpowers/specs/2026-11-05-speaking-practice-design.md` (「첫 구현 범위」의 미루는 것 6, 「역할극의 한 차례」 1, 「세 줄 표시」의 보이는 때, 「기다리는 시간과 모델」의 소희 통역 글), `docs/superpowers/specs/2026-11-05-roleplay-practice-design.md` (9의 「말풍선 자체를 누르는 것은 지금과 같다」)
- Modify: `docs/superpowers/specs/2026-11-06-korean-translation-design.md` (「잰 것」)
- Modify: `docs/guide/SPEECH_맥서버_받아쓰기와_목소리_20261105.md` (목소리를 더할 때: 작업 프로세스는 모르는 이름을 기본 목소리로 대신 만들어 오류가 나지 않는다, 같은 이름의 다른 모델을 고르면 모델이 하나 더 올라간다, 시험으로 넘기는 이름을 확인한다) 와 `docs/guide/README.md` 색인(고친 날짜)
- Create(커밋에 넣음): `docs/todo/20261106_03_todo_korean_translation.md` — 원래 폴더의 할 일 파일을 옮겨 오고 상태 줄을 「**완료** (2026-11-06, PR #…)」로 고친다.

- [ ] **Step 1: PRD와 앞 스펙 둘을 고친다.** 스펙 korean-translation 「6. 다른 문서 고치기」대로. 고친 곳마다 날짜와 이 스펙 경로를 적는다.
- [ ] **Step 2: 가이드를 고친다.**
- [ ] **Step 3: 사용자에게 알리고 실제로 잰다.** 원래 폴더의 서버를 끄고 이 worktree에서 띄울 것과 Claude 한두 번 호출을 알린다(다른 카드가 시험 중인지 먼저 본다). 이 브랜치의 서버로 역할극 하나를 만들고 줄 하나의 `…/ko`와 `…/ko/audio`를 불러, 글이 나오는 시간, 소리가 나오는 시간, 쓴 토큰(서버 밖 임시 스크립트로 같은 요청을 한 번 보내 `usage`를 본다, scratchpad에 두고 커밋하지 않는다)을 잰다. 옮긴 글은 기록하지 않는다. 같은 서버와 이 브랜치의 APK로 에뮬레이터에서 Review Focus의 앞 셋을 본다: 열고 바로 접으면 소리가 나지 않는다, 라이언이 말하는 동안 열면 글만 나온다, 역할극 중 연습으로 떠나면 소희 목소리가 따라오지 않는다(이 셋은 훅 안의 일이라 jest로 시험하지 않는다). 화면을 한 번 찍어 소희 줄이 한글 발음과 구별되는지 본다. 끝나면 원래 폴더에서 서버를 다시 띄운다.
- [ ] **Step 4: 잰 값을 스펙 「잰 것」에 적는다.**
- [ ] **Step 5: 전체 시험.** `cd server && uv run pytest -q`, `cd app && npx jest && npx tsc --noEmit`, `node --test 'scripts/**/*.test.mjs'` 모두 PASS.
- [ ] **Step 6: Commit** `docs: record Sohee's interpretation in the PRD, specs and speech guide` (할 일 파일은 PR 번호가 생긴 뒤 같은 PR의 devlog 커밋에 상태를 고쳐 넣는다)
