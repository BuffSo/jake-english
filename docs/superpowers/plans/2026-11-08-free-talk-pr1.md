# 자유 대화와 대화 뒤 고쳐 주기(PR 1) 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 첫 화면의 「자유 대화」로 라이언과 대본 없이 영어로 이야기하고(라이언은 첫 문장부터 말하고, 내가 끊을 수 있다), 「대화 끝내기」 뒤 많아야 세 가지 고친 문장을 한 화면에 하나씩 듣고 따라 말하고 ☆로 모은다.

**Architecture:** 자유 대화는 역할극 기록(`Roleplay`)에 `kind: "talk"`를 단 것이다. 그래서 줄 번호로 쓰는 것(녹음 듣기, 통역, 세 줄, 본보기, ☆, 연습 시도)은 지금 경로를 그대로 쓴다. 대화의 흐름(첫 질문, 차례, 끊기, 끝내기)은 새 모듈 `server/je_server/talk.py`의 `Talks`가 맡고, `Engine`의 받아쓰기, `speak`, 잠금을 빌려 쓴다. 고쳐 주기를 거르는 규칙은 순수 함수 모듈 `fixes.py`에 둔다. 앱은 대화와 고쳐 주기를 새 화면 둘(`TalkScreen`, `TalkFixScreen`)과 순수 리듀서 둘(`flow/talk.ts`, `flow/talkFix.ts`)로 만들고, `RoleplayScreen.tsx`(41KB)는 모아 둔 문장 연습의 두 군데만 고친다.

**Tech Stack:** Python 3 + FastAPI(서버, `cd server && uv run pytest -q`), React Native + Expo + jest(앱, `cd app && npx jest && npx tsc --noEmit`). 새 꾸러미 없음.

**Spec:** `docs/superpowers/specs/2026-11-08-free-talk-design.md`. 이 계획은 「정한 것」 1~8과 「확인 방법」의 PR 1 부분만 옮긴다. 9(한국어로 묻기, PR 2)와 10(첫 화면에서 말로 하기, PR 3)은 하지 않지만, 한국어 차례의 자리(`kind: "ask"`, `"help"`)를 남겨 막지 않는다.

**실행 방식:** subagent-driven(이미 정함). 작업마다 새 서브에이전트가 구현하고 새 리뷰어가 본다. 리뷰 요청에는 `REVIEW.md`와 `AGENTS.md`를 함께 넘긴다(`CLAUDE.md` 「PR 리뷰」). 끝에 브랜치 전체 리뷰 한 번, PR을 열면 pr-review.

## 파일 구조

| 파일 | 맡는 것 |
|---|---|
| `server/je_server/models.py` | `LineKind`, `Fix`, `ScriptLine.parts/heard_upto/fix`, `Roleplay.kind` |
| `server/je_server/review.py`, `store.py`, `engine.py` | 자유 대화를 「지난 상황」, 이어 하기, 최근 상황, 복사에서 빼기. 고친 문장 줄의 소리와 앞뒤. `speak`의 영어 목소리. 첫 질문 소리 미리 만들기 |
| `server/je_server/tts.py` | `Voice.demote`: 끊은 답의 남은 소리를 새 답 뒤로 |
| `server/je_server/prompts.py`, `claude.py`, `config.py` | `TALK_SYSTEM`, `FIX_SYSTEM`, `Claude.talk`, `Claude.fixes`, `JE_CLAUDE_TALK` |
| `server/je_server/phrases.py` | `TALK_OPENERS`, 정해진 말 둘 |
| `server/je_server/fixes.py`(새) | 고쳐 주기 거르기(순수), 고친 문장 줄의 앞 대사 |
| `server/je_server/talk.py`(새) | `Talks`: 대화 만들기, 차례, 끝내기. 대화를 Claude 메시지로 바꾸기 |
| `server/je_server/app.py` | `/talks` 경로 셋 |
| `contract/` | 바뀐 키, 새 예시 `talk.json`, `talk-events.ndjson`, `talk-end.json` |
| `app/src/api/types.ts`, `client.ts` | 같은 모양, `createTalk`, `talkTurn`, `endTalk` |
| `app/src/flow/talk.ts`(새), `talkFix.ts`(새) | 대화와 고쳐 주기의 리듀서와 판단 함수 |
| `app/src/audio/useMic.ts`(새) | 두 새 화면이 같이 쓰는 녹음 버튼 동작(게이트, 취소 기억, 짧은 막기) |
| `app/src/screens/TalkScreen.tsx`(새), `TalkFixScreen.tsx`(새) | 대화 화면, 대화 돌아보기 화면 |
| `app/src/screens/HomeScreen.tsx`, `app/App.tsx`, `app/src/flow/state.ts`, `app/src/ui/theme.ts` | 셋째 카드, 화면 잇기 |
| `app/src/screens/RoleplayScreen.tsx` | 모아 둔 고친 문장의 「앞 대사」, 「이 상황 다시 하기」 숨기기 |
| `server/scripts/compare_talk_models.py`, `compare_fix_models.py`(새), `try_talk.py`(새) | 실제 모델 확인, 학습자 목소리 녹음 시험 |

> **2026-11-08 바뀜:** 사용자가 자유 대화에서는 라이언이 영어로만 말하기로 정했다. 그래서 이 정해진 말은 한국어 `PHRASES["talk_english"]`가 아니라, 라이언의 영어 목소리로 하는 영어 `TALK_ENGLISH` "Could you try that in English? Short is fine."(`PHRASES` 밖)가 되었다. 아래에서 한국어 말 「영어로 말해 볼까요? 짧게 말해도 괜찮아요.」나 `PHRASES["talk_english"]`를 적은 곳은 옛 버전을 가리킨다. 계획은 기록이라 고쳐 쓰지 않았다.

## Global Constraints

- **첫 화면 카드(그대로 쓴다):** 차례 「대화 연습하기」(파랑) → 「자유 대화」(보라) → 「복습하기」(청록). 「자유 대화」의 설명은 「대본 없이 라이언과 영어로 이야기해요」, 그림 글자 🗣️, 색 `colors.free = "#7048E8"`(첫 화면 카드에만 쓴다).
- **대화 화면:** 위 「‹ 뒤로」, 제목 「자유 대화」, 「N번째」(내가 말한 차례). 맨 아래 「🎤 말하기」(주된 버튼, 남은 너비)와 「대화 끝내기」(덜 주된 버튼). 녹음 중에는 「취소」와 「● 말하기 끝」(`StopButton`). 「건너뛰기」 없음. 첫 내 차례에 「🎤를 누르고 말하세요」. 기다릴 때 라이언의 생각하는 얼굴(`Waiting who="ryan"`).
- **정해진 말(그대로):** `TALK_ENGLISH` "Could you try that in English? Short is fine."(바뀜), `talk_no_fixes` 「이번 대화에서는 고칠 곳을 찾지 못했어요. 수고했어요.」. 지금 것 `no_speech` 「잘 안 들렸어요. 한 번 더 말해 줄래요?」, `claude_down`, `too_long`.
- **라이언의 답(지시문 규칙):** 영어 두세 문장, 모두 35낱말 안쪽, 첫 문장은 2~5낱말 맞장구이고 같은 대화에서 쓴 맞장구로 시작하지 않는다, 대답하기 쉬운 질문 하나로 끝, 고치지 않는다, 못 알아들으면 지어내지 말고 다시 말해 달라고 한다, 어떻게 말하는지 물으면 짧은 영어 문장 하나로 알려 주고 이어 간다, 목록·따옴표·이모지·행동 묘사 없음. 큰따옴표는 서버가 지운다.
- **모델:** 대화 상대 `JE_CLAUDE_TALK`(`haiku`, `sonnet`, `opus`), 기본 `sonnet`(생각 끔, effort low = `WRITERS["sonnet"]`). 고쳐 주기는 글쓰기 모델(`JE_CLAUDE_WRITER`). 대화 상대는 실시간 호출 설정(`LIVE_OPTIONS`)으로 빨리 실패한다.
- **받아쓰기:** 「🎤 말하기」는 영어로만 받아쓴다(자동 언어 없음). 영어 받아쓰기에 한글이 있으면 한국어로 고정해 다시 받아쓰고, 그 글을 보이고 `talk_english`로 답한다. 이 차례는 Claude에 보내지 않는다.
- **고쳐 주기:** 많아야 3가지, 한 가지는 내 영어 차례 하나. 고친 문장 12낱말 안쪽. 설명 한두 문장 해요체. 발음 짐작은 두 낱말의 사전 발음이 두 소리 이내로 다르고 바뀐 소리가 소리 설명 목록에 있을 때만 남기고, 「~처럼 들렸어요」 문장 뒤에 목록의 설명을 글자 그대로 붙인다. 「~라고 말했어요」라고 단정하지 않는다. 고치지 않는 것: 한국어 차례, 어떻게 말하는지 묻는 차례, 라이언이 못 알아들은 차례, 뜻이 통하는 흔한 짧은 대답.
- **대화 돌아보기 화면(그대로):** 제목 「대화 돌아보기」, 「1/2」, 노란 상자의 라이언 설명(열리면 라이언 한국어 목소리), 「내가 한 말」과 「🔊 내 녹음 들어 보기」(눌러야 들린다), 「이렇게 말해 보세요」와 「🔊 듣기」·「읽는 법 보기」·「☆ 모아 두기」, 맨 아래 「🎤 따라 말하기」(주된)와 「다음 ›」(덜 주된), 마지막은 「끝」. 세 줄이 아직이면 「세 줄을 만들고 있어요…」.
- **기록:** 자유 대화도 앱 데이터 폴더에 남는다. 「지난 상황」, 「하던 대화 이어 하기」, 제이크 추천의 최근 상황, 「이 상황 다시 하기」(복사)에서 빠진다. 자유 대화를 해도 이어 하기의 역할극은 남는다. 「모아 둔 문장」에는 제목 「자유 대화」로 나오고, 연습의 「앞 대사」는 고친 차례 앞의 라이언 말이다.
- **ADR-0004:** Anthropic에는 글만 보낸다. 녹음은 맥에만 둔다. 받아쓴 글과 녹음 경로를 로그에 쓰지 않는다(시간과 수만).
- **공개 저장소:** 시험 문장, 계약 예시, 지시문 예, 가이드의 예는 모두 지어낸다. 맥의 기록이나 녹음 시험에서 본 받아쓰기와 라이언의 답은 PR, 가이드, 커밋에 옮기지 않는다(숫자만).
- **경로 보안:** 모든 새 경로는 토큰 검사 라우터에 둔다. 녹음은 `read_body`(5MB 제한)로 받는다. id는 `ID` 패턴, `heard`는 `0..50` 정수.
- **돈:** 실제 Claude 확인에 대화 상대 견주기 $0.1쯤, 고쳐 주기 견주기 $0.15쯤, 녹음 시험 $0.05쯤, 합해 $0.5 안쪽(구독 밖 API 크레딧). 돈 든 횟수와 값을 PR에 적는다.
- **시험 서버와 에뮬레이터:** 시험 서버는 `JE_HOST=127.0.0.1 JE_PORT=8791 JE_WHISPER_PORT=8792`, 기록은 녹음(`rec/`, `tmp/`)을 뺀 복사본. 원래 폴더 서버(launchd)는 멈추지 않는다. 에뮬레이터는 이 앱의 AVD `jake-english`만 쓴다(다른 AVD는 다른 프로젝트 것).
- **같이 도는 카드:** leftover-minors 카드가 `useRecorder`, `StopButton`, `cueSound`를 고치고 있다. Task 11 전에 `/usr/bin/git fetch origin`으로 main에 그 머지가 있는지 보고, 있으면 main을 받아 맞춘다(스펙 「제약」).
- **커밋:** 영어 Conventional Commits, scope는 `app`, `server`, 걸치면 생략. 본문에 이유와 돌린 시험과 결과. 끝에 `Refs: docs/superpowers/specs/2026-11-08-free-talk-design.md`와 `Refs: docs/superpowers/plans/2026-11-08-free-talk-pr1.md`. AI 서명 줄 없음. `/usr/bin/git add <파일들>`(-A, . 금지) 뒤 `/usr/bin/git commit -F - <<'EOF'`.

## Review Focus

1. **소리가 하나도 나기 전에, 또는 마지막 문장이 막 끝날 때 끊기:** 들은 문장 수가 0이거나 답 문장 수와 같다. 0이면 Claude에 「아무 말도 하기 전에 끊겼다」고 알리고, 다 들었으면 끊긴 것으로 적지 않는다. → Task 4 `test_messages_say_when_ryan_was_cut_off_before_a_word`, Task 5 `test_heard_all_of_the_reply_is_not_a_cut`, Task 9 `heardCount is 0 before any sound and all once the last started`.
2. **「대화 끝내기」나 「🎤 말하기」를 빠르게 두 번:** Claude 고쳐 주기 호출은 한 번, 녹음 시작도 한 번. → Task 7 `test_two_ends_at_once_ask_claude_once`, `test_end_again_returns_the_same_fixes_without_claude`, Task 9 `a second recordStart or endStart does nothing`, Task 11/12 화면은 게이트(`createGate`)와 `now` ref로 막는다.
3. **영어와 한국어가 섞인 「말하기」:** 영어 받아쓰기에 한글이 조금이라도 있으면 한국어 차례로 다루고, 한국어 받아쓰기가 실패해도 화면이 멈추지 않는다. → Task 5 `test_hangul_in_the_english_transcript_is_heard_again_in_korean`, `test_korean_transcription_failing_still_answers_in_korean`.
4. **라이언 답 중간에 Claude가 끊김:** 내 차례는 대화에 남고 라이언 줄은 남지 않으며, 다음 차례에 학습자 말 둘이 이어져도 Claude 요청이 깨지지 않는다. → Task 5 `test_claude_down_mid_reply_keeps_my_turn_only`, Task 4 `test_messages_join_two_learner_turns_in_a_row`.
5. **옛 기록과 옛 서버:** `kind`가 없는 기록은 역할극으로 읽고, 새 앱이 옛 서버에 붙어 `/talks`가 404면 대화 화면이 오류와 「다시 시도」를 보인다. → Task 1 `test_records_from_before_read_as_roleplays`, Task 9 `a failed opening can be tried again`.

---

### Task 1: 기록이 자유 대화를 안다

**Files:**
- Modify: `server/je_server/models.py`, `server/je_server/review.py`, `server/je_server/store.py`, `server/je_server/engine.py`(`copy`), `app/src/api/types.ts`
- Modify: `contract/roleplay.json`, `contract/line-user.json`, `contract/summary.json`, `contract/resume.json`(줄마다 `"parts": null, "heard_upto": null, "fix": null`, 기록에 `"kind": "roleplay"`)
- Create: `contract/talk.json`
- Test: `server/tests/test_contract.py`, `server/tests/test_review.py`, `server/tests/test_store.py`, `server/tests/test_engine.py`, `server/tests/fakes.py`(`talk_example`), `app/src/api/contract.test.ts`

**Interfaces:**
- Produces(서버):
  - `LineKind = Literal["script", "reply", "turn", "ask", "help", "fix"]`. 자유 대화에서 라이언의 영어 줄(첫 질문 포함)은 `reply`, 내 영어 차례는 `turn`, 한국어 차례는 `ask`, 라이언의 한국어 답은 `help`, 고친 문장은 `fix`(말한 사람 `user`).
  - `class Fix(BaseModel): of: int; said: str; why_ko: str; why_audio: str | None = None` — `of`는 고친 내 차례의 줄 번호, `said`는 그 차례의 문제 든 한 문장(들린 대로), `why_ko`는 라이언의 한국어 설명(발음 짐작을 남기면 목록 설명까지), `why_audio`는 그 설명의 라이언 한국어 소리. 줄의 `text`가 고친 문장, `audio`가 그 본보기다.
  - `ScriptLine`에 `parts: list[Said] | None = None`(라이언 답을 문장마다 글과 소리로), `heard_upto: int | None = None`(끊었을 때 들은 문장 수, 끝까지 들었으면 None), `fix: Fix | None = None`. `Said`를 `ScriptLine` 위로 옮긴다.
  - `Roleplay.kind: Literal["roleplay", "talk"] = "roleplay"`.
  - `fakes.talk_example() -> Roleplay`: `contract/talk.json`을 읽은 것.
- Produces(앱): `LineKind`, `Fix = { of: number; said: string; why_ko: string; why_audio: string | null }`, `ScriptLine`에 `parts: Said[] | null; heard_upto: number | null; fix: Fix | null`, `Roleplay.kind: "roleplay" | "talk"`. `LINE_KEYS`에 `"parts", "heard_upto", "fix"`, `ROLEPLAY_KEYS`에 `"kind"`, 새 `FIX_KEYS = ["of", "said", "why_ko", "why_audio"]`와 `KEYS_MATCH`의 줄.

- [ ] **Step 1: 시작 상태를 본다** — `cd server && uv run pytest -q` 모두 통과, `cd app && npm ci && npx jest && npx tsc --noEmit` 모두 통과(새 worktree라 `npm ci` 먼저).

- [ ] **Step 2: `contract/talk.json`을 쓴다.** 지어낸 자유 대화 기록 하나(id `b1b2c3d4e5f6`, `kind` `"talk"`, `situation` `"자유 대화"`, `frame` `{"title_ko": "자유 대화", "user_role_ko": "나", "ryan_role_ko": "대화 상대", "place_ko": "자유 대화", "goal_ko": "대본 없이 영어로 이야기하기"}`(Task 4의 `TALK_FRAME`과 같다), `topic`·`pick`·`origin` null). 줄 여덟:
  0. ryan `reply` 「Hi! What did you do today?」, `parts` 한 개
  1. user `ask` 「주말에 한 일을 말하고 싶어요」(시도 `n` 1, `mode` `turn`, `followed` false, `timings`에 `transcribed`, `total`)
  2. ryan `help` 「영어로 말해 볼까요? 짧게 말해도 괜찮아요.」, `audio`와 `parts` 한 개
  3. user `turn` 「I walked to the park with my dog.」(시도 하나, `timings`에 `transcribed`, `first_text`, `first_audio`, `total`)
  4. ryan `reply` 「Sounds lovely! I like quiet parks too. Did you go far?」, `parts` 셋, `heard_upto` 1
  5. user `turn` 「Yesterday I go to the market and buy two apple.」(시도 하나)
  6. ryan `reply` 「Nice! What did you get there?」, `parts` 둘
  7. user `fix` 「Yesterday I went to the market and bought two apples.」, `fix` `{of: 5, said: …(5의 글), why_ko: "지난 일이라 go와 buy를 went와 bought로 바꿔요. 사과가 둘이라 apples예요.", why_audio: 64자}`, `audio` 64자. 앞 대사(`fix.of - 1`)는 줄 4의 라이언 말이다.
  
  소리 키는 다른 예시처럼 같은 글자 64개(`"aaaa…"`, `"bbbb…"`)로 쓴다.

- [ ] **Step 3: 실패하는 시험을 쓴다**
  - `test_contract.py`: `test_talk_example_matches_model` — `Roleplay.model_validate(raw).model_dump(mode="json") == raw`, `raw["kind"] == "talk"`, 줄 kind 차례가 `["reply","ask","help","turn","reply","turn","reply","fix"]`. 지금 시험 넷(roleplay, line-user, summary, resume)은 고친 예시로 그대로 통과해야 한다.
  - `test_contract.py`: `test_records_from_before_read_as_roleplays` — `contract/roleplay.json`에서 `kind`와 줄의 새 키 셋을 지운 것을 읽으면 `kind == "roleplay"`, 줄마다 `parts is None and heard_upto is None and fix is None`.
  - `test_review.py`: `test_a_talk_is_not_a_past_situation` — `past_items([talk_example()]) == []`, `latest_run([talk_example()], talk.id) is None`.
  - `test_review.py`: `test_resume_skips_a_newer_talk` — 내 줄이 남은 역할극(`make(A, "2026-11-08T09:00:00")`)과 그보다 새 자유 대화 → `to_resume(...)`의 id가 `A`. 자유 대화만 있으면 None.
  - `test_store.py`: `test_recent_situations_leave_talks_out` — 자유 대화를 저장해도 `recent_situations()`에 「자유 대화」가 없다.
  - `test_engine.py`: `test_a_talk_is_not_copied` — 저장한 자유 대화를 `engine.copy(id)` → `NotFound`.
  - `contract.test.ts`: `talk example has the keys the talk screens read` — `talk.json` 키가 `ROLEPLAY_KEYS`, 줄마다 `LINE_KEYS`, `fix`가 있는 줄의 `fix` 키가 `FIX_KEYS`.

- [ ] **Step 4: 실패를 본다** — `cd server && uv run pytest -q tests/test_contract.py tests/test_review.py tests/test_store.py tests/test_engine.py` → `kind`, `parts` 없음으로 FAIL. `cd app && npx jest src/api/contract.test.ts` → 키가 다름으로 FAIL.

- [ ] **Step 5: 구현한다**
  - `models.py`: 위 모양과 주석(스펙 경로, 각 값의 뜻). `kind`의 `reply`는 2026-11-07 이전 기록의 「대사와 다르게 한 말에 대한 라이언의 역할 안 답」에도 쓰였다고 한 줄 남긴다.
  - `review.py`: `_groups`가 `rp.kind == "talk"`를 건너뛴다(그래서 `past_items`, `latest_run`도). `to_resume`은 `kind != "talk"`인 기록 가운데 가장 새것을 본다(스펙 8 「자유 대화를 해도 이어 하기의 역할극은 남는다」).
  - `store.py` `recent_situations`: 자유 대화를 뺀다.
  - `engine.py` `copy`: `old.kind == "talk"`이면 `NotFound`(스펙 「하지 않을 것」: 같은 자유 대화를 다시 할 수 없다).
  - `types.ts`: 위 모양, 키 목록, 주석(옛 서버에는 없는 키라 `kind`가 없으면 역할극으로 본다).
  - 계약 예시 넷에 새 키를 넣는다.

- [ ] **Step 6: 통과를 본다** — `cd server && uv run pytest -q`, `cd app && npx jest && npx tsc --noEmit` 모두 통과.

- [ ] **Step 7: 커밋한다** — `feat: add free talk records to the shared shapes`(서버와 앱이 함께 바뀌어 scope 없음)

### Task 2: 끊은 답의 남은 소리를 뒤로 미루기

**Files:**
- Modify: `server/je_server/tts.py`, `server/tests/fakes.py`(`FakeVoice.demote`)
- Test: `server/tests/test_tts.py`

**Interfaces:**
- Produces: `Voice.demote(keys: Iterable[str]) -> None`, `Voice.demoted: set[str]`. 미룬 키의 급한 일은 다른 급한 일 뒤, 미리 만드는 일 앞에 만든다. 아직 만들지 않은 키만 넣고, 만들면 뺀다. `FakeVoice.demote`는 받은 키를 `self.demoted: list[str]`에 더한다.

- [ ] **Step 1: 실패하는 시험을 쓴다** (`test_tts.py`, 가짜 작업 프로세스 `voice` 고정물)
  - `test_a_demoted_urgent_job_waits_behind_a_new_urgent_one` — `busy`(급함)를 만들게 하고, `old rest`(급함)를 줄 세운 뒤 `voice.demote([audio_key("ryan","english","old rest")])`, 그다음 `new first`(급함). 셋을 기다린 뒤 `calls(tmp_path).index("new first") < calls(tmp_path).index("old rest")`.
  - `test_a_demoted_job_is_still_made` — 미룬 키의 `say`가 끝나고 파일이 있다. 끝난 뒤 `voice.demoted == set()`.
  - `test_demoting_a_sound_already_made_does_nothing` — 만든 소리의 키를 미루면 `voice.demoted == set()`.
  - `test_demoted_jobs_still_go_before_prepared_ones` — 미리 만드는 일(`urgent=False`) 하나와 미룬 급한 일 하나 → 미룬 것이 먼저.

- [ ] **Step 2: 실패를 본다** — `cd server && uv run pytest -q tests/test_tts.py` → `AttributeError: 'Voice' object has no attribute 'demote'`

- [ ] **Step 3: 구현한다.** 대기열의 모양(`(우선, 순위, 차례, …)`)은 그대로 두고, 꺼내는 쪽에서 미룬 키의 급한 항목을 순위 1로 다시 넣는다(급한 항목의 순위는 지금 늘 0이다):

```python
pri, rank, seq, key, text, voice, lang, check = await self.queue.get()
...
if pri == 0 and rank == 0 and key in self.demoted:
    self.queue.put_nowait((0, 1, seq, key, text, voice, lang, check))
    continue
```

  만든 뒤(성공이든 실패든) `self.demoted.discard(key)`. 주석에 스펙 2 「끊은 말의 남은 소리」와 까닭(목소리 작업 프로세스가 하나라 남은 문장 1~3초가 새 답 첫 문장 앞에 끼인다)을 쓴다.

- [ ] **Step 4: 통과를 본다** — `cd server && uv run pytest -q tests/test_tts.py`, 이어 `uv run pytest -q`

- [ ] **Step 5: 커밋한다** — `feat(server): let a cut-off reply's sounds wait behind the next reply`

### Task 3: 대화 상대 호출과 모델 설정

**Files:**
- Modify: `server/je_server/prompts.py`, `server/je_server/claude.py`, `server/je_server/config.py`, `server/je_server/app.py`(`build_services`만), `server/scripts/compare_talk_models.py`, `server/.env.example`, `server/README.md`(모델 표)
- Test: `server/tests/test_claude.py`, `server/tests/test_claude_models.py`

**Interfaces:**
- Produces:
  - `prompts.TALK_START = "(The learner opened free talk.)"`, `prompts.TALK_SYSTEM`, `prompts.TALK_CUT = "(Ryan was cut off here. The learner did not hear the rest.)"`, `prompts.TALK_CUT_SILENT = "(Ryan was cut off before he said anything.)"`.
  - `claude.TALKERS = WRITERS`(같은 설정 묶음, 고를 수 있는 이름도 같다).
  - `Claude.__init__(..., talker: dict[str, Any] = SONNET)`, `async def talk(self, messages: list[dict]) -> AsyncIterator[str]` — 라이언을 assistant로 둔 여러 차례 메시지를 그대로 보내고, 글을 흘려 준다. `max_tokens=300`, `LIVE_OPTIONS`, 큰따옴표 지움.
  - `Claude._stream(self, kw, system, body: dict | list[dict], max_tokens, whole=False)` — 목록이면 그대로 `messages`, 사전이면 지금처럼 그 JSON 한 개의 user 메시지.
  - `config.DEFAULT_TALK = "sonnet"`, `Settings.claude_talk: str = DEFAULT_TALK`(`JE_CLAUDE_TALK`, `TALKERS`에서).

- [ ] **Step 1: 실패하는 시험을 쓴다**
  - `test_claude.py` `test_talk_streams_the_turns_on_the_talk_model` — `FakeAnthropic([["Nice! ", "What did you eat?"]])`, `Claude(fake, talker=WRITERS["haiku"])`, 메시지 `[{"role":"user","content":TALK_START},{"role":"assistant","content":"Hi!"},{"role":"user","content":"I ate rice."}]` → 조각 `["Nice! ", "What did you eat?"]`. 요청의 `messages`가 준 그대로, `system == prompts.TALK_SYSTEM`, `model == "claude-haiku-5-5"`, `max_tokens == 300`, `fake.options == [LIVE_OPTIONS]`.
  - `test_talk_drops_double_quotes` — `['He said "hi". ', 'Fun?']` → 큰따옴표 없음.
  - `test_talk_is_unavailable_when_the_connection_fails` — `connection_error()` → `ClaudeUnavailable`.
  - `test_talk_prompt_answers_how_to_say` — `"how to say" in TALK_SYSTEM.lower()`, `"Never correct" in TALK_SYSTEM`.
  - `_stream`이 사전을 지금처럼 보내는 것은 지금의 `feedback`, `aside` 시험이 지킨다.
  - `test_claude_models.py` `test_talk_model_defaults_to_sonnet`(`load_settings({...토큰...}).claude_talk == "sonnet"`), `test_talk_model_read_from_env`(`JE_CLAUDE_TALK=haiku`), `test_unknown_talk_model_stops_the_server`(`ValueError`, 글에 `JE_CLAUDE_TALK`).

- [ ] **Step 2: 실패를 본다** — `cd server && uv run pytest -q tests/test_claude.py tests/test_claude_models.py` → `ImportError: TALK_SYSTEM`

- [ ] **Step 3: 구현한다**
  - `prompts.py`: `compare_talk_models.py`의 `SYSTEM`을 `TALK_SYSTEM`으로 옮기고, 「If the learner asks you something…」 줄 뒤에 그대로 한 줄을 더한다: `- If the learner asks how to say something in English, tell them in one short, natural English sentence, then carry on the conversation.` 주석에 스펙 3, 4와 견주기(스펙 「잰 것」)를 적는다.
  - `claude.py`: 위 시그니처. `talk`은 `self._request(self.talker, {})`로 `_stream(..., whole=False)`(짧은 답이라 끝까지 오지 않아도 온 것을 쓴다).
  - `config.py`, `build_services`(`talker=TALKERS[settings.claude_talk]`, 로그 줄에 `talk %s`), `.env.example`(`JE_CLAUDE_TALK=` 한 줄과 설명), `README.md` 표에 `JE_CLAUDE_TALK | 자유 대화의 라이언 | haiku, sonnet, opus | sonnet`.
  - `compare_talk_models.py`: `from je_server.prompts import TALK_START, TALK_SYSTEM`. 스크립트 안의 `SYSTEM`, `START`를 지우고, 머리 주석의 「A draft …」를 「the prompt that ships」로 고친다. `CASES`에 `("how do you say", ["What did you do today?", "How do you say I'm tired in English?"])`를 더한다.

- [ ] **Step 4: 통과를 본다** — `cd server && uv run pytest -q`

- [ ] **Step 5: 커밋한다** — `feat(server): add Ryan's free-talk partner call and its model setting`

### Task 4: 자유 대화 만들기와 첫 질문

**Files:**
- Create: `server/je_server/talk.py`, `server/tests/test_talk.py`
- Modify: `server/je_server/phrases.py`, `server/je_server/store.py`, `server/je_server/engine.py`(`warm`), `server/tests/conftest.py`(`talks` 고정물), `server/tests/fakes.py`(`FakeClaude.talk`, `FakeWhisper.by_lang`)
- Test: `server/tests/test_talk.py`, `server/tests/test_phrases.py`, `server/tests/test_store.py`

**Interfaces:**
- Consumes: Task 1의 모양, Task 3의 `TALK_START`, `TALK_CUT`, `TALK_CUT_SILENT`.
- Produces:
  - `phrases.TALK_OPENERS: tuple[str, ...]` — 아래 열 개, 이 차례로.
  - `PHRASES["talk_english"]`, `PHRASES["talk_no_fixes"]`(Global Constraints 그대로). `warm`이 다른 정해진 말처럼 만든다.
  - `Store.load_talk() -> int`(다음 첫 질문 차례. 없거나 읽을 수 없으면 0, 깨진 것은 경고 한 줄), `Store.save_talk(next_: int) -> None`(`talk.json`, `{"next": n}`, `_write`로).
  - `talk.TALK_FRAME = Frame(title_ko="자유 대화", user_role_ko="나", ryan_role_ko="대화 상대", place_ko="자유 대화", goal_ko="대본 없이 영어로 이야기하기")`.
  - `talk.messages(rp: Roleplay) -> list[dict]` — 아래 규칙.
  - `class Talks: __init__(self, engine: Engine)`, `async def create(self) -> Roleplay`.
  - `FakeClaude.talk(messages)`: `self.talk_calls.append(messages)`, `fail_next`를 따르고, `self.talk_gate`(있으면 첫 조각 전에 기다린다)를 지나 `self.talk_pieces = ["Sounds fun! ", "I walk there too. ", "Was it busy?"]`를 흘린다. `self.talk_fail_after: int | None`(그 조각 수 뒤 `ClaudeUnavailable`).
  - `FakeWhisper.by_lang: dict[str, str]` — `transcribe(wav, lang)`이 `by_lang.get(lang, self.text)`. `FakeWhisper.fail_lang: str | None` — 그 언어의 `transcribe`는 `WhisperError`.
  - `conftest.talks(engine)` → `Talks(engine)`.

`TALK_OPENERS`(지어낸 일상 질문, 그대로):

```python
TALK_OPENERS: tuple[str, ...] = (
    "Hi! What did you do today?",
    "What did you have for lunch today?",
    "Do you have any plans for this weekend?",
    "What have you been enjoying lately?",
    "How was your morning?",
    "What did you do last weekend?",
    "Are you a morning person or a night person?",
    "What do you usually do after work?",
    "Have you watched anything good recently?",
    "What's the weather like where you are today?",
)
```

`messages(rp)` 규칙:
- 맨 앞은 `{"role": "user", "content": TALK_START}`.
- 라이언의 `reply` 줄은 assistant. 글은 줄의 `text`. `heard_upto`가 있으면 `parts` 앞쪽 그 수만큼의 글을 띄어 잇고 뒤에 `TALK_CUT`, `heard_upto == 0`이면 `TALK_CUT_SILENT`만.
- 내 `turn` 줄은 user, 글은 `text`.
- `ask`, `help`, `fix` 줄은 넣지 않는다(스펙 3: 한국어 차례는 Claude에 보내지 않는다).
- 같은 역할이 이어지면 줄바꿈으로 합친다(Claude가 답하지 못한 뒤의 내 차례 둘).

- [ ] **Step 1: 실패하는 시험을 쓴다**
  - `test_phrases.py` `test_openers_are_short_everyday_questions` — 열 개, 서로 다름, 모두 `?`로 끝, 12낱말 이하, 한글 없음. `test_talk_phrases` — `PHRASES["talk_english"]`, `PHRASES["talk_no_fixes"]`가 Global Constraints 글과 같다.
  - `test_store.py` `test_talk_turn_is_kept`(`save_talk(3)` 뒤 `load_talk() == 3`), `test_unreadable_talk_file_starts_over`(`{not json` → 0).
  - `test_talk.py`(`pytestmark = pytest.mark.anyio`):
    - `test_create_starts_with_the_next_opener_in_turn` — 두 번 만들면 첫 줄이 `TALK_OPENERS[0]`, `[1]`. 기록 `kind == "talk"`, `frame == TALK_FRAME`, 줄 하나 `speaker "ryan"`, `kind "reply"`, `parts == [Said(text=opener, audio=fake_voice.key("ryan","english",opener))]`, 저장되어 `engine.load(id)`로 읽힌다.
    - `test_openers_keep_their_turn_across_a_restart` — `Talks(engine_factory())`로 하나, 새 엔진으로 하나 → `[0]`, `[1]`.
    - `test_openers_wrap_after_the_last` — 열한 번째가 `[0]`.
    - `test_opener_sound_is_made_if_missing` — 만들 때 `fake_voice.calls`에 `(opener, "ryan", "english", True)`.
    - `test_openers_and_talk_phrases_are_made_ahead` — `await engine.warm()` 뒤 `set(TALK_OPENERS) <= set(fake_voice.checked)`이고 그 호출은 `("ryan", "english", False)`, `PHRASES["talk_english"]`도 만들어짐.
    - `test_messages_put_ryan_as_assistant_after_the_start` — `talk_example()` → 역할 차례 `["user","assistant","user","assistant","user","assistant"]`(시작, 줄 0, 3, 4, 5, 6).
    - `test_messages_tell_where_ryan_was_cut_off` — 줄 4(`heard_upto` 1)의 글이 `"Sounds lovely! " + TALK_CUT`(띄어쓰기 하나로).
    - `test_messages_say_when_ryan_was_cut_off_before_a_word` — 줄 4의 `heard_upto`를 0으로 바꾼 사본 → 그 글이 `TALK_CUT_SILENT`.
    - `test_messages_leave_korean_turns_and_fixes_out` — 한글이 든 글 없음(줄 1, 2), 줄 7의 고친 문장 없음, 마지막이 assistant 줄 6.
    - `test_messages_join_two_learner_turns_in_a_row` — `turn`, `turn`이 이어진 기록 → user 메시지 하나에 두 글이 줄바꿈으로.

- [ ] **Step 2: 실패를 본다** — `cd server && uv run pytest -q tests/test_talk.py tests/test_phrases.py tests/test_store.py` → `ModuleNotFoundError: je_server.talk`

- [ ] **Step 3: 구현한다**
  - `talk.py` 머리 주석: 스펙 경로, 자유 대화는 `kind "talk"` 기록이고 줄 번호 경로를 그대로 쓴다는 것, 녹음은 맥에만 두고 Claude에는 글만 간다는 것.
  - `Talks.create`: `load_talk` → 고르기 → `save_talk(n + 1)`을 await 없이 이어서(같은 때 둘이 와도 차례가 하나씩 간다) → `await voice.say(opener, "ryan", "english", urgent=True, check=True)`(이미 있으면 바로 돌아온다, `VoiceError`는 로그 한 줄로 넘긴다) → 기록 저장.
  - `engine.warm`: `TALK_OPENERS`를 라이언 영어 목소리로 `urgent=False, check=True`.
  - `phrases.py`: 주석에 스펙 2(가벼운 일상 질문, 한국어 소개 말 없음, 차례로 돌림, 맥 기록 폴더에 다음 차례).

- [ ] **Step 4: 통과를 본다** — `cd server && uv run pytest -q`

- [ ] **Step 5: 커밋한다** — `feat(server): start a free talk with Ryan's next everyday question`

### Task 5: 한 차례: 받아쓰기, 한국어 대비책, 흘려 보내는 답, 끊기

**Files:**
- Modify: `server/je_server/talk.py`, `server/je_server/engine.py`(`speak`), `server/je_server/sentences.py`(`split`)
- Test: `server/tests/test_talk.py`, `server/tests/test_engine.py`, `server/tests/test_sentences.py`(가짜는 Task 4의 `FakeClaude.talk`, `FakeWhisper.by_lang`, `fail_lang`)

**Interfaces:**
- Consumes: Task 2 `Voice.demote`, Task 3 `Claude.talk`, Task 4 `messages`, `Talks`.
- Produces:
  - `sentences.split(text: str) -> list[str]` — `SentenceBuffer`에 한 번에 넣고 `flush`한 것(흘려 넣을 때와 같은 자리에서 자른다).
  - `Engine.speak(self, text, said, keys, timings, t0, lang: Literal["korean", "english"] = "korean", on_text_end: Callable[[str], Awaitable[dict | None]] | None = None)` — 문장 소리를 라이언의 `lang` 목소리로 만든다. 글이 오류 없이 끝나면 `on_text_end("".join(said))`를 부르고, 돌려준 이벤트를 그 자리에서 앱에 보낸다(소리 이벤트 사이일 수 있다). 지금 부르는 곳은 그대로 한국어.
  - `talk.TalkEnded(Exception)`, `talk.TalkBusy(Exception)`.
  - `Talks.check_open(self, rp_id: str) -> Roleplay` — 자유 대화가 아니면 `NotFound`, 고친 문장 줄이 있으면 `TalkEnded`, 차례가 도는 중이면 `TalkBusy`.
  - `Talks.turn(self, rp_id: str, body: bytes, heard: int | None) -> AsyncIterator[dict]`, 이벤트(이 차례로):
    - `{"type": "heard", "text": str, "n": int, "idx": int, "korean": bool}` — `idx`는 내 줄 번호, `n`은 녹음 번호
    - `{"type": "text", "delta": str}`…
    - `{"type": "reply", "idx": int, "kind": "reply" | "help", "parts": [{"text", "audio"}…]}` — 글이 다 왔을 때, 라이언 줄을 저장한 뒤
    - `{"type": "audio", "key": str}`… (`reply` 앞에 올 수도 있다)
    - `{"type": "done", "idx": int}` — 라이언 줄 번호, 소리까지 다 보낸 뒤
    - 오류는 `{"type": "error", "code": "no_speech" | "too_long" | "claude_unavailable" | "ended" | "busy", "say": Said | None}`이고 그 뒤 `done` 없음.
  - `Talks.turning: set[str]`, `Talks.finishing: dict[tuple[str, int], asyncio.Task]`.

차례의 순서(`Talks.turn`):
1. `engine._answering()` 안에서 돈다(소희 소리 미리 만들기가 기다린다). `rp_id`가 `turning`에 있으면 `busy` 오류, 고친 줄이 있으면 `ended` 오류. 아니면 넣는다. **라이언 줄(`reply`나 `help`)을 저장하는 즉시 뺀다.** 그 뒤 소리를 만드는 동안 학습자가 끊고 다음 차례를 보낼 수 있어야 하기 때문이다(스펙 2). 그 전에 끝나면(오류, 끊긴 연결) `finally`에서 뺀다.
2. 앞 라이언 줄 표시(`_mark_heard`): 마지막 줄이 라이언의 `reply`이고 `heard is not None and heard < len(parts)`이면 그 줄의 `heard_upto = heard`로 저장, `voice.demote(남은 parts의 audio)`, 남은 문장 가운데 파일이 없는 것을 `urgent=False`로 만드는 뒷일을 `finishing[(rp_id, idx)]`에 둔다(`engine._keep`처럼, 이미 있으면 새로 두지 않는다). `heard >= len(parts)`면 끝까지 들은 것이라 아무것도 적지 않는다.
3. `idx = len(rp.lines)`, `n, rec = store.next_rec(rp_id, idx)`, 녹음을 쓴다(맥에 남는다).
4. `audio.to_wav16k`(`AudioError` → `no_speech`), `MAX_SECONDS` 넘음 → `too_long`, `has_speech` 아님 → `no_speech`. 이때는 줄을 남기지 않는다(녹음 파일은 역할극처럼 남는다).
5. `whisper.transcribe(wav, "en")`. 결과에 `HANGUL`이 있으면 `whisper.transcribe(wav, "ko")`(`WhisperError`면 영어 받아쓰기를 그대로 보인다)로 `korean=True`. 보일 글에 영어 낱말도 한글도 없으면 `no_speech`. WAV는 지운다. `timings["transcribed"]`.
6. 내 줄(`turn` 또는 `ask`, `text`는 들린 말)과 시도(`Attempt(n, mode="turn", heard=글, followed=False, issues=[], say_ko="", audio=[], timings, at=지금)`)를 `engine.lock` 안에서 더해 저장하고 `heard` 이벤트.
7. 한국어면: `help = engine.said("talk_english")`, `text` 이벤트(그 글) → 라이언 `help` 줄(`audio`와 `parts=[help]`) 저장 → `reply` 이벤트(`kind "help"`) → `audio` 이벤트 → `done`. Claude는 부르지 않는다.
8. 영어면: `engine.speak(self._reply_text(rp_id), said, keys, timings, t0, lang="english", on_text_end=...)`. `_reply_text`는 `claude.talk(messages(지금 기록))`을 흘리고, 아무 글 없이 끝나면 `ClaudeUnavailable("empty")`. `on_text_end`는 `parts = [Said(text=s, audio=voice.key("ryan","english",s)) for s in sentences.split(글)]`로 라이언 `reply` 줄을 저장하고 `reply` 이벤트를 돌려준다. `speak`이 `claude_down` 오류를 냈으면 라이언 줄은 없고(내 줄은 남는다, 스펙 4) `done`도 없다.
9. `timings["total"]`을 그 시도에 저장(`engine.lock` 안에서 그 시도만 고친다), 로그 한 줄 `talk %s/%d n=%d korean=%s transcribed=%.2f first_text=%.2f first_audio=%.2f total=%.2f`(글 없음).

- [ ] **Step 1: 실패하는 시험을 쓴다**
  - `test_sentences.py` `test_split_cuts_like_the_buffer` — `split("Sounds fun! I walk there too. Was it busy?") == ["Sounds fun!", "I walk there too.", "Was it busy?"]`, 빈 글 `[]`.
  - `test_engine.py` `test_speak_in_english_uses_ryans_english_voice` — `speak(…, lang="english")`의 소리 호출이 `("ryan", "english", True)`. `test_speak_tells_when_the_text_is_done` — `on_text_end`가 다 이은 글을 한 번 받고, 돌려준 이벤트가 마지막 `text` 뒤에 나온다. Claude가 끊기면 부르지 않는다.
  - `test_talk.py`(`speech_bytes`, `silent_bytes` 고정물, 대화는 `talks.create()`로):
    - `test_turn_events_in_order` — `type`의 차례가 `heard`, `text`…, 그리고 `reply`와 `audio`…(둘은 섞일 수 있음), 마지막 `done`. `heard`: `idx 1, n 1, korean False`, 글은 `fake_whisper.text`. `reply`: `idx 2, kind "reply"`, `parts`의 글이 `["Sounds fun!", "I walk there too.", "Was it busy?"]`, 소리 키가 라이언 영어. `done.idx == 2`.
    - `test_turn_is_transcribed_in_english_only` — `fake_whisper.langs == ["en"]`.
    - `test_turn_saves_my_line_the_recording_and_ryans_reply` — 줄 1 `turn`(글 = 들린 말), 시도 `mode "turn"`, `timings`에 `transcribed`, `first_text`, `first_audio`, `total`, `store.find_rec(id, 1, 1)`이 있다. 줄 2 `reply`, `parts` 셋.
    - `test_reply_goes_to_claude_as_turns` — `fake_claude.talk_calls[0]`의 역할 차례 `["user","assistant","user"]`, 마지막 글이 들린 말.
    - `test_hangul_in_the_english_transcript_is_heard_again_in_korean` — `by_lang = {"en": "I am 피곤해 today", "ko": "오늘 피곤해요"}` → `langs == ["en","ko"]`, `heard.text == "오늘 피곤해요"`, `korean True`. 줄 1 `ask`, 줄 2 `help`(글 `PHRASES["talk_english"]`, `audio == engine.said("talk_english").audio`), `reply.kind == "help"`, `talk_calls == []`.
    - `test_korean_transcription_failing_still_answers_in_korean` — `by_lang["en"]`에 한글, `fail_lang = "ko"` → `heard.text`가 영어 받아쓰기, `korean True`, `help`로 답.
    - `test_korean_turns_are_not_sent_to_claude` — 한국어 차례 뒤 영어 차례 → 둘째 `talk_calls`에 한글 없음.
    - `test_claude_down_mid_reply_keeps_my_turn_only` — `talk_fail_after = 1` → `error` 코드 `claude_unavailable`, `say`가 `claude_down`, `done` 없음. 기록 줄이 둘(첫 질문, 내 차례). 다음 차례의 메시지에 내 차례 둘이 한 user 메시지로.
    - `test_no_speech_turn_saves_no_line` — `silent_bytes` → `error no_speech`, 줄 하나 그대로.
    - `test_cut_reply_is_kept_and_told` — 첫 차례 뒤 둘째 차례를 `heard=1` → 줄 2 `heard_upto == 1`, 둘째 `talk_calls`의 assistant 글이 `"Sounds fun! " + TALK_CUT`.
    - `test_heard_all_of_the_reply_is_not_a_cut` — `heard=3`, `heard=99` → `heard_upto is None`.
    - `test_cut_reply_rest_is_demoted_and_still_made` — 첫 차례 뒤 `parts[1:]`의 소리 파일을 지우고 `heard=1`로 둘째 차례 → `fake_voice.demoted`가 그 두 키, `talks.finishing`의 일을 기다리면 두 파일이 다시 있고 그 호출은 `urgent False`.
    - `test_a_second_turn_while_one_runs_is_busy` — `talk_gate`로 첫 차례의 답을 붙잡은 채 둘째 → `error busy`, `check_open` → `TalkBusy`. 문을 열고 다 받으면 `turning`이 빈다.
    - `test_a_turn_can_start_once_the_reply_text_is_saved` — 첫 차례의 이벤트를 `reply`까지만 받은 때(소리는 아직) `check_open(id)`이 오류 없이 돌아온다(끊기).
    - `test_turn_on_a_roleplay_is_not_found` — 보통 역할극 id로 `check_open` → `NotFound`.

- [ ] **Step 2: 실패를 본다** — `cd server && uv run pytest -q tests/test_talk.py tests/test_engine.py tests/test_sentences.py`

- [ ] **Step 3: 구현한다.** 위 순서대로. `engine.speak`의 `make_audio`는 `self.voice.say(s, "ryan", lang, urgent=True)`. 주석에 스펙 3(영어로만, 0.85초), 4(첫 문장부터), 2(끊기)를 적는다.

- [ ] **Step 4: 통과를 본다** — `cd server && uv run pytest -q`

- [ ] **Step 5: 커밋한다** — `feat(server): answer a free-talk turn sentence by sentence in Ryan's English voice`

### Task 6: 고쳐 주기를 고르고 거르기

**Files:**
- Create: `server/je_server/fixes.py`, `server/tests/test_fixes.py`
- Modify: `server/je_server/compare.py`(`listed_sound`), `server/je_server/prompts.py`(`FIX_SYSTEM`, `FIX_SCHEMA`), `server/je_server/claude.py`(`fixes`), `server/tests/fakes.py`(`FakeClaude.fixes`)
- Test: `server/tests/test_fixes.py`, `server/tests/test_claude.py`, `server/tests/test_compare.py`

**Interfaces:**
- Produces:
  - `compare.listed_sound(meant: str, heard: str) -> tuple[tuple[str, str], str] | None` — 낱말 하나씩일 때만 `_listed`와 같다(사전 발음 두 소리 이내, 목록에 있는 소리, 그 설명).
  - `prompts.FIX_SCHEMA = _obj({"items": {"type": "array", "items": _obj({"idx": INT, "said": STR, "fixed": STR, "why_ko": STR, "sound": _obj({"heard": STR, "meant": STR, "say_ko": STR})})}})`(`INT = {"type": "integer"}`), 짐작이 없으면 `sound`의 세 값이 `""`.
  - `prompts.FIX_SYSTEM`(한국어 지시문, 아래 규칙).
  - `Claude.fixes(self, conversation: list[dict]) -> list[dict]` — 글쓰기 모델, JSON(`_json`, `max_tokens=1500`, 실시간 설정 아님). 보내는 몸: `{"대화": [{"차례": idx, "말한 사람": "라이언" | "학습자", "말": text}…]}`. JSON이 아니거나 `items` 목록이 없으면 `ClaudeUnavailable("bad fixes")`.
  - `fixes.MAX_FIXES = 3`, `fixes.FIXED_MAX_WORDS = 12`.
  - `@dataclass(frozen=True) class Found: of: int; said: str; fixed: str; why_ko: str`.
  - `fixes.check(items: list[dict], turns: dict[int, str]) -> list[Found]` — `turns`는 내 영어 차례(줄 번호 → 들린 말). 아래 규칙.
  - `fixes.line_before(rp: Roleplay, idx: int) -> ScriptLine | None` — 고친 문장 줄이면 `rp.lines[fix.of - 1]`(그 차례 앞의 라이언 말), 아니면 `rp.lines[idx - 1]`, 없으면 None.
  - `FakeClaude.fixes(conversation)`: `self.fix_calls.append(conversation)`, `fail_next`를 따르고, `self.fix_items: list[dict]`(기본 빈 목록)을 돌려준다. `self.fix_gate`(있으면 기다린다).

`FIX_SYSTEM`이 담을 규칙(문구는 빌더가 쓴다, 다른 지시문처럼 한국어):
- 받는 것: 자유 대화 전체. 학습자의 말은 맥의 받아쓰기라 틀린 낱말이 있을 수 있다.
- 학습자의 차례에서 어색한 곳을 많아야 세 가지, 확실한 것만 고른다. 없으면 빈 목록. 한 가지는 차례 하나.
- `idx`는 그 차례 번호, `said`는 그 차례에서 고칠 곳이 든 한 문장을 받은 글 그대로, `fixed`는 그 문장을 학습자가 한 말에 가깝게 원어민이 실제로 하는 말로 고친 것(12낱말 안쪽, 길면 고칠 곳이 든 부분만), `why_ko`는 무엇을 왜 바꾸는지 한두 문장(해요체).
- 고치지 않는다: 뜻이 통하는 흔한 짧은 대답(「Good.」, 「Yes, I like it.」), 영어로 어떻게 말하는지 묻는 차례, 라이언이 못 알아들어 다시 말해 달라고 한 차례. 받아쓰기가 잘못 적은 것일 수 있는 낱말을 문법 실수로 짚지 않는다.
- 발음 짐작: 받아쓴 낱말이 앞뒤와 맞지 않고 소리가 비슷한 낱말이 맞으면 `sound.heard`(받아쓴 낱말), `sound.meant`(하려던 낱말), `sound.say_ko`(「meant가 heard처럼 들렸어요.」 한 문장)를 채우고 `fixed`에는 하려던 낱말을 넣는다. 「~라고 말했어요」라고 단정하지 않는다. 소리 내는 법은 쓰지 않는다(맥이 붙인다). 이것만 고칠 곳이면 `why_ko`는 비운다.
- 영어 낱말 뒤 조사 규칙(`FEEDBACK_SYSTEM`의 그 줄과 같게), 마크다운·따옴표·이모지 없음.

`check` 규칙(이 차례로):
1. `idx`가 `turns`에 없으면 버린다(라이언 줄, 한국어 차례, 고친 줄). 같은 `idx`는 처음 것만.
2. `said`가 비었거나 `sentence_key(said)`가 `sentence_key(turns[idx])` 안에 없으면 버린다.
3. `fixed`가 비었거나 `compare.words(fixed)`가 12개를 넘거나 `sentence_key(fixed) == sentence_key(said)`면 버린다.
4. 발음 짐작은 `heard`, `meant`가 낱말 하나씩이고, `heard`가 `compare.words(said)`에 있고, `listed_sound(meant, heard)`가 있고, `say_ko`에 한글과 「처럼 들렸」이 있고 「말했」이 없을 때만 남긴다. 남기면 설명은 `" ".join([why_ko, say_ko, 목록 설명])`(빈 것 빼고, 목록 설명은 글자 그대로).
5. 짐작을 버렸고 `why_ko`가 비었거나 한글이 없으면 그 가지를 버린다.
6. 차례 순서로 정렬해 앞의 셋.

- [ ] **Step 1: 실패하는 시험을 쓴다**
  - `test_compare.py` `test_listed_sound_for_one_word_each` — `listed_sound("right", "light")`의 소리가 `("R", "L")`, 설명이 `sounds.find("R","L").explain`. `listed_sound("cut", "cat") is None`(목록에 없는 소리), `listed_sound("restaurant", "rest around") is None`.
  - `test_fixes.py`(지어낸 차례 `TURNS = {1: "I walked to the park with my dog.", 3: "Yesterday I go to the market.", 5: "I turned light at the bank.", 7: "I had a cat on my finger."}`, 도우미 `item(idx, said, fixed, why="…해요.", heard="", meant="", say="")`):
    - `test_items_beyond_three_are_dropped` — 넷 → 셋, 차례 순서.
    - `test_an_item_on_a_line_that_is_not_my_english_turn_is_dropped` — `idx` 2(라이언), 9(없음) → 빈 목록.
    - `test_one_item_per_turn` — 같은 `idx` 둘 → 첫 것.
    - `test_said_must_be_in_the_turn` — 차례에 없는 문장 → 버림. 대소문자와 문장부호만 다르면 남김.
    - `test_fixed_over_twelve_words_or_unchanged_is_dropped`.
    - `test_a_listed_sound_guess_adds_the_list_words` — 차례 5, `heard "light"`, `meant "right"`, `say_ko "right가 light처럼 들렸어요."`, `why ""` → `why_ko == "right가 light처럼 들렸어요. " + sounds.find("R","L").explain`, `fixed`는 받은 그대로.
    - `test_an_unlisted_guess_is_dropped_and_its_item_too_without_other_fixes` — 차례 7, `cut`/`cat`, `why ""` → 빈 목록. 같은 것에 `why`가 있으면 남고, `why_ko`에 「처럼 들렸」이 없다.
    - `test_a_guess_that_says_what_was_said_is_dropped` — `say_ko`에 「light라고 말했어요」 → 짐작 버림.
    - `test_a_guess_whose_heard_word_is_not_in_the_sentence_is_dropped`.
    - `test_line_before_a_fix_is_ryans_line_before_the_turn` — `talk_example()`의 줄 7 → 줄 4(바로 앞 줄 6이 아니다). 보통 줄 3 → 줄 2, 줄 0 → None.
  - `test_claude.py` `test_fixes_sends_the_conversation_and_reads_items` — `FakeAnthropic([json.dumps({"items": [...]})])` → 돌려준 목록이 같고, 요청 `system == FIX_SYSTEM`, `model`이 글쓰기 모델, `output_config.format.schema == FIX_SCHEMA`, 보낸 user 글의 JSON에 `"대화"`. `test_fixes_bad_json_is_unavailable` — `"not json"` → `ClaudeUnavailable`.

- [ ] **Step 2: 실패를 본다** — `cd server && uv run pytest -q tests/test_fixes.py tests/test_compare.py tests/test_claude.py`

- [ ] **Step 3: 구현한다.** `fixes.py` 머리 주석: 스펙 7, 「확실한 것만 짚는다」, 소리 설명은 목록 그대로(말하기 연습 스펙 「소리 설명 목록」), 맥이 짐작을 확인한다는 것(ADR-0004 「영향」: 무엇을 짚을지는 맥이 정한다). `prompts.py`에 `INT = {"type": "integer"}`를 더한다.

- [ ] **Step 4: 통과를 본다** — `cd server && uv run pytest -q`

- [ ] **Step 5: 커밋한다** — `feat(server): pick at most three post-talk fixes and keep only listed sound guesses`

### Task 7: 대화 끝내기와 고친 문장 줄

**Files:**
- Modify: `server/je_server/talk.py`(`end`, `fix_input`), `server/je_server/engine.py`(`_sound`, `ready`, `context`, `_make_ko`, `_attempt`)
- Test: `server/tests/test_talk.py`, `server/tests/test_engine.py`

**Interfaces:**
- Consumes: Task 6 `Claude.fixes`, `fixes.check`, `fixes.line_before`, Task 5 `_mark_heard`, `turning`.
- Produces:
  - `talk.fix_input(rp: Roleplay) -> tuple[list[dict], dict[int, str]]` — Claude에 보낼 대화(라이언 `reply` 줄과 내 `turn` 줄만, 줄 번호와 글)와 내 영어 차례 지도.
  - `Talks.end(self, rp_id: str, heard: int | None = None) -> dict` — 몸 `{"items": [{"line": ScriptLine JSON, "rec": {"rp_id", "idx", "n"} | None}…], "say": Said JSON | None}`. 고칠 것이 없거나 내 영어 차례가 없으면 `items` 빈 목록과 `say = said("talk_no_fixes")`. 차례가 도는 중이면 `TalkBusy`. Claude가 답하지 못하면 `ClaudeUnavailable`.
  - `Talks.ending: dict[str, asyncio.Task]` — 같은 대화의 끝내기는 하나의 일을 나눠 기다린다.
  - `Engine.ready(line)`: 고친 문장 줄은 `fix.why_audio`까지 있어야 한다. `Engine._sound`: 고친 문장 줄의 `why_audio`가 없으면 먼저 라이언 한국어로(`urgent=False, rank=idx`) 만들어 `fix`를 바꿔 저장한다.

끝내기의 순서:
1. 자유 대화인지만 본다(아니면 `NotFound`, `check_open`과 달리 끝난 대화를 막지 않는다). 차례가 도는 중이면 `TalkBusy`. 이미 `fix` 줄이 있으면 Claude 없이 그 줄들로 몸을 만든다. 도는 끝내기가 있으면 그것을 기다린다(`asyncio.shield`).
2. `_mark_heard(rp, heard)`. 마지막 라이언 답의 아직 없는 소리를 `voice.demote`(끝내기 소리가 앞서게).
3. 내 영어 차례가 없으면 Claude 없이 「고칠 것 없음」 몸.
4. `fixes.check(await claude.fixes(대화), turns)`. 빈 목록이면 「고칠 것 없음」.
5. `engine.lock` 안에서 다시 읽고, `fix` 줄이 그사이 생겼으면 그것을 쓴다. 아니면 줄마다 `ScriptLine(idx, speaker="user", kind="fix", text=fixed, fix=Fix(of, said, why_ko))`를 더해 저장.
6. 첫 가지: `why_ko`(라이언 한국어)와 `fixed`(라이언 영어)를 `urgent=True`로 만들어 `update_line`(`VoiceError`는 로그만, 뒤에서 다시 만든다).
7. 모든 고친 줄을 `engine.schedule`(본보기, 설명 소리, 세 줄을 뒤에서).
8. 가지마다 `rec`은 `of` 줄의 마지막 `turn` 시도 번호.

- [ ] **Step 1: 실패하는 시험을 쓴다**
  - `test_talk.py`(대화를 만들고 영어 차례 둘을 보낸 뒤, `fake_claude.fix_items`를 그 차례에 맞게 둔다):
    - `test_end_appends_the_checked_fixes_as_my_lines` — 맞는 것 넷 → 셋, 줄 `kind "fix"`, `speaker "user"`, `fix.of`가 차례 번호, `text`가 `fixed`. 몸 `items`의 `line.idx`가 그 줄, `rec == {"rp_id": id, "idx": of, "n": 1}`, `say is None`.
    - `test_end_makes_the_first_fix_sounds_first_and_urgent` — 끝내기 뒤 `fake_voice.calls`에서 첫 고친 것의 `(why_ko, "ryan", "korean", True)`, `(fixed, "ryan", "english", True)`가 다른 고친 것의 소리보다 앞. 몸의 첫 줄에 `audio`와 `fix.why_audio`가 있다.
    - `test_two_ends_at_once_ask_claude_once` — `fix_gate`로 붙잡고 `asyncio.gather(end, end)` → `len(fix_calls) == 1`, 두 몸이 같다.
    - `test_end_again_returns_the_same_fixes_without_claude`.
    - `test_end_without_english_turns_says_nothing_to_fix_without_claude` — 한국어 차례만 → `items == []`, `say.text == PHRASES["talk_no_fixes"]`, `fix_calls == []`.
    - `test_end_with_nothing_to_fix_says_so` — `fix_items = []` → 같은 몸, 줄 그대로.
    - `test_end_sends_english_turns_and_ryans_replies_only` — 한국어 차례가 있는 대화 → `fix_calls[0]`에 한글 없음, 「차례」가 줄 번호.
    - `test_end_while_a_turn_runs_is_busy`, `test_a_turn_after_end_is_ended`(`check_open` → `TalkEnded`).
    - `test_end_marks_where_ryan_was_cut_off` — `end(id, heard=1)` → 마지막 답 `heard_upto == 1`.
  - `test_engine.py`(`talk_example()`을 저장해서):
    - `test_a_fix_line_waits_for_its_explanation_sound_too` — 줄 7의 `audio`, `why_audio`를 비운 사본 → `await engine.line(id, 7)`의 `audio`와 `fix.why_audio`가 있고, 설명 소리는 `("ryan", "korean", False)`.
    - `test_a_fix_lines_notes_see_the_turn_it_fixes` — 줄 7의 세 줄 맥락(`fake_claude.calls`의 `annotate` 둘째 값)에 `rp.lines[fix.of - 1].text`가 있고 줄 6의 글이 없다.
    - `test_interpreting_a_fix_line_uses_ryans_line_before_the_turn` — `engine.ko(id, 7)` → `interpret_calls[0]["before"] == ("ryan", line_before의 글)`, `after is None`.
    - `test_practising_a_fix_line_aside_sees_the_conversation_up_to_the_turn` — 줄 7에 따라 말하지 않은 녹음(`mode "practice"`) → `aside_calls[0]["history"]`에 고친 문장 줄과 `ask`, `help` 줄이 없고, 마지막이 `fix.of` 앞 줄.
    - 지금 `test_ko_context_is_the_conversation_as_it_went`, `test_history_skips_asides`가 그대로 통과(역할극은 바뀌지 않는다).

- [ ] **Step 2: 실패를 본다** — `cd server && uv run pytest -q tests/test_talk.py tests/test_engine.py`

- [ ] **Step 3: 구현한다**
  - `talk.py`: 위 순서. 몸 만들기는 `_end_body(rp, lines)` 하나로.
  - `engine.py`: `history`는 줄과 한 칸씩 맞는 지금 모양 그대로 둔다(`_make_ko`가 줄 번호로 고른다). 고친 문장 줄만 따로: `context`와 `_make_ko`는 `fixes.line_before`로 앞 줄을 쓰고 뒤 줄은 없다. `_attempt`의 선생님 답 대화는 고친 문장 줄이면 `history(rp, fix.of)`, 자유 대화면 `reply`, `turn` 줄만 남긴다(`zip(history, rp.lines)`로 거른다). 주석에 스펙 8 「앞 대사」.

- [ ] **Step 4: 통과를 본다** — `cd server && uv run pytest -q`

- [ ] **Step 5: 커밋한다** — `feat(server): end a free talk with checked fixes as practice lines`

### Task 8: `/talks` 경로와 계약

**Files:**
- Modify: `server/je_server/app.py`
- Create: `contract/talk-events.ndjson`, `contract/talk-end.json`
- Test: `server/tests/test_api.py`, `server/tests/test_contract.py`

**Interfaces:**
- Consumes: `Talks`(Task 4, 5, 7), `TalkEnded`, `TalkBusy`.
- Produces:
  - `Services.talks: Talks | None = None` — 없으면 `__post_init__`에서 `Talks(engine)`. `Services.start`는 그대로(`engine.warm`이 첫 질문도 만든다).
  - `POST /talks` → 기록 JSON. `VoiceError`는 이미 `create`가 삼킨다.
  - `POST /talks/{rp_id}/turns?heard=k` (`rp_id` `ID` 패턴, `heard: int | None = Query(None, ge=0, le=50)`, 몸은 `read_body`) → `application/x-ndjson`. 흘리기 전에 `check_open`: `NotFound` → 404 `not_found`, `TalkEnded` → 409 `ended`, `TalkBusy` → 409 `busy`.
  - `POST /talks/{rp_id}/end?heard=k` → 몸. `NotFound` 404, `TalkBusy` 409, `ClaudeUnavailable` → 503 `claude_unavailable`와 `claude_down`.
  - `contract/talk-events.ndjson`: `heard`(`korean` false), `text` 둘, `reply`, `audio` 둘, `done`, 그리고 `error no_speech` 한 줄(지어낸 글, 소리 키는 같은 글자 64개).
  - `contract/talk-end.json`: `talk.json` 줄 7을 `line`으로, `rec {"rp_id": "b1b2c3d4e5f6", "idx": 5, "n": 1}`, `say: null`.

- [ ] **Step 1: 실패하는 시험을 쓴다**
  - `test_api.py`:
    - `test_talk_routes_need_token` — 토큰 없는 `POST /talks`, `/talks/000000000000/turns`, `/talks/000000000000/end` → 401.
    - `test_create_talk_route` — `kind "talk"`, `lines[0].parts[0].text == TALK_OPENERS[0]`.
    - `test_turn_route_streams_ndjson` — `speech_bytes`로 보내 줄마다 JSON, 첫 `type`이 `heard`, 마지막이 `done`, 사이에 `reply`.
    - `test_turn_route_refuses_a_big_upload` — `MAX_UPLOAD + 1` 바이트 → 413.
    - `test_turn_route_on_unknown_or_roleplay_is_404` — 없는 id, 보통 역할극 id → 404, 나쁜 id(`..%2Fx`) → 404나 422.
    - `test_turn_after_end_is_409`, `test_heard_must_be_a_small_count`(`heard=-1`, `heard=51` → 422).
    - `test_end_route_returns_items` — `fix_items`를 둔 뒤 → `items[0].line.kind == "fix"`, `rec`. `test_end_route_when_claude_is_down_is_503` — `fail_next` → 503 `claude_unavailable`, `say.text == PHRASES["claude_down"]`.
    - `test_a_fix_line_is_practised_on_the_attempt_route` — 끝낸 뒤 `POST /roleplays/{id}/lines/{fix idx}/attempts?mode=practice` → `heard`부터 흘러오고, 기록의 그 줄에 `practice` 시도.
    - `test_a_saved_fix_is_listed_as_free_talk` — `POST /saved {rp_id, idx: fix idx, on: true}` 뒤 `GET /saved`의 그 항목 `title_ko == "자유 대화"`, `speaker "user"`.
  - `test_contract.py` `test_talk_events_example_has_the_engine_types`(형이 `{"heard","text","reply","audio","error","done"}`, `heard` 키 `{type,text,n,idx,korean}`, `reply` 키 `{type,idx,kind,parts}`, `done` 키 `{type,idx}`), `test_talk_end_example_has_the_engine_shape`(키 `{items, say}`, 항목 키 `{line, rec}`, `ScriptLine.model_validate(line).model_dump(mode="json") == line`).

- [ ] **Step 2: 실패를 본다** — `cd server && uv run pytest -q tests/test_api.py tests/test_contract.py`

- [ ] **Step 3: 구현한다.** 경로 주석에 「토큰 뒤에 있다」, 크기 제한, 스펙 2·6·7. `test_routes_need_token`의 목록에도 새 경로를 더한다.

- [ ] **Step 4: 통과를 본다** — `cd server && uv run pytest -q`

- [ ] **Step 5: 커밋한다** — `feat(server): serve free talk turns and post-talk fixes behind the token`

### Task 9: 앱의 요청, 모양, 대화 리듀서

**Files:**
- Modify: `app/src/api/types.ts`, `app/src/api/client.ts`, `app/src/ui/theme.ts`
- Create: `app/src/flow/talk.ts`, `app/src/flow/talk.test.ts`
- Test: `app/src/api/client.test.ts`, `app/src/api/contract.test.ts`, `app/src/flow/talk.test.ts`

**Interfaces:**
- Consumes: Task 8의 경로와 이벤트.
- Produces(`types.ts`):
  - `TalkEvent = { type: "heard"; text: string; n: number; idx: number; korean: boolean } | { type: "text"; delta: string } | { type: "reply"; idx: number; kind: "reply" | "help"; parts: Said[] } | { type: "audio"; key: string } | { type: "error"; code: string; say: Said | null } | { type: "done"; idx: number }`
  - `TalkItem = { line: ScriptLine; rec: TryRef | null }`, `TalkEnd = { items: TalkItem[]; say: Said | null }`, `TALK_EVENT_TYPES`, `TALK_END_KEYS = ["items", "say"]`, `TALK_ITEM_KEYS = ["line", "rec"]`와 `KEYS_MATCH`의 줄.
- Produces(`client.ts`): `createTalk(): Promise<Roleplay>`(`POST /talks`, `LONG`), `talkTurn(id: string, fileUri: string, heard: number | null, onEvent: (e: TalkEvent) => void): Promise<void>`(`/talks/${id}/turns`, `heard`가 있으면 `?heard=k`), `endTalk(id: string, heard: number | null): Promise<TalkEnd>`(`LONG`). `attempt`의 흘려 읽기(30초 쉬면 `offline`)를 `readEvents(res, onEvent)` 하나로 빼서 둘이 같이 쓴다.
- Produces(`theme.ts`): `colors.free = "#7048E8"`(주석: 첫 화면 「자유 대화」 카드에만, 스펙 1).
- Produces(`flow/talk.ts`):
  - `TalkPhase = "opening" | "ryan" | "ready" | "recording" | "waiting" | "replying" | "ending" | "fixes" | "error"`
  - `TalkBubble = { kind: "ryan"; idx: number; text: string; parts: Said[]; heard: number | null } | { kind: "help"; idx: number; text: string; audio: string | null } | { kind: "me"; idx: number; text: string; rec: TryRef; korean: boolean }`
  - `TalkState = { phase; roleplay: Roleplay | null; bubbles: TalkBubble[]; turn: number; heardIn: boolean; pending: string; done: boolean; message: string | null; micUsed: boolean; end: TalkEnd | null; errorFrom: "opening" | "ending" | null }`, `talkInitial`(phase `opening`, turn 0).
  - `TalkAction = { type: "opened"; roleplay: Roleplay } | { type: "openFailed"; message: string } | { type: "retry" } | { type: "ryanDone" } | { type: "recordStart"; heard: number | null } | { type: "recordCancel" } | { type: "noSpeech" } | { type: "recordStop" } | { type: "event"; turn: number; e: TalkEvent } | { type: "failed"; turn: number; message: string } | { type: "endStart"; heard: number | null } | { type: "ended"; end: TalkEnd } | { type: "endFailed"; message: string }`
  - `talkReduce(s: TalkState, a: TalkAction): TalkState`
  - 판단 함수: `canSpeak(s)`(`ready`, 또는 `ryan`), `canEnd(s)`(같음), `mayListenTalk(s)`(`ready`만, 지난 말풍선의 🔊·통역·내 녹음), `isCurrent(s, turn)`(`turn === s.turn`), `englishTurns(s)`(한국어가 아닌 `me` 수), `turnNo(s)`(「N번째」의 N), `heardCount(parts: Said[], started: ReadonlySet<string>): number`(소리가 시작된 마지막 문장까지의 수, 없으면 0), `cutOf(s): number | null`(맨 마지막 말풍선이 라이언 말풍선이면 그 `heard`, 아니면 null. 서버도 마지막 줄이 라이언 `reply`일 때만 받는다), `lineSounds(line: Pick<ScriptLine, "parts" | "audio">): string[]`(`parts`가 있으면 그 소리들, 아니면 `audio` 하나, 없으면 빈 목록).

리듀서 규칙:
- `turn`은 `recordStart`마다 1 늘린다. 이벤트와 `failed`는 그 차례의 번호를 달고 오고, 지금 번호가 아니면 버린다(끊은 답의 늦은 소리, 뒤로 뒤의 늦은 답).
- `opened` → `ryan`, 말풍선은 첫 줄(`parts`, `heard` null), `done` true(첫 질문은 더 올 것이 없다).
- `ryanDone`은 `ryan`이고 `done`일 때만 `ready`.
- `recordStart`는 `canSpeak`일 때만. `ryan`에서 오면 마지막 라이언 말풍선의 `heard`를 받은 값으로(받은 값이 `parts` 수 이상이거나 null이면 null). `micUsed` true, `message` null.
- `recordCancel` → `ready`(끊긴 표시는 남는다), `noSpeech` → `ready`, `message`는 `state.ts`의 `NO_SPEECH`.
- `recordStop` → `waiting`, `heardIn` false, `pending ""`, `done` false.
- `heard` → `me` 말풍선(`rec {rp_id, idx, n}`), `heardIn` true. `text` → `replying`, `pending`에 더함. `reply` → `ryan`, `kind`가 `reply`면 라이언 말풍선(`text`는 `pending`을 다듬은 것, `parts`), `help`면 `help` 말풍선(`audio`는 `parts[0].audio`), `pending ""`. `done` → `done` true.
- `error`: `pending`을 버리고 `ready`, `message`는 `say.text`(없으면 `state.ts` 문구와 같게). 내 말풍선은 남는다. `failed`도 `ready`와 그 글.
- `endStart`는 `canEnd`일 때만 `ending`, 마지막 라이언 말풍선의 `heard`를 받은 값으로. `ended` → `fixes`, `end`. `endFailed` → `error`, `errorFrom "ending"`. `openFailed` → `error`, `errorFrom "opening"`. `retry`는 `error`에서 `errorFrom`의 단계로.
- `turnNo`: 내 말풍선 수 + (`waiting`이나 `replying`이고 `heardIn`이면 0, 아니면 1).

- [ ] **Step 1: 실패하는 시험을 쓴다**
  - `client.test.ts`: `talkTurn posts the recording with how much of Ryan was heard`(URL `${URL}/talks/x/turns?heard=1`, `Content-Type audio/mp4`, 이벤트를 차례로 받음), `talkTurn without a cut has no query`, `endTalk posts and reads the fixes`(`/talks/x/end`), `createTalk posts`. 지금 `attempt` 시험은 그대로 통과.
  - `contract.test.ts`: `talk events example types are known`(`TALK_EVENT_TYPES`), `talk end example has the keys the review screen reads`(`TALK_END_KEYS`, `TALK_ITEM_KEYS`, `line` 키 `LINE_KEYS`, `fix` 키 `FIX_KEYS`).
  - `talk.test.ts`(`contract/talk.json`의 줄 0을 첫 질문으로, 지어낸 `parts` 셋):
    - `opening shows Ryan's question and his turn ends when it is played` — `opened` → `ryan`, 말풍선 하나, `ryanDone` → `ready`.
    - `ryanDone waits for done` — `reply` 뒤 `done` 전의 `ryanDone`은 그대로(`toBe`).
    - `the mic cuts Ryan off once his text is complete` — `ryan`에서 `recordStart {heard: 1}` → `recording`, 마지막 라이언 `heard` 1, `turn` +1.
    - `no mic while Ryan is thinking or still writing` — `waiting`, `replying`, `recording`에서 `recordStart`는 `toBe(s)`.
    - `a second recordStart or endStart does nothing` — 같은 동작을 두 번 → 두 번째는 `toBe`.
    - `cancel after cutting Ryan off gives my turn, still cut`.
    - `events of an older turn are dropped` — `isCurrent(s, s.turn - 1) === false`, 그 이벤트는 `toBe(s)`.
    - `heard adds my bubble with its recording`, `Ryan's text streams then becomes his line`, `done hands back my turn when the sounds end`.
    - `Korean heard gets Ryan's fixed Korean nudge` — `heard {korean: true}` → `me.korean`, `reply {kind: "help"}` → `help` 말풍선.
    - `no speech goes back to my turn with Ryan's words`, `Claude down drops the half reply and keeps my bubble`, `a failed request gives my turn back`.
    - `ending only from my turn or while Ryan speaks`, `ended shows the fixes`, `a failed end can be tried again`, `a failed opening can be tried again`.
    - `turnNo counts my turns` — 첫 질문 1 → `heard` 뒤 1 → `reply` 뒤 2.
    - `englishTurns leaves Korean turns out`.
    - `heardCount is 0 before any sound and all once the last started` — 시작된 키 없음 0, 둘째 키만 2, 셋 다 3.
    - `lineSounds plays a reply's parts in order and a line's own sound otherwise`.

- [ ] **Step 2: 실패를 본다** — `cd app && npx jest src/flow/talk.test.ts src/api`

- [ ] **Step 3: 구현한다.** `talk.ts` 머리 주석에 스펙 2(끊기, 뒤로, 첫 내 차례), 6(끝내기), 「영어 차례가 없으면 첫 화면」은 화면이 `englishTurns`로 정한다는 것.

- [ ] **Step 4: 통과를 본다** — `cd app && npx jest && npx tsc --noEmit`

- [ ] **Step 5: 커밋한다** — `feat(app): add the free-talk requests and the talk flow reducer`

### Task 10: 고쳐 주기 리듀서와 모아 둔 문장의 판단

**Files:**
- Create: `app/src/flow/talkFix.ts`, `app/src/flow/talkFix.test.ts`
- Modify: `app/src/flow/talk.ts`(`savedBefore`, `replaysSituation`), `app/src/flow/talk.test.ts`

**Interfaces:**
- Consumes: `TalkEnd`, `TalkItem`(Task 9), `AttemptEvent`.
- Produces(`talkFix.ts`):
  - `FixPhase = "loading" | "ready" | "recording" | "evaluating" | "evaluated" | "error"`
  - `FixState = { rpId: string; items: TalkItem[]; at: number; line: ScriptLine | null; phase: FixPhase; tries: number; heard: string | null; heardRec: TryRef | null; feedback: string; message: string | null; reading: boolean }`, `fixInitial(rpId: string, end: TalkEnd): FixState`(`at` 0, `loading`)
  - `FixAction = { type: "lineLoaded"; line: ScriptLine } | { type: "lineFailed"; message: string } | { type: "retry" } | { type: "recordStart" } | { type: "recordCancel" } | { type: "noSpeech" } | { type: "recordStop" } | { type: "event"; tries: number; e: AttemptEvent } | { type: "failed"; tries: number; message: string } | { type: "again" } | { type: "next" } | { type: "toggleReading" }`
  - `fixReduce`, `isLastFix(s): boolean`, `nextLabel(s): "다음 ›" | "끝"`, `fixCount(s): string | null`(`"1/2"`, 가지가 하나면 null).
- Produces(`talk.ts`): `savedBefore(rp: Roleplay, line: ScriptLine): ScriptLine | undefined`(고친 문장 줄이면 `rp.lines[fix.of - 1]`, 아니면 `rp.lines[line.idx - 1]`, 서버 `fixes.line_before`와 같은 규칙), `replaysSituation(rp: Roleplay): boolean`(`rp.kind !== "talk"`).

규칙: `recordStart`는 `ready`나 `evaluated`에서만, `tries` +1, 앞 평가를 지운다. 이벤트는 지금 `tries`만. `heard` → 들린 말과 `heardRec {rp_id: rpId, idx: line.idx, n}`, `text` → `feedback`에 더함, `done` → `evaluated`, `error`의 `no_speech`·`too_long` → `ready`와 글, 그 밖 → `error`. `again` → `ready`, 평가 지움. `next`는 `evaluating`, `recording`이 아닐 때, 마지막이 아니면 `at` +1, `loading`, 새 상태. 마지막이면 그대로(화면이 첫 화면으로 간다).

- [ ] **Step 1: 실패하는 시험을 쓴다**
  - `talkFix.test.ts`(`contract/talk-end.json`): `opens on the first fix and loads its line`, `the practice result shows below and can be tried again`, `late events of an earlier try are dropped`, `no speech keeps the fix ready with the words`, `next goes to the next fix and the last says 끝`, `next does nothing while recording or evaluating`, `fixCount is shown only for two or more`.
  - `talk.test.ts`: `the line before a saved fix is Ryan's line before the turn it fixes`(줄 7 → `rp.lines[of - 1]`), `a roleplay line keeps the line right before it`, `a free talk is not played again from saved practice`(`replaysSituation`가 talk false, `contract/roleplay.json` true, `kind` 없는 옛 것 true).

- [ ] **Step 2: 실패를 본다** — `cd app && npx jest src/flow/talkFix.test.ts src/flow/talk.test.ts`

- [ ] **Step 3: 구현한다**

- [ ] **Step 4: 통과를 본다** — `cd app && npx jest && npx tsc --noEmit`

- [ ] **Step 5: 커밋한다** — `feat(app): add the post-talk fixes reducer`

### Task 11: 녹음 버튼 묶음과 대화 돌아보기 화면

**Files:**
- Create: `app/src/audio/useMic.ts`, `app/src/screens/TalkFixScreen.tsx`

**Interfaces:**
- Consumes: `fixReduce`, `fixInitial`, `nextLabel`, `fixCount`(Task 10), `useRecorder`, `createGate`, `createStartCancel`, `startKeepingCancel`, `stopThenSend`, `runThenHold`, `tapHold`, `api.getLine`, `api.getThree`, `api.attempt`(`mode "practice"`), `api.recordingSource`, `useSaved`, `StarButton`, `ThreeLineView`, `notesView`, `StopButton`, `SoonEnds`, `BackButton`, `useBackKey`, `tapPlay`, `usePlayingTag`.
- Produces:
  - `useMic(o: { canStart: () => boolean; beforeStart: () => void; onCancelled: () => void; onNoSpeech: () => void; onStopped: () => void; send: (uri: string, live: () => boolean) => Promise<void> }): { start: () => void; stop: () => void; cancel: () => void; leave: () => Promise<void>; liveSince: number | null; onLevel: ReturnType<typeof useRecorder>["onLevel"] }` — `RoleplayScreen`의 `doStart`, `stopRec`, `sendRec`의 파일 지우기, `doCancel`, `doSilentCancel`과 같은 순서와 막기(게이트 하나, 켜지는 동안의 취소 기억, 취소 뒤 짧은 막기, 8초 쉼 끝과 5초 취소, 떠나면 `epoch`가 바뀌어 늦은 것을 버림). `start`는 게이트 안에서 `canStart()`가 아니면 아무것도 하지 않고, 맞으면 `beforeStart()` 뒤 마이크를 켠다. `RoleplayScreen`은 바꾸지 않는다(41KB, 이 PR의 범위 밖).
  - `TalkFixScreen({ rp, end, sounds, onHome }: { rp: Roleplay; end: TalkEnd; sounds: SoundQueue; onHome: () => void })`.

- [ ] **Step 1: 먼저 main을 본다** — `/usr/bin/git fetch origin && /usr/bin/git log --oneline HEAD..origin/main -- app/src/audio/useRecorder.ts app/src/ui/StopButton.tsx app/src/audio/cueSound.ts`. 머지가 있으면 `/usr/bin/git merge origin/main`으로 받아 시험이 통과하는지 본 뒤 다음으로(스펙 「제약」).

- [ ] **Step 2: `useMic`를 쓴다.** 머리 주석에 `RoleplayScreen`에서 무엇을 옮겨 왔는지와, 그 규칙은 `gate.test.ts`가 지킨다는 것.

- [ ] **Step 3: `TalkFixScreen`을 쓴다**
  - 위: 「‹ 뒤로」(첫 화면), 제목 「대화 돌아보기」, `fixCount`.
  - 가지가 없으면: 노란 상자에 `end.say.text`, 열릴 때 한 번 그 소리, 맨 아래 「끝」(주된) → 첫 화면.
  - 가지마다: `loading`에서 `api.getLine(rp.id, line.idx)`(맥이 본보기와 설명 소리를 다 만들 때까지 기다린다) → `lineLoaded`, 실패 → `lineFailed`와 「다시 시도」. 열리면 한 번(`played` ref, 가지 번호로) `fix.why_audio`를 튼다.
  - 노란 상자: `fix.why_ko`. 「내가 한 말」: `fix.said`와 「🔊 내 녹음 들어 보기」(`rec`이 있을 때, 눌러야 들린다, `tapPlay`). 「이렇게 말해 보세요」: 고친 문장, 「🔊 듣기」(`line.audio`), 「읽는 법 보기」(`notesView`, 아직이면 「세 줄을 만들고 있어요…」), 「☆ 모아 두기」(`saved.toggle(rp.id, line.idx, line.text)`). 통역은 두지 않는다(스펙 7).
  - 맨 아래: `recording`이면 「취소」(덜 주된)와 `StopButton`, `SoonEnds`. `evaluated`면 「다음 ›」/「끝」(덜 주된)과 「다시 해 보기」(주된). 그 밖에는 「다음 ›」/「끝」(덜 주된, 녹음·평가 중 꺼짐)과 「🎤 따라 말하기」(주된, `evaluating`이면 「평가하고 있어요」로 꺼짐).
  - 따라 말하기: `useMic`. 보낼 때 `tries`를 달고 `api.attempt(rp.id, line.idx, uri, "practice", onEvent)`, 소리는 그 시도가 지금일 때만 넣는다. 들린 말과 피드백은 같은 화면 아래(노란 상자).
  - 「다음 ›」: 소리를 멈추고 `next`. 마지막의 「끝」과 뒤로(화면 버튼, 폰 키): 소리 멈춤, `mic.leave()`, `onHome()`.
  - 화면의 한국어는 `keepWords`.

- [ ] **Step 4: 확인한다** — `cd app && npx jest && npx tsc --noEmit` 모두 통과(화면은 Task 12가 잇는다).

- [ ] **Step 5: 커밋한다** — `feat(app): add the post-talk review screen with one fix at a time`

### Task 12: 첫 화면 카드와 대화 화면

**Files:**
- Create: `app/src/screens/TalkScreen.tsx`
- Modify: `app/src/screens/HomeScreen.tsx`, `app/App.tsx`, `app/src/flow/state.ts`, `app/src/flow/state.test.ts`

**Interfaces:**
- Consumes: `talkReduce`과 판단 함수(Task 9), `useMic`, `TalkFixScreen`(Task 11), `api.createTalk`, `api.talkTurn`, `api.endTalk`, `Waiting`, `useInterpret`, `KoButton`, `KoLine`, `ThreeLineView`, `InRowButton`, `PlayLabel`, `Named`, `StopButton`, `SoonEnds`, `BackButton`, `useBackKey`, `usePlayingTag`, `tapPlay`.
- Produces:
  - `TalkScreen({ sounds, onHome }: { sounds: SoundQueue; onHome: () => void })`.
  - `state.ts`: `Screen`에 `"talk"`, 동작 `{ type: "openTalk" }`(첫 화면에서만, `{ ...initial, screen: "talk" }`). `back`은 `talk`에서 첫 화면.
  - `HomeScreen`의 새 prop `onTalk: () => void`.

- [ ] **Step 1: 실패하는 시험을 쓴다** — `state.test.ts`: `openTalk opens the free talk from home`, `openTalk elsewhere does nothing`, `back from the free talk goes home`.

- [ ] **Step 2: 실패를 본다** — `cd app && npx jest src/flow/state.test.ts`

- [ ] **Step 3: `state.ts`, `HomeScreen`, `App.tsx`를 고친다**
  - `HomeScreen`: 두 카드 사이에 `ChoiceCard icon="🗣️" title="자유 대화" line="대본 없이 라이언과 영어로 이야기해요" color={colors.free} onPress={() => leaveHome(sounds, onTalk)}`와 `gap`. 주석의 「new or again: … two」를 셋으로 고친다(스펙 1: 새로 하기 둘과 다시 하기 하나).
  - `App.tsx`: `state.screen === "talk"`이면 `<TalkScreen sounds={sounds} onHome={() => dispatch({ type: "home" })} />`.

- [ ] **Step 4: `TalkScreen`을 쓴다**
  - 처음: 게이트 안에서 `api.createTalk()` → `opened`, 실패 → `openFailed`(`messageOf`). 첫 줄의 `lineSounds`를 차례로 넣는다.
  - 소리 꼬리표: 대화 소리는 `talk:<key>`. `sounds.subscribeTag`로 `talk:`로 시작하는 꼬리표가 시작되면 그 키를 `started` ref에 넣는다(끊을 때 `heardCount`).
  - `turnRef`: `recordStart`를 보낼 때 같이 1 늘린다. 보내는 녹음은 그 번호를 달고, `onEvent`는 `mounted`이고 그 번호가 `turnRef.current`일 때만 소리를 넣고 `dispatch({ type: "event", turn, e })`. `audio`는 `talk:<key>`로 넣는다. `error`의 `say.audio`도 넣는다.
  - `ryan`이고 `done`이면 `sounds.onIdle(() => dispatch({ type: "ryanDone" }))`.
  - 「🎤 말하기」: `useMic.start`. `canStart`는 `now` ref의 `canSpeak`. `beforeStart`에서 `heard = phase === "ryan" ? heardCount(마지막 라이언 parts, started) : null`, `sounds.clear()`, `turnRef` +1, `dispatch({ type: "recordStart", heard })`. 보낼 때 `api.talkTurn(rp.id, uri, cutOf(그때의 상태), onEvent)`, 실패는 `failed`.
  - 「대화 끝내기」: 따로 게이트. `canEnd(now.current)`가 아니면 아무것도 하지 않는다. `englishTurns === 0`이면 `sounds.clear()` 뒤 `onHome()`. 아니면 `heard`를 위처럼 구해 `sounds.clear()`, `endStart`, `api.endTalk(rp.id, heard)` → `ended` / `endFailed`.
  - 뒤로(화면 버튼과 폰 키): `mounted = false`, `sounds.clear()`, `await mic.leave()`, `onHome()`. 묻지 않고 고쳐 주기도 없다(스펙 2).
  - 말풍선: 라이언은 왼쪽 회색, 나는 오른쪽 파랑(`RoleplayScreen`과 같은 모양 값을 이 파일에 둔다). 라이언 말풍선은 `parts`를 이어 그리고 `heard`가 있으면 그 뒤 문장을 `colors.weak`로. 지나간 말풍선은 눌러야 「🔊 듣기」(`lineSounds`를 `bubble:<idx>` 꼬리표로), 「통역」(`useInterpret(rp?.id ?? "", …)`), 「읽는 법 보기」(`api.getThree`)가 펼쳐지고, 지금 말하는 말풍선은 펼친 채다. 버튼은 `mayListenTalk`가 아니면 흐리다. 내 말풍선은 들린 말, 펼치면 「🔊 내 녹음」. `help` 말풍선은 노란 평가 상자, 누르면 그 소리를 다시. `pending`이 있으면 쓰고 있는 라이언 말풍선(버튼 없음).
  - 기다림: `waiting`이고 `pending`이 빈 동안 `Waiting who="ryan" text="라이언이 듣고 있어요"`, `ending` 동안 `Waiting who="ryan" text="라이언이 대화를 돌아보고 있어요"`.
  - 맨 아래: `recording`이면 「취소」(덜 주된)와 `StopButton`, `SoonEnds`. 아니면 「대화 끝내기」(덜 주된, `canEnd`가 아니면 꺼짐)와 「🎤 말하기」(주된, `grow`, `canSpeak`가 아니면 꺼짐). 첫 내 차례(`!micUsed`이고 `canSpeak`)에 「🎤를 누르고 말하세요」. `message`는 그 위에.
  - `fixes`면 `<TalkFixScreen rp={roleplay} end={end} sounds={sounds} onHome={onHome} />`, `error`면 `ErrorText`와 「다시 시도」(`retry`).
  - 화면의 한국어는 `keepWords`.

- [ ] **Step 5: 확인한다** — `cd app && npx jest && npx tsc --noEmit` 모두 통과.

- [ ] **Step 6: 커밋한다** — `feat(app): add the free talk card and conversation screen`

### Task 13: 모아 둔 고친 문장 연습

**Files:**
- Modify: `app/src/screens/RoleplayScreen.tsx`(두 군데)

**Interfaces:**
- Consumes: `savedBefore`, `replaysSituation`, `lineSounds`(Task 9, 10).

- [ ] **Step 1: 고친다**
  - `const savedBefore = fromSaved && line ? rp.lines[line.idx - 1] : undefined` → `savedBefore(rp, line)`(이름이 겹치면 가져올 때 `beforeOfSaved`로 바꿔 부른다).
  - 「앞 대화 보기」의 말풍선 소리: `playBefore`가 소리 목록을 받게 해 `lineSounds(savedBefore)`를 차례로 넣는다(첫 것에 꼬리표). 자유 대화의 라이언 말은 `audio`가 없고 `parts`에 있다.
  - 「이 상황 다시 하기 ›」: `fromSaved && replaysSituation(rp)`일 때만.
- [ ] **Step 2: 확인한다** — `cd app && npx jest && npx tsc --noEmit`
- [ ] **Step 3: 커밋한다** — `feat(app): practise a saved free-talk fix after Ryan's line before it`

### Task 14: 실제 모델 확인

**Files:**
- Create: `server/scripts/compare_fix_models.py`, `server/tests/test_compare_fix_models.py`

**Interfaces:**
- Consumes: `Claude.fixes`, `fixes.check`, `WRITERS`.
- Produces: `compare_fix_models.py`의 `CASES: list[Case]`(`Case(name, conversation: list[tuple[str, str]], keep_off: set[int])` — `keep_off`는 고치면 안 되는 차례 번호), `flags(raw: list[dict], checked: list[Found], case: Case) -> list[str]`(「셋 넘음」, 「고치면 안 될 차례」, 「거른 것 n」), `main()`(`--runs 3`, `--only N`).

- [ ] **Step 1: `flags` 시험을 쓴다** — `test_flags_count_rule_breaks`: 넷 고름 → 「4 items」, `keep_off` 차례를 고름 → 「keep-off turn 3」, 걸러진 것 → 「dropped 1」, 문제없음 → 빈 목록. 실패를 보고, 쓰고, 통과를 본다(`uv run pytest -q tests/test_compare_fix_models.py`).
- [ ] **Step 2: 지어낸 대화를 쓴다.** 경우마다 하나: 맞는 영어만(모두 `keep_off`), 문법 실수 둘, 받아쓰기가 잘못 적은 낱말(right/light, 짐작이 남아야 한다), 받아쓰기가 여러 소리를 바꿔 적은 말(rest around, 짐작이 버려져야 한다), 어떻게 말하는지 묻는 차례(`keep_off`), 라이언이 못 알아들은 차례(`keep_off`), 흔한 짧은 대답(「Good.」, `keep_off`). 한국어 차례는 서버가 보내지 않으므로 넣지 않는다. 머리 주석에 돈(Sonnet 한 번 0.5센트쯤)과 「모두 지어낸 것이라 찍어도 된다」.
- [ ] **Step 3: 대화 상대를 다시 견준다** — `cd server && uv run python scripts/compare_talk_models.py --runs 3`. 규칙에 걸린 답 수를 스펙 「잰 것」(Sonnet 30번 중 2번)과 견주고, 「how do you say」 경우의 답이 짧은 영어 문장 하나를 주고 이어 가는지 읽는다. 걸린 답이 크게 늘면 `TALK_SYSTEM`을 고치고 다시(고친 것은 `fix(server): …` 커밋).
- [ ] **Step 4: 고쳐 주기를 견준다** — `uv run python scripts/compare_fix_models.py --runs 3`. 두 모델의 걸린 수, 틀린 고쳐 주기(맞는 영어를 고침, 받아쓰기 잘못을 문법으로 짚음)를 직접 읽어 센다. 결과(숫자와 추천 하나)를 main 세션에 보낸다(`CLAUDE.md` 「카드와 main 세션 사이의 메시지」). 사용자가 Haiku를 고르면 그때 설정을 더한다. 기본은 글쓰기 모델 그대로.
- [ ] **Step 5: 커밋한다** — `chore(server): compare Sonnet and Haiku for post-talk fixes on made-up talks`(스크립트와 시험. 본문에 견준 숫자와 든 돈, 대화 상대 견주기 결과)

### Task 15: 학습자 목소리 녹음으로 시험 서버 재기

**Files:**
- Create: `server/scripts/try_talk.py`, `server/tests/test_try_talk.py`

**Interfaces:**
- Produces: `try_talk.py`의 `summarize(events: list[tuple[float, dict]]) -> dict`(받은 때와 이벤트에서 `heard_s`, `first_text_s`, `first_audio_s`, `done_s`, `korean`, `reply_words`), `main()`(`--port`, 녹음 여럿, `--heard N`(둘째 차례부터 앞 답에서 들은 문장 수), `--end`). 토큰과 주소는 `try_recordings.py`처럼 `server/.env`에서 읽고 찍지 않는다. 찍는 것은 시간, 낱말 수, 한국어 여부, 그리고 고쳐 주기의 가지 수와 소리 짐작 여부. 받아쓴 글과 라이언의 답은 `--show`일 때만 터미널에 찍는다(파일에 남기지 않는다).

- [ ] **Step 1: `summarize` 시험을 쓴다** — `test_summarize_times_each_stage`(지어낸 이벤트와 시각 → 각 값), `test_summarize_a_korean_turn`. 실패, 구현, 통과.
- [ ] **Step 2: 녹음을 만든다.** 비공개 메모(`docs/private/mac-env.md` 「학습자 목소리로 시험 녹음 만들기」)대로 학습자 목소리로, 저장소 밖 scratchpad에. 지어낸 문장: 짧은 영어(2초쯤), 긴 영어(7초쯤), 문법 실수가 든 영어, R/L 낱말이 든 영어, 한국어 문장 하나, 「~을 영어로 어떻게 말해요?」 꼴의 한국어 하나.
- [ ] **Step 3: 시험 서버를 띄운다.** `DEVENV_맥서버_저절로_띄우기_20261107.md` 「launchd 서버를 멈추지 않고 시험하기」대로. `lsof -nP -iTCP -sTCP:LISTEN`으로 8791, 8792가 빈지 보고, 기록은 `rsync -a --exclude 'rec/'`로 `roleplays`, `audio`, `saved.json`만 scratchpad에 복사, `JE_HOST=127.0.0.1 JE_PORT=8791 JE_WHISPER_PORT=8792 JE_DATA_DIR=<복사본> uv run python -m je_server`. 로그에 `ready`.
- [ ] **Step 4: 잰다** — `uv run python scripts/try_talk.py --port 8791 <녹음들> --end`를 세 번.
  - 영어 차례의 맥 안 첫 소리(`first_audio`, 서버가 저장한 값)의 가운데 값이 3초 안쪽인지(스펙 「실패로 볼 것」 맥 안 3초, 어림 3.1초).
  - 한국어 녹음: 한글이 섞이면 `korean` true이고 첫 소리가 `talk_english` 소리. 영어로 번역되어 나오면 영어 차례로 가고 라이언이 짧은 영어 문장을 알려 주는지(`--show`로 터미널에서만 본다).
  - 끊기: 세 문장 답 뒤 `--heard 1`로 다음 차례 → 새 답의 `first_audio`가 끊지 않은 때와 비슷한지(남은 소리가 앞에 끼지 않는지), 끝난 뒤 앞 답의 남은 문장 소리 파일이 복사본 `audio/`에 생겼는지.
  - 끝내기: 가지가 셋 이하, R/L 녹음이면 소리 짐작이 남는지, 첫 가지의 소리가 먼저인지(서버 로그 시간).
  - 숫자만 PR과 가이드(Task 17)에 적는다.
- [ ] **Step 5: 폰 구간.** `adb devices`에 폰이 있으면 `DEVENV_폰을_adb로_시험하기_20261108.md`대로 시험 서버 앱을 깔고, 맥에서 튼 학습자 목소리를 폰 마이크로 넣어 「말하기 끝」부터 라이언 첫 소리까지를 화면 녹화 프레임으로 잰다. 폰이 없으면 main 세션에 「폰을 꽂아 달라」고 이유와 함께 한 번 부탁하고, 끝내 못 하면 PR `## 한계`에 적는다.
- [ ] **Step 6: 끝낸다** — 시험 서버를 끄고 두 포트가 빈지 보고, 복사본과 녹음 파일을 지운다.
- [ ] **Step 7: 커밋한다** — `chore(server): add a script that times free-talk turns on a side server`(본문에 잰 가운데 값)

### Task 16: 에뮬레이터 화면

- [ ] **Step 1: 띄운다.** `DEVENV_폰을_adb로_시험하기_20261108.md`대로 AVD `jake-english`만(다른 AVD는 건드리지 않는다). 앱은 Task 15처럼 띄운 시험 서버(복사본)에 붙인다. 누르기 전에 앞에 뜬 앱이 이 앱인지 본다. 스크린샷은 저장소 밖.
- [ ] **Step 2: 첫 화면** — 360dp 폭과 실제 폰 높이에서 카드 셋과 라이언 그림, 「복습하기」가 잘리지 않는지. 잘리면 첫 화면의 그림을 줄이고(`HomeScreen`의 그림 자리) 다시 본 뒤 `fix(app): shrink Ryan's picture so three cards fit on the first screen`.
- [ ] **Step 3: 대화** — 「자유 대화」를 누르면 바로 라이언 질문과 소리, 「🎤를 누르고 말하세요」, 녹음(`hostmicon`으로 맥 소리를 넣을 수 있으면 학습자 목소리 녹음을, 아니면 Task 15의 서버 시험으로 갈음), 들린 말 말풍선, 생각하는 얼굴, 라이언 답 글과 소리, 「3번째」 같은 차례 수.
- [ ] **Step 4: 끊기와 버튼** — 라이언이 말하는 중 「🎤 말하기」 → 소리가 바로 멈추고 뒤 문장이 흐려진다, 생각하는 동안 「🎤 말하기」와 「대화 끝내기」가 꺼짐, 「🎤 말하기」와 「대화 끝내기」를 빠르게 두 번(시험 서버 로그에 요청 하나).
- [ ] **Step 5: 끝내기와 돌아보기** — 영어 차례 없이 「대화 끝내기」 → 첫 화면. 영어 차례 뒤 → 생각하는 얼굴 → 「대화 돌아보기」 「1/N」, 설명 소리, 「🔊 내 녹음 들어 보기」, 「🔊 듣기」, 「읽는 법 보기」, 「☆ 모아 두기」, 「🎤 따라 말하기」와 평가, 「다음 ›」, 마지막 「끝」 → 첫 화면.
- [ ] **Step 6: 모아 둔 문장** — 「복습하기」 → 「모아 둔 문장」에 「자유 대화」 제목의 고친 문장, 연습 화면 「앞 대화 보기」가 라이언 말이고 소리가 나는지, 「이 상황 다시 하기」가 없는지. 「지난 상황」에 자유 대화가 없고, 하던 역할극이 이어 하기 줄에 남는지.
- [ ] **Step 7: 뒤로** — 라이언 답을 기다리는 중과 녹음 중에 「뒤로」 → 묻지 않고 첫 화면, 소리 없음, 늦은 답이 첫 화면에서 들리지 않음.
- [ ] **Step 8: 정리** — 시험 서버와 에뮬레이터를 끄고 복사본, 스크린샷, 녹음을 지운다. 본 것을 PR 「테스트 체크리스트」에 `[x]`로 적는다.

### Task 17: 문서

**Files:**
- Modify: `docs/PRD.md`, `docs/guide/README.md`
- Create: `docs/guide/SPEECH_자유대화_기다림과_한국어_가르기_20261108.md`

- [ ] **Step 1: PRD** — 머리말 「고침」에 이 날의 줄. 「첫 화면」의 「첫 화면의 선택지는 「대화 연습하기」와 「복습하기」다 … 「자유 대화」를 어디에 둘지는 그 스펙에서 정한다」를 카드 셋(대화 연습하기, 자유 대화, 복습하기, 새로 하기 둘과 다시 하기 하나)으로 고치고 스펙 경로를 적는다. 「고쳐 주기」에 모양(많아야 셋, 한 화면에 하나, 라이언 한국어 설명, 눌러야 들리는 내 녹음, 고친 문장의 세 줄·본보기·☆·따라 말하기, 발음 짐작은 소리 설명 목록에 있을 때만)을 한두 문장으로.
- [ ] **Step 2: 가이드** — 기준: 「말하기」는 영어로만 받아쓰고 한글이 섞이면 한국어로 다시(자동 언어가 영어 26%를 한국어로 알아들은 것), 첫 문장부터 말하기와 첫 문장을 짧은 맞장구로, 끊은 답의 남은 소리를 미루기(목소리 작업 프로세스가 하나), 첫 질문 소리를 미리, 대화 상대 모델 견주기. 겪은 문제: Task 14~16에서 만난 것(증상, 원인, 고친 것, 막는 법). 확인 방법: `try_talk.py`, `compare_talk_models.py`, `compare_fix_models.py` 명령. 숫자만, 받아쓰기와 답은 쓰지 않는다. `README.md`에 색인 한 줄.
- [ ] **Step 3: 커밋한다** — `docs(prd): place free talk on the first screen and shape the post-talk fixes`, 이어 `docs(guide): add the free-talk waiting time and Korean detection guide`(커밋 둘)

devlog는 PR 리뷰로 고친 뒤 머지 결정을 묻기 전에 카드가 따로 쓴다(`AGENTS.md` 「작업 일지: devlog」). 할 일 `20261105_09_todo_speaking_practice_next.md`의 상태 줄은 PR 3까지 끝나야 완료로 고치므로 이 PR에서는 건드리지 않는다.
