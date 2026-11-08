# 목록 대본의 소희 통역 미리 준비하기 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 목록 상황의 대본 줄마다 소희의 한국어를 저장소에 써 두고, 소희 소리는 처음 고를 때 뒤에서 만들어 둔다. 통역을 눌러도 Claude를 부르지 않고, 소리도 대개 이미 있다.

**Architecture:** `topics.Pick`에 줄마다의 한국어(`ko`)를 더한다. `Engine.create_pick`은 그 한국어를 줄의 통역으로 넣고, 맥에 이미 있는 소희 소리는 그대로 쓴다. 없는 소리는 그 역할극의 본보기 소리와 내 대사 읽는 법이 끝난 뒤, 녹음에 답하는 동안은 쉬면서 한 줄씩 만든다.

**Tech Stack:** Python 3 + FastAPI(서버, `cd server && uv run pytest -q`). 앱은 고치지 않는다(앱은 줄에 온 `ko`, `ko_audio`를 이미 쓴다, `app/src/flow/interpret.ts`의 `koOf`).

**Spec:** 할 일 `docs/todo/20261108_13_todo_list_scripts_ko_and_sohee_model.md`(원래 폴더에서 옮겨 온다). 고칠 스펙: `docs/superpowers/specs/2026-11-06-korean-translation-design.md`(「하지 않을 것」의 미리 만들기), `docs/superpowers/specs/2026-11-08-fixed-list-scripts-design.md`. ADR-0013 「영향」.

## Global Constraints

- 목록에서 고른 줄의 통역은 Claude를 부르지 않는다. 제이크 추천과 직접 쓴 상황은 지금처럼 누를 때 만든다.
- 첫 내 대사가 늦어지지 않는다: 소희 소리는 그 역할극의 본보기 소리와 내 대사 읽는 법 뒤에 만든다. 고친 뒤에도 처음 고른 운동화 사이즈의 첫 내 대사가 PR #36처럼 0.1초 안쪽이다.
- 소희 소리는 지금처럼 복제 소희(`"sohee"`), 한국어, 받아쓰기로 끝까지 맞는지 본다(`check=True`). 미리 만드는 일이라 급하지 않다(`urgent=False`).
- 한국어는 공개 파일에 들어간다: 지어낸 대본을 옮긴 것만 쓰고, 사용자의 지난 기록 문장과 문장 단위로 겹치지 않는다(개수만 출력해 확인). 사실은 대본과 같고, 앞뒤 줄을 이어 읽어 뜻이 새로 생기지 않는다.
- 같이 도는 카드: `tts_worker.py`와 `engine.py`의 `_quiet`는 고치지 않는다(three-line-listen이 고친다). `topics.py`는 목록 줄(`picks`)만 고친다(jake-endings가 주제별 예문을 고친다).
- git은 `/usr/bin/git`, 커밋은 `git commit -F - <<'EOF'`, Conventional Commits 영어, 본문에 이유와 시험 결과와 `Refs:`, AI 서명 없음.

## Review Focus

1. **맥에 이미 같은 소희 소리가 있다**(앞 회차가 만들었거나, 같은 글을 전에 누른 적이 있다): 새 역할극의 줄에 바로 그 소리가 붙고 다시 만들지 않는다. 시험: Task 1 `test_sohee_sound_already_on_the_mac_comes_with_the_line`.
2. **녹음에 답하는 동안 차례가 온다:** 소희 소리를 새로 시작하지 않고, 답이 끝나면 이어 간다. 답이 오래 끝나지 않아도(닫히지 않은 요청) 영영 멈추지 않는다. 시험: Task 1 `test_sohee_waits_while_a_recording_is_answered`, `test_sohee_does_not_wait_forever`.
3. **소희 소리를 만들지 못한다:** 그 줄의 통역 글은 그대로 있고, 다음 줄의 소리는 계속 만든다. 앱에서 누르면 지금처럼 다시 만든다. 시험: Task 1 `test_a_failed_sohee_sound_leaves_the_text_and_the_rest`.
4. **앞 회차의 통역이 저장소와 다르다**(이 PR 전에 Haiku가 만든 것): 저장소의 한국어가 이긴다. 옛 소리도 따라오지 않는다. 시험: Task 1 `test_repository_korean_wins_over_an_earlier_runs`.
5. **사용자가 통역을 눌러 소리를 먼저 만들었다**(뒤에서 차례가 오기 전): 뒤에서는 같은 소리를 다시 만들지 않는다. 시험: Task 1 `test_sohee_asked_first_is_not_made_twice`.

---

### Task 1: 목록 줄의 통역과 소희 소리를 미리 준비하는 틀

**Files:**
- Modify: `server/je_server/topics.py`(`Pick.ko`), `server/je_server/engine.py`(`create_pick`, 새 `_sohee_later`, `attempt`을 감싸는 답하는 동안 표시)
- Test: `server/tests/test_picks.py`, `server/tests/fakes.py`(`FakeVoice`가 `rank`를 남김)

**Interfaces:**
- Produces:
  - `Pick.ko: tuple[str, ...] = ()` — `script`와 같은 차례의 소희 한국어. 비어 있거나 짧으면 그 줄은 지금처럼 누를 때 만든다.
  - `Engine.sohees: dict[str, asyncio.Task]` — 역할극마다 소희 소리를 미리 만드는 일 하나(시험이 기다린다).
  - `SOHEE_RANK = 1000` — 미리 만드는 소희 소리의 차례(`rank=SOHEE_RANK + idx`). 다른 역할극의 본보기 소리(`rank=idx`)가 먼저다.
  - `QUIET_WAIT = 60` — 녹음에 답하는 동안 소희 소리를 미루는 가장 긴 시간(초).

- [ ] **Step 1: 실패하는 시험** — `test_picks.py`에 도우미 `with_korean(monkeypatch)`(운동화 줄마다 지어낸 한국어 `"테스트 한국어 {i}"`를 `dataclasses.replace(p, ko=...)`로 붙여 `topics.pick`에 건다)와 아래 시험:
  - `test_pick_lines_carry_the_repository_korean`: 줄마다 `ko == p.ko[i]`, `await engine.ko(rp.id, i)`가 그 글을 주고 `fake_claude.interpret_calls == []`.
  - `test_first_pick_makes_sohee_sounds_after_the_lines_are_ready`: `await engine.sohees[rp.id]` 뒤 줄마다 `ko_audio == audio_key("sohee", "korean", ko)`. `fake_voice.calls`에서 소희 부름은 모두 `(ko, "sohee", "korean", False)`이고, 그 역할극의 본보기 소리 부름(`"ryan", "english"`)보다 뒤다. 소희 글은 모두 `fake_voice.checked`에 있고, `fake_voice.ranks`의 소희 차례는 `SOHEE_RANK + idx`다.
  - `test_sohee_waits_for_the_learner_notes`: `fake_claude.annotate_gate`로 읽는 법을 막으면 소희 부름이 없다. 풀면 생긴다.
  - `test_sohee_sound_already_on_the_mac_comes_with_the_line`: 첫 회차의 소희 소리를 다 만든 뒤 두 번째 고르면 줄마다 만들 때부터 `ko_audio`가 있고, 소희 부름이 늘지 않으며 `rp.id not in engine.sohees`.
  - `test_sohee_waits_while_a_recording_is_answered`: `fake_whisper.transcribe`를 막아 둔 `attempt`가 도는 동안 소희 부름이 없다. 답이 끝나면 생긴다.
  - `test_sohee_does_not_wait_forever`: `engine_module.QUIET_WAIT`를 0.01로 줄이고 답하는 표시를 닫지 않아도 소희 소리가 만들어진다.
  - `test_a_failed_sohee_sound_leaves_the_text_and_the_rest`: `fake_voice.fail_text`를 한 줄의 한국어로 두면 그 줄은 `ko`가 있고 `ko_audio is None`, 다른 줄은 `ko_audio`가 있다. 그 뒤 `fail_text = None`이면 `await engine.ko_audio(...)`가 만든다.
  - `test_repository_korean_wins_over_an_earlier_runs`: 첫 회차 기록의 한 줄에 다른 `ko`와 `ko_audio`를 넣어 저장하면, 다음 회차의 그 줄은 저장소의 `ko`이고 옛 `ko_audio`가 아니다.
  - `test_sohee_asked_first_is_not_made_twice`: 읽는 법을 막아 소희 차례를 늦춘 채 `await engine.ko_audio(rp.id, 1)`로 먼저 만들면, 풀고 `sohees`를 기다린 뒤 그 글의 소희 부름은 한 번이다.
  - 기존 `test_ko_comes_with_its_sound`는 저장소 한국어가 없는 줄(`ko=()`)의 길로 그대로 둔다.
- [ ] **Step 2: 실패를 본다** — `cd server && uv run pytest tests/test_picks.py -q`, 새 시험이 FAIL(`Pick`에 `ko`가 없다)
- [ ] **Step 3: 구현**
  - `create_pick`: `_prepared` 뒤, 저장소 한국어가 있는 줄은 `ko`를 그 글로, `ko_audio`를 `audio_key("sohee", "korean", ko)`의 파일이 맥에 있을 때만 그 키로(없으면 `None`) 둔다. 저장소 한국어가 없는 줄만 앞 회차의 것을 빌린다(지금 `_prepared`). `ko`가 있고 `ko_audio`가 없는 줄이 있으면 `self.sohees[rp.id] = asyncio.create_task(self._sohee_later(rp.id))`(`_quiet` 콜백, 끝나면 사전에서 뺀다).
  - `_sohee_later(rp_id)`: 그 역할극의 `self.tasks`와 `self.threes` 일을 `gather(..., return_exceptions=True)`로 기다린 뒤, 줄마다 차례로: 녹음에 답하는 동안이면 `QUIET_WAIT`까지 기다리고, `voice.say(ko, "sohee", "korean", urgent=False, rank=SOHEE_RANK + idx, check=True)`, `update_line(..., ko_audio=key)`. 한 줄의 `VoiceError`는 기록만 하고 다음 줄로 간다.
  - 답하는 동안 표시: `attempt`를 새 `_attempt`(지금 몸통)로 옮기고, `attempt`는 그 둘레에서 답하는 수를 세어 0이 되면 `asyncio.Event`를 켠다.
- [ ] **Step 4: 통과를 본다** — `cd server && uv run pytest -q` 모두 PASS
- [ ] **Step 5: 커밋** (`feat(server): prepare Sohee's sound for list picks after the lines`)

### Task 2: 목록 대본 줄마다 소희 한국어를 써 둔다

사용자가 고른 통역 모델(Haiku 또는 Sonnet)로 한 번 만들고, 읽어 고친 것을 쓴다.

**Files:**
- Modify: `server/je_server/topics.py`(대본 줄을 `(말하는 사람, 영어, 한국어)` 셋으로, `_pick`이 `script`와 `ko`로 나눈다)
- Test: `server/tests/test_topics.py`

- [ ] **Step 1: 실패하는 시험**
  - `test_every_line_has_sohee_korean`: 모든 목록 줄에서 `len(p.ko) == len(p.script)`, 한국어마다 한글이 있고, 로마자, 따옴표(`claude.QUOTES`), 줄바꿈, 중괄호가 없다(소희가 소리 내 읽는다).
  - `test_korean_keeps_the_facts`: 대본 사실 시험(`test_script_keeps_the_facts_of_its_description`)과 짝을 이룬다. 경복궁 `4호선`, `충무로`, `3호선`, `5번 출구`; 교통카드 `현금`, `편의점`; 삼겹살 `삼겹살`, `2인분`; 새우 트럭 `스캠피`, `밥`, `두 스쿱`; 호텔 `여권`, `체크아웃`, `와이파이`; 운동화 `270`, `9`.
- [ ] **Step 2: 실패를 본다** — `cd server && uv run pytest tests/test_topics.py -q`
- [ ] **Step 3: 한국어 만들기** — 스크래치 스크립트로 고른 모델의 `Claude.interpret`를 줄마다 한 번 부른다(앞뒤 줄은 대본 그대로). 읽어 고칠 것: 사실이 대본과 같은지, 앞뒤 줄을 이어 읽어 뜻이 새로 생기지 않는지(PR #34: 「현금이 없다」 뒤 「편의점」), 말투(점원은 손님에게, 서울 사람은 낯선 관광객에게 존댓말), 로마자 없이 소리 나는 대로(`티머니`, `와이파이`).
- [ ] **Step 4: 지난 기록과 맞대기** — 앱 데이터 폴더의 `roleplay.json` 모든 줄의 `ko`와 평가 글을 문장으로 나눠(띄어쓰기와 문장부호 무시) 새 한국어 문장과 같은 것의 개수만 출력한다. 0이 아니면 그 문장을 바꿔 쓰고 다시 센다. 기록의 글은 출력하지 않는다.
- [ ] **Step 5: 통과를 본다** — `cd server && uv run pytest -q` 모두 PASS
- [ ] **Step 6: 커밋** (`feat(server): write Sohee's Korean for every list script line`)

### Task 3 (사용자가 Sonnet을 고를 때만): 통역은 글쓰기 모델로

- **Files:** `server/je_server/claude.py`(`interpret`이 `self.writer`), `server/tests/test_claude.py`, `server/README.md` 「Claude 모델 고르기」, 말하기 스펙 「기다리는 시간과 모델」, ADR-0004 「영향」, 소희 통역 스펙 「제약」
- [ ] 시험: `interpret`의 요청 모델이 글쓰기 모델(`claude-sonnet-5-5`)이고 `live` 설정(빠른 실패)은 그대로다 → 실패를 보고 → 고치고 → `uv run pytest -q` → 커밋(`feat(server): interpret with the writer model`)

### Task 4: 문서와 할 일

- [ ] 소희 통역 스펙 「하지 않을 것」의 미리 만들기: 목록 상황은 저장소에 한국어를 써 두고 소리를 처음 고를 때 뒤에서 만든다(사용자 2026-11-08). 「정한 것」 4, 5와 「잰 것」에 한 줄씩.
- [ ] 목록 대본 스펙 1, 2와 「하지 않을 것」(통역은 저장소에 둔다), 처음 대본 표 아래에 통역은 `topics.py`에 있다는 한 줄. ADR-0013 「영향」에 한 줄. PRD 「통역」에 한 줄과 머리의 고침 줄.
- [ ] 원래 폴더의 할 일 13을 이 worktree로 옮겨 상태를 「완료」로, 1~4가 어떻게 끝났는지 적는다. 원래 폴더의 사본은 머지 뒤 정리 때 지운다.
- [ ] 커밋(`docs: prepare Sohee's Korean for list picks in the specs`)

### Task 5: 시간 재기와 서버 확인

- [ ] `docs/guide/DEVENV_맥서버_저절로_띄우기_20261107.md`대로 데이터 세 항목을 복사해 worktree 서버를 `JE_HOST=127.0.0.1 JE_PORT=8795 JE_WHISPER_PORT=8796`으로 띄운다.
- [ ] 운동화 사이즈(나 먼저)와 경복궁(라이언 먼저)을 처음 고르고, 고르기, 첫 내 대사까지, 그 역할극의 소희 소리가 다 만들어지기까지를 잰다. 줄의 `ko`가 고를 때 이미 있고, `GET …/ko`가 Claude 없이 오고, `GET …/ko/audio`가 소리가 만들어진 뒤 바로 오는지 본다. Expected: 첫 내 대사 0.1초 안쪽(운동화).
- [ ] 두 번째 고를 때 줄마다 `ko_audio`가 처음부터 있다.
- [ ] 시험 서버를 끄고 복사본을 지운다. devlog에 잰 값을 적는다.
