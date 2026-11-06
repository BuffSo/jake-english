# 기다리는 동안 생각하는 얼굴 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 기다리는 여섯 곳의 도는 표시를 생각하는 얼굴(두 장 크로스페이드)과 점 세 개로 바꾼다.

**Architecture:** 맥 서버가 생각하는 얼굴 그림 네 장을 `/assets/`로 내주고, 그 경로를 `/home`의 `images.thinking`으로 알린다. 앱은 `/home` 답을 React context로 앱 전체에 나눠 준다. `ThinkingFace`가 경로를 받아 그림을 동그라미에 겹쳐 놓고 투명도로 번갈아 보여 준다. 어느 얼굴을 쓸지 고르는 규칙과 경로 꺼내기는 순수 함수로 두고 jest로 시험한다.

**Tech Stack:** FastAPI(pytest), Expo SDK 58 / React Native 0.88 `Animated`(jest-expo, tsc). 새 패키지는 없다.

**Spec:** `docs/superpowers/specs/2026-11-06-waiting-animation-design.md`

## Global Constraints

- 새 패키지를 설치하지 않는다. 움직임은 React Native `Animated`만 쓰고 `useNativeDriver: true`(투명도만 바꾼다).
- 그림 파일은 저장소에 넣지 않는다. 서버가 `JE_ASSETS_DIR`에서 읽는다.
- 그림 이름: `jake-thinking-1.png`, `jake-thinking-2.png`, `ryan-thinking-1.png`, `ryan-thinking-2.png`(512×512 정사각형, 얼굴만 담았다).
- `/home`의 `images.thinking`: `{"jake": ["/assets/jake-thinking-1.png", "/assets/jake-thinking-2.png"], "ryan": ["/assets/ryan-thinking-1.png", "/assets/ryan-thinking-2.png"]}`.
- 타이밍: 그림 한 장 1.8초 보여 주기, 0.6초 동안 겹쳐 바꾸기. 점 세 개 한 바퀴 1.2초.
- 크기: 상황 화면 위쪽 동그라미 160, 역할극 화면과 끝 화면의 동그라미 96.
- 얼굴 고르기: 기다리는 글이 「제이크」로 시작하면 제이크, 아니면 라이언.
- 도는 표시(`ActivityIndicator`)는 다시 쓰지 않는다.

## Review Focus

- **옛 서버와 새 앱:** `/home` 답에 `images.thinking`이 없으면(머지 전 서버) 얼굴 없이 글과 점만 나오고, 상황 화면은 듣는 얼굴을 그대로 둔다. Task 2의 `framesFor` 시험이 `undefined`를 다룬다.
- **기다리는 중에 사람이 바뀜:** 지금 main의 상황 화면은 `working` 단계 안에서 「제이크가 상황을 고르고 있어요」에서 「라이언이 대본을 만들고 있어요」로 글만 바뀐다. 얼굴도 제이크에서 라이언으로 바뀌고, 앞 사람의 애니메이션 상태가 남지 않아야 한다. Task 3에서 `ThinkingFace`를 사람마다 `key`로 새로 그린다.
- **화면을 떠날 때:** 기다리는 중에 뒤로 가면 `Animated.loop`가 멈춰야 한다. Task 3의 두 애니메이션 모두 effect 정리에서 `stop()`한다.
- **그림을 못 받음(404, 연결 끊김):** 동그라미 배경색만 남고 오류 문구도 앱 멈춤도 없다. 폰에서 옛 서버로 확인한다.
- **경로가 한 장뿐:** 한 장이면 번갈아 보여 주지 않고 그대로 둔다. Task 3의 애니메이션은 두 장 이상일 때만 돈다.

---

### Task 1: 서버가 생각하는 얼굴을 내주고 경로를 알린다

**Files:**
- Modify: `server/je_server/app.py:26` (`ASSETS`), `server/je_server/app.py:124-128` (`/home`)
- Test: `server/tests/test_api.py` (`test_home_lists_fixed_lines` 고치기, 새 시험 하나)

**Interfaces:**
- Produces: `/home` 답 `images.thinking: {"jake": [str, str], "ryan": [str, str]}`. `/assets/{위 네 이름}`이 200.

- [ ] **Step 1: Write the failing tests**

`test_home_lists_fixed_lines`의 마지막 줄을 바꾼다.

```python
    assert j["images"] == {
        "front": "/assets/ryan-front.png",
        "listening": "/assets/ryan-listening.png",
        "thinking": {
            "jake": ["/assets/jake-thinking-1.png", "/assets/jake-thinking-2.png"],
            "ryan": ["/assets/ryan-thinking-1.png", "/assets/ryan-thinking-2.png"],
        },
    }
```

새 시험:

```python
def test_thinking_faces_served(client, settings):
    settings.assets_dir.mkdir(parents=True)
    names = ["jake-thinking-1.png", "jake-thinking-2.png", "ryan-thinking-1.png", "ryan-thinking-2.png"]
    for n in names + ["jake-front.png"]:
        (settings.assets_dir / n).write_bytes(b"png")
    for n in names:
        r = client.get(f"/assets/{n}")
        assert r.status_code == 200 and r.content == b"png"
    assert client.get("/assets/jake-front.png").status_code == 404  # on disk but not listed
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd server && uv run pytest tests/test_api.py -q`
Expected: 2 failed (`images` 비교, 새 시험의 404)

- [ ] **Step 3: `ASSETS`에 네 이름을 더하고, `/home`의 `images`에 `thinking`을 더한다**

`/home`의 경로 목록은 `ASSETS`와 따로 손으로 적지 말고 한 곳(모듈 상수 `THINKING = {"jake": [...], "ryan": [...]}`)에서 만들어 `ASSETS`와 `/home`이 같이 쓴다.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd server && uv run pytest -q`
Expected: 모두 통과

- [ ] **Step 5: Commit** — `feat(server): serve the thinking faces and list them in /home`

### Task 2: 앱이 얼굴과 그림 경로를 고른다

**Files:**
- Modify: `app/src/api/types.ts` (`Home.images`)
- Create: `app/src/ui/thinking.ts`
- Test: `app/src/ui/thinking.test.ts`

**Interfaces:**
- Produces (in `app/src/ui/thinking.ts`):
  - `export type Who = "jake" | "ryan"`
  - `export type Thinking = { jake: string[]; ryan: string[] }` (`types.ts`의 `Home.images.thinking`도 이 타입)
  - `export function waiterOf(text: string): Who`
  - `export function framesFor(thinking: Thinking | null | undefined, who: Who): string[]`

- [ ] **Step 1: Write the failing tests**

```ts
import { framesFor, waiterOf } from "./thinking";

const thinking = { jake: ["/assets/jake-thinking-1.png", "/assets/jake-thinking-2.png"], ryan: ["/r1.png", "/r2.png"] };

test("the person named in the waiting text thinks, Ryan otherwise", () => {
  expect(waiterOf("제이크가 상황을 고르고 있어요")).toBe("jake");
  expect(waiterOf("라이언이 대본을 만들고 있어요")).toBe("ryan");
  expect(waiterOf("받아쓰고 있어요")).toBe("ryan");
  expect(waiterOf("다음 대사를 준비하고 있어요")).toBe("ryan");
  expect(waiterOf("")).toBe("ryan");
});

test("frames come from /home for that person", () => {
  expect(framesFor(thinking, "jake")).toEqual(["/assets/jake-thinking-1.png", "/assets/jake-thinking-2.png"]);
  expect(framesFor(thinking, "ryan")).toEqual(["/r1.png", "/r2.png"]);
});

test("no frames before /home or from an older server", () => {
  expect(framesFor(null, "jake")).toEqual([]);
  expect(framesFor(undefined, "ryan")).toEqual([]);
  expect(framesFor({ ryan: ["/r1.png"] } as never, "jake")).toEqual([]);
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd app && npx jest src/ui/thinking.test.ts`
Expected: FAIL (`Cannot find module './thinking'`)

- [ ] **Step 3: `thinking.ts`를 만들고 `Home.images`에 `thinking: Thinking`을 더한다**

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd app && npx jest && npx tsc --noEmit`
Expected: 모두 통과, 타입 오류 없음

- [ ] **Step 5: Commit** — `feat(app): pick the thinking face and its pictures for a wait`

### Task 3: 생각하는 얼굴과 점을 그리고 여섯 기다림에 붙인다

**Files:**
- Create: `app/src/ui/ThinkingFace.tsx`
- Modify: `app/src/screens/common.tsx` (`Waiting`), `app/App.tsx`(provider), `app/src/screens/SituationScreen.tsx`(위쪽 동그라미), `app/src/screens/RoleplayScreen.tsx`(두 곳), `app/src/screens/EndScreen.tsx`(한 곳)

**Interfaces:**
- Consumes: Task 2의 `Who`, `Thinking`, `framesFor`, `waiterOf`. `api.imageSource(path)`.
- Produces (in `app/src/ui/ThinkingFace.tsx`):
  - `export const ThinkingFaces: React.Context<Thinking | null>`
  - `export function ThinkingFace({ who, size, fallback }: { who: Who; size: number; fallback?: ReactNode }): ReactNode` — 경로가 없으면 `fallback`(없으면 `null`)
  - `export function Dots(): ReactNode`
- `Waiting({ text, who }: { text: string; who?: Who })` — `who`가 있으면 크기 96 얼굴, 글, 점. 없으면 글과 점.

이 Task의 화면은 jest로 그리지 않는다(시험 도구를 새로 들이지 않는다). `tsc`와 기존 jest, 그리고 PR 뒤 폰 확인으로 본다.

- [ ] **Step 1: `ThinkingFace.tsx`를 만든다**
  - 동그라미: `RyanCircle`과 같은 모양(`overflow: "hidden"`, 배경 `colors.ryan`, 가운데 정렬). 그림은 정사각형이라 동그라미 크기 그대로 채운다.
  - 모든 그림을 겹쳐(`position: "absolute"`) 한 번에 그린다. 그래야 바뀔 때 받기를 기다리지 않는다. 첫 장 투명도 1, 나머지 0.
  - 그림이 두 장 이상일 때만 `Animated.loop`로 돌린다: 지금 장을 1.8초 두고, 0.6초 동안 지금 장 투명도 1→0과 다음 장 0→1을 함께(`Animated.parallel`) 바꾼다. 마지막 장 다음은 첫 장이다.
  - 사람이 바뀌면 처음부터 다시 그린다: 바깥 `ThinkingFace`가 안쪽 컴포넌트를 `key={who}`로 그린다.
  - 점 세 개(`Dots`): 지름 8, 간격 6, 색 `colors.sub`. 0.4초씩 차례로 투명도 0.3→1→0.3, 한 바퀴 1.2초, `Animated.loop`.
  - 두 애니메이션 모두 effect 정리에서 `stop()`한다.
  - 파일 맨 위에 주석: 왜 도는 표시를 바꿨는지(2026-11-06 사용자), 스펙 경로.
- [ ] **Step 2: `Waiting`을 바꾼다** — `ActivityIndicator`를 빼고 위 인터페이스대로. 글 아래에 `Dots`.
- [ ] **Step 3: `App.tsx`에서 화면 전체를 `<ThinkingFaces.Provider value={home?.images.thinking ?? null}>`로 감싼다**
- [ ] **Step 4: 화면에 붙인다**
  - `RoleplayScreen.tsx`: 두 `Waiting`에 `who="ryan"`.
  - `EndScreen.tsx`: `Waiting`에 `who="ryan"`.
  - `SituationScreen.tsx`: 위쪽 `RyanCircle`을 담은 자리에서, `step === "working"`이면 `<ThinkingFace who={waiterOf(status)} size={160} fallback={듣는 얼굴 RyanCircle} />`, 아니면 지금처럼 듣는 얼굴. 아래 `<Waiting text={status} />`는 바꾸지 않는다(얼굴 없이 글과 점). PR #18과 겹치지 않게 다른 줄은 건드리지 않는다.
- [ ] **Step 5: 확인**

Run: `cd app && npx jest && npx tsc --noEmit`
Expected: 모두 통과, 타입 오류 없음. `grep -rn ActivityIndicator app/src`가 아무것도 찾지 않는다.

- [ ] **Step 6: Commit** — `feat(app): show a thinking face instead of the spinner while waiting`

### Task 4: 문서

**Files:**
- Modify: `docs/PRD.md` (「첫 화면: 라이언이 묻는다」)
- Create: `docs/guide/ASSET_제미나이로_얼굴_그림_만들기_20261106.md`, 색인 `docs/guide/README.md`
- 비공개(커밋 안 함): 원래 폴더 `docs/private/private-notes.md`에 그림 폴더와 만든 과정

- [ ] **Step 1: PRD** — 라이언 얼굴이 나오는 때에 「Claude가 무언가 만드는 동안 생각하는 얼굴」을 더하고, 제이크 얼굴도 AI가 만든 반실사 그림이며 비공개 폴더에 둔다는 것, 스펙 경로를 적는다. 만든 방법의 개인적인 부분은 「비공개 메모 참고」로만 쓴다.
- [ ] **Step 2: 가이드** — 이번에 겪은 문제와 해결: 다른 사람 그림을 그림체 참고로 넣으면 얼굴이 섞인다, 같은 대화에서 고쳐 달라고 하면 거의 안 바뀐다, 같은 그림을 두 번 고친 결과는 구도가 같아 맥에서 맞추고 섞을 수 있다(50/50 섞기로 겹침 확인, 두 그림의 중간 그림풍 만들기). 개인 정보 없이 쓴다.
- [ ] **Step 3: 비공개 메모** — 원래 폴더의 `private-notes.md`에 `jake-gemini-inputs/`, `assets/jake-drafts/`, `assets/thinking-drafts/`와 제이크 얼굴을 만든 과정을 적는다(커밋하지 않는다).
- [ ] **Step 4: Commit** — `docs: record the thinking faces in the PRD and the image guide`
