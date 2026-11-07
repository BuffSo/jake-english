# 다시 연습과 상황 주제의 작은 일 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 다시 연습(PR #27)과 상황 주제(PR #28)의 최종 리뷰가 미룬 작은 일 여섯을 고친다.

**Architecture:** 기능은 바꾸지 않는다. 맥 서버의 기록 읽기(`Engine.saved`, `Engine.latest`, `Store.load_saved`)를 깨진 파일에 강하게 하고 한 번만 읽게 하며, 앱의 소리 차례에 쉼을 넣고, 상황 정하기의 돌아올 단계를 바로잡는다. 테스트와 계약 예시를 더한다.

**Tech Stack:** Python(맥 서버, pytest), React Native + Expo(앱, jest). 새 꾸러미 없음.

**Spec:** 원래 폴더의 `docs/todo/20261107_01_todo_review_practice_minors.md`, `docs/todo/20261107_05_todo_situation_topics_minors.md`(아직 커밋하지 않은 할 일 파일, 마지막 커밋에 「완료」로 넣는다). 기능의 스펙은 `docs/superpowers/specs/2026-11-07-review-practice-design.md`, `docs/superpowers/specs/2026-11-07-situation-topics-design.md`.

## Global Constraints

- 새로 설치하는 것이 없다. 공개 저장소 규칙대로 테스트의 문장은 지어낸 것을 쓴다.
- 커밋은 `/usr/bin/git`, `git commit -F - <<'EOF'`, 앞 커밋이 성공해야 다음이 돌게 `&&`로 잇는다.
- 테스트: 앱 `cd app && npx jest && npx tsc --noEmit`, 서버 `cd server && uv run pytest -q`.

## 정한 것 (AI 판단)

- **처음 녹음 사이의 쉼(01-1):** 맥에 있는 녹음 마흔 개의 앞뒤 빈 소리를 쟀다. 끝에 빈 소리가 거의 없는 녹음이 많아(0초가 열여섯 개), 두 녹음 사이가 0.3~0.5초뿐이거나 드물게 붙는다. 그래서 0.6초 쉰다. 소리 차례(`SoundQueue`)에 쉼을 넣는 `enqueuePause(ms)`를 더한다. `clear()`는 쉼도 버린다.
- **깨진 `saved.json`(01-2):** 읽을 때는 `Store.all`처럼 건너뛰고(목록은 빈 것으로, 읽지 못한 항목은 하나씩 뺀다) 기록을 남긴다. 다음에 모으거나 빼서 새로 쓸 때 깨진 파일을 덮어쓰기 전에 `saved.broken.json`으로 남긴다. 이미 있으면 `saved.broken.2.json`처럼 다음 이름으로 남긴다(최종 리뷰가 짚음: 처음에는 한 번만 남겨 두 번째로 깨지면 잃었다). 손으로 고칠 수 있게 하려는 것이다.
- **빈 목록으로 돌아오기(05-1):** 돌아올 단계가 「목록」인데 그 주제의 목록이 비었으면 「정하는 방법」으로 연다. 돌아올 곳을 고르는 일을 `flow/situation.ts`의 함수 하나로 모은다.

---

### Task 1: 처음 녹음 두 개 사이에 쉬기 (01-1)

**Files:** Modify `app/src/audio/player.ts`, `app/src/screens/EndScreen.tsx`. Test `app/src/audio/player.test.ts`.

- [ ] 실패하는 테스트: `a pause holds the next sound until it has passed`(a, 600ms 쉼, b를 넣고 a가 끝난 뒤 599ms에는 b가 아직, 600ms에 b), `clear drops a pause on its way`(쉼 중에 `clear()` 하면 b가 나오지 않는다), 쉼 동안 `isPlaying()`은 참.
- [ ] `SoundQueue.enqueuePause(ms: number): void`. 차례의 항목을 `{ src } | { pause }`로 바꾸고, 쉼이면 `setTimeout`으로 `next()`.
- [ ] `EndScreen`의 `playPair`가 이번 녹음이 있으면 사이에 `enqueuePause(PAIR_GAP_MS)`(600).
- [ ] 커밋 `fix(app): pause between the first and this recording`.

### Task 2: 깨진 기록에서 모아 둔 문장이 멈추지 않게 (01-2)

**Files:** Modify `server/je_server/engine.py`(`_resolve`), `server/je_server/store.py`(`load_saved`, `save_saved`). Test `server/tests/test_saved.py`.

- [ ] 실패하는 테스트: 모아 둔 문장이 가리키는 `roleplay.json` 하나가 깨져도 `Engine.saved()`가 나머지를 돌려준다. 깨진 `saved.json`이면 `saved()`가 빈 목록이고, 항목 하나만 깨졌으면 그 항목만 빠진다. 깨진 `saved.json`에서 문장을 모으면 새 파일이 써지고 옛 내용은 `saved.broken.json`에 남는다.
- [ ] `_resolve`가 `KeyError`와 함께 `ValueError`(pydantic의 검증 오류 포함)도 `None`으로. `load_saved`가 파일과 항목을 읽지 못하면 건너뛰고 경고를 남긴다(글은 남기지 않는다). `save_saved`가 지금 파일을 읽지 못하면 덮어쓰기 전에 `saved.broken.json`으로 옮긴다.
- [ ] 커밋 `fix(server): skip unreadable records in the saved sentences`.

### Task 3: 지난번 대화가 기록을 한 번만 읽게 (01-3)

**Files:** Modify `server/je_server/engine.py`(`summary`, `latest`). Test `server/tests/test_review.py` 또는 `test_summary.py`.

- [ ] 실패하는 테스트: `Engine.latest(group)`이 `Store.all`을 한 번만 부른다(세는 감싸개로).
- [ ] `summary(rp_id, rps: list[Roleplay] | None = None)`: 받은 기록이 있으면 그것으로 묶음을 고른다. `latest`가 읽은 기록을 넘긴다.
- [ ] 커밋 `perf(server): read the records once for the last conversation`.

### Task 4: 빈 목록으로 돌아오지 않게 (05-1)

**Files:** Modify `app/src/flow/situation.ts`, `app/src/screens/SituationScreen.tsx`. Test `app/src/flow/situation.test.ts`.

- [ ] 실패하는 테스트: `resumeFrom(start, topics)`가 모르는 주제면 `null`, 단계가 `list`인데 그 주제의 목록이 비었으면 `{ topic, step: "how" }`, 아니면 그대로.
- [ ] `resumeFrom`을 만들고 `SituationScreen`의 `known`을 그것으로.
- [ ] 커밋 `fix(app): open how-to-pick when the topic's list came back empty`.

### Task 5: 목록의 첫 사람을 지키는 대본 테스트 (05-2)

**Files:** Test `server/tests/test_claude.py`(필요하면 `fakes.py`의 `script_json`에 `first` 인자).

- [ ] 테스트: 목록 줄의 첫 사람이 나(`first="user"`)인데 Claude가 라이언으로 시작하는 대본을 주면, `make_script`가 다시 요청하고(두 번째 요청에 「the learner must speak first」), 두 번째 대본(내가 먼저)을 돌려준다. 지금 코드로 통과해야 한다(빠졌던 테스트를 채우는 것).
- [ ] 커밋 `test(server): pin a list pick's first speaker through make_script`.

### Task 6: 자잘한 것 (05-3)

**Files:** Modify `app/src/flow/situation.ts`, `app/src/screens/SituationScreen.tsx`, `server/je_server/store.py`. Create `contract/home-topics.json`. Test `server/tests/test_contract.py`, `app/src/api/contract.test.ts`, `app/src/api/types.ts`(키 목록).

- [ ] 앱: `OTHER_TOPIC`(`"other"`)을 `flow/situation.ts`에서 내보내고, 상황 화면의 버튼 색과 `BEFORE_TOPICS`가 그것을 쓴다.
- [ ] 서버: `store.recent_situations`의 기본값과 비교를 `topics.OTHER`로.
- [ ] 계약: `/home`의 `topics` 모양 예시(`contract/home-topics.json`, 지어낸 주제 하나와 목록 줄 하나). 서버 테스트는 `topics.public()`의 키와 같은지, 앱 테스트는 `TOPIC_KEYS`, `PICK_KEYS`와 같은지 본다.
- [ ] 커밋 둘: `refactor: name the other topic once on each side`, `test: add a contract example for the home topics`.

## 마무리

브랜치 전체 리뷰, todo 01과 05를 「완료」로 고쳐 마지막 커밋에 넣기, push, PR, pr-review, devlog. 서버를 바꾸므로 머지 뒤 원래 폴더 서버를 다시 띄운다. 폰 확인은 「처음 녹음」 사이의 쉼만(사용자가 들어야 아는 것).
