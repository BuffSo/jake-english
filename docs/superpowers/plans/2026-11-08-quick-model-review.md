# 제이크 추천만 Sonnet으로 바꾸기 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 제이크 추천은 Sonnet(새 설정 `JE_CLAUDE_RECOMMEND`, 기본 sonnet)으로 하고, 소희 통역과 라이언 평가는 짧은 말 모델(`JE_CLAUDE_QUICK`, Haiku) 그대로 둔다. 추천 답에 메시지의 이름표(「끝말:」 같은 것)가 따라 나오면 서버가 걷어 낸다(할 일 21).

**Architecture:** `Claude`가 짧은 말 모델과 따로 추천 모델을 받는다. 값은 짧은 말과 같은 `QUICKS`에서 고른다(설정은 같고 모델만 다르다). 이름표는 `strip_endings` 앞에서 걷어, 이름표 뒤에 다시 붙은 끝말도 지금의 끝말 갈아 끼우기로 하나가 되게 한다.

**Tech Stack:** Python 3.12, FastAPI 서버(`server/`), pytest, anthropic SDK.

**Spec:** 사용자 결정(2026-11-08 main 세션에서 「ㅇㅋ」), 할 일 `docs/todo/20261108_24_todo_quick_model_sonnet_review.md`, `docs/todo/20261108_21_todo_jake_echoes_message_labels.md`. 고칠 스펙: 말하기 스펙 「기다리는 시간과 모델」, 상황 주제 스펙 4, 통역 스펙 「제약」, ADR-0004 「영향」.

## Global Constraints

- 소희 통역(`interpret`)과 라이언 평가(`feedback`)의 모델과 요청은 바뀌지 않는다. `JE_CLAUDE_QUICK` 기본은 `haiku` 그대로다.
- 추천 모델 값은 `haiku`, `sonnet`(`QUICKS`의 키)이고 기본은 `sonnet`이다. 없는 값이면 서버가 시작할 때 `JE_CLAUDE_RECOMMEND must be one of haiku, sonnet, not '…'`로 멈춘다.
- Sonnet 추천 요청은 견준 그대로다: `thinking: {"type": "between_tools"}`, effort를 보내지 않는다.
- 추천은 지금처럼 한 번만 부른다. 이름표를 걷어도 다시 부르지 않는다.
- 로그에 문장을 쓰지 않는다(지금의 끝말 로그와 같다).
- 시험과 예문은 지어낸 문장으로 쓴다(`REVIEW.md` 「공개 저장소 노출」). 사용자 기록과 녹음 받아쓰기를 옮기지 않는다.
- 문서는 한국어, 코드와 커밋 메시지는 영어. CSS 없음.

## Review Focus

- 이름표가 문장 맨 앞에 올 때(「예: 인사동에서 …」): 이름표만 걷고 문장은 그대로 말한다. Task 2의 시험에 넣는다.
- 이름표 뒤에 끝말만 남을 때(「…골라 봤어요. 끝말: 상황을 골라 봤어요.」): 끝말 하나만 남는다. Task 2.
- 이름표 낱말이 문장 속 보통 낱말일 때(「예약」, 「주제곡」처럼 쌍점 없는 것): 걷지 않는다. Task 2.
- `.env`에 `JE_CLAUDE_RECOMMEND`가 없는 원래 폴더 서버: 기본 Sonnet으로 뜨고 로그에 그렇게 찍힌다. Task 1.
- `JE_CLAUDE_QUICK=sonnet`만 둔 사람: 통역과 평가만 Sonnet이 되고 추천은 기본 Sonnet 그대로다. Task 1.

---

### Task 1: 추천 모델 설정 `JE_CLAUDE_RECOMMEND`

**Files:**
- Modify: `server/je_server/claude.py` (`QUICKS` 옆, `Claude.__init__`, `Claude.recommend`)
- Modify: `server/je_server/config.py` (`Settings`, `load_settings`)
- Modify: `server/je_server/app.py:58-68` (`build_services`)
- Modify: `server/.env.example`, `server/README.md` 「Claude 모델 고르기」
- Test: `server/tests/test_claude_models.py`, `server/tests/test_claude.py`

**Interfaces:**
- Produces: `claude.QUICK_SONNET: dict` (`QUICKS["sonnet"]`와 같은 객체), `Claude(client, writer=SONNET, quick=HAIKU, recommender=QUICK_SONNET)`, 속성 `Claude.recommender`, `Settings.claude_recommend: str`(기본 `"sonnet"`), `config.DEFAULT_RECOMMEND = "sonnet"`.

- [ ] **Step 1: 실패하는 시험을 쓴다**

`test_claude_models.py`:
- `test_recommend_model_defaults_to_sonnet`: `load_settings(TOKEN).claude_recommend == "sonnet"`, 빈 값(`" "`)도 `"sonnet"`.
- `test_recommend_model_read_from_env`: `"Haiku"` → `"haiku"`.
- `test_unknown_recommend_model_stops_the_server`: `"opus"` → `ValueError`, 메시지 `JE_CLAUDE_RECOMMEND must be one of haiku, sonnet, not 'opus'`.
- `test_sonnet_quick_request`를 고친다: `Claude(fake, quick=QUICKS["sonnet"])`로 `interpret`를 불러 `model == "claude-sonnet-5-5"`, `thinking == {"type": "between_tools"}`, `"effort" not in output_config`.
- `test_recommend_uses_its_own_model`: `Claude(fake, quick=HAIKU, recommender=QUICKS["sonnet"]).recommend(...)` → Sonnet 요청. `Claude(fake, quick=QUICKS["sonnet"], recommender=HAIKU).recommend(...)` → `claude-haiku-5-5`, `thinking == {"type": "disabled"}`.
- `test_server_uses_and_logs_the_chosen_models`: `claude_recommend="haiku"`로 `build_services` → `claude.recommender is QUICKS["haiku"]`, 로그 `claude models: writer claude-haiku-5-5, quick claude-haiku-5-5, recommend claude-haiku-5-5`.
- `test_server_defaults_to_the_spec_models`: `claude.recommender is QUICKS["sonnet"]`, `claude.quick is HAIKU`.

`test_claude.py`: `test_recommend_uses_haiku_and_avoids_recent`를 `test_recommend_uses_sonnet_and_avoids_recent`로 바꾸고 `Claude(fake)` 기본 요청이 `claude-sonnet-5-5`, `thinking == {"type": "between_tools"}`, effort 없음인지 본다.

- [ ] **Step 2: 실패를 본다**

Run: `cd server && uv run pytest -q tests/test_claude_models.py tests/test_claude.py`
Expected: FAIL (`claude_recommend`, `recommender` 없음)

- [ ] **Step 3: 구현한다**

- `claude.py`: `QUICK_SONNET`을 두고 `QUICKS["sonnet"]`이 그것을 가리키게 한다. `Claude.__init__`에 `recommender`, `recommend()`는 `self.quick` 대신 `self.recommender`로 부른다. 주석에 2026-11-08 견준 것(추천만 Sonnet, 사용자)을 한 줄로 적는다.
- `config.py`: `DEFAULT_RECOMMEND = "sonnet"`, `Settings.claude_recommend`, `_model_name(env, "JE_CLAUDE_RECOMMEND", QUICKS, DEFAULT_RECOMMEND)`.
- `app.py`: `recommender = QUICKS[settings.claude_recommend]`, 로그 `claude models: writer %s, quick %s, recommend %s`.
- `.env.example`: `JE_CLAUDE_QUICK` 설명을 「녹음 평가 글, 소희 통역」으로 고치고 `# 상황 추천(제이크): haiku, sonnet. 기본 sonnet` + `JE_CLAUDE_RECOMMEND=`를 더한다.
- `README.md` 표: `JE_CLAUDE_QUICK`은 「녹음 평가 글, 소희 통역」, 새 줄 `JE_CLAUDE_RECOMMEND` | 제이크의 상황 추천 | `haiku`, `sonnet` | `sonnet`. 로그 줄 설명도 고친다.

- [ ] **Step 4: 통과를 본다**

Run: `cd server && uv run pytest -q`
Expected: 모두 PASS

- [ ] **Step 5: 커밋**

`feat(server): give jake's recommendation its own model setting`

### Task 2: 추천 답의 이름표 걷어 내기 (할 일 21)

**Files:**
- Modify: `server/je_server/claude.py` (`strip_endings` 근처, `Claude.recommend`)
- Test: `server/tests/test_claude.py`

**Interfaces:**
- Consumes: Task 1의 `Claude.recommend`.
- Produces: `claude.MESSAGE_LABELS: tuple[str, ...] = ("주제", "예", "끝말")`, `drop_labels(text: str) -> str`.

- [ ] **Step 1: 실패하는 시험을 쓴다**

`test_recommend_drops_message_labels`(parametrize, `answer, ending, said`), 모두 한 번만 부른다(`len(fake.requests) == 1`), 로그에 「label」이 있고 문장은 없다:
- `"카페에서 주문하는 상황을 추천해요. 끝말: 상황을 추천해요."`, `"상황을 추천해요."` → `"카페에서 주문하는 상황을 추천해요."`
- `"카페에서 주문하는 상황을 골라 봤어요. 끝말: 상황을 골라 봤어요."`, `"상황을 추천해요."` → `"카페에서 주문하는 상황을 추천해요."`
- `"끝말: 공항에서 짐을 찾는 상황을 골라 봤어요."`, `"상황을 골라 봤어요."` → `"공항에서 짐을 찾는 상황을 골라 봤어요."`
- `"예: 공항에서 짐을 찾는 상황을 골라 봤어요."`, 같은 끝말 → `"공항에서 짐을 찾는 상황을 골라 봤어요."`
- `"주제 : 공항에서 짐을 찾는 상황을 추천해요."`, `"상황을 추천해요."` → `"공항에서 짐을 찾는 상황을 추천해요."`

`test_recommend_keeps_words_that_only_look_like_labels`: `"호텔 예약을 바꾸는 상황을 추천해요."`와 `"공연장에서 주제곡을 묻는 상황을 추천해요."`는 그대로 나오고 로그에 「label」이 없다.

- [ ] **Step 2: 실패를 본다**

Run: `cd server && uv run pytest -q tests/test_claude.py -k label`
Expected: FAIL

- [ ] **Step 3: 구현한다**

`drop_labels`: 문장 맨 앞이나 띄어쓰기 뒤에 오는 `MESSAGE_LABELS` 낱말 + 쌍점(앞뒤 띄어쓰기 허용)을 지운다. 낱말에 붙은 것(「예약:」)은 지우지 않는다. `recommend()`는 받은 글에 먼저 `drop_labels`를 하고, 바뀌었으면 `log.info("recommendation label dropped")`를 남긴 뒤 지금처럼 끝말을 본다. 이름표를 걷어 끝말이 둘 붙은 것은 지금의 `strip_endings`가 하나로 만든다. 메시지 형식과 지시문은 바꾸지 않는다(견준 조건을 바꾸지 않으려고).

- [ ] **Step 4: 통과를 본다**

Run: `cd server && uv run pytest -q`
Expected: 모두 PASS

- [ ] **Step 5: 커밋**

`fix(server): drop message labels jake echoes in his recommendation`

### Task 3: 견주기 스크립트와 실제 모델 시험

**Files:**
- Create: `server/scripts/compare_quick_models.py`
- Modify: `server/scripts/check_jake_recommend.py` (추천 모델, 지어낸 최근 상황, `--model`)
- Modify: `server/README.md` 「시험」의 스크립트 표
- Test: `server/tests/test_compare_quick_models.py`, `server/tests/test_check_jake_recommend.py`

**Interfaces:**
- Consumes: Task 1의 `QUICKS`, `Claude(recommender=…)`, Task 2의 `drop_labels`.
- Produces: `compare_quick_models.py --only interpret|recommend|feedback --runs N --presses N --seed N --out FILE`. 추천의 걸림 표시 `rec_flags(raw: str, said: str, ending: str, seen: list[str]) -> list[str]`, 가격표 `PRICE`.

- [ ] **Step 1: 실패하는 시험을 쓴다**

- `test_compare_quick_models.py`: `PRICE`가 `QUICKS`의 모든 모델을 덮는다. `rec_flags`가 「끝말:」이 든 답에 `says '끝말'`, 두 문장에 `more than one sentence`, 「제가」로 시작하면 `odd start`, 목록에 있던 상황을 되풀이하면 `repeats a listed situation`을 내고, 바르게 지킨 답에는 빈 목록을 낸다.
- `test_check_jake_recommend.py`: `RECENT`가 주제마다 지어낸 최근 상황을 갖고, `--model haiku`를 주면 `recommender`가 `QUICKS["haiku"]`다(`build(args, settings)`처럼 Claude를 만드는 함수를 하나 두고 그것을 본다).

- [ ] **Step 2: 실패를 본다**

Run: `cd server && uv run pytest -q tests/test_compare_quick_models.py tests/test_check_jake_recommend.py`
Expected: FAIL

- [ ] **Step 3: 구현한다**

- `compare_quick_models.py`: 견줄 때 쓴 스크립트를 옮긴다. 세 일을 두 모델에 같은 입력으로, 순서를 번갈아 묻는다. 통역은 지어낸 열두 줄(숫자, 길 안내, 관용 표현, 짧은 대답), 추천은 서버의 `pick_ending`과 `recommend`로 주제마다 `--presses`번(거절 목록을 이어 붙임, 최근 상황은 `--recent big`이면 열 개), 평가는 `check_ryan_wording.FEEDBACK`과 `flags`. 첫 글자, 첫 문장, 끝까지 걸린 시간, 값, 걸림 수를 요약하고 `--out`에 JSON으로 남긴다. 머리 주석에 돈과 「돌리기 전에 알린다」를 쓴다.
- `check_jake_recommend.py`: 기본 모델을 `QUICKS[s.claude_recommend]`로, `--model haiku|sonnet`으로 바꿀 수 있게, 주제마다 지어낸 최근 상황 몇 개를 함께 보낸다(할 일 21 「이번에 나온 조건」). 머리 주석의 값을 Sonnet 기준으로 고친다.

- [ ] **Step 4: 통과를 본다**

Run: `cd server && uv run pytest -q`
Expected: 모두 PASS

- [ ] **Step 5: 실제 모델로 잰다 (돈이 든다, 먼저 main 세션에 알리지 않아도 되는 크기: 6센트쯤)**

Run: `cd server && uv run python scripts/check_jake_recommend.py`
Expected: 스물한 번 모두 끝말이 맞고(`MISSED 0`), 「끝말」이 말한 글에 없다.

- [ ] **Step 6: 서버로 확인한다**

worktree 서버를 `127.0.0.1:8797`(받아쓰기 8798)에 녹음을 뺀 데이터 복사본으로 띄운다(`docs/guide/DEVENV_맥서버_저절로_띄우기_20261107.md` 「launchd 서버를 멈추지 않고 시험하기」). 로그에 `quick claude-haiku-5-5, recommend claude-sonnet-5-5`가 찍히고, `POST /recommend`가 주제 셋에서 제이크 목소리까지 오는지, 따라 말한 녹음 하나의 평가가 Haiku로 오는지 본다. 끝나면 서버를 끄고 복사본과 녹음을 지운다.

- [ ] **Step 7: 커밋**

`test(server): add the quick model comparison script` 와 `test(server): send made-up recent situations in the recommendation check` (나눠서)

### Task 4: 문서

**Files:**
- Modify: `docs/superpowers/specs/2026-11-05-speaking-practice-design.md` 「기다리는 시간과 모델」
- Modify: `docs/superpowers/specs/2026-11-07-situation-topics-design.md` 4와 「지금과 같은 것」
- Modify: `docs/superpowers/specs/2026-11-06-korean-translation-design.md` 「제약」
- Modify: `docs/adr/0004-ryan-ai-on-claude-api.md` 「영향」
- Create: `docs/guide/PROMPT_일마다_모델_견주기_20261108.md`, 색인 `docs/guide/README.md`
- Add: `docs/todo/20261108_21_todo_jake_echoes_message_labels.md`, `docs/todo/20261108_24_todo_quick_model_sonnet_review.md` (상태 「완료」)

- [ ] **Step 1: 스펙과 ADR을 고친다**

말하기 스펙에 「상황 추천은 Sonnet(`JE_CLAUDE_RECOMMEND`)」과 견준 값(추천 63번 중 Haiku 12번, Sonnet 2번 이상한 문장, 평가와 통역은 Haiku 그대로, 기다림, 값), 모델 바꾸기 줄에 새 설정. 상황 주제 스펙의 「짧은 말 모델」 두 곳을 추천 모델로. 통역 스펙 「제약」에 열두 줄을 더 넓게 견주고도 Haiku 그대로인 이유. ADR-0004 「영향」에 일마다 모델을 고르게 된 것 한 줄.

- [ ] **Step 2: 가이드를 쓴다**

견주는 기준(같은 입력, 지어낸 입력, 서버가 실제로 보내는 조건을 살린다, 순서를 번갈아, 품질은 직접 읽는다, 값은 claude-api 스킬로), 명령(`compare_quick_models.py`, `check_jake_recommend.py --model`, `check_ryan_wording.py --quick`, 녹음 시험), 겪은 것(최근 상황 둘로는 드물던 Haiku 실수가 열 개에서 늘었다, 녹음 시험 스크립트가 원본 줄을 찍어 헷갈렸다, 첫 소리는 첫 문장 소리가 맥에 있는지에 달려 모델 비교에는 첫 글자와 첫 문장 시간을 쓴다).

- [ ] **Step 3: 할 일 두 개를 「완료」로 넣는다**

원래 폴더의 할 일 21과 24를 이 worktree에 복사하고 상태 줄을 고친다. 21에는 「학습자」 지시문을 넣지 않은 이유(지어낸 입력 126번에서 두 모델 모두 0번, 견준 조건을 바꾸지 않음)를 적는다.

- [ ] **Step 4: 커밋**

`docs: record the quick model comparison and the recommend model`(스펙, ADR, 가이드, 할 일을 scope 없이 한 커밋으로. ADR이 섞여 scope를 생략한다)
