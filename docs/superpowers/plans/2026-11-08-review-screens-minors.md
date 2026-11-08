# 복습하기 화면 다시 그리기의 작은 일 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 복습하기 화면 다시 그리기(PR #30)의 최종 리뷰와 PR 리뷰가 미룬 작은 일 다섯을 고친다.

**Architecture:** 기능과 맥 서버는 바꾸지 않는다. 앱만 고친다. 모아 둔 문장 저장소(`flow/savedStore.ts`)에 「빼기만」을 더하고, `keepWords`를 한글에 붙은 모든 글자로 넓혀 오류 글, 대화 화면, 끝 화면이 거치게 하고, 지난 상황 목록을 복습하기 화면이 한 번 받아 두게 한다.

**Tech Stack:** React Native + Expo(앱, jest, tsc). 새 꾸러미 없음.

**Spec:** 원래 폴더의 `docs/todo/20261107_12_todo_review_screens_minors.md`(아직 커밋하지 않은 할 일 파일, 마지막 커밋에 「완료」로 넣는다). 화면의 스펙은 `docs/superpowers/specs/2026-11-07-review-screens-design.md`, 줄바꿈 규칙은 `docs/guide/APP_Expo_앱_뼈대와_서버_연결_20261105.md` 「문제: 한국어가 낱말 가운데서 줄이 바뀐다」.

## Global Constraints

- 새로 설치하는 것이 없다. 테스트와 문서의 문장은 지어낸 것을 쓴다. 화면 캡처는 공개 파일에 넣지 않는다(지난 역할극의 실제 문장이 보인다).
- `keepWords`를 거친 글은 보이기만 한다. 서버로 보내거나 비교하지 않는다(가이드).
- 같이 도는 fixed-list-scripts 카드가 다음 PR에서 `RoleplayScreen.tsx`를 고친다. 그 파일은 글을 감싸는 곳만 작게 고친다.
- 커밋은 `/usr/bin/git`, `git commit -F - <<'EOF'`, 앞 커밋이 성공해야 다음이 돌게 `&&`로 잇는다.
- 테스트: `cd app && npx jest && npx tsc --noEmit`.

## 정한 것 (AI 판단)

- **빼기(할 일 1):** 할 일 파일이 든 두 방법을 다 한다. 모아 둔 문장 목록의 「빼기」는 `toggle`이 아니라 빼기만 하는 `remove`를 부르고, 빼기가 되면 목록을 다시 받지 못해도 저장소의 목록에서 그 줄을 바로 지운다. 화면은 빼기가 잘될 때와 같다(줄이 사라진다).
- **`keepWords`를 넓힌다(할 일 2, 3):** 한글 글자 사이만이 아니라, 한글과 그 앞뒤에 붙은 글자(숫자, 영어, 괄호, 문장 부호) 사이도 잇는다. 띄어쓰기와 이미 넣은 이음 문자는 잇지 않는다. 「11월」, 「7일에」뿐 아니라 라이언의 평가에 자주 나오는 「coffee를」, 「「coffee」를」도 영어 뒤에서 조사가 떨어질 수 있어서다(안드로이드의 줄바꿈 규칙은 영어와 한글 사이, 닫는 괄호와 한글 사이에서도 줄을 바꿀 수 있다고 본다). 한국어는 띄어쓰기로 낱말을 나누므로, 한글이 든 낱말은 띄어쓰기에서만 줄이 바뀐다.
- **오류 글은 한 곳(할 일 2):** `screens/common.tsx`에 `ErrorText`를 두고 `keepWords`를 거친다. `common.styles`의 `error`는 내보내지 않는다. 그러면 오류 글을 `ErrorText` 없이 그리는 곳은 `tsc`가 잡는다.
- **세 줄의 한글 발음(할 일 3):** 강세 표시 때문에 한 낱말이 여러 조각(`Text` 안의 `Text`)으로 그려진다. 조각마다 `keepWords`를 거치면 조각 사이가 끊길 수 있어, 조각 목록을 이어 주는 `keepPieces`를 둔다.
- **지난 상황 목록(할 일 4):** `ReviewScreen`이 열릴 때 한 번 받아 `PastTab`에 넘긴다. 모아 둔 문장처럼 복습하기를 연 동안 탭을 바꿔도 다시 받지 않는다. 지난번 대화를 보고 돌아오면 복습하기가 다시 열리므로 다시 받는다(새로 한 회차가 보인다).
- **준비 중의 ★(할 일 5):** `askRemove`가 연습 시작 게이트가 닫혀 있으면(`gate.busy`) 무시한다. 상태 `starting`은 다음 그리기 전에는 옛 값이라, 누른 그 자리에서 게이트를 본다(`REVIEW.md` 「앱 화면」의 두 번 누르기와 같은 까닭).
- 앱에 화면을 그려 보는 시험 도구가 없다(새로 설치해야 한다). 그래서 논리는 jest로, 화면에 잇는 것은 `tsc`와 에뮬레이터 캡처로 확인한다(앞 카드들과 같다).

## Review Focus

1. 라이언의 평가처럼 영어 낱말에 조사가 붙은 글(「coffee를」, 「「coffee」를」)은 한 덩어리로 넘어가야 한다. Task 2 테스트.
2. 맥에서 빼기는 됐는데 목록을 다시 받지 못하면, 줄이 사라지고 다시 눌러도 다시 모으지 않아야 한다. Task 1 테스트.
3. 그림 글자(💬, 두 칸짜리 글자)가 한글 옆에 있어도 깨지지 않아야 한다. Task 2 테스트(`💬💬`는 그대로).
4. 같은 글을 두 번 거쳐도 이음 문자가 겹치지 않아야 한다(서버에서 받은 글을 저장소에 둔 채 그릴 때마다 거친다). Task 2 테스트.
5. 지난 상황 탭을 열자마자 「모아 둔 문장」으로 바꿨다가 돌아와도, 받던 목록이 그대로 보이고 「다시 시도」가 다시 받는다. Task 4 에뮬레이터 확인.

---

### Task 1: 「빼기」는 빼기만 하고, 빼면 목록에서 바로 지운다 (할 일 1)

**Files:**
- Modify: `app/src/flow/savedStore.ts`, `app/src/screens/SavedTab.tsx:68`
- Test: `app/src/flow/savedStore.test.ts`

**Interfaces:**
- Produces: `SavedStore.remove(rpId: string, idx: number, text: string): Promise<void>`. `toggle`과 같이 `busy`로 두 번 누르기를 막고, 실패하면 `onFail`.

- [ ] **Step 1: 실패하는 테스트**

```ts
test("removing takes a sentence off the list at once, even when the list cannot be loaded again", async () => {
  // list: 처음엔 [item("Sure.", "sure")], 그다음부터 throw
  await store.refresh();
  await store.remove("aaaaaaaaaaaa", 1, "Sure.");
  expect(set).toHaveBeenCalledWith("aaaaaaaaaaaa", 1, false);
  expect(store.items()).toEqual([]);
  expect(store.has("Sure.")).toBe(false);
});

test("remove never saves: a sentence already out is sent out again", async () => {
  // list: [] (has가 거짓)
  await store.refresh();
  await store.remove("aaaaaaaaaaaa", 1, "Sure.");
  expect(set).toHaveBeenCalledWith("aaaaaaaaaaaa", 1, false);
});

test("unsaving with toggle also takes it off the list when the list cannot be loaded again", async () => {
  // 첫 테스트와 같은 list
  await store.refresh();
  await store.toggle("aaaaaaaaaaaa", 1, "Sure.");
  expect(store.items()).toEqual([]);
});
```

- [ ] **Step 2:** `cd app && npx jest src/flow/savedStore.test.ts` → 세 테스트 FAIL(`store.remove is not a function`, 목록에 줄이 남음).
- [ ] **Step 3:** `toggle`의 몸통을 `change(rpId, idx, text, on)`로 옮기고 `toggle`은 `change(..., !keys.has(key))`, `remove`는 `change(..., false)`. 저장이 되면 `on`이 거짓일 때 `items`에서 그 `key`의 줄을 지운 뒤 `refresh()`. `SavedTab`의 「빼기」가 `saved.remove`를 부른다.
- [ ] **Step 4:** 같은 명령 → PASS, `npx tsc --noEmit` 오류 없음.
- [ ] **Step 5:** 커밋 `fix(app): take a saved sentence out only, and off the list at once`.

### Task 2: `keepWords`를 한글에 붙은 글자로 넓히고, 오류 글을 한 곳에서 거친다 (할 일 2)

**Files:**
- Modify: `app/src/ui/keepWords.ts`, `app/src/screens/common.tsx`, 오류 글을 그리는 곳(`HomeScreen.tsx:95`, `SituationScreen.tsx:274,330`, `PastTab.tsx:47`, `SavedTab.tsx:97,102`, `EndScreen.tsx:222`, `RoleplayScreen.tsx:489,589`)
- Test: `app/src/ui/keepWords.test.ts`

**Interfaces:**
- Produces: `keepWords(text: string): string`(넓힌 규칙), `keepPieces(pieces: string[]): string[]`(Task 3이 쓴다), `ErrorText({ text }: { text: string })`(`screens/common.tsx`).

- [ ] **Step 1: 실패하는 테스트.** 지금의 「a word mixing Hangul with signs or digits is joined only between Hangul letters」를 아래로 바꾼다.

```ts
test("a Korean word stays whole with the digits, letters and signs on it", () => {
  expect(keepWords("11월 7일에")).toBe(`11${WJ}월 7${WJ}일${WJ}에`);
  expect(keepWords("2026")).toBe("2026"); // no Hangul: nothing to keep
  expect(keepWords("coffee를 세게")).toBe(`coffee${WJ}를 세${WJ}게`);
  expect(keepWords("「coffee」를")).toBe(`「coffee」${WJ}를`);
  expect(keepWords("연습(4)")).toBe(`연${WJ}습${WJ}(4)`);
  expect(keepWords("반가워요.")).toBe(`반${WJ}가${WJ}워${WJ}요${WJ}.`);
});

test("keepWords twice is keepWords once", () => {
  const once = keepWords("11월 7일에 모음 · coffee를");
  expect(keepWords(once)).toBe(once);
});

test("an emoji next to Hangul stays whole", () => {
  expect(keepWords("💬💬")).toBe("💬💬");
  expect(keepWords("💬대화")).toBe(`💬${WJ}대${WJ}화`);
});

test("pieces of one word in different styles stay one word", () => {
  expect(keepPieces(["스", "테", "이션"])).toEqual([`스${WJ}`, `테${WJ}`, `이${WJ}션`]);
  expect(keepPieces(["cof", "fee."])).toEqual(["cof", "fee."]);
  const parts = ["아잇 ", "라", "이커"];
  expect(keepPieces(parts).join("")).toBe(keepWords(parts.join("")));
});
```

- [ ] **Step 2:** `npx jest src/ui/keepWords.test.ts` → FAIL(숫자와 영어 뒤에 이음 문자가 없음, `keepPieces` 없음).
- [ ] **Step 3:** `keepWords`: 붙은 두 글자 `a`, `b`가 둘 다 띄어쓰기(`\s`)나 이음 문자가 아니고 하나라도 한글(`[가-힣]`)이면 사이에 이음 문자를 넣는다. 뒤보기(lookbehind) 없이 앞보기 정규식과 함수 치환으로 쓴다(Hermes). 두 칸짜리 글자의 반쪽끼리는 한글이 아니라 잇지 않는다. `keepPieces`: 조각마다 `keepWords`를 거치고, 조각의 끝 글자와 다음 조각의 첫 글자가 이어질 글자면 조각 끝에 이음 문자를 붙인다. 파일 머리 주석에 넓힌 까닭(2026-11-08, todo 12의 2, 3)을 더한다.
- [ ] **Step 4:** `common.tsx`에 `ErrorText`(`keepWords(text)`를 빨간 글자로)를 두고 `error` 스타일을 내보내는 `styles`에서 뺀다. `npx tsc --noEmit`이 짚는 곳을 모두 `ErrorText`로 바꾼다. `RoleplayScreen.tsx:589`은 오류면 `ErrorText`, 알림이면 `keepWords(state.message)`.
- [ ] **Step 5:** `npx jest && npx tsc --noEmit` → 모두 PASS, 오류 없음.
- [ ] **Step 6:** 커밋 `fix(app): keep Korean words whole next to digits and in error text`.

### Task 3: 대화 화면과 끝 화면의 한국어가 `keepWords`를 거친다 (할 일 3)

**Files:**
- Modify: `app/src/ui/Interpret.tsx:31`(소희의 통역), `app/src/ui/ThreeLine.tsx`(한글 발음 조각, 읽는 법), `app/src/screens/RoleplayScreen.tsx`(제목 476, 아래 줄 480-482, 제이크의 말 502, 지난 말풍선 521, 라이언의 평가 584), `app/src/screens/EndScreen.tsx`(제목 178, 마무리 말 181, 짚은 것 335)

**Interfaces:**
- Consumes: `keepWords`, `keepPieces`(Task 2).

- [ ] **Step 1:** 위 곳의 글을 `keepWords(...)`로 감싼다. `ThreeLine`의 `Pieces`는 무리마다 `keepPieces(g.map((s) => s.text))`로 조각 글을 바꾼다(영어 무리는 그대로 나온다). 영어 대사(라이언 말풍선, 들린 말)와 짧은 고정 글(버튼, 기다리는 글)은 감싸지 않는다.
- [ ] **Step 2:** `npx jest && npx tsc --noEmit` → 모두 PASS, 오류 없음.
- [ ] **Step 3:** 커밋 `fix(app): keep Korean words whole on the conversation and end screens`.

### Task 4: 지난 상황 목록을 복습하기를 연 동안 한 번만 받는다 (할 일 4)

**Files:**
- Modify: `app/src/screens/ReviewScreen.tsx`, `app/src/screens/PastTab.tsx`

**Interfaces:**
- Produces: `PastTab({ items, error, onRetry, dispatch }: { items: PastItem[] | null; error: string | null; onRetry: () => void; dispatch: Dispatch<Action> })`.

- [ ] **Step 1:** `ReviewScreen`이 `items`, `error`와 `loadPast()`(지금 `PastTab`의 `load`)를 갖고, 열릴 때 `saved.refresh()`와 함께 한 번 부른다. `PastTab`은 받은 것을 그리기만 한다. 머리 주석의 「switching tabs keeps this screen」에 지난 상황 목록도 더한다.
- [ ] **Step 2:** `npx jest && npx tsc --noEmit` → 모두 PASS, 오류 없음.
- [ ] **Step 3:** 커밋 `fix(app): load the past situations once while review is open`.

### Task 5: 연습을 준비하는 동안 ★는 확인 창을 열지 않는다 (할 일 5)

**Files:**
- Modify: `app/src/screens/SavedTab.tsx:53`

- [ ] **Step 1:** `askRemove`의 첫 줄을 `if (gate.busy || asking.current || saved.pending(i.text)) return;`로. 주석에 까닭(PR #30 리뷰 25점: 받아 오기가 끝나면 창이 연습 화면 위에 남아, 「빼기」를 누르면 연습 중인 문장이 빠졌다).
- [ ] **Step 2:** `npx jest && npx tsc --noEmit` → 모두 PASS, 오류 없음.
- [ ] **Step 3:** 커밋 `fix(app): ignore the star while a saved practice is starting`.

### Task 6: 스펙, 가이드, 할 일

**Files:**
- Modify: `docs/superpowers/specs/2026-11-07-review-screens-design.md`(2 탭, 4 ★, 7 줄바꿈), `docs/guide/APP_Expo_앱_뼈대와_서버_연결_20261105.md`, `docs/guide/README.md`
- Create: `docs/todo/20261107_12_todo_review_screens_minors.md`(원래 폴더의 것을 옮겨 상태 「완료」)

- [ ] **Step 1: 스펙.** 2에 「탭을 바꿔도 목록을 다시 받지 않는다(복습하기를 열 때 한 번)」, 4에 「「빼기」는 빼기만 하고, 빼면 목록에서 바로 지운다」와 「연습을 준비하는 동안 ★는 창을 열지 않는다」, 7에 「대화 화면, 끝 화면, 오류 글, 한글에 붙은 숫자와 영어도」를 2026-11-08 날짜와 함께 더한다.
- [ ] **Step 2: 가이드.** 「한국어가 낱말 가운데서 줄이 바뀐다」의 고친 것과 막는 방법을 넓힌 규칙, `ErrorText`(`tsc`가 잡는다), `keepPieces`로 고친다. 새 문제 셋을 더한다: 확인 창의 「빼기」가 `toggle`이라 다시 모을 수 있던 것(한 방향만 묻는 창은 한 방향 동작을 부르고, 되면 화면의 목록도 고친다), 조건으로 그린 탭이 바꿀 때마다 다시 만들어져 목록을 다시 받던 것(받은 것은 탭을 바꿔도 남는 화면에 둔다), 받아 오는 동안 연 확인 창이 다음 화면 위에 남던 것(누른 자리에서 게이트를 본다). 색인 한 줄을 고친다.
- [ ] **Step 3:** 커밋 `docs: record the review screens minors in the spec and guide`(할 일 파일을 「완료」로 함께 넣는다).

## 마무리

브랜치 전체 리뷰(리뷰어 한 명), push, PR, pr-review, devlog. 에뮬레이터(AVD `jake-english`)에서 확인한다: 긴 한국어(지난번 대화의 짚은 것, 소희의 통역, 상황 이름)가 낱말 사이에서 넘어가는 것, 지난 상황 탭을 오갈 때 목록이 비지 않는 것(맥 서버 기록에 `/past`가 한 번만 남는지), ★ 확인 창. 서버는 바꾸지 않으니 원래 폴더 서버를 멈추지 않는다. 그다음 APK를 폰에 깔고, 폰에서만 알 수 있는 것을 한두 개로 묶어 부탁한다.
