# 녹음 중 알리기와 말이 없을 때 취소 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 녹음이 켜지고, 끝나고, 취소될 때 소리와 진동으로 알린다. 녹음하는 동안 「● 말하기 끝」의 깜빡이는 빨간 동그라미와 얇은 목소리 줄을 보인다. 첫 내 차례에는 「🎤를 누르고 말하세요」를 보이고, 말소리 없이 몇 초가 지나면 녹음을 버린다.

**Architecture:** 소리는 앱이 코드로 만든 WAV를 폰 임시 폴더에 써 두고 튼다(`cueSound.ts`는 순수 함수, `cues.ts`는 파일과 플레이어와 진동). `useRecorder`가 시작 소리 뒤에 마이크를 켜고, 0.1초마다 마이크 크기를 읽어 목소리 줄에 넘기고, 말소리 지켜보기(`speechWatch.ts`, 순수 함수)가 「조용함」을 내면 화면이 준 `onNoSpeech`를 부른다. 화면은 저절로 취소를 「취소」와 같은 게이트 길(`runThenHold`)로 보내고, 안내와 「말소리가 없어」 글은 리듀서가 정한다. 맥 서버는 바꾸지 않는다.

**Tech Stack:** React Native 0.88 + Expo SDK 58(`expo-audio`, `expo-file-system`, RN `Vibration`), jest(`cd app && npx jest && npx tsc --noEmit`). 새 꾸러미 없음. 앱 권한에 `VIBRATE`만 더한다.

**Spec:** `docs/superpowers/specs/2026-11-08-record-feedback-design.md`

**실행 방식:** 이 세션이 직접 한다(executing-plans). 작업이 `useRecorder`, `RoleplayScreen.tsx`, `flow/` 둘레로 서로 기대고, 마지막 작업은 폰에서 재어 값을 고치는 일이라 한 세션이 이어 하는 편이 낫다. 끝에 새 리뷰어 한 명이 브랜치 전체를 보고, PR을 열면 pr-review로 본다. 이 저장소는 머지 전까지 묻지 않으므로(`AGENTS.md` 「PR과 머지」) 고르는 것을 묻지 않았다.

## Global Constraints

- 화면 글귀(그대로 쓴다): 녹음 중 큰 버튼 「● 말하기 끝」(마이크가 켜지기 전에는 「말하기 끝」), 안내 「🎤를 누르고 말하세요」, 50초 뒤 「녹음이 곧 끝나요」, 저절로 취소 뒤 「말소리가 없어 녹음을 멈췄어요.」. 다른 버튼 글귀는 그대로다.
- 「말하기 끝」 버튼은 `kind="primary"` 파랑 그대로. 빨간 동그라미는 `colors.danger` 계열(흰 테두리), 목소리 줄은 연한 하늘색. 띠와 흐르는 초는 없다. 버튼 색 가이드의 세 모양은 바꾸지 않는다.
- 소리 A: 시작 659Hz 80ms + 쉼 20ms + 880Hz 110ms, 끝은 그 반대 순서, 취소 392Hz 260ms. 가장 큰 값은 0.5(-6dBFS)를 넘지 않는다. 저장소에 소리 파일을 넣지 않는다(커밋 전 검사가 막는다).
- 진동: 시작 50ms 한 번, 끝 50ms 두 번(사이 80ms), 취소 180ms 한 번.
- 55초 상한(`RECORD_LIMIT_MS`)은 그대로. 「녹음이 곧 끝나요」는 마이크가 켜진 지 50초부터.
- 말이 없을 때: 처음 값 N = 8초, L = 0.2초, T는 Task 6에서 폰으로 재어 정한다. 말소리를 놓쳐 녹음을 버리는 것보다 조용한 녹음이 맥에 가는 편이 낫다(스펙 「실패로 볼 것」 2).
- 맥 서버, API, 계약 예시(`contract/`)는 바꾸지 않는다.
- 화면에 보이는 한국어 문장은 `keepWords`를 거친다(APP 가이드). 시험 문장은 지어낸다(`REVIEW.md`).
- 폰 시험은 main 세션에 먼저 알리고, 누르기 전마다 앞에 뜬 앱이 `dev.jakeso.english`인지 본다. 맥 스피커로 넣은 시험 기록은 바로 지우고 받아쓴 글을 옮기지 않는다.
- 커밋 메시지는 영어 Conventional Commits, 본문에 이유와 시험 결과, 끝에 `Refs: docs/superpowers/specs/2026-11-08-record-feedback-design.md`. AI 서명 줄 없음. git은 `/usr/bin/git`, `git add`는 파일을 지정한다.

## Review Focus

1. **마이크 크기를 못 읽는 폰:** `metering`이 늘 없으면(`undefined`) 모든 녹음이 8초에 버려진다. 크기를 한 번도 읽지 못했으면 저절로 취소하지 않아야 한다. → Task 2 시험 `never silent when no level ever came`.
2. **녹음을 시작하자마자 낸 큰 소리 하나:** 버튼을 누른 소리나 폰을 건드린 소리 하나는 말소리가 아니다. 그 뒤 조용하면 취소한다. → Task 2 시험 `one loud reading is not speech`.
3. **말한 뒤 조용히 기다리기:** 말하고 나서 「말하기 끝」을 누르기 전에 오래 조용해도 취소하면 안 된다. → Task 2 시험 `once speech is heard it never turns silent`.
4. **저절로 취소와 「■ 말하기 끝」이 겹침:** 먼저 게이트에 든 쪽만 하고, 보내는 녹음은 지우지 않는다. 취소가 먼저면 그 자리에 다시 그린 「🎤 말하기」를 같은 때의 누름이 켜지 않는다. → Task 4 시험 `a silent cancel while a stop runs does nothing` 과 `a tap right after a silent cancel starts nothing`.
5. **시작 소리를 내지 못함:** 플레이어를 못 만들었거나 끝났다는 알림이 오지 않아도 마이크는 소리 길이 뒤에 켜진다. → Task 4 시험 `waitForEnd gives up after the cap`.

---

### Task 1: 소리를 코드로 만들기

**Files:**
- Create: `app/src/audio/cueSound.ts`
- Test: `app/src/audio/cueSound.test.ts`

**Interfaces:**
- Produces: `export type Cue = "start" | "end" | "cancel";`, `export const CUE_RATE = 22050;`, `export function cueSamples(cue: Cue): Float32Array`(-1~1), `export function cueWav(cue: Cue): Uint8Array`(44바이트 머리 + 16비트 모노 PCM), `export function cueMs(cue: Cue): number`.

- [ ] **Step 1: 실패하는 시험을 쓴다**

```ts
test("each cue is a 16-bit mono WAV at CUE_RATE", () => {
  for (const cue of ["start", "end", "cancel"] as const) {
    const w = cueWav(cue);
    const text = (a: number, b: number) => String.fromCharCode(...w.slice(a, b));
    const v = new DataView(w.buffer);
    expect(text(0, 4)).toBe("RIFF");
    expect(text(8, 12)).toBe("WAVE");
    expect(v.getUint16(22, true)).toBe(1); // channels
    expect(v.getUint32(24, true)).toBe(CUE_RATE);
    expect(v.getUint16(34, true)).toBe(16);
    expect(v.getUint32(40, true)).toBe(cueSamples(cue).length * 2);
  }
});

test("cue lengths: start and end 210 ms, cancel 260 ms", () => {
  expect(cueMs("start")).toBe(210);
  expect(cueMs("end")).toBe(210);
  expect(cueMs("cancel")).toBe(260);
  expect(Math.abs(cueSamples("cancel").length - 0.26 * CUE_RATE)).toBeLessThanOrEqual(1);
});

test("no cue is louder than half scale", () => {
  for (const cue of ["start", "end", "cancel"] as const) expect(Math.max(...cueSamples(cue).map(Math.abs))).toBeLessThanOrEqual(0.5);
});

// zero crossings in the first and last 60 ms tell the pitch: start goes up, end goes down, cancel is the lowest
test("start rises, end falls, cancel is low", () => {
  const crossings = (s: Float32Array, from: number, to: number) => { /* count sign changes in [from, to) */ };
  const ms = (n: number) => Math.round((n / 1000) * CUE_RATE);
  const s = cueSamples("start"), e = cueSamples("end"), c = cueSamples("cancel");
  expect(crossings(s, 0, ms(60))).toBeLessThan(crossings(s, s.length - ms(60), s.length));
  expect(crossings(e, 0, ms(60))).toBeGreaterThan(crossings(e, e.length - ms(60), e.length));
  expect(crossings(c, ms(20), ms(80))).toBeLessThan(crossings(s, 0, ms(60)));
});
```

- [ ] **Step 2: 시험이 실패하는지 본다** — `cd app && npx jest src/audio/cueSound.test.ts` → 모듈이 없어 실패.
- [ ] **Step 3: `cueSound.ts`를 쓴다** — 음 하나는 사인파에 4ms 올림, 지수 감쇠(시작과 끝의 음은 초당 8과 10, 취소는 9), 끝 20ms 내림을 곱한 것. 크기는 시작과 끝 0.5, 취소 0.45. 초안을 만든 스크립트와 같은 값이다. WAV 머리는 표준 PCM(fmt 16바이트, 포맷 1).
- [ ] **Step 4: 시험이 통과하는지 본다** — 같은 명령, 4개 통과.
- [ ] **Step 5: 커밋** — `feat(app): synthesize recording cue sounds in code`. 본문에 소리 파일을 커밋하지 않는 이유(커밋 전 검사)를 적는다.

### Task 2: 말소리 지켜보기와 목소리 줄 길이

**Files:**
- Create: `app/src/flow/speechWatch.ts`, `app/src/ui/voiceLevel.ts`
- Modify: `app/src/config.ts`(`SOON_ENDS_MS`)
- Test: `app/src/flow/speechWatch.test.ts`, `app/src/ui/voiceLevel.test.ts`

**Interfaces:**
- Produces:
  - `export type SpeechRule = { level: number; loudMs: number; waitMs: number; skipMs: number };` `export const SPEECH_RULE: SpeechRule = { level: -40, loudMs: 200, waitMs: 8000, skipMs: 300 };`(level과 waitMs는 Task 6에서 고친다)
  - `export type Heard = "listening" | "speech" | "silent";` `export function createSpeechWatch(rule?: SpeechRule): { feed(atMs: number, db: number | undefined): Heard }` — `atMs`는 마이크가 켜진 뒤 지난 시간, `db`는 그때 읽은 크기(dBFS, 없으면 `undefined`).
  - `export const LINE_FLOOR_DB = -50, LINE_TOP_DB = -15, LINE_MIN = 0.08;` `export function voiceShare(db: number | undefined): number`(0~1, 바닥 아래와 `undefined`는 `LINE_MIN`, 꼭대기 위는 1, 사이는 dB에 비례).
  - `config.ts`: `export const SOON_ENDS_MS = 50_000;`

- [ ] **Step 1: 실패하는 시험을 쓴다** (`speechWatch.test.ts`, 0.1초마다 `feed`하는 작은 도우미 `run(levels: (number | undefined)[], rule?)`로 마지막 결과를 본다)

```ts
const rule = { level: -40, loudMs: 200, waitMs: 8000, skipMs: 300 };
test("quiet turns silent at waitMs, not before", () => { /* -60 every 100 ms: "listening" at 7900, "silent" at 8000 */ });
test("one loud reading is not speech", () => { /* -20 once at 1000, else -60: "silent" at 8000 */ });
test("loud readings adding up to loudMs are speech", () => { /* -20 at 1000, 1100: "speech" from 1100 */ });
test("once speech is heard it never turns silent", () => { /* speech at 1100, then -60 to 20000: "speech" */ });
test("readings before skipMs do not count", () => { /* -20 at 100, 200, then -60: "silent" at 8000 */ });
test("never silent when no level ever came", () => { /* undefined every 100 ms to 20000: "listening" */ });
test("a long gap between readings counts at most 250 ms of loud", () => { /* -20 at 1000, next -20 at 5000 after nothing: loud is 100 + 250 */ });
```

`voiceLevel.test.ts`: `voiceShare(-80)`과 `voiceShare(undefined)`는 `LINE_MIN`, `voiceShare(-5)`는 1, `voiceShare(-32.5)`는 `LINE_MIN`과 1 사이(가운데쯤).

- [ ] **Step 2: 시험이 실패하는지 본다** — `cd app && npx jest src/flow/speechWatch.test.ts src/ui/voiceLevel.test.ts`.
- [ ] **Step 3: 구현한다** — 시끄러운 시간은 `db >= level`인 읽기마다 「지난 읽기와의 간격」을 더한다(간격은 250ms를 넘지 않게 자른다). 첫 읽기는 100ms로 친다. 숫자인 읽기가 한 번이라도 와야 `silent`가 된다. 한 번 `speech`면 계속 `speech`.
- [ ] **Step 4: 시험이 통과하는지 본다** — 같은 명령.
- [ ] **Step 5: 커밋** — `feat(app): watch the mic level for speech and draw it as a line`.

### Task 3: 리듀서 — 첫 차례 안내와 말이 없어 취소

**Files:**
- Modify: `app/src/flow/state.ts`
- Test: `app/src/flow/state.test.ts`

**Interfaces:**
- Consumes: 없음.
- Produces: `State.micUsed: boolean`(처음 `false`), `Action` `{ type: "noSpeech" }`, `export const NO_SPEECH = "말소리가 없어 녹음을 멈췄어요.";`, `export function showMicHint(s: State): boolean`.

- [ ] **Step 1: 실패하는 시험을 쓴다**

```ts
describe("first-turn hint and the silent cancel (spec record-feedback 3, 4)", () => {
  test("the hint shows on my turn before the mic was ever used", () => {
    expect(showMicHint(at("ready"))).toBe(true);
    expect(showMicHint(at("recording"))).toBe(false);
  });
  test("it goes for good once the mic starts, even after a cancel", () => {
    const started = reduce(at("ready"), { type: "recordStart" });
    expect(started.micUsed).toBe(true);
    expect(showMicHint(reduce(started, { type: "recordCancel" }))).toBe(false);
  });
  test("a skip keeps it for the next turn", () => { /* at("ready") → skip → micUsed false */ });
  test("not on Ryan's turn", () => { /* phase "ryan" → false */ });
  test("a new roleplay, a practice from the end, a saved practice and a mid-roleplay line all start without it used", () => {
    /* created, restarted, startPractice, startSaved, practiseLine from micUsed true → micUsed false */
  });
  test("back from a mid-roleplay line keeps the roleplay's, or takes the practice's if the mic was used there", () => {
    /* practiseLine from micUsed false → recordStart in the practice → endPractice → micUsed true */
  });
  test("noSpeech goes back to before speaking with the notice, in the same mode", () => {
    const s = reduce(at("recording", { mode: "retry" }), { type: "noSpeech" });
    expect(s.phase).toBe("ready");
    expect(s.mode).toBe("retry");
    expect(s.message).toBe(NO_SPEECH);
  });
  test("noSpeech outside recording does nothing", () => { /* at("evaluating") → same object */ });
  test("the notice goes at the next start", () => { /* noSpeech → recordStart → message null */ });
});
```

- [ ] **Step 2: 시험이 실패하는지 본다** — `cd app && npx jest src/flow/state.test.ts`.
- [ ] **Step 3: 구현한다** — `recordStart`가 `micUsed: true`. `startPractice`, `practiseLine`은 `micUsed: false`(`created`, `restarted`, `startSaved`는 `initial`에서 오므로 그대로 된다). `leavePractice`의 역할극 복귀는 `micUsed: s.resume.micUsed || s.micUsed`. `noSpeech`는 `recording`에서만 `{ phase: "ready", message: NO_SPEECH }`. `showMicHint`는 `canSkip`이 쓰는 「말할 줄」 조건(`toSay`)과 `phase === "ready"`와 `!micUsed`.
- [ ] **Step 4: 시험이 통과하는지 본다** — 같은 명령, 그리고 `npx tsc --noEmit`.
- [ ] **Step 5: 커밋** — `feat(app): add the first-turn mic hint and the no-speech cancel to the flow`.

### Task 4: 소리와 진동, 녹음기

**Files:**
- Create: `app/src/audio/cues.ts`, `app/src/audio/cues.test.ts`
- Modify: `app/src/audio/useRecorder.ts`, `app/App.tsx`, `app/app.json`
- Test: `app/src/flow/gate.test.ts`(겹침 시험만 더함)

**Interfaces:**
- Consumes: Task 1의 `Cue`, `cueWav`, `cueMs`. Task 2의 `createSpeechWatch`.
- Produces:
  - `cues.ts`: `export const VIBRATE: Record<Cue, number | number[]> = { start: 50, end: [0, 50, 80, 50], cancel: 180 };` `export function waitForEnd(listen: (done: () => void) => () => void, capMs: number): Promise<void>`(알림이나 시간 넘김 중 먼저 온 것에 끝나고, 듣기를 끊는다) `export async function prepareCues(): Promise<void>`(세 소리를 `Paths.cache`의 `cue-<이름>.wav`에 쓰고 플레이어를 만든다, 실패는 삼킨다) `export function playCue(cue: Cue): Promise<void>`(진동하고 소리를 처음부터 튼다. 끝나면, 또는 `cueMs + 300`ms 뒤에 끝난다. 플레이어가 없거나 오류면 `cueMs` 뒤에 끝난다).
  - `useRecorder()`가 돌려주는 것에 더함: `start(onAutoStop: () => void, opts?: { onNoSpeech?: () => void }): Promise<void>`, `cancel(): Promise<void>`(`discard` + 취소 소리, 버릴 녹음이 없으면 소리도 없음), `live: boolean`(마이크가 켜져 있음), `liveSince: number | null`, `onLevel(cb: (db: number | undefined) => void): () => void`.

- [ ] **Step 1: 실패하는 시험을 쓴다**
  - `cues.test.ts`(가짜 시계): `waitForEnd ends when done is called`, `waitForEnd gives up after the cap`, `waitForEnd stops listening once it ends`(돌려받은 끊기 함수가 한 번 불림).
  - `gate.test.ts`: `a silent cancel while a stop runs does nothing`(멈춤이 게이트를 쥔 동안 `runThenHold(gate, hold, silentCancel)`이 `false`이고 `silentCancel`을 부르지 않으며 멈춤은 보냄), `a tap right after a silent cancel starts nothing`(저절로 취소가 `true`를 돌려준 뒤 `hold.on`이 참이라 시작을 받지 않음).
- [ ] **Step 2: 시험이 실패하는지 본다** — `cd app && npx jest src/audio/cues.test.ts src/flow/gate.test.ts`. 겹침 시험은 지금 코드로도 통과할 수 있다. 통과하면 그대로 두고, 저절로 취소를 같은 길로 보낸다는 약속의 시험으로 남긴다.
- [ ] **Step 3: `cues.ts`를 쓴다** — 진동은 `Vibration.vibrate(VIBRATE[cue])`. 플레이어는 `createAudioPlayer({ uri })` 셋을 만들어 두고, 틀 때 `seekTo(0)` 뒤 `play()`, 끝은 `playbackStatusUpdate`의 `didJustFinish`.
- [ ] **Step 4: `useRecorder`를 고친다**
  - 녹음 설정에 `isMeteringEnabled: true`.
  - `start`: 권한 → 준비 → `await playCue("start")` → `record()` → `live`, `liveSince` 켜기 → 55초 타이머 → 0.1초마다 `recorder.getStatus().metering`을 읽어 `onLevel` 구독자에게 넘기고, `onNoSpeech`가 있으면 `createSpeechWatch().feed(지난 시간, 값)`가 처음 `silent`일 때 한 번 부른다.
  - `stop`: 읽기를 멈추고 `live`를 끈 뒤 멈추고, 멈춤이 되면 `playCue("end")`(기다리지 않음).
  - `discard`: 읽기를 멈추고 `live`를 끈다(소리 없음, 뒤로가기). `cancel`: 녹음 중이었으면 `discard` 뒤 `playCue("cancel")`.
  - 화면이 사라지면 읽기를 멈춘다(지금의 타이머 정리 옆).
- [ ] **Step 5: 앱에 붙인다** — `App.tsx`의 소리 설정 다음에 `prepareCues()`. `app.json` `android.permissions`에 `"VIBRATE"`.
- [ ] **Step 6: 시험이 통과하는지 본다** — `cd app && npx jest && npx tsc --noEmit`.
- [ ] **Step 7: 커밋** — `feat(app): play cues and vibrate when the mic starts, stops or is cancelled`. 본문에 시작 소리가 끝난 뒤 마이크를 켜는 이유(소리 = 녹음 중, 녹음에 들어가지 않음)와, 소리를 못 내도 녹음은 된다는 것.

### Task 5: 화면

**Files:**
- Create: `app/src/ui/StopButton.tsx`
- Modify: `app/src/screens/RoleplayScreen.tsx`
- Test: `npx tsc --noEmit`, 지금 jest 전체(화면은 Task 6 폰에서 본다)

**Interfaces:**
- Consumes: Task 2 `voiceShare`, `SOON_ENDS_MS`. Task 3 `showMicHint`, `noSpeech`. Task 4 `rec.live`, `rec.liveSince`, `rec.onLevel`, `rec.cancel`, `start(..., { onNoSpeech })`.
- Produces: `StopButton(props: { live: boolean; onLevel: (cb: (db: number | undefined) => void) => () => void; onPress: () => void })` — 주된 버튼 모양(`buttonLook("primary", …)`, `grow`)으로 「말하기 끝」을 그리고, `live`면 글자 앞에 천천히 깜빡이는 빨간 동그라미(흰 테두리, `Animated` 반복, 1.4초쯤)와 글자 아래 얇은 목소리 줄(`voiceShare`로 너비)을 그린다. 0.1초마다 다시 그리는 것은 이 컴포넌트 안에서만 한다.

- [ ] **Step 1: `StopButton.tsx`를 쓴다** — 바깥 크기는 `Button`의 큰 버튼과 같게(같은 안쪽 여백, 테두리 2). 줄의 자리는 늘 잡아 두어 `live`가 켜져도 버튼 높이가 바뀌지 않게 한다.
- [ ] **Step 2: `RoleplayScreen.tsx`를 고친다**
  - 녹음 중 큰 버튼을 `StopButton`으로(`state.phase === "recording"`일 때). 다른 때는 지금 `Button` 그대로.
  - 버튼 둘째 줄 바로 위: `showMicHint(state)`면 파란 글자 `keepWords("🎤를 누르고 말하세요")`, 녹음 중이고 `rec.liveSince`에서 `SOON_ENDS_MS`가 지났으면 회색 글자 「녹음이 곧 끝나요」(그때 한 번 다시 그리게 타이머 하나).
  - `doCancel`과 켜지는 동안 취소된 길(`how === "cancelled"`)은 `rec.discard()` 대신 `rec.cancel()`. 뒤로가기의 `discard`는 그대로.
  - 저절로 취소: `doStart`가 `rec.start(stopRecording, { onNoSpeech: silentCancel })`. `silentCancel = () => runThenHold(gate, tapHold, doSilentCancel)`, `doSilentCancel`은 녹음 중이 아니면 `false`, 맞으면 `await rec.cancel(); dispatch({ type: "noSpeech" }); return true`.
- [ ] **Step 3: 확인한다** — `cd app && npx jest && npx tsc --noEmit`. 상황 정하기 화면은 고치지 않는다: `useRecorder`가 시작과 끝 소리를 내고, `onNoSpeech`를 주지 않아 저절로 취소하지 않는다.
- [ ] **Step 4: 커밋** — `feat(app): show the recording dot, voice line and first-turn hint`.

### Task 6: 폰에서 재고 맞추기, 화면 확인

**Files:**
- Modify: `app/src/flow/speechWatch.ts`(`SPEECH_RULE`), `app/src/ui/voiceLevel.ts`(`LINE_FLOOR_DB`, `LINE_TOP_DB`)
- 재는 동안만: `useRecorder`의 읽기마다 `console.log("[je-level]", 지난 시간, 값)`. 커밋하지 않는다.

- [ ] **Step 1: main 세션에 폰을 쓴다고 알리고 답을 받는다.** 이 브랜치 앱을 깔 것, 맥 스피커로 학습자 목소리를 틀 것을 함께 알린다.
- [ ] **Step 2: 재는 앱을 빌드해 깐다** — `app/README.md` 빌드, `adb install -r`. 앞에 뜬 앱을 보는 누르기 스크립트(`docs/guide/DEVENV_폰을_adb로_시험하기_20261108.md` 「겪은 것」)만 쓴다.
- [ ] **Step 3: 잰다** — 시험용 역할극 복사본(「이 상황 다시 하기」)에서 「🎤 말하기」를 누르고 `adb logcat -s ReactNativeJS`로 `[je-level]`을 모은다. 녹음은 「취소」로 버려 맥에 보내지 않는다.
  - 조용한 방 10초 두 번: 가장 큰 값과 대부분의 값.
  - 학습자 목소리 녹음(비공개 메모의 명령, 지어낸 문장)을 맥 스피커로 보통 크기, 작게(`afplay -v 0.3`) 틀며: 말하는 동안의 값.
- [ ] **Step 4: 값을 정한다** — `level`은 조용한 방의 가장 큰 값보다 넉넉히 위, 작게 튼 말소리보다 아래. `LINE_FLOOR_DB`는 조용한 방 값 바로 위, `LINE_TOP_DB`는 보통 말소리의 큰 값. `waitMs`는 8초 그대로 두고, 잰 것에서 바꿀 까닭이 나오면 바꾼다. 로그 줄을 지우고 단위 시험의 값이 바뀌었으면 맞춘다.
- [ ] **Step 5: 화면과 소리를 본다** (값을 넣고 다시 빌드한 앱)
  - 첫 내 차례의 안내, 「🎤」 뒤 사라짐, 다음 내 차례에 다시 나오지 않음(스크린샷).
  - 녹음 중 「● 말하기 끝」, 빨간 동그라미, 목소리 줄이 말소리에 움직이고 조용하면 멈춤(스크린샷 둘).
  - 시작, 끝, 취소 소리(`logcat`의 `AudioTrack`)와 진동(`adb shell dumpsys vibrator_manager`의 최근 진동).
  - 조용한 방에서 8초 뒤 저절로 취소, 「말소리가 없어 녹음을 멈췄어요.」, 맥의 시험 데이터에 그 시도가 없음.
  - 학습자 목소리를 틀고 「말하기 끝」: 맥이 평가함. 그 시험 시도가 든 복사본은 바로 지운다.
  - 50초 뒤 「녹음이 곧 끝나요」, 55초에 저절로 멈추며 끝 소리.
  - 상황 정하기 「🎤 말로 하기」의 시작과 끝 소리.
- [ ] **Step 6: 폰을 되돌린다** — 원래 주소 판(main)의 앱으로 다시 깔고 main 세션에 알린다.
- [ ] **Step 7: 커밋** — `fix(app): set the speech level and voice line range from phone measurements`. 본문에 잰 값(조용한 방, 보통, 작게)과 고른 값.

### Task 7: 문서

**Files:**
- Modify: `docs/PRD.md`(「사용자 차례(역할극)」 한 줄, 맨 위 「고침」에 한 줄), `docs/superpowers/specs/2026-11-08-record-cancel-skip-design.md`(4의 「녹음하는 동안」 그림 아래 「바뀜」 한 줄), `docs/guide/APP_버튼_색과_모양_20261108.md`(「버튼이 아닌 것」 아래에 녹음 중 빨간 동그라미는 상태 표시라는 것과 빨간 띠·빨간 버튼을 고르지 않은 까닭), `docs/guide/README.md`
- Create: `docs/guide/APP_녹음_중_알리기_20261108.md`(정한 기준: 소리 = 녹음 중, 시작 소리 뒤 마이크, 소리 파일을 코드로 만들기, 말소리 기준과 잰 값, 재는 방법. 겪은 문제와 해결)
- Modify(원래 폴더, 커밋 안 함 → 이 브랜치로 옮겨 넣음): `docs/todo/20261108_31_todo_recording_state_feedback.md` 상태 줄을 「완료」로.

- [ ] **Step 1: 문서를 고치고 쓴다.**
- [ ] **Step 2: 할 일 파일을 이 worktree의 `docs/todo/`에 복사해 상태를 「**완료** (2026-11-08, PR #…)」로 고친다.**
- [ ] **Step 3: 커밋** — `docs: record the recording cues, dot and silent cancel` (PRD, 스펙, 가이드, 할 일).
