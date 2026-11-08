# 세 줄 소리 구분과 듣기 버튼 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 세 줄의 한글 발음 줄을 영어 줄과 나누고, 통역 줄에 「통역」 표를 달고, 대화 화면의 지나간 말풍선과 방금 녹음한 차례에서 소리를 다시 듣게 하고, 소리 버튼을 🔊로 맞춘다. 같은 화면의 통역 리뷰 작은 일도 함께 고친다.

**Architecture:** 서버는 녹음 평가 흐름의 `heard` 이벤트에 녹음 번호 `n`을 더한다. 앱은 그 번호를 차례(`heardRec`)와 대화 기록 말풍선(`Bubble.rec`)에 붙여 `api.recordingSource`로 튼다. 언제 틀 수 있는지는 `flow/`의 순수 함수(`mayListen`)와 소리 큐를 지켜보는 작은 모듈(`answerWatch`)이 정하고, 화면은 그것을 부른다.

**Tech Stack:** Python 3 + FastAPI(서버, `cd server && uv run pytest -q`), React Native + Expo + jest(앱, `cd app && npx jest && npx tsc --noEmit`). 새 꾸러미 없음.

**Spec:** `docs/superpowers/specs/2026-11-08-three-line-listen-design.md`

**실행 방식:** 이 세션이 직접 한다(executing-plans). 작업 대부분이 `RoleplayScreen.tsx` 한 파일과 그 둘레라, 작업마다 새 에이전트를 띄우면 같은 맥락을 다시 읽는 데 더 든다. 끝에 새 리뷰어 한 명이 브랜치 전체를 보고, PR을 열면 pr-review로 본다. 이 저장소는 머지 전까지 묻지 않으므로(`AGENTS.md` 「PR과 머지」) 고르는 것을 묻지 않았다.

## Global Constraints

- 한글 발음 줄: 글자 17, 색 `#4A6585`(`colors.pron`), 앞에 「발음」 표. 센 음절은 영어 줄과 같은 `colors.stress` 굵게, 약한 음절은 작은 `colors.weak`.
- 표 둘(「발음」, 「통역」)은 같은 부품, 같은 크기와 모양(글자 12 굵게 흰색, 둥근 8, 안쪽 여백 가로 6 세로 1). 「발음」 바탕 `colors.pron`, 「통역」 바탕 `colors.sohee`.
- 읽는 법의 `[[...]]`는 「…」로 보이고 `colors.pron` 굵게(700).
- 버튼 글귀(그대로 쓴다): 「🔊 듣기」, 「🔊 내 녹음」, 「🔊 처음 녹음」, 「🔊 다시 듣기」, 「🔊 눌러서 듣기」, 「🔊 눌러서 다시 듣기」, 통역 줄 끝 「 🔊」, 기다림 「통역하고 있어요…」, 실패 「지금은 통역할 수 없어요」.
- 화면에 보이는 한국어는 `keepWords`/`keepPieces`를 거친다(APP 가이드). 시험과 서버로 보내는 글은 거치지 않는다.
- 새 응답 필드는 선택으로 받는다: `n`이 없는 `heard`에서도 앱이 돈다.
- 시험 문장과 예는 지어낸다(`REVIEW.md` 「공개 저장소 노출」).
- 커밋 메시지는 영어 Conventional Commits, 본문에 이유와 시험 결과, 끝에 `Refs: docs/superpowers/specs/2026-11-08-three-line-listen-design.md`. AI 서명 줄 없음. git은 `/usr/bin/git`.

## Review Focus

1. **옛 서버(`n` 없음):** 「들린 말」은 보이고 「🔊 내 녹음」만 없다. 다른 버튼은 그대로 돈다. → Task 2 시험 `heard without n leaves no recording`.
2. **라이언의 대답이 끝난 뒤:** 마지막 문장이 끝나면 🔊가 다시 살아난다. 대답 중 「다시 듣기」로 끊은 경우에도 살아난다(소리 큐가 멈추면 풀린다). → Task 3 시험 `clears when the queue stops for any reason`.
3. **다시 해 보기 두 번:** 같은 줄의 두 말풍선이 각자 자기 녹음 번호를 튼다. → Task 2 시험 `each retry bubble keeps its own recording`.
4. **선생님 라이언 차례(aside):** 「🔊 내 녹음」은 차례 동안 보이고, 「다시 해 보기」 뒤 대화 기록에는 남지 않는다. → Task 2 시험 `an aside keeps its recording only while on screen`.
5. **통역 실패 뒤 다시 누르기:** 접힌 뒤 「통역 ›」을 누르면 다시 만들고, 3초가 지나기 전에 다시 눌러도 다시 만든다. → Task 5 시험 `a failure folds after FAIL_SHOW_MS and a tap asks again`.

---

### Task 1: 서버 `heard`에 녹음 번호

**Files:**
- Modify: `server/je_server/engine.py` (녹음 평가 흐름의 `yield {"type": "heard", ...}`)
- Modify: `contract/attempt-events.ndjson` (첫 줄 `heard`)
- Test: `server/tests/test_engine.py`

**Interfaces:**
- Produces: `heard` 이벤트 `{"type": "heard", "text": str, "followed": bool, "n": int}`. `n`은 `Store.next_rec`가 준 번호이고, 이벤트를 보내기 전에 녹음 파일이 이미 있다.

- [ ] **Step 1: 실패하는 시험** — 녹음 평가를 같은 줄에 두 번 보내 `heard`의 `n`이 1, 2이고, `engine.recording(rp_id, idx, n)`이 그 파일을 찾는지 본다. 이름: `test_heard_carries_the_recording_number`. 같은 파일의 기존 녹음 평가 시험이 쓰는 고정물(fake whisper, speech bytes)을 그대로 쓴다.
- [ ] **Step 2:** `cd server && uv run pytest -q tests/test_engine.py -k recording_number` → 실패(`KeyError: 'n'`).
- [ ] **Step 3:** `heard`에 `"n": n`을 더한다. `contract/attempt-events.ndjson`의 `heard` 예에 `"n": 1`을 더한다.
- [ ] **Step 4:** `uv run pytest -q` 전체 통과.
- [ ] **Step 5:** 커밋 `feat(server): send the recording number with the heard event`.

### Task 2: 앱 상태에 녹음 번호와 듣기 조건

**Files:**
- Modify: `app/src/api/types.ts` (`AttemptEvent`의 `heard`)
- Modify: `app/src/flow/state.ts` (`Bubble`, `State`, `initial`, `freshTurn`, `exchange`, 이벤트 처리, 새 `mayListen`)
- Modify: `app/src/flow/interpret.ts` (`mayReplay`)
- Test: `app/src/flow/state.test.ts`, `app/src/flow/interpret.test.ts`

**Interfaces:**
- Produces:
  - `AttemptEvent` `{ type: "heard"; text: string; followed: boolean; n?: number }`
  - `Bubble.rec?: TryRef` — 그 차례의 녹음(`{ rp_id, idx, n }`).
  - `State.heardRec: TryRef | null` — 지금 차례의 녹음. `freshTurn`이 비운다. `heard` 이벤트가 `n`이 있을 때 `{ rp_id: s.roleplay.id, idx: s.line.idx, n }`로 채운다.
  - `exchange(s)`의 내 말풍선에 `rec: s.heardRec ?? undefined`.
  - `mayListen(phase: Phase, answering: boolean): boolean` = `canReplay(phase) && !answering`.
  - `mayReplay(where: Where, phase: Phase, answering: boolean): boolean` — 끝 화면은 언제나 true, 대화 화면은 `mayListen`.

- [ ] **Step 1: 실패하는 시험**
  - `heard with n keeps the recording of this turn`: 평가 중 `heard`(`n: 3`) → `heardRec`가 `{ rp_id: 역할극 id, idx: 줄 idx, n: 3 }`.
  - `heard without n leaves no recording`: `heardRec`가 `null`, `heard` 글은 그대로.
  - `each retry bubble keeps its own recording`: `heard`(n 1) → done → again → 녹음 → `heard`(n 2) → done → next. 대화 기록의 내 말풍선 둘의 `rec.n`이 1, 2.
  - `an aside keeps its recording only while on screen`: `heard`(followed false, n 4) → done(issues 0) → `heardRec.n`이 4 → again → 대화 기록에 내 말풍선 없음, `heardRec`가 `null`.
  - `mayListen`: ready·evaluated에서 answering false면 true, answering true면 false, recording·evaluating·ryan·loading에서는 false.
  - `interpret.test.ts`: `mayReplay("roleplay", "evaluated", true)`가 false, `mayReplay("end", "loading", true)`가 true.
- [ ] **Step 2:** `cd app && npx jest src/flow` → 새 시험 실패.
- [ ] **Step 3:** 위 Interfaces대로 고친다. `mayReplay`를 부르는 곳(`RoleplayScreen`)은 Task 6에서 `answering`을 넘긴다. 이 작업에서는 `false`를 넘겨 타입만 맞춘다.
- [ ] **Step 4:** `npx jest && npx tsc --noEmit` 통과.
- [ ] **Step 5:** 커밋 `feat(app): keep the recording number of each turn and bubble`.

### Task 3: 라이언의 대답이 나오는 동안 알기

**Files:**
- Create: `app/src/audio/answerWatch.ts`, `app/src/audio/answerWatch.test.ts`
- Create: `app/src/audio/useAnswering.ts`

**Interfaces:**
- Consumes: `SoundQueue.subscribe(cb: (playing: boolean) => void): () => void`, `SoundQueue.isPlaying(): boolean`
- Produces:
  - `createAnswerWatch(sounds: Pick<SoundQueue, "subscribe" | "isPlaying">, onChange: (answering: boolean) => void): { mark(): void; stop(): void }` — `mark()`은 대답의 소리를 큐에 넣은 직후 부른다. 큐가 재생 중이면 answering이 true가 된다. 큐가 멈추면(다 틀었거나 `clear()`) false가 된다. 같은 값으로는 `onChange`를 다시 부르지 않는다.
  - `useAnswering(sounds: SoundQueue): { answering: boolean; mark: () => void }` — 위를 React 상태로 감싼다. 화면이 사라지면 `stop()`.

- [ ] **Step 1: 실패하는 시험**(가짜 큐: `subscribe`로 받은 콜백을 시험이 부른다)
  - `mark while playing turns answering on`
  - `clears when the queue stops for any reason`: mark 뒤 콜백(false) → onChange(false).
  - `mark while nothing plays stays off`: 큐가 이미 멈춘 뒤의 mark는 false 그대로.
  - `stop unsubscribes`: stop 뒤 콜백을 불러도 onChange 없음.
- [ ] **Step 2:** `npx jest src/audio/answerWatch` → 실패.
- [ ] **Step 3:** 구현.
- [ ] **Step 4:** `npx jest && npx tsc --noEmit` 통과.
- [ ] **Step 5:** 커밋 `feat(app): know while Ryan's answer is playing`.

### Task 4: 세 줄의 발음 줄과 표

**Files:**
- Create: `app/src/ui/Tag.tsx`
- Modify: `app/src/ui/theme.ts` (`pron`)
- Modify: `app/src/ui/threeLineSegments.ts` (`Style`, `readingSegments`)
- Modify: `app/src/ui/ThreeLine.tsx`
- Test: `app/src/ui/threeLineSegments.test.ts`

**Interfaces:**
- Produces:
  - `Tag({ label, color }: { label: string; color: string })` — Global Constraints의 표 모양. 줄 앞에 둘 때는 `flexDirection: "row"`인 줄 안에서 글과 나란히 놓는다(지금 `KoLine`의 `line`, `tag` 모양).
  - `colors.pron = "#4A6585"`
  - `Style = "strong" | "weak" | "plain" | "sound"`; `readingSegments(reading: string): Seg[]` — `[[x]]`는 `{ text: "「x」", style: "sound" }`, 그 사이 글은 `plain`. 빈 조각은 빼고, 앞뒤 공백은 지금처럼 다듬는다.

- [ ] **Step 1: 실패하는 시험** — 기존 `reading refs show as corner brackets`를 고친다: `readingSegments("앞을 세게, [[카-피]].")`가 `[{ text: "앞을 세게, ", style: "plain" }, { text: "「카-피」", style: "sound" }, { text: ".", style: "plain" }]`. `[[터]]`로 시작하는 글이 `sound`로 시작하는지, `""`가 `[]`인지도 본다.
- [ ] **Step 2:** `npx jest src/ui/threeLineSegments` → 실패.
- [ ] **Step 3:** `readingSegments`를 고치고, `ThreeLineView`를 고친다. 한글 줄은 `[Tag 발음][Text: Pieces size 17, color pron]`인 가로 줄, 읽는 법은 조각마다 `Text`(sound는 `colors.pron`, 700)이고 `keepPieces`로 낱말을 잇는다.
- [ ] **Step 4:** `npx jest && npx tsc --noEmit` 통과.
- [ ] **Step 5:** 커밋 `feat(app): set the Korean pronunciation line apart from the English`.

### Task 5: 통역 줄의 「통역」 표와 실패 안내 접기

**Files:**
- Modify: `app/src/ui/Interpret.tsx`
- Modify: `app/src/flow/interpret.ts` (`KoEntry`, `koView`)
- Modify: `app/src/flow/koFetch.ts` (`FAIL_SHOW_MS`, 실패 뒤 접기)
- Test: `app/src/flow/interpret.test.ts`, `app/src/flow/koFetch.test.ts`

**Interfaces:**
- Consumes: `Tag` (Task 4)
- Produces: `KoEntry = Ko | "loading" | "failed" | "folded"`; `koView("folded", open)`은 `"closed"`; `export const FAIL_SHOW_MS = 3000` (koFetch.ts). 실패하면 `"failed"`를 두고, `FAIL_SHOW_MS` 뒤에도 그대로 `"failed"`면 `"folded"`로 바꾼다. 다음 열기는 지금처럼 다시 만든다.

- [ ] **Step 1: 실패하는 시험**(jest 가짜 타이머)
  - `a failure folds after FAIL_SHOW_MS and a tap asks again`: 실패 → `"failed"` → 시간이 지나면 `"folded"` → `koView`는 `"closed"` → 다시 `open` → `getKo` 두 번째 호출, `"loading"`.
  - `a new opening before the fold is not folded by the old timer`: 실패 → 1초 뒤 다시 open → 성공 → 3초가 지나도 `Ko` 그대로.
  - `interpret.test.ts`: `koView("folded", true)`가 `"closed"`, `koOpensOnTap("closed")`가 true.
- [ ] **Step 2:** `npx jest src/flow` → 실패.
- [ ] **Step 3:** 구현. `KoLine`은 표를 `Tag label="통역" color={colors.sohee}`로, 기다림을 「통역하고 있어요…」로, 끝의 「 ▶」를 「 🔊」로 바꾼다. 파일 맨 위 주석의 「소희」 태그 설명도 고친다.
- [ ] **Step 4:** `npx jest && npx tsc --noEmit` 통과.
- [ ] **Step 5:** 커밋 둘로 나눈다: `feat(app): label the interpretation line 통역 instead of Sohee` (Interpret.tsx), `fix(app): fold the interpretation failure note after a few seconds` (interpret.ts, koFetch.ts와 시험).

### Task 6: 대화 화면 말풍선을 함수로 그리기 (할 일 20261106_10의 3)

**Files:**
- Modify: `app/src/screens/RoleplayScreen.tsx`

**Interfaces:**
- Produces: 화면 안의 `Ko`, `RyanBubble`, `MyBubble`이 부품(`<RyanBubble/>`)이 아니라 함수(`ryanBubble({...})`, `myBubble(...)`, `koLine(idx)`)로 불린다. 목록에서 부를 때 `key`는 바깥 `Named`에 준다. 하는 일은 바꾸지 않는다.

- [ ] **Step 1:** 세 부품을 함수로 바꾼다. 훅을 부르지 않는 것을 확인한다.
- [ ] **Step 2:** `npx jest && npx tsc --noEmit` 통과. 화면 시험 도구가 없어 동작은 Task 9의 폰 확인에서 본다.
- [ ] **Step 3:** 커밋 `refactor(app): draw the roleplay bubbles with plain functions`(본문: 그릴 때마다 새 부품이 되어 말풍선이 다시 만들어지던 것, 할 일 20261106_10의 3).

### Task 7: 대화 화면의 듣기 버튼

**Files:**
- Modify: `app/src/screens/RoleplayScreen.tsx`

**Interfaces:**
- Consumes: `State.heardRec`, `Bubble.rec`, `mayListen`, `mayReplay(where, phase, answering)` (Task 2), `useAnswering` (Task 3), `InRowButton`, `api.audioSource(key, rate)`, `api.recordingSource(rp_id, idx, n)`

- [ ] **Step 1: 대답 알기** — `useAnswering(sounds)`를 두고, `sendRec`의 `onEvent`에서 대답 소리(`audio`, 소리가 있는 `error`)를 큐에 넣은 직후 `mark()`를 부른다. `listenOk = mayListen(state.phase, answering)`.
- [ ] **Step 2: 지나간 라이언 말풍선** — 펼친 말풍선의 버튼 줄 맨 앞에 `InRowButton label="🔊 듣기" dim={!listenOk}`. 줄의 `audio`가 없거나 라이언 차례의 말풍선(`row`가 없는 것)이면 두지 않는다. 누르면 `listenOk`일 때만 `sounds.clear()` 뒤 `api.audioSource(audio, rate)`.
- [ ] **Step 3: 지나간 내 말풍선** — 펼친 말풍선의 버튼 줄 맨 앞에 「🔊 듣기」(그 줄의 본보기, `lineAt(idx)?.audio`, `rate`). 「들린 말」 줄을 가로 줄로 바꿔 오른쪽에 `b.rec`가 있을 때 「🔊 내 녹음」(`api.recordingSource`). 둘 다 `dim={!listenOk}`이고 막힐 때는 무시한다.
- [ ] **Step 4: 지금 차례** — `state.heard` 줄을 가로 줄로 바꿔, `state.heardRec`가 있으면 오른쪽에 「🔊 내 녹음」(같은 규칙).
- [ ] **Step 5: 다른 말풍선 소리** — `playBefore`, `replayJake`, `useInterpret`의 `allow`(대화 화면의 다시 듣기)가 `mayListen`/`mayReplay(..., answering)`을 쓴다. 안내 글을 「🔊 눌러서 듣기」, 「🔊 눌러서 다시 듣기」로, 아래 버튼을 「🔊 다시 듣기」로 바꾼다(아래 버튼은 막지 않는다). `PractiseLink` 주석을 지금 동작에 맞게 고친다(할 일 20261106_10의 4).
- [ ] **Step 6:** `npx jest && npx tsc --noEmit` 통과.
- [ ] **Step 7:** 커밋 `feat(app): play past bubbles and the turn just recorded in the roleplay`.

### Task 8: 끝 화면 🔊

**Files:**
- Modify: `app/src/screens/EndScreen.tsx`

- [ ] **Step 1:** 「▶ 듣기」 → 「🔊 듣기」, 「▶ 처음 녹음」 → 「🔊 처음 녹음」, 「▶ 내 녹음」 → 「🔊 내 녹음」. 내 줄(`MyLine`)의 버튼 줄 맨 앞에 「🔊 듣기」(`l.line.audio`가 있을 때, 1배). 주석의 ▶도 고친다.
- [ ] **Step 2:** `npx jest && npx tsc --noEmit` 통과.
- [ ] **Step 3:** 커밋 `feat(app): mark every play button on the end screen with 🔊`.

### Task 9: 서버 주석과 로그 (할 일 20261106_10의 4)

**Files:**
- Modify: `server/je_server/tts_worker.py` (맨 위 약속의 `"voice"` 값 목록: 지금 받는 값을 `tts.py`의 `WORKER_VOICE`와 맞춘다)
- Modify: `server/je_server/engine.py` (`_quiet`의 로그 글을 통역, 세 줄, 소리 준비를 모두 덮는 글로)

- [ ] **Step 1:** 고친다. sohee-prepared 카드가 이 두 곳을 고치는지 main 세션에 들은 것이 있으면 그쪽에 맞춘다.
- [ ] **Step 2:** `uv run pytest -q` 통과(로그 글을 보는 시험이 있으면 함께 고친다).
- [ ] **Step 3:** 커밋 `docs(server): bring the voice worker protocol and prep log up to date`.

### Task 10: 문서

**Files:**
- Modify: `docs/PRD.md` (「사용자 차례(역할극)」 세 줄 표시, 「통역」 표, 「역할극 뒤 연습과 주고받은 말 보기」 듣기)
- Modify: `docs/superpowers/specs/2026-11-06-korean-translation-design.md` (맨 위에 이 스펙이 「소희」 이름표를 「통역」 표로 바꿨다는 줄, 21·77·172줄 둘레)
- Modify: `docs/guide/PRONUNCIATION_한글발음_세줄표시_20261105.md` (「무엇을 보여 주나」 2)

- [ ] **Step 1:** 고친다. PRD에는 이 스펙 경로와 사용자 말을 적고, 내용은 스펙을 되풀이하지 않는다.
- [ ] **Step 2:** 커밋 `docs: record the pronunciation tag, the 통역 tag and the listen buttons`.

### Task 11: 폰 확인

- [ ] **Step 1: APK** — `app/README.md`대로 빌드한다(JDK 17, `-PreactNativeArchitectures=arm64-v8a`, `ANDROID_HOME`). 사용자에게 이 카드의 앱을 깐다고 알린 뒤 `adb install -r`.
- [ ] **Step 2: 서버 바꾸기** — 같이 도는 카드(main 세션 경유)에 알리고, `docs/guide/DEVENV_맥서버_저절로_띄우기_20261107.md` 「카드가 서버를 시험할 때」대로 원래 폴더 서버를 멈추고 이 worktree 서버를 띄운다.
- [ ] **Step 3: 화면** — 「이 상황 다시 하기」로 만든 복사본에서 adb로 본다(`docs/guide/DEVENV_폰을_adb로_시험하기_20261108.md`): 세 줄(발음 표, 색, 크기), 통역 표와 기다림 글, 🔊 버튼 자리. 스크린샷은 저장소 밖에 둔다.
- [ ] **Step 4: 녹음** — 학습자 목소리로 지어낸 문장을 만들어 맥 스피커로 틀고 폰에서 말하기를 누른다. 「🔊 내 녹음」, 지나간 말풍선의 「🔊 듣기」와 「🔊 내 녹음」을 누르고 `logcat`의 `AudioTrack ... frames delivered`로 끝까지 났는지 센다. 대답이 나오는 동안 🔊가 흐리고 소리가 나지 않는지 본다. 통역을 눌러 소리까지 걸린 시간을 서버 로그로 잰다(할 일 20261106_10의 6).
- [ ] **Step 5: 되돌리기** — worktree 서버를 끄고 `autostart.sh start`. 시험 복사본과 녹음 파일을 지운다.
- [ ] **Step 6:** 겪은 문제는 APP 가이드에, 폰 시험 노하우는 원래 폴더 `docs/private/wiki-outbox.md`에 적는다.

### Task 12: 마무리

- [ ] 할 일 두 파일의 상태 줄을 「완료」로 고쳐 마지막 커밋에 넣는다(`20261106_10`은 2, 5를 닫은 이유를 적는다).
- [ ] 새 리뷰어 한 명이 브랜치 전체를 본다(`REVIEW.md`, `AGENTS.md`를 함께 넘긴다). 고친다.
- [ ] push, PR(본문 「사용자: 추천대로」), pr-review, devlog, 머지 결정을 묻는다.
