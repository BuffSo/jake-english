# 듣기 버튼 울림과 녹음 듣기용 사본 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 듣기 버튼을 누르면 그 버튼의 🔊가 소리가 끝날 때까지 쿵쿵 울린다. 다시 누르면 멈춘다. 맥은 녹음 대신, 첫 말소리 0.2초 앞부터 마지막 말소리 0.4초 뒤까지 자른 듣기용 사본을 내준다.

**Architecture:**
- 서버: `audio.speech_span`이 50ms 창으로 말소리 구간을 재고, `audio.play_cut`이 ffmpeg로 다시 인코딩 없이 자른다(`-c copy -movflags +faststart`). `Engine.recording`은 같은 폴더의 `{idx}-{n}.play.m4a`를 만들어(한 번, 동시 요청은 하나로) 내주고, 실패하면 원본을 내준다. 시도를 받은 뒤 곁에서 미리 만든다.
- 앱: 소리 대기열(`SoundQueue`)에 이름표(tag)를 붙인다. 지금 울리는 이름표와 같은 버튼만 🔊(`PlayIcon`)를 움직인다. 누르기 규칙은 순수 함수(`playTap`)다.

**Tech Stack:** Python 3 + FastAPI + ffmpeg(`cd server && uv run pytest -q`), React Native + Expo + jest(`cd app && npx jest && npx tsc --noEmit`). 새 꾸러미 없음.

**Spec:** `docs/superpowers/specs/2026-11-08-play-button-feedback-design.md`

**실행 방식:** 이 세션이 직접 한다(executing-plans). 서버 둘, 앱 셋, 폰, 문서로 이어지고 앱 작업이 같은 화면 파일을 고친다. 끝에 새 리뷰어 한 명이 브랜치 전체를 보고, PR을 열면 pr-review로 본다. 리뷰가 도는 동안 devlog와 PR 본문을 쓴다(사용자가 정한 일하는 방식, 2026-11-08).

## Global Constraints

- 글자는 바꾸지 않는다. 움직이는 것은 🔊뿐이다. 움직임: 0.36초마다 1 → 1.35배 → 1.1배, -6도 → 4도, 반복.
- 울림은 소리가 대기열에 들어갈 때 시작하고, 그 이름표의 소리(이어 트는 둘과 사이의 쉼 포함)가 끝나거나 대기열이 비워지면 멈춘다. 저절로 트는 소리(라이언, 연습의 본보기)에는 이름표가 없다.
- 누르기: 울리는 버튼을 다시 누르면 멈춘다. 다만 그 소리가 시작한 뒤 0.4초(`TAP_HOLD_MS`) 안의 누름은 무시한다. 흐린 버튼은 지금처럼 누름을 무시한다.
- 듣기용 사본: 말소리는 50ms 평균 크기 -45 dBFS 이상. 앞 0.2초, 뒤 0.4초 여유. 말소리가 없으면 자르지 않고 머리 정보만 앞으로. 원본은 바꾸지 않는다. 파일 이름 `{idx}-{n}.play.m4a`, 원본과 같은 `rec/`.
- 녹음은 폰에 두지 않는다. 사본을 만들다 실패하면 원본을 내준다. 로그에 경로와 받아쓴 글을 남기지 않는다.
- 맥 서버 API 모양과 계약 예시(`contract/`)는 바꾸지 않는다.
- 시험 소리는 ffmpeg로 지어낸다(사인파와 조용함). 사용자 녹음을 시험 자료로 쓰지 않는다.
- 폰 시험은 main 세션에 먼저 알리고, 누르기 전마다 앞의 앱을 본다. 서버 시험은 원래 폴더 서버를 멈추지 않고 옆 포트(`JE_HOST=127.0.0.1`, `JE_PORT=8795`, `JE_WHISPER_PORT=8796`)에 데이터 복사본으로 띄운다. 끝나면 복사본을 지운다. 지우는 명령은 `"${VAR:?}"/x` 꼴이나 글자 그대로의 경로로 쓴다.
- 커밋 메시지는 영어 Conventional Commits, 본문에 이유와 시험 결과, 끝에 `Refs: docs/superpowers/specs/2026-11-08-play-button-feedback-design.md`. AI 서명 줄 없음. git은 `/usr/bin/git`, 커밋과 기록은 `&&`로 잇는다.

## Review Focus

1. **소리가 끝났는데 🔊가 계속 울림:** 소리가 오류로 끝나거나(파일 없음, 연결 끊김) 30초 지킴이(`STUCK_MS`)로 넘어갈 때도 이름표가 지워져야 한다. → Task 3 시험 `the tag clears when the queue moves on without a finish`.
2. **처음 녹음의 쉼 동안 울림이 끊김:** 녹음 둘 사이의 쉼도 같은 이름표다. → Task 3 시험 `a pair keeps its tag through the pause`.
3. **빠르게 두 번 누름이 틀자마자 멈춤:** → Task 4 시험 `a second tap within the hold is ignored`.
4. **작게 시작하는 첫마디가 잘림:** -45 dBFS 아래로 시작해 커지는 소리. → Task 1 시험 `a soft start stays in the cut`.
5. **사본을 만드는 동안 같은 녹음을 또 부름 / 실패:** → Task 2 시험 `two requests at once make the copy once`, `a failing cut serves the original`.

---

### Task 1: 말소리 구간 재기와 자르기 (서버 audio)

**Files:**
- Modify: `server/je_server/audio.py`
- Test: `server/tests/test_audio.py`, `server/tests/audiotools.py`(시험 소리 도우미가 필요하면)

**Interfaces:**
- Produces: `PLAY_MIN_DBFS = -45.0`, `PLAY_LEAD = 0.2`, `PLAY_TAIL = 0.4`; `def speech_span(wav: Path) -> tuple[float, float] | None`(첫 창 시작 초, 마지막 창 끝 초, 없으면 `None`); `async def play_cut(src: Path, span: tuple[float, float] | None, seconds: float, dst: Path) -> None`(ffmpeg, 실패하면 `AudioError`).

- [ ] **Step 1: 실패하는 시험을 쓴다** — 지어낸 소리는 `aevalsrc`로 한 소스에 만든다(예: `aevalsrc='if(between(t,1,2),0.5*sin(2*PI*220*t),0)':s=16000:d=5`).
  - `test_speech_span_finds_the_loud_part`: 1~2초만 소리인 wav → `(1.0±0.05, 2.0±0.05)`.
  - `test_speech_span_none_for_silence`: 조용함 → `None`.
  - `test_a_soft_start_stays_in_the_cut`: 0.5~1초 진폭 0.01(-40 dBFS쯤), 1~2초 0.5 → 시작이 0.5±0.05.
  - `test_play_cut_trims_and_puts_moov_first`: 같은 소리의 m4a를 자르면 길이 1.6±0.1초, 맨 위 상자 순서에서 `moov`가 `mdat`보다 앞.
  - `test_play_cut_without_speech_keeps_everything`: `span=None`이면 길이가 원본과 같고 `moov`가 앞.
- [ ] **Step 2: 실패를 본다** — `cd server && uv run pytest tests/test_audio.py -q`.
- [ ] **Step 3: 구현한다** — `speech_span`은 `_window_dbfs`를 다시 쓴다. `play_cut`은 시작 `max(0, start - PLAY_LEAD)`, 끝 `min(seconds, end + PLAY_TAIL)`으로 `ffmpeg -ss <a> -to <b> -i src -c copy -movflags +faststart dst`(인자는 목록으로, `_ffmpeg`).
- [ ] **Step 4: 통과를 본다** — 같은 명령.
- [ ] **Step 5: 커밋** — `feat(server): cut a recording to its speech for replay`.

### Task 2: 녹음 주소가 듣기용 사본을 내준다 (서버 engine)

**Files:**
- Modify: `server/je_server/store.py`(`play_path`), `server/je_server/engine.py`(`recording`을 async로, 사본 만들기, `_attempt` 뒤 미리 만들기), `server/je_server/app.py`(라우트 async)
- Test: `server/tests/test_api.py`(지금 「원본 그대로」 시험을 고침), `server/tests/test_engine.py` 또는 새 `server/tests/test_play_copy.py`

**Interfaces:**
- Consumes: Task 1의 `speech_span`, `play_cut`, `to_wav16k`.
- Produces: `Store.play_path(rp_id, idx, n) -> Path`(`rec/{idx}-{n}.play.m4a`, 폴더를 만들지 않음); `async def Engine.recording(rp_id, idx, n) -> Path`(사본, 실패하면 원본, 없으면 `NotFound`).

- [ ] **Step 1: 실패하는 시험을 쓴다**
  - `test_recording_is_served_as_a_play_copy`(test_api): 시도 뒤 녹음 주소가 200, `audio/mp4`, 내용이 원본과 다르고 `moov`가 앞, 원본 파일은 그대로, `rec/1-1.play.m4a`가 생김.
  - `test_two_requests_at_once_make_the_copy_once`: `play_cut`을 세는 가짜로 바꾸고 `asyncio.gather`로 두 번 부르면 한 번.
  - `test_a_failing_cut_serves_the_original`: `play_cut`이 `AudioError`를 던지면 원본 경로.
  - `test_the_copy_is_not_a_try`: 사본이 있어도 다음 시도 번호는 2이고 `find_rec(…, 2)`는 없음.
  - `test_the_copy_is_made_after_an_attempt`: 시도를 보낸 뒤 사본 파일이 생긴다(곁 작업이 끝나기를 기다린 뒤).
  - 지금 `test_recording_is_served_after_an_attempt`의 `r.content == speech_bytes`는 사본으로 바뀌어 맞지 않는다. 위 시험으로 바꾼다.
- [ ] **Step 2: 실패를 본다** — `cd server && uv run pytest tests/test_api.py tests/test_play_copy.py -q`.
- [ ] **Step 3: 구현한다** — 사본이 있으면 바로 내준다. 없으면 임시 폴더에 wav로 풀어(`to_wav16k`) `speech_span`을 재고 임시 파일로 자른 뒤 `os.replace`로 옮긴다. 진행 중인 작업은 사본 이름으로 나눠 쓴다(`tts.rate_file`과 같은 꼴). 실패는 `log.info("play copy failed: %s", type(e).__name__)`만 남기고 원본을 낸다. `_attempt`가 시도를 저장한 뒤 `asyncio.create_task`로 같은 함수를 부른다(평가를 늦추지 않음, 실패는 삼킴).
- [ ] **Step 4: 통과를 본다** — `cd server && uv run pytest -q`(전체).
- [ ] **Step 5: 커밋** — `feat(server): serve a play copy of each recording, made once`.

### Task 3: 소리 대기열의 이름표 (앱)

**Files:**
- Modify: `app/src/audio/player.ts`
- Test: `app/src/audio/player.test.ts`

**Interfaces:**
- Produces: `enqueue(src: AudioSource, tag?: string)`, `enqueuePause(ms: number, tag?: string)`, `nowTag(): { tag: string | null; since: number }`, `subscribeTag(cb: (now: { tag: string | null; since: number }) => void): () => void`. 이름표는 그 항목을 틀기 시작할 때 정해지고, 다음 항목의 이름표가 다르면 바뀐다(같으면 `since`를 바꾸지 않음). 대기열이 비거나 `clear()`면 `null`.

- [ ] **Step 1: 실패하는 시험을 쓴다** — `a tagged sound sets the tag until it finishes`, `a pair keeps its tag through the pause`, `clear drops the tag`, `an untagged sound after a tagged one clears it`, `the tag clears when the queue moves on without a finish`(지킴이 `STUCK_MS`), `listeners hear only changes`.
- [ ] **Step 2: 실패를 본다** — `cd app && npx jest src/audio/player.test.ts`.
- [ ] **Step 3: 구현한다** — 항목에 `tag`를 두고 `next()`에서 바꾼다. `Date.now()`는 바꿀 때만 읽는다.
- [ ] **Step 4: 통과를 본다** — 같은 명령.
- [ ] **Step 5: 커밋** — `feat(app): tag queued sounds with the button that asked for them`.

### Task 4: 누르기 규칙과 지금 울리는 이름표 (앱)

**Files:**
- Create: `app/src/flow/playTap.ts`, `app/src/flow/playTap.test.ts`, `app/src/audio/usePlayingTag.ts`

**Interfaces:**
- Consumes: Task 3의 `nowTag`, `subscribeTag`. `gate.ts`의 `TAP_HOLD_MS`(400).
- Produces: `playTap(now: { tag: string | null; since: number }, mine: string, at: number): "play" | "stop" | "ignore"`; `usePlayingTag(sounds: SoundQueue): string | null`(바뀔 때만 다시 그림).

- [ ] **Step 1: 실패하는 시험을 쓴다** — `a tap on a quiet button plays`, `a tap on the playing button stops it`, `a second tap within the hold is ignored`, `a tap on another button plays`.
- [ ] **Step 2: 실패를 본다** — `cd app && npx jest src/flow/playTap.test.ts`.
- [ ] **Step 3: 구현한다.**
- [ ] **Step 4: 통과를 본다.**
- [ ] **Step 5: 커밋** — `feat(app): decide play, stop or ignore for a play button tap`.

### Task 5: 🔊가 울리는 버튼 (앱 화면)

**Files:**
- Create: `app/src/ui/PlayIcon.tsx`
- Modify: `app/src/ui/InRowButton.tsx`, `app/src/ui/Button.tsx`(앞에 붙일 요소), `app/src/ui/Interpret.tsx`, `app/src/ui/useInterpret.ts`, `app/src/flow/koFetch.ts`(`play(audio, idx)`), `app/src/screens/RoleplayScreen.tsx`, `app/src/screens/EndScreen.tsx`
- Test: `npx jest`(koFetch 시험의 `play` 바뀜 포함), `npx tsc --noEmit`

**Interfaces:**
- Consumes: Task 3, 4.
- Produces: `PlayIcon({ on, style }: { on: boolean; style?: StyleProp<TextStyle> })` — `on`이면 Global Constraints의 움직임을 `Animated.loop`로(native driver), 아니면 그대로. 이름표 꼴: 대화 화면 `bubble:<history index>`, `rec:<rp>:<idx>:<n>`, `listen`, `jake`, `before`, `savedBefore`, `ko:<idx>`; 끝 화면 `line:<idx>`, `first:<idx>`, `try:<idx>:<n>`, `ko:<idx>`.

- [ ] **Step 1: `PlayIcon`을 쓰고, 🔊를 글자와 나눠 그린다** — `InRowButton`과 `Button`에 앞에 붙일 요소(`lead`)를 받게 한다. 「🔊 눌러서 (다시) 듣기」 안내는 🔊와 글을 한 줄에 나란히. 통역 줄의 🔊는 글 뒤 한 줄 안에서 울려야 하는데, 안드로이드에서 글 속 글자는 움직일 수 없으므로 글 블록 옆(아래쪽 정렬)에 따로 둔다.
- [ ] **Step 2: 화면을 잇는다** — 버튼마다 `playTap(nowTag, 이름표, Date.now())`로 정한다. `play`면 지금처럼 `sounds.clear()` 뒤 이름표를 붙여 넣고, `stop`이면 `sounds.clear()`. `koFetch`의 `play`가 줄 번호를 받아 `ko:<idx>`로 넣는다. 저절로 트는 소리는 이름표 없이 그대로.
- [ ] **Step 3: 확인한다** — `cd app && npx jest && npx tsc --noEmit`.
- [ ] **Step 4: 커밋** — `feat(app): bounce the 🔊 of the button whose sound is playing`.

### Task 6: 옆 포트 서버와 폰으로 확인

- [ ] **Step 1: main 세션에 폰을 쓴다고 알리고 답을 받는다.** 옆 포트 서버와 `adb reverse`로 붙는 시험 앱을 깔 것을 함께 알린다.
- [ ] **Step 2: 옆 포트 서버를 띄운다** — 원래 폴더 데이터의 복사본(소리 폴더 포함)을 스크래치패드에 두고 `JE_DATA_DIR`, `JE_HOST=127.0.0.1`, `JE_PORT=8795`, `JE_WHISPER_PORT=8796`.
- [ ] **Step 3: 시험 앱** — `app/.env`의 주소를 `http://127.0.0.1:8795`로 바꿔 빌드하고(커밋하지 않음), `adb reverse tcp:8795 tcp:8795`.
- [ ] **Step 4: 본다** — 시험 대화에서 학습자 목소리 녹음(지어낸 대사)을 넣고 평가를 받은 뒤:
  - 「🔊 내 녹음」: 누르자마자 🔊가 울리고, 앞 침묵 없이 목소리가 나오는지(재는 동안만 넣은 로그로 누름 → 재생 시작, 플레이어 위치). 끝나면 멈추는지.
  - 다시 누르면 멈추는지, 0.4초 안의 두 번째 누름은 무시되는지, 다른 🔊로 옮겨 가는지, 「🔊 다시 듣기」, 통역 줄, 끝 화면의 「🔊 처음 녹음」.
  - `adb shell screenrecord`로 「🔊 내 녹음」을 누르는 몇 초를 찍어 맥에 남기고 경로를 main 세션에 보낸다.
  - 맥의 사본이 원본보다 짧고 `moov`가 앞인지(`rec/`의 파일).
- [ ] **Step 5: 되돌린다** — `app/.env`를 원래대로, `adb reverse --remove`, main 판 앱을 다시 깐다, 옆 포트 서버를 멈추고 복사본을 지운다. 폰을 홈 화면으로, 화면 켜 둠을 끈다.

### Task 7: 문서

- [ ] PRD 「사용자 차례(역할극)」 듣기 줄에 한 줄과 맨 위 「고침」에 한 줄, 말하기 스펙 「녹음과 기록」에 듣기용 사본 한 줄, 듣기 스펙 6 아래 「바뀜」 한 줄.
- [ ] `docs/guide/`: 듣기 버튼 울림과 누르기, 녹음 앞 침묵을 잰 방법과 값, 사본, 겪은 것(새 APP 가이드 또는 기존 APP 가이드의 절). 색인.
- [ ] 할 일 `20261108_33_todo_play_button_feedback.md`를 이 브랜치 `docs/todo/`에 복사해 상태를 완료로.
- [ ] 커밋 — `docs: record the play button bounce and the recording play copy`.
