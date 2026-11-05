# 처음엔 평범하게, 역할극 중에도 그 줄만 연습 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 내가 말할 대사를 처음엔 평범한 글자로 보이고 「읽는 법 보기」로 세 줄을 펼치게 하며, 역할극 중 지나간 말풍선에서 그 줄만 연습하고 같은 자리로 돌아오게 한다.

**Architecture:** 앱만 고친다. reducer(`app/src/flow/state.ts`)에 세 줄 펼침(`reading`), 역할극 중 연습(`practiseLine`, 떠나기 전 상태 `resume`), 연습 번호(`practiceNo`)를 더하고, 화면이 쓸 순수 함수(`practiceFor`, `askFirst`, `leavesScreen`, `modelKey`)를 둔다. 소리 큐(`SoundQueue`)는 지금 소리가 나오는지 알려 준다. 화면은 새 `LineToSay`와 말풍선의 연습 버튼으로 이것을 쓴다. 서버는 이미 `practice`와 `shadow`를 역할극 중에도 받고 진행 위치를 바꾸지 않으므로 고치지 않는다.

**Tech Stack:** React Native + Expo SDK 58 + Jest(jest-expo) + TypeScript. 새 의존성 없음.

**Spec:** `docs/superpowers/specs/2026-11-05-roleplay-practice-design.md`의 목표 7, 8과 「정한 것」 8, 9 (함께 읽을 것: 같은 스펙의 4, 5, 7, `docs/guide/PRONUNCIATION_한글발음_세줄표시_20261105.md` 「언제 보여 주나」)

## Global Constraints

- 이 worktree에서 git은 `/usr/bin/git`으로 부른다. `git add`는 파일을 지정한다(`-A`, `.` 금지). 커밋은 `/usr/bin/git commit -F - <<'EOF'`, Conventional Commits 영어, scope `app`. AI 서명 줄을 넣지 않는다.
- 커밋 본문에 왜, 어떻게 확인했는지(명령과 결과)를 쓰고, 끝에 `Refs: docs/superpowers/specs/2026-11-05-roleplay-practice-design.md`를 단다. 커밋과 그 뒤의 기록은 `&&`로 잇는다(커밋이 훅에 막히면 다음 명령이 돌지 않게).
- 서버(`server/`)는 고치지 않는다. 같은 때 도는 follow-feedback 카드가 서버의 평가를 고친다. 맥 서버를 끄거나 다시 띄울 일도 없다.
- 테스트 문장은 지어낸 것만 쓴다(`REVIEW.md`, ADR-0005). 녹음, 받아쓴 실제 글, 홈 폴더 경로를 코드, 테스트, 문서에 쓰지 않는다.
- 화면 글귀(스펙): 「읽는 법 보기」, 「따라 말하기」, 「이 줄 다시」, 「세 줄을 만들고 있어요」, 「역할극을 그만둘까요?」. 버튼 모양과 그 밖의 글귀는 빌더 몫이다(스펙 「빌더에게 맡기는 것」).
- 앱 시험: `cd app && npm test && npx tsc --noEmit`. 매 작업 끝에 통과해야 한다. worktree에는 `node_modules`가 없으니 처음에 `cd app && npm ci`를 한 번 한다(잠금 파일 그대로, 새 의존성이 아니다).
- 코드와 주석은 영어, 문서는 한국어.

## Review Focus

1. **같은 줄을 역할극 중에 두 번 연습:** 두 번째에도 본보기가 한 번 나와야 한다. 화면은 같은 것이 그대로 떠 있어서, 틀었던 소리를 기억하는 키가 겹치면 조용해진다 → Task 2 `two practices of the same line get different model keys`.
2. **연습에서 돌아온 뒤:** 지금 줄의 본보기를 다시 틀지 않아야 한다 → Task 2 `the roleplay line keeps its model key across a practice`.
3. **다르게 말한 바로 뒤에 지난 줄 연습:** 서버는 남은 대본을 다시 만드는 동안 줄 받기를 길면 120초 붙잡는다. 연습 줄은 서버에 묻지 않고 바로 `ready`여야 한다 → Task 2 `my past line opens at once from the line the app holds`.
4. **역할극 중 연습에서 「처음으로」:** 하던 역할극이 사라지므로 물어야 한다. 「뒤로」는 묻지 않고 역할극으로 간다 → Task 2 `asks first only when a roleplay would be lost`.
5. **세 줄이 없는 줄:** 세 줄을 끝내 못 만든 줄은 「읽는 법 보기」 없이 영어만 보이고 말하기는 그대로 된다 → Task 4 `a line without notes shows only the plain text`.

---

## 파일 지도

| 파일 | 맡는 것 | 작업 |
|---|---|---|
| `app/src/flow/state.ts` | `reading`, `toggleReading`, `practiseLine`, `resume`, `practiceNo`, `Practice.from`, 순수 함수 넷 | 1, 2 |
| `app/src/audio/player.ts` | `SoundQueue.isPlaying()`, `subscribe()` | 3 |
| `app/src/audio/usePlaying.ts` (새) | 소리가 나오는지 화면에 알리는 훅 | 3 |
| `app/src/ui/notesView.ts` (새) | 세 줄 펼침의 네 가지 모양을 가르는 순수 함수 | 4 |
| `app/src/ui/LineToSay.tsx` (새) | 평범한 대사와 「읽는 법 보기」, 펼친 세 줄 | 4 |
| `app/src/screens/RoleplayScreen.tsx` | `LineToSay` 쓰기, 말풍선의 연습 버튼, 떠날 때 묻기, 제목 | 4, 5 |
| `app/src/screens/EndScreen.tsx` | 라이언 줄의 「따라 말하기」 | 5 |

시험 파일: `app/src/flow/state.test.ts`, `app/src/audio/player.test.ts`(새), `app/src/ui/notesView.test.ts`(새). 화면(`*.tsx`)은 시험 도구가 없어(새 의존성을 넣지 않는다) `tsc`와 폰 확인(Task 6)으로 본다.

계약 대본(`contract/roleplay.json`)은 줄 셋이다: 라이언 0(`audio` 있음), 사용자 1(`three`, `audio` 있음), 라이언 2. 지난 내 줄이 필요한 시험은 지어낸 사용자 줄 3을 더해 쓴다.

---

### Task 1: 세 줄은 처음에 접혀 있다 (reducer)

**Files:**
- Modify: `app/src/flow/state.ts`
- Test: `app/src/flow/state.test.ts`

**Interfaces:**
- Produces: `State.reading: boolean`(지금 줄의 세 줄을 펼쳤는지, `initial`은 `false`), `Action` `{ type: "toggleReading" }`.

- [ ] **Step 1: Write the failing tests** (`state.test.ts` 끝에 더한다)

```ts
describe("notes start closed (spec roleplay-practice 8)", () => {
  test("a new line starts with its notes closed", () => {
    expect(reduce({ ...at("loading"), reading: true }, { type: "lineLoaded", line: userLine }).reading).toBe(false);
  });

  test("toggleReading opens and closes", () => {
    const s = reduce(at("ready"), { type: "toggleReading" });
    expect(s.reading).toBe(true);
    expect(reduce(s, { type: "toggleReading" }).reading).toBe(false);
  });

  test("again keeps the notes open on the same line", () => {
    expect(reduce(at("evaluated", { reading: true }), { type: "again" }).reading).toBe(true);
  });

  test("the next line starts closed again", () => {
    const s = reduce(at("evaluated", { reading: true, nextIdx: 2 }), { type: "next" });
    expect(reduce(s, { type: "lineLoaded", line: ryanLine }).reading).toBe(false);
  });

  test("a practice line from the end starts closed", () => {
    expect(reduce(end({ reading: true }), { type: "startPractice", kind: "mine", order: [1] }).reading).toBe(false);
  });
});
```

- [ ] **Step 2: Run to see them fail**

Run: `cd app && npx jest src/flow/state.test.ts -t "notes start closed"`
Expected: FAIL (`reading`이 없어 `tsc`형 오류 또는 `undefined`).

- [ ] **Step 3: Implement**

`State`에 `reading`을 더하고 `initial`에 `reading: false`. `lineLoaded`와 `startPractice`가 `reading: false`로 놓는다. `toggleReading`은 `s.line`이 있을 때만 뒤집는다. `again`은 건드리지 않는다.

- [ ] **Step 4: Run the app tests**

Run: `cd app && npm test && npx tsc --noEmit`
Expected: 모두 통과, 타입 오류 없음.

- [ ] **Step 5: Commit**

```bash
/usr/bin/git add app/src/flow/state.ts app/src/flow/state.test.ts
/usr/bin/git commit -F - <<'EOF'
feat(app): keep the three-line notes closed until asked
...(왜: 스펙 8, 확인: npm test 결과)
Refs: docs/superpowers/specs/2026-11-05-roleplay-practice-design.md
EOF
```

---

### Task 2: 역할극 중에 그 줄만 연습 (reducer와 순수 함수)

**Files:**
- Modify: `app/src/flow/state.ts`
- Test: `app/src/flow/state.test.ts`

**Interfaces:**
- Consumes: Task 1의 `State.reading`.
- Produces:
  - `Practice = { kind: "mine" | "shadow"; order: number[]; at: number; from: "end" | "roleplay" }`. `startPractice`는 `from: "end"`.
  - `Bubble`의 내 말풍선에 `idx`(그 줄 번호)가 붙는다. `exchange()`가 `s.line?.idx`를 넣는다.
  - `State.resume: State | null`(역할극 중 연습을 시작할 때 떼어 둔 역할극 상태), `State.practiceNo: number`(`startPractice`와 `practiseLine`마다 1씩 는다, `initial`은 0).
  - `Action` `{ type: "practiseLine"; kind: "mine" | "shadow"; idx: number }`.
  - `practiceFor(s: State, b: Pick<Bubble, "kind" | "idx">): "mine" | "shadow" | null` — 그 말풍선에 붙일 연습 버튼.
  - `askFirst(s: State, a: "back" | "home"): boolean` — 떠나기 전에 「역할극을 그만둘까요?」를 물을지.
  - `leavesScreen(s: State, a: "back" | "home"): boolean` — 이 동작 뒤 역할극 화면이 사라지는지(사라지지 않으면 화면이 진행 중인 녹음과 평가만 버린다, Task 5).
  - `modelKey(s: State): string | null` — 본보기를 한 번만 틀려고 기억하는 키. 연습 밖은 `${line.idx}:${mode}`, 연습 안은 `${line.idx}:${mode}:${practiceNo}`, 줄이 없으면 `null`.

- [ ] **Step 1: Update the bubble test and write the failing tests**

기존 시험 `the learner's bubble keeps the script line and what was heard`의 기대값에 `idx: 1`을 더한다. 그리고 끝에 더한다:

```ts
describe("one line in the middle of the roleplay (spec roleplay-practice 9)", () => {
  const ryan2 = rp.lines[2] as ScriptLine;
  const user3: ScriptLine = { ...userLine, idx: 3, text: "Just one, thanks." };
  // the learner is on line 3; lines 0-2 are behind
  const midway = (phase: State["phase"], extra: Partial<State> = {}): State => ({
    ...reduce(situation, { type: "created", roleplay: rp }),
    idx: 3,
    line: user3,
    phase,
    progress: { no: 2, total: 2 },
    seen: { 0: ryanLine, 1: userLine, 2: ryan2, 3: user3 },
    history: [
      { kind: "ryan", text: ryanLine.text, idx: 0 },
      { kind: "user", text: "I'd like a cup of coffee", script: userLine.text, idx: 1 },
      { kind: "feedback", text: "좋아요." },
      { kind: "ryan", text: ryan2.text, idx: 2 },
    ],
    ...extra,
  });

  test("my past line opens at once from the line the app holds", () => {
    const s = reduce(midway("ready"), { type: "practiseLine", kind: "mine", idx: 1 });
    expect([s.screen, s.mode, s.idx, s.phase, s.line, s.history, s.practice?.from]).toEqual([
      "roleplay", "practice", 1, "ready", userLine, [], "roleplay",
    ]);
  });

  test("Ryan's past line opens as shadow", () => {
    const s = reduce(midway("evaluated"), { type: "practiseLine", kind: "shadow", idx: 2 });
    expect([s.mode, s.idx, s.phase, s.line]).toEqual(["shadow", 2, "ready", ryan2]);
  });

  test("next after the line comes back to the same spot", () => {
    const before = midway("evaluated", { heard: "Just one, thanks.", feedback: "좋아요.", nextIdx: 4, reading: true });
    let s = reduce(before, { type: "practiseLine", kind: "mine", idx: 1 });
    s = reduce(reduce(s, { type: "recordStart" }), { type: "recordStop" });
    s = reduce(reduce(s, { type: "event", e: { type: "done", next: 1, issues: 0 } }), { type: "next" });
    expect(s).toEqual({ ...before, practiceNo: before.practiceNo + 1 });
  });

  test("back from the line comes back to the roleplay", () => {
    const before = midway("ready");
    const s = reduce(reduce(before, { type: "practiseLine", kind: "shadow", idx: 0 }), { type: "back" });
    expect(s).toEqual({ ...before, practiceNo: before.practiceNo + 1 });
  });

  test("only while my turn is waiting", () => {
    for (const p of ["loading", "ryan", "recording", "evaluating", "error"] as const) {
      const s = midway(p);
      expect(reduce(s, { type: "practiseLine", kind: "mine", idx: 1 })).toBe(s);
    }
  });

  test("not the line on screen, an unseen line, the wrong speaker, or inside a practice", () => {
    const s = midway("ready");
    for (const a of [
      { kind: "mine", idx: 3 }, // the line on screen: 「다시 해 보기」 covers it
      { kind: "mine", idx: 5 }, // not seen yet
      { kind: "shadow", idx: 1 }, // my line is not Ryan's
      { kind: "mine", idx: 0 }, // Ryan's line is not mine
    ] as const)
      expect(reduce(s, { type: "practiseLine", ...a })).toBe(s);
    const inside = reduce(s, { type: "practiseLine", kind: "mine", idx: 1 });
    expect(reduce(inside, { type: "practiseLine", kind: "shadow", idx: 0 })).toBe(inside);
  });

  test("which bubbles get a practice button", () => {
    const s = midway("ready");
    expect(s.history.map((b) => practiceFor(s, b))).toEqual(["shadow", "mine", null, "shadow"]);
    expect(practiceFor(s, { kind: "user", idx: 3 })).toBeNull(); // the line on screen, tried again
    const reply: ScriptLine = { idx: 4, speaker: "ryan", text: "Sure thing!", kind: "reply", three: null, audio: null };
    expect(practiceFor({ ...s, seen: { ...s.seen, 4: reply } }, { kind: "ryan", idx: 4 })).toBe("shadow");
    const inside = reduce(s, { type: "practiseLine", kind: "mine", idx: 1 });
    expect(practiceFor(inside, s.history[0])).toBeNull();
  });

  test("asks first only when a roleplay would be lost", () => {
    const s = midway("ready");
    expect([askFirst(s, "back"), askFirst(s, "home")]).toEqual([true, true]);
    const inside = reduce(s, { type: "practiseLine", kind: "mine", idx: 1 });
    expect([askFirst(inside, "back"), askFirst(inside, "home")]).toEqual([false, true]);
    const fromEnd = reduce(end(), { type: "startPractice", kind: "mine", order: [1] });
    expect([askFirst(fromEnd, "back"), askFirst(fromEnd, "home")]).toEqual([false, false]);
  });

  test("only back from a line practised mid-roleplay stays on the roleplay screen", () => {
    const s = midway("ready");
    const inside = reduce(s, { type: "practiseLine", kind: "mine", idx: 1 });
    const fromEnd = reduce(end(), { type: "startPractice", kind: "mine", order: [1] });
    expect([leavesScreen(inside, "back"), leavesScreen(inside, "home")]).toEqual([false, true]);
    expect([leavesScreen(s, "back"), leavesScreen(fromEnd, "back")]).toEqual([true, true]);
  });

  test("the roleplay line keeps its model key across a practice", () => {
    const before = midway("ready");
    const after = reduce(reduce(before, { type: "practiseLine", kind: "mine", idx: 1 }), { type: "back" });
    expect(modelKey(after)).toBe(modelKey(before));
  });

  test("two practices of the same line get different model keys", () => {
    const first = reduce(midway("ready"), { type: "practiseLine", kind: "mine", idx: 1 });
    const second = reduce(reduce(first, { type: "back" }), { type: "practiseLine", kind: "mine", idx: 1 });
    expect(modelKey(second)).not.toBe(modelKey(first));
  });
});
```

`import`에 `askFirst`, `leavesScreen`, `modelKey`, `practiceFor`를 더한다.

- [ ] **Step 2: Run to see them fail**

Run: `cd app && npx jest src/flow/state.test.ts -t "middle of the roleplay|bubble keeps"`
Expected: FAIL (`practiseLine`과 함수 넷이 없음, 말풍선에 `idx` 없음).

- [ ] **Step 3: Implement in `app/src/flow/state.ts`**

- `practiseLine`: `screen === "roleplay"`, `!s.practice`, `canReplay(s.phase)`, `idx !== s.line?.idx`, `s.seen[idx]`가 있고 그 `speaker`가 `kind`에 맞을 때(`mine`→`user`, `shadow`→`ryan`)만. 새 상태는 `{ ...s, ...freshTurn, screen: "roleplay", mode: kind === "shadow" ? "shadow" : "practice", practice: { kind, order: [idx], at: 0, from: "roleplay" }, idx, line: s.seen[idx], phase: "ready", history: [], reading: false, nextIdx: null, practiceNo: s.practiceNo + 1, resume: s }`. 서버에 줄을 묻지 않으려고 `loading`을 거치지 않는다(Review Focus 3).
- 연습을 떠나는 곳(`back`, 마지막 줄의 `next`)은 한 함수로: `from === "roleplay"`이면 `{ ...s.resume!, practiceNo: s.practiceNo }`, 아니면 지금의 `toEnd(s)`.
- `startPractice`는 `from: "end"`, `practiceNo: s.practiceNo + 1`.
- `initial`에 `resume: null`, `practiceNo: 0`.
- `practiceFor`: 연습 안이면 `null`. `idx`가 없거나 `s.line?.idx`와 같거나 `s.seen[idx]`가 없으면 `null`. 라이언 말풍선은 `"shadow"`, 내 말풍선은 `"mine"`, 그 밖(평가)은 `null`.
- `askFirst`: 연습 밖이면 `true`. 연습 안이면 `from === "roleplay" && a === "home"`.
- `leavesScreen`: `!(s.practice?.from === "roleplay" && a === "back")`.

- [ ] **Step 4: Run the app tests**

Run: `cd app && npm test && npx tsc --noEmit`
Expected: 모두 통과. 기존 연습 시험(끝 화면으로 돌아가기)도 그대로 통과.

- [ ] **Step 5: Commit**

```bash
/usr/bin/git add app/src/flow/state.ts app/src/flow/state.test.ts
/usr/bin/git commit -F - <<'EOF'
feat(app): practise one past line mid-roleplay and come back to it
...(왜: 스펙 9, 서버에 묻지 않는 이유, 확인: npm test 결과)
Refs: docs/superpowers/specs/2026-11-05-roleplay-practice-design.md
EOF
```

---

### Task 3: 소리가 나오는지 알리기 (`SoundQueue`)

**Files:**
- Modify: `app/src/audio/player.ts`
- Create: `app/src/audio/usePlaying.ts`
- Test: `app/src/audio/player.test.ts` (새)

**Interfaces:**
- Produces: `SoundQueue.isPlaying(): boolean`, `SoundQueue.subscribe(cb: (playing: boolean) => void): () => void`(값이 바뀔 때만 부르고, 돌려준 함수로 끊는다), `usePlaying(sounds: SoundQueue): boolean`(React `useSyncExternalStore`로 `subscribe`와 `isPlaying`을 쓴다).

- [ ] **Step 1: Write the failing tests**

`expo-audio`를 가짜로 바꾼다. jest의 `jest.mock` 공장 안에서 쓰는 바깥 변수는 이름이 `mock`으로 시작해야 한다. 지켜보기 타이머(30초) 때문에 `jest.useFakeTimers()`를 쓴다.

```ts
const mockFinish: ((s: { didJustFinish: boolean }) => void)[] = [];
jest.mock("expo-audio", () => ({
  createAudioPlayer: () => ({
    addListener: (_: string, cb: (s: { didJustFinish: boolean }) => void) => mockFinish.push(cb),
    replace: () => {},
    play: () => {},
    pause: () => {},
  }),
}));
import { SoundQueue } from "./player";

beforeEach(() => {
  mockFinish.length = 0;
  jest.useFakeTimers();
});
const finish = () => mockFinish.forEach((cb) => cb({ didJustFinish: true }));

test("playing is reported when sound starts and when the queue runs dry", () => {
  const q = new SoundQueue();
  const seen: boolean[] = [];
  q.subscribe((p) => seen.push(p));
  q.enqueue("a");
  q.enqueue("b");
  expect(q.isPlaying()).toBe(true);
  finish();
  expect(q.isPlaying()).toBe(true);
  finish();
  expect(q.isPlaying()).toBe(false);
  expect(seen).toEqual([true, false]);
});

test("clear reports quiet", () => {
  const q = new SoundQueue();
  const seen: boolean[] = [];
  q.subscribe((p) => seen.push(p));
  q.enqueue("a");
  q.clear();
  expect([q.isPlaying(), seen]).toEqual([false, [true, false]]);
});

test("a stopped subscription hears nothing", () => {
  const q = new SoundQueue();
  const seen: boolean[] = [];
  q.subscribe((p) => seen.push(p))();
  q.enqueue("a");
  expect(seen).toEqual([]);
});
```

- [ ] **Step 2: Run to see them fail**

Run: `cd app && npx jest src/audio/player.test.ts`
Expected: FAIL (`subscribe is not a function`).

- [ ] **Step 3: Implement**

`player.ts`: `playing`을 바꾸는 곳(`next`, `clear`)을 한 메서드로 모아, 값이 바뀔 때 구독자에게 알린다. `usePlaying.ts`는 `useSyncExternalStore((cb) => sounds.subscribe(cb), () => sounds.isPlaying())`.

- [ ] **Step 4: Run the app tests**

Run: `cd app && npm test && npx tsc --noEmit`
Expected: 모두 통과.

- [ ] **Step 5: Commit**

```bash
/usr/bin/git add app/src/audio/player.ts app/src/audio/usePlaying.ts app/src/audio/player.test.ts
/usr/bin/git commit -F - <<'EOF'
feat(app): let screens know whether a sound is playing
...(왜: 스펙 9의 「소리가 나오는 동안 눌리지 않는다」, 확인: npm test 결과)
Refs: docs/superpowers/specs/2026-11-05-roleplay-practice-design.md
EOF
```

---

### Task 4: 평범한 대사와 「읽는 법 보기」 (화면)

**Files:**
- Create: `app/src/ui/notesView.ts`, `app/src/ui/LineToSay.tsx`
- Modify: `app/src/screens/RoleplayScreen.tsx`
- Test: `app/src/ui/notesView.test.ts` (새)

**Interfaces:**
- Consumes: Task 1의 `State.reading`, `{ type: "toggleReading" }`. 기존 `ThreeLineView`.
- Produces:
  - `notesView(three: ThreeLine | "loading" | null, open: boolean): "plain" | "closed" | "loading" | "open"`. `null`은 보일 세 줄이 없다(끝내 못 만듦, 아직 묻지 않음)는 뜻이다.
  - `LineToSay({ text, three, open, onToggle }: { text: string; three: ThreeLine | "loading" | null; open: boolean; onToggle: () => void })`. `plain`과 `closed`는 대사를 큰 평범한 글자로, `closed`에만 「읽는 법 보기」. `loading`은 대사와 「세 줄을 만들고 있어요…」. `open`은 대사 자리에 `ThreeLineView`(영어 줄이 그 안에 있다)와 접는 버튼.

- [ ] **Step 1: Write the failing tests** (`notesView.test.ts`)

```ts
import lineUser from "../../../contract/line-user.json";
import type { ThreeLine } from "../api/types";
import { notesView } from "./notesView";

const three = lineUser.three as ThreeLine;

test("closed notes show the plain line with a button", () => {
  expect([notesView(three, false), notesView("loading", false)]).toEqual(["closed", "closed"]);
});

test("open notes show the three lines, or that they are being made", () => {
  expect([notesView(three, true), notesView("loading", true)]).toEqual(["open", "loading"]);
});

test("a line without notes shows only the plain text", () => {
  // the notes could not be made: the line and the mic still work (spec roleplay-practice 8)
  expect([notesView(null, false), notesView(null, true)]).toEqual(["plain", "plain"]);
});
```

- [ ] **Step 2: Run to see them fail**

Run: `cd app && npx jest src/ui/notesView.test.ts`
Expected: FAIL (모듈 없음).

- [ ] **Step 3: Implement `notesView`, `LineToSay`, and use it in `RoleplayScreen.tsx`**

- `RoleplayScreen.tsx`의 내 차례 부분에서 지금의 세 줄 표시 세 갈래(`shadow`일 때 큰 글자, `shadowThree`, `line.three`)를 `LineToSay` 하나로 바꾼다. `three`는 내 줄이면 `line.three`, 따라 말하기면 `line.three ?? threes[line.idx] ?? null`. `open`은 `state.reading`, `onToggle`은 `dispatch({ type: "toggleReading" })`.
- 따라 말하기의 라이언 줄 세 줄을 `ready`에서 미리 받는 지금 효과는 그대로 둔다(스펙 5, 펼칠 때 기다리지 않게).
- 라이언 말풍선(`RyanBubble`)의 「눌러서 읽는 법 보기」는 그대로 둔다.

- [ ] **Step 4: Run the app tests**

Run: `cd app && npm test && npx tsc --noEmit`
Expected: 모두 통과, 타입 오류 없음.

- [ ] **Step 5: Commit**

```bash
/usr/bin/git add app/src/ui/notesView.ts app/src/ui/notesView.test.ts app/src/ui/LineToSay.tsx app/src/screens/RoleplayScreen.tsx
/usr/bin/git commit -F - <<'EOF'
feat(app): show the line to say as plain text with a notes button
...(왜: 사용자 「처음 보여 주는 문장은 평범하게」, 확인: npm test, tsc 결과)
Refs: docs/superpowers/specs/2026-11-05-roleplay-practice-design.md
EOF
```

---

### Task 5: 말풍선과 끝 화면의 연습 버튼 (화면)

**Files:**
- Modify: `app/src/screens/RoleplayScreen.tsx`, `app/src/screens/EndScreen.tsx`

**Interfaces:**
- Consumes: Task 2의 `practiseLine`, `practiceFor`, `askFirst`, `leavesScreen`, `modelKey`, `Practice.from`. Task 3의 `usePlaying`.

- [ ] **Step 1: Wire the practice buttons in `RoleplayScreen.tsx`**

- 누를 수 있는 때: `const canPractise = !state.practice && canReplay(state.phase) && !usePlaying(sounds)`. 눌리지 않을 때의 모양(숨김, 흐림)은 빌더 몫.
- 대화의 말풍선마다 `practiceFor(state, b)`가 `"shadow"`면 「따라 말하기 ›」, `"mine"`이면 「이 줄 다시 ›」를 붙인다. 방금 나온 라이언 대답(`state.reply`)도 같다. 라이언 차례에 말하고 있는 줄(`phase === "ryan"`)에는 붙이지 않는다. 누르면 `dispatch({ type: "practiseLine", kind, idx })`.
- 본보기를 한 번만 트는 키(`played`)를 `modelKey(state)`로 바꾼다(Review Focus 1, 2).
- 떠나기: `askLeave`는 `askFirst(state, a)`가 거짓이면 묻지 않는다.
- 떠난 뒤에도 같은 화면이 남는 경우(`leavesScreen(state, a)`가 거짓)가 생긴다. 지금은 떠날 때 `mounted.current = false`로 녹음과 평가 흐름을 끊는데, 화면이 남으면 그 값이 거짓인 채로 남아 돌아온 역할극의 녹음과 평가가 모두 버려진다. 그래서 떠날 때마다 1씩 느는 `epoch` ref를 두고, `doStart`와 `doStop`은 시작할 때의 값을 잡아 두었다가 `!mounted.current || epoch.current !== 잡은 값`이면 지금처럼 버린다. `mounted.current = false`는 `leavesScreen(state, a)`가 참일 때만 놓는다.
- 제목: `state.practice?.from === "roleplay"`이면 `mine`은 「이 줄 다시」, `shadow`는 「따라 말하기」, 숫자는 숨긴다. 평가 뒤 「다음」은 「역할극으로」로 보인다.

- [ ] **Step 2: Add 「따라 말하기」 to Ryan's lines in `EndScreen.tsx`**

`RyanLine`에 「따라 말하기 ›」를 더해 `practise("shadow", [l.line.idx])`를 부른다. 내 줄의 「이 줄 다시 ›」와 같은 모양으로 둔다.

- [ ] **Step 3: Run the app tests**

Run: `cd app && npm test && npx tsc --noEmit`
Expected: 모두 통과, 타입 오류 없음.

- [ ] **Step 4: Commit**

```bash
/usr/bin/git add app/src/screens/RoleplayScreen.tsx app/src/screens/EndScreen.tsx
/usr/bin/git commit -F - <<'EOF'
feat(app): add practice buttons to past bubbles and Ryan's end lines
...(왜: 사용자 「지금은 3개를 모두 완료해야 연습할 수 있게 되어 있네?」, epoch를 둔 이유, 확인: npm test, tsc 결과)
Refs: docs/superpowers/specs/2026-11-05-roleplay-practice-design.md
EOF
```

---

### Task 6: 빌드해서 폰에 깔기

**Files:** 없음(커밋하지 않는다).

- [ ] **Step 1: Copy `app/.env` from the original folder**

`git worktree list`의 첫 줄 폴더의 `app/.env`를 이 worktree의 `app/.env`로 복사한다. 커밋하지 않는다(`.gitignore`에 있다).

- [ ] **Step 2: Build and install**

`app/README.md` 「빌드와 설치」대로 한다. `JAVA_HOME`과 `ANDROID_HOME`은 비공개 메모 `mac-env.md`를 본다. 폰은 USB로 꽂고 SDK의 `platform-tools/adb`로 `install -r`한다(adb는 PATH에 없다).
Expected: `Success`.

- [ ] **Step 3: Ask the user to check on the phone**

사용자에게 볼 것을 알린다: 내 차례의 대사가 평범하게 시작하는지, 「읽는 법 보기」, 다음 줄에서 다시 접히는지, 지난 말풍선의 「따라 말하기」와 「이 줄 다시」, 돌아왔을 때 그 자리 그대로인지, 끝 화면 라이언 줄의 「따라 말하기」, 센 음절 색(바꿀지는 사용자가 정한다).
