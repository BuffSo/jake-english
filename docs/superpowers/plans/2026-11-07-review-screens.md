# 첫 화면과 복습하기 화면 다시 그리기 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 첫 화면 버튼을 설명이 든 카드(「대화 연습하기」, 「복습하기」)로 바꾸고, 「다시 연습」 메뉴 화면을 두 탭(지난 상황, 모아 둔 문장)의 「복습하기」 화면으로 바꾸고, 화면의 「역할극」을 「대화」로 부른다.

**Architecture:** 기능과 맥 서버 API는 그대로 두고 화면만 바꾼다. 앱 상태에서 `review` 메뉴 화면을 없애고 `past`와 `saved`를 한 화면(`ReviewScreen`)의 두 탭으로 그린다. 그래서 지금의 「돌아올 곳」 규칙(지난번 대화 → `past`, 모아 둔 문장 연습 → `saved`)이 그대로 「들어갈 때의 탭으로 돌아오기」가 된다. 맥 서버는 라이언의 정해진 말 네 줄만 바꾼다.

**Tech Stack:** React Native 0.88 + Expo SDK 58(앱, jest-expo), Python(맥 서버, pytest). 새 꾸러미 없음.

**Spec:** `docs/superpowers/specs/2026-11-07-review-screens-design.md`

## Global Constraints

- 새로 설치하는 것이 없다. 그림은 그림 글자 💬와 보통 글자 ↻로 그린다. 꾸러미를 더해야 하면 멈추고 사용자에게 묻는다(`AGENTS.md`).
- 코드와 API 이름(`roleplay`, `Roleplay`, `review`, `past`, `saved`, `openReview`, `openPast`, `openSaved`)은 바꾸지 않는다. 화면에 보이는 글만 바꾼다.
- `server/je_server/prompts.py`는 고치지 않는다(같이 도는 offscript-aside 카드가 고친다, 스펙 6).
- 공개 저장소: 테스트와 문서의 예문은 지어낸 것만 쓴다. 지난 역할극 기록의 문장, 화면 캡처를 커밋하지 않는다.
- 색: 「대화 연습하기」는 `colors.primary`(`#1C7ED6`), 「복습하기」는 청록 `#0C8599`. 다른 화면의 버튼 색은 바꾸지 않는다.
- 글귀(스펙 그대로):
  - 첫 화면 버튼: 「대화 연습하기」 + 「상황을 정하면 라이언과 영어로 주고받아요」, 「복습하기」 + 「지난 상황과 모아 둔 문장을 다시 말해 봐요」
  - 라이언: `ask_mode` 「오늘은 무엇을 연습해 볼까요?」, `ask_again` 「이번에는 무엇을 연습해 볼까요?」
  - 복습하기 제목 「복습하기」, 탭 「지난 상황」, 「모아 둔 문장 4」(수를 모르면 「모아 둔 문장」)
  - 지난 상황 목록 위: 「마지막으로 한 날」, 줄의 날짜는 `latest`를 `dayKo`로(「11월 7일」)
  - 확인 창: 제목 「목록에서 뺄까요?」, 본문은 그 문장, 버튼 「취소」, 「빼기」
  - 「역할극」 → 「대화」: 스펙 6의 표 그대로
- git은 `/usr/bin/git`으로 부른다(worktree). 커밋은 `git commit -F - <<'EOF'`, Conventional Commits 영어, AI 서명 줄 없음, 끝에 `Refs: docs/superpowers/specs/2026-11-07-review-screens-design.md`.
- 테스트: 앱은 `cd app && npx jest && npx tsc --noEmit`, 서버는 `cd server && uv run pytest -q`(`server/README.md`).

## Review Focus

- **★를 눌러도 그 줄의 연습이 시작되지 않는다:** 모아 둔 문장 줄은 누르면 연습이 시작되는 카드이고 ★는 그 안의 작은 버튼이다. ★는 `InRowButton`(누를 수 없을 때도 `disabled`를 쓰지 않는다)으로 둔다. Task 3에서 에뮬레이터로 확인한다.
- **연습을 준비하는 사이 탭을 바꾸면:** 모아 둔 문장 탭에서 줄을 누르고(역할극을 받아 오는 중) 「지난 상황」 탭을 누르면 연습이 시작되지 않아야 한다. `startSaved`는 `saved` 화면에서만 받는다. Task 2의 테스트가 지킨다.
- **복습하기의 뒤로는 첫 화면으로:** 「모아 둔 문장」 탭에서 폰의 뒤로를 눌러도 「지난 상황」 탭이 아니라 첫 화면으로 간다(스펙 2). Task 2의 테스트가 지킨다.
- **마지막 문장을 빼면:** 목록이 비면 빈 안내가 나오고 맨 아래 「처음부터 차례로 연습」이 사라진다. 탭의 수도 0이 된다. Task 3에서 에뮬레이터로 확인한다.
- **긴 상황 이름:** 두 줄로 넘어가도 날짜와 「›」가 밀려나지 않는다. Task 3에서 에뮬레이터로 확인한다(「하와이 새우 트럭에서 갈릭 쉬림프」 같은 이름).

---

### Task 1: 라이언의 정해진 말

**Files:**
- Modify: `server/je_server/phrases.py`
- Test: `server/tests/test_phrases.py`

**Interfaces:**
- Produces: `PHRASES["ask_mode"]`, `PHRASES["ask_again"]`, `PHRASES["closing_retry"]`, `PHRASES["closing_clean"]`의 새 글. 소리 이름은 글에서 만들어지므로(`Engine.said`의 `audio_key`) 따로 할 일이 없다.

- [ ] **Step 1: 실패하는 테스트를 쓴다**

```python
def test_first_screen_asks_what_to_practise():
    # spec review-screens 1: 「복습하기」 is not a way of talking, so Ryan asks what to practise
    assert PHRASES["ask_mode"] == "오늘은 무엇을 연습해 볼까요?"
    assert PHRASES["ask_again"] == "이번에는 무엇을 연습해 볼까요?"


def test_ryan_says_daehwa_not_roleplay():
    # spec review-screens 6: on screen and in Ryan's fixed lines the roleplay is 「대화」
    assert PHRASES["closing_retry"].startswith("대화 끝! 수고했어요.")
    assert PHRASES["closing_clean"].startswith("대화 끝! 수고했어요.")
    assert not [k for k, v in PHRASES.items() if "역할극" in v]
```

`test_asking_again_neither_greets_nor_assumes_a_finished_roleplay`는 그대로 통과해야 한다.

- [ ] **Step 2: 실패를 본다** — `cd server && uv run pytest tests/test_phrases.py -q` → 새 두 테스트 FAIL
- [ ] **Step 3: `phrases.py`의 네 글을 바꾼다** — `closing_retry`는 「대화 끝! 수고했어요. 고칠 것이 남았던 대사를 다시 해 볼까요?」, `closing_clean`은 「대화 끝! 수고했어요. 오늘 정말 잘했어요.」. 그 밖의 글과 키는 그대로.
- [ ] **Step 4: 서버 테스트 전체를 돌린다** — `cd server && uv run pytest -q` → 모두 PASS. 글을 그대로 비교하는 다른 테스트(`test_contract.py`, `contract/`)가 깨지면 새 글로 맞춘다.
- [ ] **Step 5: 커밋** — `feat(server): have Ryan ask what to practise and say 대화`

### Task 2: 앱 상태의 복습하기 탭

**Files:**
- Modify: `app/src/flow/state.ts`
- Test: `app/src/flow/state.test.ts`(「다시 연습」 describe를 「복습하기」로)

**Interfaces:**
- Produces: `Screen = "home" | "situation" | "roleplay" | "end" | "past" | "saved"`(`review` 없음). `openReview`는 `home`에서만 받아 `past` 탭을 연다. `openPast`와 `openSaved`는 `past`나 `saved`에서만 받아 그 탭으로 바꾼다(`{ ...initial, screen }`). `back`은 `past`와 `saved`에서 `initial`(첫 화면)로 간다. 나머지 규칙(지난번 대화의 뒤로 → `past`, 모아 둔 문장 연습이 끝나거나 뒤로 → `saved`, `startSaved`는 `saved`에서만)은 그대로다.

- [ ] **Step 1: 테스트를 바꾼다** — describe 위의 줄을 `const review = reduce(initial, { type: "openReview" })`(이제 `past` 탭), `pastList = review`, `savedList = reduce(review, { type: "openSaved" })`로 두고 아래를 쓴다. 이름에 「다시 연습」이 든 테스트 이름과 주석은 「복습하기」로 바꾼다.

```ts
test("home opens 복습하기 on the past tab; back from either tab goes home", () => {
  expect(review.screen).toBe("past");
  expect(reduce(review, { type: "back" })).toEqual(initial);
  expect(reduce(savedList, { type: "back" })).toEqual(initial);
});

test("the tabs switch between past and saved", () => {
  expect(savedList.screen).toBe("saved");
  expect(reduce(savedList, { type: "openPast" }).screen).toBe("past");
});

test("the tabs are taken only on 복습하기", () => {
  expect(reduce(initial, { type: "openPast" })).toBe(initial);
  expect(reduce(initial, { type: "openSaved" })).toBe(initial);
  expect(reduce(at("ready"), { type: "openSaved" })).toEqual(at("ready"));
  expect(reduce(review, { type: "openReview" })).toBe(review);
});

test("a saved practice asked for before switching to the past tab does not start", () => {
  expect(reduce(pastList, { type: "startSaved", runs: [rp], order: [1] })).toBe(pastList);
});
```

  지금의 `"home opens review, review back goes home"`과 `"review opens past and saved; back from them returns to review"`는 위 둘로 바꾼다. `"back from a past view returns to the past list"`, `"back from saved practice returns to the saved list"`, `"a missing line in saved practice moves on"`은 그대로 통과해야 한다.
- [ ] **Step 2: 실패를 본다** — `cd app && npx jest src/flow/state.test.ts` → 새 테스트 FAIL
- [ ] **Step 3: `state.ts`를 고친다** — `Screen`에서 `review`를 빼고, 위 Interfaces대로 `back`, `openReview`, `openPast`, `openSaved`를 바꾼다. `Screen` 위 주석도 고친다. `askFirst` 주석의 「역할극을 그만둘까요?」는 「대화를 그만둘까요?」로.
- [ ] **Step 4: 테스트와 타입 검사** — `cd app && npx jest && npx tsc --noEmit` → jest는 PASS. `tsc`는 `App.tsx`의 `state.screen === "review"`에서 실패할 수 있다. 그 줄은 Task 3에서 고치므로, 이 Task에서는 `App.tsx`의 `review` 분기만 지우고(`past`, `saved` 분기는 그대로) 타입 검사를 통과시킨다.
- [ ] **Step 5: 커밋** — `feat(app): turn the review menu into past and saved tabs in the app state`

### Task 3: 복습하기 화면

**Files:**
- Modify: `app/src/ui/theme.ts`(`colors.review = "#0C8599"`, `colors.onColorSub = "rgba(255,255,255,0.85)"`, `colors.line = "#E9ECEF"` 같은 이름 — 이미 같은 값이 있으면 그것을 쓴다)
- Create: `app/src/ui/ListCard.tsx`, `app/src/ui/Tabs.tsx`
- Modify: `app/src/screens/ReviewScreen.tsx`(메뉴 → 틀: 뒤로, 제목, 탭, 탭 내용)
- Rename + Modify: `app/src/screens/PastScreen.tsx` → `app/src/screens/PastTab.tsx`, `app/src/screens/SavedScreen.tsx` → `app/src/screens/SavedTab.tsx`(`git mv` 뒤 고친다. 헤더와 뒤로 버튼은 `ReviewScreen`으로 옮긴다)
- Modify: `app/App.tsx`

**Interfaces:**
- Consumes: Task 2의 `Screen`, `openPast`, `openSaved`, `back`.
- Produces:
  - `ListCard({ onPress, children, chevron = true }: { onPress: () => void; children: ReactNode; chevron?: boolean })`: 연회색(`colors.ryan`) 둥근 카드, 누르면 흐려짐, 오른쪽 끝 「›」. Task 4가 상황 정하기 목록에 쓴다.
  - `Tabs({ tabs, current, onChange }: { tabs: { key: string; label: string }[]; current: string; onChange: (key: string) => void })`: 연회색 바탕, 고른 칸만 흰 바탕.
  - `ReviewScreen({ tab, dispatch }: { tab: "past" | "saved"; dispatch: Dispatch<Action> })`
  - `PastTab({ dispatch })`, `SavedTab({ dispatch })`: 목록만 그린다.

- [ ] **Step 1: `ListCard`, `Tabs`와 색 이름을 만든다.** 화면 부품이라 jest 테스트는 없다. 길이는 React Native 숫자 값.
- [ ] **Step 2: `ReviewScreen`을 틀로 바꾼다.** 위에서부터 `BackButton`(→ `dispatch({ type: "back" })`, `useBackKey`도), 제목 「복습하기」(`common.title`), `Tabs`(「지난 상황」, 「모아 둔 문장 n」 — n은 `useSaved().items()?.length`, `undefined`면 수 없이), 그 아래 `flex: 1`로 `PastTab` 또는 `SavedTab`. 탭을 누르면 `openPast`/`openSaved`. 열릴 때 `saved.refresh()`는 지금처럼 한 번(`SavedTab`이 따로 부르지 않게 하나로 모은다).
- [ ] **Step 3: `PastTab`.** 목록 위에 「마지막으로 한 날」(`common.sub`보다 작게, `colors.weak`), 줄은 `ListCard` 안에 상황 이름(왼쪽, `flex: 1`, 두 줄까지 넘어감)과 `dayKo(i.latest)`(오른쪽, 작게). 빈 목록, 오류, 다시 시도, 누르면 `openPastRun`은 지금과 같다. 맨 위 주석의 「first day」를 「last day」로 고친다.
- [ ] **Step 4: `SavedTab`.** 줄은 `ListCard`(`chevron={false}`) 안에: 위쪽 왼쪽 이름표(지금과 같은 색), 위쪽 오른쪽 ★(`InRowButton`, 노란 별 `#F59F00`, `dim={saved.pending(i.text)}`), 문장, 「상황 이름 · 11월 7일에 모음」. ★를 누르면:

  ```ts
  Alert.alert("목록에서 뺄까요?", i.text, [
    { text: "취소", style: "cancel" },
    { text: "빼기", style: "destructive", onPress: () => saved.toggle(i.rp_id, i.idx, i.text) },
  ]);
  ```

  빈 안내는 「아직 모아 둔 문장이 없어요. 대화나 연습에서 ☆를 누르면 여기에 모여요.」 맨 아래 「처음부터 차례로 연습(n)」, 연습 시작(게이트, 역할극 받아 오기, `startSaved`)은 지금과 같다.
- [ ] **Step 5: `App.tsx`** — `state.screen === "past" || state.screen === "saved"`이면 `<ReviewScreen tab={state.screen} dispatch={dispatch} />`. 같은 자리에 같은 부품이라 탭을 바꿔도 틀은 다시 만들어지지 않는다.
- [ ] **Step 6: 검사** — `cd app && npx jest && npx tsc --noEmit` → PASS. `grep -rn "PastScreen\|SavedScreen" app/src app/App.tsx` → 결과 없음(주석 포함).
- [ ] **Step 7: 커밋** — `feat(app): show 복습하기 as past and saved tabs of gray cards`

### Task 4: 첫 화면 카드와 상황 정하기 목록

**Files:**
- Create: `app/src/ui/ChoiceCard.tsx`
- Modify: `app/src/screens/HomeScreen.tsx`, `app/src/screens/SituationScreen.tsx`(목록 단계만)

**Interfaces:**
- Consumes: Task 3의 `ListCard`, `colors.review`, `colors.onColorSub`.
- Produces: `ChoiceCard({ icon, title, line, color, onPress }: { icon: string; title: string; line: string; color: string; onPress: () => void })`: 색이 찬 둥근 카드. 왼쪽 그림(`icon`, 흰색, 굵게, 26쯤 — 그림 글자는 색을 무시한다), 가운데 제목(흰색, 굵게)과 설명(`colors.onColorSub`, 작게), 오른쪽 「›」. 테두리와 그림 뒤 바탕은 없다(스펙 1).

- [ ] **Step 1: `ChoiceCard`를 만든다.**
- [ ] **Step 2: `HomeScreen`** — 두 `Button`을 `ChoiceCard`로: 「대화 연습하기」(💬, `colors.primary`, `onRoleplay`)와 「복습하기」(↻, `colors.review`, `onReview`). 라이언의 말과 첫 카드 사이를 띄우고(20쯤), 두 카드 사이는 12쯤. 버튼 위 주석의 이름도 새 이름으로.
- [ ] **Step 3: `SituationScreen`** — 목록 단계의 카드(`styles.card`, `styles.chevron`)를 `ListCard`로 바꾸고 쓰지 않게 된 스타일을 지운다. 다른 단계는 그대로.
- [ ] **Step 4: 검사** — `cd app && npx jest && npx tsc --noEmit` → PASS
- [ ] **Step 5: 커밋** — `feat(app): draw the first screen choices as cards with a line inside`

### Task 5: 화면의 「역할극」을 「대화」로

**Files:**
- Modify: `app/src/screens/RoleplayScreen.tsx`(확인 창 두 줄, 「역할극으로」 버튼 한 줄만. offscript-aside 카드가 같은 파일을 고치므로 이 세 줄 말고는 손대지 않는다)

- [ ] **Step 1: 바꾼다** — `Alert.alert("대화를 그만둘까요?", "하던 대화는 아직 이어 할 수 없어요.", …)`, `label={midway ? "대화로 돌아가기" : "다음"}`.
- [ ] **Step 2: 남은 것을 찾는다** — `grep -rn '역할극\|상황 역할극\|다시 연습' app/src app/App.tsx server/je_server | grep -v '^\S*:\s*//\|^\S*:\s*#\|test'` 결과에서 화면이나 라이언의 말로 나가는 글(따옴표 안의 한국어)만 본다. 「내 대사 다시 연습」은 그대로 둔다. `prompts.py`는 고치지 않는다(Global Constraints). 남은 것이 있으면 같은 커밋에서 고친다.
- [ ] **Step 3: 검사** — `cd app && npx jest && npx tsc --noEmit` → PASS
- [ ] **Step 4: 커밋** — `feat(app): call the roleplay 대화 on screen`

### Task 6: 한국어 줄바꿈 확인과 에뮬레이터 확인

화면을 처음 실제로 보는 Task다. 에뮬레이터는 이 앱 전용 AVD `jake-english`만 쓴다(다른 AVD는 다른 프로젝트 것이다). 다른 세션이 `jake-english`를 띄웠으면 쓰지 않고 사용자에게 묻는다. 맥 서버는 원래 폴더의 것(launchd)을 그대로 쓴다. 이 Task에서는 서버를 멈추지 않는다(라이언의 새 말은 폰 시험에서 듣는다).

**Files:**
- (끊길 때만) Create: `app/src/ui/keepWords.ts`, Test: `app/src/ui/keepWords.test.ts`
- (끊길 때만) Modify: 한국어를 보이는 첫 화면, 복습하기, 상황 정하기 목록의 `Text`

- [ ] **Step 1: APK를 빌드해 에뮬레이터에 깐다** — `app/README.md` 「빌드와 설치」(JDK 17, `-PreactNativeArchitectures=arm64-v8a`), `app/.env`가 없으면 원래 폴더에서 복사한다. `adb -s <에뮬레이터> install -r …`.
- [ ] **Step 2: 화면을 본다** — 첫 화면, 복습하기 두 탭, ★ 확인 창(취소와 빼기, 마지막 문장을 빼면 빈 안내와 버튼이 사라지는지), 줄을 누르면 연습, ★를 누르면 연습이 시작되지 않는지, 긴 상황 이름, 상황 정하기 목록, 대화 중 뒤로의 확인 창 글. `adb exec-out screencap -p`로 찍은 것은 scratchpad에만 두고 커밋하지 않는다.
- [ ] **Step 3: 낱말 가운데서 줄이 바뀌는지 본다** — 라이언의 인사(「안녕하세요, 라이언입니다. 오늘도 만나서 반가워요.」), 카드의 설명, 긴 상황 이름에서 낱말이 갈리는지 본다.
  - **갈리지 않으면:** Step 4~6을 건너뛰고, 확인한 것을 devlog 「검증」에 적는다.
  - **갈리면:** Step 4로.
- [ ] **Step 4: (갈릴 때) 실패하는 테스트**

```ts
import { keepWords } from "./keepWords";

const WJ = "⁠";

test("Korean breaks only between words", () => {
  expect(keepWords("반가워요")).toBe(`반${WJ}가${WJ}워${WJ}요`);
  expect(keepWords("오늘도 만나서")).toBe(`오${WJ}늘${WJ}도 만${WJ}나${WJ}서`);
});

test("text without Hangul stays as it is", () => {
  expect(keepWords("Could I get a latte?")).toBe("Could I get a latte?");
});
```

- [ ] **Step 5: (갈릴 때) `keepWords(text: string): string`** — 한글 글자(가–힣) 둘 사이에 단어 이음 문자 U+2060을 넣는다. 안드로이드는 한글 글자 사이 어디서나 줄을 바꾸는데, U+2060 앞뒤에서는 바꾸지 않는다. 이 화면들의 한국어 `Text`에만 쓴다(영어 문장에는 쓰지 않는다). 테스트 PASS를 본 뒤 다시 빌드해 에뮬레이터에서 확인한다.
- [ ] **Step 6: (갈릴 때) 커밋** — `fix(app): keep Korean words whole when lines wrap`. 겪은 문제(증상, 원인, 고친 것, 같은 실수를 막는 법)는 `docs/guide/APP_Expo_앱_뼈대와_서버_연결_20261105.md`에 한 절로 더하고 같은 커밋에 넣는다.
- [ ] **Step 7: 간격과 크기를 맞춘다** — Step 2에서 보기에 어색한 간격, 크기가 있으면 고치고 `style(app): …`로 커밋한다. 사용자가 고른 초안(스펙 2~4)과 다른 배치는 만들지 않는다.

### Task 7: PRD, 가이드, 앞선 스펙의 이름

**Files:**
- Modify: `docs/PRD.md`
- Modify: `docs/guide/APP_Expo_앱_뼈대와_서버_연결_20261105.md`(「상황 역할극」 한 곳)
- Modify(맨 위에 한 줄만): `docs/superpowers/specs/2026-11-05-speaking-practice-design.md`, `2026-11-05-roleplay-practice-design.md`, `2026-11-06-waiting-animation-design.md`, `2026-11-06-korean-translation-design.md`, `2026-11-07-review-practice-design.md`, `2026-11-07-situation-topics-design.md` 가운데 첫 화면 버튼(「상황 역할극」)이나 화면 이름(「다시 연습」 화면)이 나오는 것

- [ ] **Step 1: PRD를 고친다**
  - 맨 위 「고침」 줄에 2026-11-07 review-screens를 더한다(첫 화면 버튼과 라이언의 질문, 「복습하기」 화면과 탭, 지난 상황의 마지막으로 한 날, 앱 화면에서 「역할극」을 「대화」로).
  - 「첫 화면」: 라이언이 「무엇을 연습할지」 묻는다. 선택지는 「대화 연습하기」와 「복습하기」(한 줄 설명, 파랑과 청록 카드). 「복습하기」 안의 두 탭.
  - 「방식」의 「상황 역할극」 줄에 「앱 화면에서는 「대화」라고 부르고, 첫 화면 버튼은 「대화 연습하기」다(2026-11-07 사용자)」를 더한다. 기능 이름 「역할극」은 문서에서 그대로 쓴다.
  - 「다시 연습」 절을 「복습하기」로: 「지난 상황」 목록에 상황 이름과 마지막으로 한 날이 보인다(처음 한 날에서 바꾼 까닭은 스펙 3). 횟수는 보이지 않는다.
  - 공개 규칙: 예문은 지어낸 것만, 개인 정보 없음.
- [ ] **Step 2: 가이드의 「상황 역할극」을 「대화 연습하기」로**(버튼을 가리키는 곳이면).
- [ ] **Step 3: 앞선 스펙의 맨 위에 한 줄** — `> 고침: 2026-11-07 첫 화면 버튼과 화면 이름이 바뀌었다(「상황 역할극」 → 「대화 연습하기」, 「다시 연습」 → 「복습하기」). 본문은 그때의 이름 그대로 둔다. 지금 화면은 docs/superpowers/specs/2026-11-07-review-screens-design.md.` 다시 연습 스펙에는 「지난 상황의 날짜는 마지막으로 한 날로 바뀌었다」도 붙인다. 계획과 devlog, ADR은 고치지 않는다.
- [ ] **Step 4: 커밋 둘** — PRD: `docs(prd): name the first screen choices 대화 연습하기 and 복습하기`. 가이드와 스펙 머리줄: `docs: point older specs and the app guide to the new screen names`.

---

## 마무리 (superpowers 흐름 + `AGENTS.md`)

이 계획의 Task가 아니라 브랜치를 끝내는 순서다.

1. 브랜치 전체 최종 리뷰(`REVIEW.md`, `AGENTS.md`를 함께 넘긴다). 확인된 문제를 고친다.
2. todo를 닫는다: 원래 폴더의 `docs/todo/20261107_02_todo_review_screens_design.md`를 이 worktree의 `docs/todo/`로 복사하고 상태를 「**완료** (2026-11-07 review-screens, PR #…)」로 고쳐, 마지막 작업 커밋에 함께 넣는다. 머지 뒤 원래 폴더를 fast-forward하기 전에 원래 폴더의 같은 파일(untracked)을 지운다(같은 경로라 merge가 막힌다).
3. push, PR(제목 영어, 본문 한국어 절: 요약, 배경, 한계, 테스트 체크리스트, 문서). `RoleplayScreen.tsx`를 세 줄 고친 것을 본문에 적는다(offscript-aside와 겹침).
4. pr-review로 리뷰하고 확인된 문제를 고쳐 push. `REVIEW.md` 「고치는 방법」을 본다.
5. devlog `docs/devlog/2026-11-07-review-screens.md`(흐름 표: 초안 A/B/C, ★와 확인 창, 버튼 색, 그림, 이름, 날짜).
6. APK를 빌드해 폰(USB, 이름에 `:`이 없고 `emulator-`가 아닌 것)에 깐다. 이 카드의 APK라고 사용자에게 알린다. 라이언의 새 말은 이 worktree의 서버로 들어야 하니 `docs/guide/DEVENV_맥서버_저절로_띄우기_20261107.md` 「카드가 서버를 시험할 때」를 따른다(`server/scripts/autostart.sh status`를 먼저 보고, 끝나면 바로 `start`).
7. 폰에서 확인할 것을 알리고 머지 결정을 묻는다.
8. 작은 일(원래 폴더 todo 01, 05)은 머지 뒤 같은 worktree의 새 브랜치에서 따로 계획해 다음 PR로 한다.
