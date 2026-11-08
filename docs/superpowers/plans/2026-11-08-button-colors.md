# 앱 버튼의 색과 모양 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 덜 주된 버튼을 흰 바탕에 파란 테두리로, 누를 수 없는 버튼을 kind와 상관없이 같은 회색으로 그린다. 하는 일마다 다른 색은 첫 화면 카드에만 둔다.

**Architecture:** 버튼을 어떻게 그릴지는 순수 함수 `buttonLook`(새 파일 `app/src/ui/buttonLook.ts`)이 정하고, `Button`은 그 값을 스타일로 쓴다. 색 이름은 `theme.ts`에 모은다. `Button`의 `kind`는 `"primary" | "secondary"`로 이름을 바꾸고 부르는 곳을 모두 고친다. 어느 버튼이 주된 버튼인지는 바꾸지 않는다.

**Tech Stack:** React Native + Expo + jest(`cd app && npx jest && npx tsc --noEmit`). 새 꾸러미 없음.

**Spec:** `docs/superpowers/specs/2026-11-08-button-colors-design.md`

**실행 방식:** 이 세션이 직접 한다(executing-plans). 작업이 둘이고 `Button` 둘레라, 작업마다 새 에이전트를 띄우면 같은 맥락을 다시 읽는 데 더 든다. 같은 PR의 섀도잉 한마디 계획(`docs/superpowers/plans/2026-11-08-ryan-shadowing-tip.md`)까지 마친 뒤 새 리뷰어 한 명이 브랜치 전체를 보고, PR을 열면 pr-review로 본다. 이 저장소는 머지 전까지 묻지 않으므로(`AGENTS.md` 「PR과 머지」) 고르는 것을 묻지 않았다.

## Global Constraints

- 주된 버튼: `colors.primary`(`#1C7ED6`)로 꽉 채우고 흰 글자(`colors.onColor`). 지금과 같다.
- 덜 주된 버튼: 흰 바탕(`colors.bg`), 파란 테두리(두께 2, `colors.primary`), 파란 글자(`colors.primary`).
- 누를 수 없는 버튼: kind와 상관없이 회색 바탕, 회색 글자, 테두리 없음(바탕과 같은 색). 반투명으로 그리지 않는다. 글자는 「평가하고 있어요」가 읽힐 만큼 진하게(시작 값 바탕 `#E9ECEF`, 글자 `#868E96`, 폰에서 보고 정한다).
- 누르는 동안: 그 모양 그대로 조금 흐리게(`opacity` 0.7). 누를 수 없는 모양과 다르다.
- 테두리 두께는 정수 2. 주된 버튼에도 바탕과 같은 색 테두리 2를 둬 두 kind의 높이가 같다. 테두리만큼 안쪽 여백을 줄여 버튼의 바깥 크기는 지금과 같게 한다(보통 14/18 → 12/16, 작은 8/12 → 6/10).
- 바꾸지 않는 것: 어느 버튼이 주된 버튼인지, 버튼 글귀와 크기와 둥글기, 첫 화면 카드(`ChoiceCard`), 목록 카드(`ListCard`), 탭(`Tabs`), 글자 버튼(`InRowButton`, `StarButton`, `PractiseLink`), `BackButton`.
- 화면 캡처는 저장소 밖 임시 폴더(scratchpad)에 두고 공개 파일에 넣지 않는다.
- 커밋 메시지는 영어 Conventional Commits(scope `app`), 본문에 이유와 시험 결과, 끝에 `Refs: docs/superpowers/specs/2026-11-08-button-colors-design.md`. AI 서명 줄 없음. git은 `/usr/bin/git`.

## Review Focus

1. **누를 수 없는 주된 버튼이 덜 주된 버튼처럼 보인다:** 반투명 파랑이 연한 파랑이 되던 것. → Task 1 시험 `a disabled button looks the same whatever its kind`, `a disabled button is neither of the pressable looks`.
2. **누르는 순간 꺼진 것처럼 보인다:** 지금은 누르는 동안과 누를 수 없을 때가 같은 반투명이다. → Task 1 시험 `pressing only dims the button, unlike a disabled one`.
3. **테두리 때문에 한 줄의 두 버튼 높이가 다르다:** 「건너뛰기 | 🎤 말하기」, 「다시 해 보기 | 다음」. → Task 1 시험 `both kinds have a border of the same width`, Task 2 화면 확인.
4. **`plain`이 남아 연회색으로 그려진다:** → Task 1 타입 검사(`kind`가 `"primary" | "secondary"`만 받는다).
5. **「평가하고 있어요」, 「준비하고 있어요」가 안 읽힌다:** → Task 2 폰 스크린샷에서 확인하고 필요하면 글자 값을 고친다.

---

### Task 1: `buttonLook`와 `Button`

**Files:**
- Create: `app/src/ui/buttonLook.ts`
- Test: `app/src/ui/buttonLook.test.ts`
- Modify: `app/src/ui/theme.ts`, `app/src/ui/Button.tsx`
- Modify(부르는 곳): `app/src/screens/SituationScreen.tsx`, `app/src/screens/RoleplayScreen.tsx`, `app/src/screens/EndScreen.tsx`

**Interfaces:**
- Produces: `type ButtonKind = "primary" | "secondary"`, `type ButtonLook = { background: string; text: string; border: string; opacity: number }`, `buttonLook(kind: ButtonKind, state: { disabled?: boolean; pressed?: boolean }): ButtonLook`, `BUTTON_BORDER = 2`. `colors.off`(누를 수 없는 바탕), `colors.offText`(누를 수 없는 글자).

- [ ] **Step 1: 실패하는 시험을 쓴다** (`app/src/ui/buttonLook.test.ts`)

```ts
import { BUTTON_BORDER, buttonLook } from "./buttonLook";
import { colors } from "./theme";

test("a primary button is filled blue with white words", () => {
  expect(buttonLook("primary", {})).toEqual({ background: colors.primary, text: colors.onColor, border: colors.primary, opacity: 1 });
});

test("a secondary button is white with a blue border and blue words, so it does not look switched off", () => {
  expect(buttonLook("secondary", {})).toEqual({ background: colors.bg, text: colors.primary, border: colors.primary, opacity: 1 });
});

test("a disabled button looks the same whatever its kind", () => {
  expect(buttonLook("primary", { disabled: true })).toEqual(buttonLook("secondary", { disabled: true }));
  expect(buttonLook("primary", { disabled: true })).toEqual({ background: colors.off, text: colors.offText, border: colors.off, opacity: 1 });
});

test("a disabled button is neither of the pressable looks", () => {
  const off = buttonLook("secondary", { disabled: true });
  for (const kind of ["primary", "secondary"] as const) {
    const on = buttonLook(kind, {});
    expect(off.background).not.toBe(on.background);
    expect(off.text).not.toBe(on.text);
  }
});

test("pressing only dims the button, unlike a disabled one", () => {
  const pressed = buttonLook("secondary", { pressed: true });
  expect({ ...pressed, opacity: 1 }).toEqual(buttonLook("secondary", {}));
  expect(pressed.opacity).toBeLessThan(1);
  expect(pressed).not.toEqual(buttonLook("secondary", { disabled: true }));
});

test("both kinds have a border of the same width", () => {
  expect(BUTTON_BORDER).toBe(2);
});
```

- [ ] **Step 2: 실패를 본다**

Run: `cd app && npx jest src/ui/buttonLook.test.ts`
Expected: FAIL, `Cannot find module './buttonLook'`

- [ ] **Step 3: `theme.ts`에 `off: "#E9ECEF"`, `offText: "#868E96"`를 더하고, `buttonLook.ts`를 쓴다**

`disabled`가 `pressed`보다 앞선다. `theme.ts`의 두 색 옆에 「누를 수 없는 버튼, kind와 상관없이(spec button-colors 1)」 주석을 단다.

- [ ] **Step 4: 시험이 통과하는지 본다**

Run: `cd app && npx jest src/ui/buttonLook.test.ts`
Expected: PASS (6 tests)

- [ ] **Step 5: `Button.tsx`가 `buttonLook`을 쓰게 하고 `kind`를 `ButtonKind`로 바꾼다**

`Pressable`의 `style`에 `({ pressed }) => buttonLook(kind, { disabled, pressed })`의 바탕, 테두리(`borderWidth: BUTTON_BORDER`), 투명도를, 글자에 `text`를 쓴다. 지금의 `dim`, `plain`, `plainLabel` 스타일을 지운다. 여백은 Global Constraints 값. 파일 머리에 세 모양의 뜻을 한 줄로 적는다(spec button-colors 1).

- [ ] **Step 6: 부르는 곳의 `kind="plain"`과 `"plain"`을 `"secondary"`로 바꾼다**

`/usr/bin/grep -rn '"plain"' app/src`가 아무것도 찾지 않을 때까지. 화면 주석의 「gray」, 「회색 버튼」(예: `RoleplayScreen.tsx`의 「gray on the left, blue filling the rest」)도 「outlined」로 고친다.

- [ ] **Step 7: 앱 시험과 타입 검사를 모두 돌린다**

Run: `cd app && npx jest && npx tsc --noEmit`
Expected: 모든 시험 통과, 타입 오류 없음

- [ ] **Step 8: 커밋한다**

```bash
/usr/bin/git add app/src/ui/buttonLook.ts app/src/ui/buttonLook.test.ts app/src/ui/theme.ts app/src/ui/Button.tsx app/src/screens/SituationScreen.tsx app/src/screens/RoleplayScreen.tsx app/src/screens/EndScreen.tsx
/usr/bin/git commit -F - <<'EOF'
feat(app): draw secondary buttons outlined and disabled ones gray
...(이유, 시험 결과, Refs)
EOF
```

### Task 2: 폰에서 보기, 가이드와 문서

**Files:**
- Create: `docs/guide/APP_버튼_색과_모양_20261108.md`
- Modify: `docs/guide/README.md`(목록에 한 줄), `docs/PRD.md`(머리의 「고침」, 「첫 화면」의 버튼 색 줄), `docs/superpowers/specs/2026-11-08-record-cancel-skip-design.md`(맨 위에 한 줄)
- 할 일 상태: 원래 폴더의 `docs/todo/20261107_11_todo_button_color_review.md`를 이 worktree의 `docs/todo/`로 복사해 상태 줄을 완료로 고친다. 이 계획의 끝 커밋에 넣는다(`AGENTS.md` 「미룬 일」).

**Interfaces:**
- Consumes: Task 1의 `Button`.

- [ ] **Step 1: 앱을 빌드해 폰에 깐다**

`npm ci`(아직 안 했으면), `app/.env`(원래 폴더의 것을 복사), `app/README.md` 「빌드와 설치」. 깔기 전에 main 세션에 이 브랜치 앱을 깐다고 알린다. 앱만 바뀌었으니 맥 서버는 그대로 둔다(`docs/guide/DEVENV_폰을_adb로_시험하기_20261108.md` 「정한 기준」). 섀도잉 한마디 계획의 폰 확인과 한 번에 할 수 있으면 그 계획 Task 3의 빌드를 쓴다.

- [ ] **Step 2: 화면마다 스크린샷을 찍어 본다**

볼 곳: 상황 정하기의 주제, 직접 쓰기(「🎤 말로 하기」를 눌러 말하는 동안 「시작」이 회색), 대화 화면 아래 버튼 줄의 말하기 전, 녹음하는 동안, 평가하는 동안, 평가를 받은 뒤, 끝 화면, 복습하기 모아 둔 문장. 볼 것: Review Focus 1~5. 화면 확인은 섀도잉 한마디 계획 Task 3의 시험 서버(기록 복사본)에 붙은 앱으로 한다. 녹음하는 동안은 「취소」로 버리고, 평가하는 동안은 학습자 목소리로 만든 지어낸 녹음을 맥 스피커로 틀어 넣는다(`docs/guide/DEVENV_폰을_adb로_시험하기_20261108.md`). 방 소리가 든 녹음이 복사본에 남으면 바로 지운다. 「평가하고 있어요」가 안 읽히면 `colors.offText`를 진하게 고치고 Task 1 시험을 다시 돌린다.

- [ ] **Step 3: 가이드를 쓴다** (`docs/guide/APP_버튼_색과_모양_20261108.md`)

들어갈 것: 세 모양의 표(언제, 그리는 법), 「주된 버튼은 한 줄에 하나」, 「하는 일마다 다른 색은 첫 화면 카드에만」, 「누를 수 없는 버튼은 반투명이 아니라 정해진 회색」, 「버튼이 아닌 것(목록 카드, 탭, 글자 버튼)은 이 규칙 밖」, 까닭(사용자의 말 셋, 스펙 「왜 만드나」), 코드 위치(`buttonLook.ts`, `theme.ts`), 확인 방법(Task 1 시험 이름, 폰에서 볼 곳). 겪은 문제가 있었으면 증상, 원인, 고친 것, 막는 방법으로 더한다. `docs/guide/README.md` 목록에 한 줄 더한다.

- [ ] **Step 4: PRD와 앞선 스펙을 고친다**

- PRD 머리 「고침」 끝에: 「같은 날 앱 전체의 덜 주된 버튼을 흰 바탕에 파란 테두리로, 누를 수 없는 버튼을 회색으로 바꿨다(button-colors).」
- PRD 「첫 화면」의 「두 버튼은 이름과 설명이 든 카드이고 …」 줄 끝에: 앱의 다른 화면도 같은 까닭으로 덜 주된 버튼을 흰 바탕에 파란 테두리로 그리고, 하는 일마다 다른 색은 첫 화면 카드에만 쓴다(2026-11-08, AI 추천을 사용자가 받아들임, 스펙 경로).
- 취소 스펙 머리에: 「> 바뀜: 4의 「회색 버튼」은 2026-11-08 흰 바탕에 파란 테두리가 되었다(`docs/superpowers/specs/2026-11-08-button-colors-design.md`).」

- [ ] **Step 5: 할 일 파일을 완료로 고쳐 넣고 커밋한다**

```bash
cp "$(/usr/bin/git worktree list | head -1 | cut -d" " -f1)/docs/todo/20261107_11_todo_button_color_review.md" docs/todo/   # 원래 폴더의 할 일
# 상태 줄: > 상태: **완료** (2026-11-08 first-screen-buttons 카드, PR #<번호>)
/usr/bin/git add docs/guide/APP_버튼_색과_모양_20261108.md docs/guide/README.md docs/PRD.md docs/superpowers/specs/2026-11-08-record-cancel-skip-design.md docs/todo/20261107_11_todo_button_color_review.md
/usr/bin/git commit -F - <<'EOF'
docs: add the button look guide and update the PRD
...(이유, 폰에서 본 것, Refs)
EOF
```

PR 번호는 PR을 열기 전이면 상태 줄에 쓰지 않고 「PR에 넣음」으로 둔다.
