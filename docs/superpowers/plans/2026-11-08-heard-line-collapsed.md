# 「들린 말」을 한 줄로 접어 두기 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 들린 말을 이름표 없이 흐린 한 줄로 접어 두고, 누르면 펼친다(대화 화면, 끝 화면).

**Architecture:** 들린 말을 그리는 부품 `HeardLine` 하나를 두 화면이 같이 쓴다. 접힘은 그 부품이 받는 `open`으로 정한다. 지나간 말풍선과 끝 화면의 줄은 지금의 펼침(`openRow`)을 그대로 넘기고, 방금 녹음한 내 말은 그 글을 열쇠로 한 펼침을 `toggleRow`로 바꾼다.

**Tech Stack:** Expo(React Native 0.88), TypeScript, jest(jest-expo). 새로 설치하는 것이 없다.

**Spec:** `docs/superpowers/specs/2026-11-08-heard-line-collapsed-design.md`

## Global Constraints

- 「들린 말:」 이름표를 쓰지 않는다. 글은 `keepWords`를 거친다.
- 접힌 모양: `numberOfLines={1}`, 끝을 자른다(`ellipsizeMode="tail"`). 펼친 모양: 줄 제한 없음.
- 색과 크기는 지금 값 그대로: 대화 화면 `fontSize: 14, color: colors.sub`, 끝 화면 `fontSize: 15, color: colors.sub`.
- 「펼치기」 같은 글자나 단추를 더하지 않는다. 짚은 것은 접지 않는다.
- 테스트 예문은 지어낸 것을 쓴다(`AGENTS.md` 「공개 저장소」).

## Review Focus

1. 한국어 들린 말: 펼쳤을 때 낱말 가운데서 줄이 바뀌지 않는다(`keepWords`). Task 1의 테스트가 한국어 글로 본다.
2. 방금 녹음한 내 말에서 「🔊 내 녹음」을 누르면 들린 말이 펼치지 않는다(두 Pressable이 형제). 에뮬레이터로 본다(Task 3).
3. 녹음을 다시 보내 들린 말이 바뀌면 접힌 채로 나온다. `toggleRow`를 쓰는 열쇠가 글이라 맞다. 에뮬레이터로 본다.
4. 지나간 말풍선 중 `idx`가 없는 것은 열 수 없어 들린 말도 펼 수 없다. 지금 내 말풍선은 늘 `idx`가 있다(`state.ts`의 기록). 리뷰에서 확인한다.
5. 360dp 폭에서 들린 말 한 줄과 「🔊 내 녹음」이 한 줄에 같이 들어간다(들린 말이 줄어든다, `flexShrink: 1`). 에뮬레이터로 본다.

---

### Task 1: `heardView`와 `HeardLine` 부품

**Files:**
- Create: `app/src/ui/heardView.ts`, `app/src/ui/heardView.test.ts`, `app/src/ui/HeardLine.tsx`

**Interfaces:**
- Produces: `heardView(text: string, open: boolean): { text: string; lines: 1 | undefined }`
- Produces: `HeardLine(props: { text: string; open: boolean; style?: StyleProp<TextStyle>; onPress?: () => void })`. `onPress`가 있으면 `Pressable`(hitSlop 8)로 감싸고, 없으면 `Text`만 그린다(둘레의 말풍선이 누름을 받는다).

- [ ] **Step 1: 실패하는 테스트를 쓴다** (`heardView.test.ts`)

```ts
test("no label, kept words", () => {
  expect(heardView("I'd like a cup of copy", false).text).toBe(keepWords("I'd like a cup of copy"));
  expect(heardView("커피 한 잔 주세요", true).text).toBe(keepWords("커피 한 잔 주세요"));
  expect(heardView("Hi there", false).text).not.toContain("들린 말");
});
test("folded is one line, open has no limit", () => {
  expect(heardView("Hi there", false).lines).toBe(1);
  expect(heardView("Hi there", true).lines).toBeUndefined();
});
```

- [ ] **Step 2: 돌려 실패를 본다.** `cd app && npx jest src/ui/heardView.test.ts` → 모듈이 없어 FAIL.
- [ ] **Step 3: `heardView`와 `HeardLine`을 쓴다.** `HeardLine`은 `heardView`의 `lines`를 `numberOfLines`로, `ellipsizeMode="tail"`.
- [ ] **Step 4: 돌려 통과를 본다.** 같은 명령 → PASS. `npx tsc --noEmit` 오류 없음.
- [ ] **Step 5: 커밋** `feat(app): add the folded heard line part`

### Task 2: 두 화면에 쓰기

**Files:**
- Modify: `app/src/screens/RoleplayScreen.tsx`(`myBubble`의 `heardRow`, `state.heard`의 `heardNow`, 스타일 `heardLine`, `heard`)
- Modify: `app/src/screens/EndScreen.tsx`(`TryView`, 스타일 `heard`)
- Modify: `docs/PRD.md`(「역할극 뒤 연습과 주고받은 말 보기」)

**Interfaces:**
- Consumes: Task 1의 `HeardLine`, `app/src/flow/review.ts`의 `toggleRow(open: string | null, key: string): string | null`

- [ ] **Step 1: 지나간 내 말풍선.** `keepWords(`들린 말: ${b.text}`)` 대신 `<HeardLine text={b.text} open={opened} style={[styles.heardLine, styles.shrink]} />`. `onPress` 없음.
- [ ] **Step 2: 방금 녹음한 내 말.** `const [heardOpen, setHeardOpen] = useState<string | null>(null)`. `<HeardLine text={state.heard} open={heardOpen === state.heard} onPress={() => setHeardOpen((o) => toggleRow(o, state.heard!))} style={[styles.heard, styles.shrink]} />`. 「🔊 내 녹음」은 그대로 형제로 둔다. `Pressable`이 줄어들 수 있게 감싸는 쪽에 `flexShrink: 1`을 준다.
- [ ] **Step 3: 끝 화면.** `TryView`의 들린 말을 `<HeardLine text={t.heard} open={open} style={styles.heard} />`로. `onPress` 없음(줄이 누름을 받는다).
- [ ] **Step 4: PRD 한 줄.** 「주고받은 말과 역할극 중의 지나간 말풍선은 평소에 문장만 보여 준다」 줄 뒤에: 들린 말은 이름표 없이 흐린 한 줄, 길면 「…」, 누르면 펼친다(2026-11-08 사용자, 스펙 경로).
- [ ] **Step 5: 확인.** `cd app && npm test && npx tsc --noEmit` → 모두 통과. 화면 코드에 `들린 말:`이 남지 않았다(`grep -rn "들린 말:" app/src` → 없음).
- [ ] **Step 6: 커밋** `feat(app): fold the heard line to one line until opened`(PRD는 `docs(prd): …`로 따로)

### Task 3: 에뮬레이터 확인

- [ ] APK를 빌드해 AVD `jake-english`에 깐다(`app/README.md`, 비공개 메모의 JDK와 SDK). 시험 서버는 원래 폴더 서버를 그대로 쓴다(앱만 바뀐 PR).
- [ ] 「이 상황 다시 하기」 복사본으로 본다. 학습자 목소리 녹음은 `try_recordings.py`로 보내 긴 영어와 한국어 들린 말을 만든다(`docs/guide/DEVENV_폰없이_녹음_시험하기_20261108.md`). 대화 화면은 「하던 대화 이어 하기」로 그 복사본에 들어가 본다.
- [ ] Review Focus 2, 3, 5와 스펙 「확인 방법」의 에뮬레이터 항목을 스크린샷으로 본다. 360dp는 `wm density 480`, 끝나면 `reset`.
- [ ] 스펙 3(이름표 없이 알아보는지)을 판단한다. 헷갈리면 초안을 그려 main 세션에 묻는다.
- [ ] 시험 복사본과 녹음을 지운다. 에뮬레이터를 끈다.
