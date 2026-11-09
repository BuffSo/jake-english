# 자유 대화 「다시 말하기」 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 자유 대화에서 내 마지막 말풍선 아래 「↻ 다시 말하기」를 누르면, 라이언 소리와 만들던 답이 바로 멈추고, 그 차례가 지워지고, 곧바로 다시 녹음한다.

**Architecture:** 맥 서버(`server/je_server`)는 지운 차례를 기록에서 빼지 않고 줄에 `dropped` 표시를 해 줄 번호를 다시 쓰지 않는다. 대화를 읽는 곳(라이언에게 가는 대화, 고쳐 주기, 소희 찬스, 앞 대사)은 표시된 줄을 건너뛴다. 새 경로 `POST /talks/{id}/lines/{idx}/drop`이 표시를 하고, 그 차례가 아직 돌고 있으면 멈춤 신호로 Claude 흐름을 끊는다. 앱(`app/src`)은 리듀서에 `redo`를 더하고, 녹음 시작 직전에 지우기를 보내며, 다음 차례와 「대화 끝내기」 전에 지우기가 끝났는지 확인한다.

**Tech Stack:** Python 3.12, FastAPI, pydantic, pytest(`uv run pytest`) / Expo React Native, TypeScript, jest(`npx jest`).

**Spec:** `docs/superpowers/specs/2026-11-09-talk-resay-design.md`. 화면 초안은 비공개(scratchpad)라, 스펙 1, 2의 글이 화면의 기준이다. 자유 대화 스펙 `docs/superpowers/specs/2026-11-08-free-talk-design.md` 2, 9도 함께 읽는다.

## Global Constraints

- 공개 저장소(`AGENTS.md`, `REVIEW.md`): 시험 문장은 지어낸다. 녹음, 받아쓴 글, 사용자 기록의 문장, 개인 경로를 커밋하지 않는다.
- 녹음은 맥 밖으로 나가지 않는다. Claude에는 글만 보낸다(ADR-0004). 로그에는 시간과 개수만 남긴다(받은 말이나 줄 글을 쓰지 않는다).
- 지운 줄은 기록에 남기고 `idx`와 자리를 바꾸지 않는다. `rp.lines[i].idx == i`가 늘 맞아야 한다.
- 지운 줄의 JSON에만 `"dropped": true`가 있다. 지우지 않은 줄의 JSON 키는 지금과 같다(계약 파일 `contract/*.json`을 바꾸지 않는다, `given`과 같은 방법).
- 버튼: 「↻ 다시 말하기」는 `Button`의 `small`, `kind="secondary"`, 내 말풍선 바로 아래 오른쪽. 서버에 요청을 보내는 버튼은 빠르게 두 번 눌러도 요청이 한 번(`REVIEW.md` 「앱 화면」).
- 모든 서버 경로는 토큰 뒤에 있고, 경로의 id와 번호는 검사한다(`ID`, `PathParam(ge=0)`).
- 커밋: Conventional Commits 영어, 제목 72자 안쪽, AI 서명 없음. `git`은 `/usr/bin/git`으로 부르고, 커밋을 이을 때는 `&&`로 잇는다. 파일은 이름을 지정해 `git add`한다. 커밋은 `git commit -F - <<'EOF'`로 한다.
- 시험: 서버 `cd server && uv run pytest -q`, 앱 `cd app && npx jest && npx tsc --noEmit`.

## Review Focus

1. 라이언의 답 글이 절반쯤 왔을 때 지운다: Claude 흐름이 끊기고 라이언 줄은 저장되지 않으며, 다음 차례의 대화에 지운 말이 없다(작업 2 `test_drop_while_claude_writes_stops_it_and_keeps_no_reply`).
2. 지우기와 라이언 줄 저장이 거의 같이 일어난다: 어느 쪽이 먼저든 줄 번호가 자리와 맞고, 라이언 줄이 남으면 지운 표시가 있다(작업 2 `test_drop_and_reply_save_in_either_order_keep_line_numbers`).
3. 지운 차례의 흐름이 새 차례가 시작된 뒤에 끝난다: 옛 차례가 새 차례의 「바쁨」을 풀지 않는다(작업 2 `test_a_dropped_turn_ending_late_does_not_free_the_next`).
4. 지우기 요청이 맥에 닿지 않은 채 다시 녹음해 보낸다: 지우기가 성공하기 전에는 차례를 보내지 않는다(작업 4 `settle retries a failed drop before the next turn` 외).
5. 「↻ 다시 말하기」를 빠르게 두 번 누른다: 지우기 한 번, 녹음 한 번(작업 4 리듀서 `a second redo does nothing`, 작업 5 `canStart`).

---

### Task 1: 서버가 지운 줄을 건너뛴다

**Files:**
- Modify: `server/je_server/models.py`(`ScriptLine`), `server/je_server/talk.py`(`messages`, `fix_input`, `_from_full`, `_mark_heard`, `_end`, `_end_body`), `server/je_server/hints.py`(`conversation`), `server/je_server/fixes.py`(`line_before`), `server/je_server/engine.py`(`context`, 대화 뒤 연습의 `went` 거르기)
- Test: `server/tests/test_talk.py`, `server/tests/test_hints.py`, `server/tests/test_fixes.py`, `server/tests/test_contract.py`, `server/tests/test_aside.py` 또는 `test_engine.py`(앞뒤 말이 있는 쪽)

**Interfaces:**
- Produces: `ScriptLine.dropped: bool = False`(JSON에는 참일 때만). `talk.live(rp: Roleplay) -> list[ScriptLine]`(지우지 않은 줄, 차례대로). `talk.last_live(rp: Roleplay) -> ScriptLine | None`.

- [ ] **Step 1: 실패하는 시험을 쓴다.** 지어낸 대화에 지운 줄을 넣는 도우미(`_talk`에 지운 줄을 표시하는 인자나 `model_copy(update={"dropped": True})`)를 쓴다. 시험 이름과 확인할 것:
  - `test_a_lines_dropped_is_in_its_json_only_when_set`(test_contract): 기본 줄의 JSON에 `dropped`가 없고, 참이면 `True`.
  - `test_messages_leave_dropped_lines_out`: R0, 지운 T1, 지운 R2, T3 → `messages`가 `[TALK_START, R0, T3]`.
  - `test_dropped_turns_do_not_count_for_the_echo`: 영어 차례 셋 중 하나를 지우면 마지막 메시지에 `TALK_ECHO`가 없고, 지운 것 빼고 셋이면 있다.
  - `test_fix_input_leaves_dropped_lines_out`: 대화와 `turns`에 지운 줄이 없다.
  - `test_hint_conversation_leaves_dropped_lines_out`(test_hints).
  - `test_a_dropped_helped_turn_lets_the_next_turn_be_helped`: 전체 문장을 본 R의 다음 차례가 그 문장으로 말한 차례(`given`)인데 지워졌으면, 다음 차례도 `_from_full`이 그 문장과 견준다. 그리고 가장 최근 라이언 답을 찾을 때 지운 라이언 답을 건너뛴다.
  - `test_cut_mark_goes_on_the_last_live_reply`: 마지막 줄들이 지운 차례면 `_mark_heard`가 그 앞의 라이언 답에 `heard_upto`를 단다(`turn`의 `heard`와 `end`의 `heard` 둘 다).
  - `test_end_counts_no_sohee_chance_on_a_dropped_reply`: 지운 라이언 답의 `hint`는 `sohee`에 세지 않는다.
  - `test_line_before_skips_dropped_lines`(test_fixes): 고친 줄의 `fix.of` 바로 앞이 지운 라이언 답이면 그 앞의 살아 있는 라이언 답을 준다.
  - `test_context_skips_dropped_lines`: 라이언 답의 세 줄 표시에 보내는 앞뒤 말이 지운 줄을 건너뛴 가장 가까운 줄이다.
  - `test_practice_after_the_talk_leaves_dropped_lines_out`: 대화 뒤 고친 문장을 연습할 때 선생님 라이언에게 가는 대화(`went`)에 지운 줄이 없다.
- [ ] **Step 2: 돌려 실패를 본다.** `cd server && uv run pytest -q tests/test_talk.py tests/test_hints.py tests/test_fixes.py tests/test_contract.py -k "dropped or echo or live or skips"` → 새 시험이 FAIL.
- [ ] **Step 3: 구현한다.** `ScriptLine`에 `dropped: bool = False`를 더하고 기존 `_leave_out_no_given` 직렬화에서 거짓이면 뺀다(주석에 스펙 경로). `live`, `last_live`를 `talk.py`에 두고 위 함수들이 쓴다. `fixes.line_before`와 `engine.context`, `engine`의 `went` 거르기는 `talk`를 부르지 않고 `l.dropped`를 직접 본다(순환 import를 피한다). 위로 걸어가는 곳은 지운 줄을 건너뛰며 걷는다.
- [ ] **Step 4: 돌려 통과를 본다.** `cd server && uv run pytest -q` → 모두 PASS.
- [ ] **Step 5: 커밋한다.** `feat(server): skip dropped free-talk lines when reading the talk`

### Task 2: 지우기 경로와 돌고 있는 차례 멈추기

**Files:**
- Modify: `server/je_server/talk.py`(`Talks.__init__`, `_turn`, 새 `drop`, 새 `_until`), `server/je_server/app.py`(새 경로)
- Test: `server/tests/test_talk.py`, `server/tests/test_api.py`

**Interfaces:**
- Consumes: 작업 1의 `ScriptLine.dropped`, `live`, `last_live`.
- Produces: `class CannotDrop(Exception)`(속성 `code: str`, `"not_last"` 또는 `"hinted"`). `async def Talks.drop(self, rp_id: str, idx: int) -> None`. 경로 `POST /talks/{rp_id}/lines/{idx}/drop` → 200 `{"dropped": idx}`; 404 `not_found`, 409 `ended`, `busy`, `not_last`, `hinted`.

`drop`이 정하는 것(스펙 3, 4):
- 엔진 잠금 안에서 기록을 다시 읽고 검사한 뒤 `lines[idx:]`의 지우지 않은 줄에 모두 표시하고 저장한다. 이미 지운 줄이면 아무것도 하지 않고 성공.
- 404(`NotFound`): 자유 대화가 아님, `idx`가 범위 밖, 그 줄이 내 차례(`speaker == "user"`, `kind`가 `turn`이나 `ask`)가 아님.
- `TalkEnded`: 고친 줄이 있다. `TalkBusy`: 끝내는 중(`self._ending`).
- `CannotDrop("not_last")`: `idx` 뒤의 살아 있는 줄이 「없음」이나 「라이언 답 하나」가 아니다. `CannotDrop("hinted")`: 뒤의 라이언 답에 `hint`가 있거나 `self.hinting`에 그 줄의 끝나지 않은 작업이 있다.
- 그 차례가 돌고 있으면(`self.running[rp_id]`의 `idx`가 같으면) 멈춤 신호를 켜고 그 차례의 「바쁨」을 바로 푼다. 저장된 라이언 답이 있으면 그 문장 소리를 `voice.demote`한다.
- 로그: `talk drop %s/%d running=%s` 같은 것만(시간, 개수, 참거짓).

`_turn`이 바뀌는 것:
- 내 줄을 저장한 뒤 이 차례의 기록(`idx`, `stop: asyncio.Event`, 이 차례의 `release`)을 `self.running[rp_id]`에 둔다. `finally`에서 그 기록이 아직 이 차례의 것일 때만 지운다.
- `engine.speak(...)`을 `_until(stop, ...)`으로 감싼다. `_until(stop: asyncio.Event, events: AsyncIterator[dict]) -> AsyncIterator[dict]`: 다음 이벤트와 멈춤 신호 중 먼저 오는 것을 기다리고, 신호가 먼저면 기다리던 다음 이벤트 작업을 취소하고 끝낸다(그러면 `speak`의 `finally`가 Claude 글 읽기와 소리 만들기를 멈춘다).
- `speak`에 넘기는 `said` 목록을 이름 붙여 두고, 멈췄으면 `sentences.split("".join(said))`의 키를 `voice.demote`하고, `done`을 보내지 않는다.
- 라이언 줄 저장(`saved`)은 잠금 안에서 내 줄이 지워졌으면 저장하지 않고 이벤트도 내지 않는다(`None`을 돌려준다). 저장했으면 지금처럼.
- `release`는 한 번만 「바쁨」을 푼다. 지우기가 먼저 풀었으면 옛 차례의 `finally`는 새 차례의 「바쁨」을 건드리지 않는다.

- [ ] **Step 1: 실패하는 시험을 쓴다.** `fake_claude.talk_gate`, `until`, `run`을 쓴다.
  - `test_drop_marks_my_turn_and_ryans_reply`: 차례 하나 뒤 `drop(rp, 1)` → 줄 1, 2가 `dropped`, 줄 0은 아님. 다시 부르면 그대로 성공.
  - `test_drop_refuses_what_is_not_my_last_turn`: 역할극 → `NotFound`; 범위 밖 번호, 라이언 줄(0, 2) → `NotFound`; 차례 둘 뒤 첫 차례(1) → `CannotDrop` `not_last`.
  - `test_drop_refuses_after_sohee_chance_on_the_reply`: 줄 2에 `hint` → `hinted`; `fake_claude.hint_gate`로 힌트를 만드는 중에도 `hinted`. 앞 라이언 말(줄 0)의 힌트는 상관없다.
  - `test_drop_refuses_an_ended_or_ending_talk`: 끝낸 뒤 `TalkEnded`; `fix_gate`로 끝내는 중 `TalkBusy`.
  - `test_drop_while_claude_writes_stops_it_and_keeps_no_reply`: `talk_gate`로 첫 글 앞에서 멈춘 차례에서 `heard`를 받은 뒤 `drop` → 흐름이 곧 끝나고(`done`, `reply` 없음), 기록은 줄 0, 1(지움)뿐, `talks.turning`과 `talks.running`이 빈다. Claude의 `talk` 흐름이 닫혔는지는 가짜 Claude에 닫힘 표시(`talk_closed` 같은 것)를 더해 본다.
  - `test_drop_after_the_reply_is_saved_demotes_its_sounds`: `reply` 이벤트 뒤(소리가 아직 오는 중) `drop` → 아직 안 만든 문장 키가 `fake_voice`의 미룸 목록에 있고 흐름은 `done` 없이 끝난다.
  - `test_drop_and_reply_save_in_either_order_keep_line_numbers`: 지우기가 먼저일 때(라이언 줄 없음)와 저장이 먼저일 때(라이언 줄이 `dropped`) 모두 `[l.idx for l in lines] == list(range(len(lines)))`.
  - `test_a_turn_right_after_a_drop_is_taken`: 돌고 있는 차례를 지운 뒤 곧바로 새 차례 → 새 줄 번호가 3(지운 1, 2를 다시 쓰지 않음), 새 답의 대화에 지운 말이 없다(`fake_claude.talk_calls[-1]`).
  - `test_a_dropped_turn_ending_late_does_not_free_the_next`: 지운 차례가 아직 끝나지 않은 채 새 차례가 시작되고, 옛 차례가 끝난 뒤에도 `check_open`이 `TalkBusy`.
  - `test_drop_log_has_counts_only`: 로그에 들린 말이 없다.
  - 경로(test_api): 토큰 없는 요청 막기 목록에 새 경로를 더하고, `test_drop_route_answers_and_refuses`: 200 `{"dropped": 1}`, 없는 대화 404, 역할극 404, 라이언 줄 404, 끝낸 대화 409 `ended`, 뒤에 내 차례 409 `not_last`.
- [ ] **Step 2: 돌려 실패를 본다.** `cd server && uv run pytest -q tests/test_talk.py tests/test_api.py -k drop` → FAIL.
- [ ] **Step 3: 구현한다.** 위 「`drop`이 정하는 것」과 「`_turn`이 바뀌는 것」대로. 경로는 `talk_turn` 옆에 두고, 맨 위 주석 블록과 `talk.py` 모듈 설명에 스펙 경로를 한 줄 더한다.
- [ ] **Step 4: 돌려 통과를 본다.** `cd server && uv run pytest -q` → 모두 PASS.
- [ ] **Step 5: 커밋한다.** `feat(server): drop a free-talk turn and stop the reply being made`

### Task 3: 녹음 시험 스크립트로 지우고 다시 말하기 재기

**Files:**
- Modify: `server/scripts/try_talk.py`
- Test: `server/tests/test_try_talk.py`

**Interfaces:**
- Consumes: 작업 2의 경로.
- Produces: `try_talk.py --drop`: 첫 녹음의 `heard` 이벤트가 오자마자 그 차례를 지우고(`drop_path(rp_id, idx) -> str`), 흐름이 끝나기까지의 초를 찍은 뒤, 나머지 녹음을 다시 말한 차례로 보낸다. `send_turn`에 이벤트마다 부르는 `on_event`를 더한다.

- [ ] **Step 1: 실패하는 시험을 쓴다.** `test_drop_path_is_the_turns_line`: `drop_path("abc123def456", 3) == "/talks/abc123def456/lines/3/drop"`.
- [ ] **Step 2: 돌려 실패를 본다.** `cd server && uv run pytest -q tests/test_try_talk.py` → FAIL.
- [ ] **Step 3: 구현한다.** 모듈 설명과 사용법에 `--drop`을 적는다. 받은 말과 라이언 글은 지금처럼 `--show`일 때 터미널에만.
- [ ] **Step 4: 돌려 통과를 본다.** 같은 명령 → PASS.
- [ ] **Step 5: 커밋한다.** `test(server): drop the first turn in try_talk to time saying it again`

### Task 4: 앱 흐름(리듀서, 지우기 보내기, 앞 대사)

**Files:**
- Modify: `app/src/api/types.ts`(`ScriptLine.dropped?: boolean`), `app/src/api/client.ts`(`dropTurn`), `app/src/flow/talk.ts`(`redoTarget`, `redo` 액션, `savedBefore`)
- Create: `app/src/flow/talkDrop.ts`, `app/src/flow/talkDrop.test.ts`
- Test: `app/src/flow/talk.test.ts`

**Interfaces:**
- Consumes: 작업 2의 경로와 응답 `{ dropped: number }`.
- Produces:
  - `api.dropTurn(id: string, idx: number): Promise<{ dropped: number }>`(POST, 기본 시간 제한).
  - `redoTarget(s: TalkState, asked: (idx: number) => boolean): number | null`: 「↻ 다시 말하기」를 붙일 내 말풍선의 `idx`. 단계가 `waiting`, `replying`(둘 다 `heardIn`일 때), `ryan`, `ready`이고, 마지막 `me` 말풍선 뒤에 없거나 라이언 말풍선 하나만 있고, 그 라이언 말풍선의 `idx`에 `asked`가 거짓일 때. 아니면 `null`.
  - `TalkAction`에 `{ type: "redo"; idx: number }`: `redoTarget(s, () => false) === a.idx`일 때만, 그 `me` 말풍선부터 뒤를 지우고 `phase: "recording"`, `turn + 1`, `pending: ""`, `heardIn: false`, `micUsed: true`, `message: null`, `failure: false`. 아니면 그대로.
  - `createDropper(drop: (idx: number) => Promise<unknown>): { drop(idx: number): void; settle(): Promise<void> }`(`talkDrop.ts`): `drop`은 바로 요청을 보내고 남겨 둔다. `settle`은 남은 지우기가 있으면 그것을 기다리고, 실패했으면 한 번 더 보내고, 그래도 실패하면 그 오류를 던진다(남은 지우기는 그대로라 다음 `settle`이 또 보낸다). 성공하면 남은 것을 비운다.
  - `savedBefore`는 지운 줄을 건너뛴다.

- [ ] **Step 1: 실패하는 시험을 쓴다.**
  - talk.test.ts: `redo target is my last turn from the moment it is heard`(heard 뒤 waiting, replying, ryan, done 뒤 ready에서 `1`), `no redo target before my words, while recording, at the end or with Ryan's opener only`, `no redo target once Sohee chance is asked on Ryan's reply after it`(`asked = (i) => i === 2`면 `null`, `asked = (i) => i === 0`이면 `1`), `redo drops my turn and Ryan's reply and records`(말풍선이 `[첫 질문]`, `phase` recording, `turn` 1 증가, 「N번째」 `turnNo`가 1), `redo drops a reply still being written`(replying 중 `pending` 비움), `late events of a dropped turn are dropped`(옛 `turn`의 `text`, `reply`, `done`, `error`가 상태를 바꾸지 않음), `a second redo does nothing`, `cancel after redo leaves the turn dropped and my turn on Ryan's line before`(`recordCancel` 뒤 ready, `cutOf`는 앞 라이언 말풍선의 `heard`), `savedBefore skips dropped lines`.
  - talkDrop.test.ts: `settle waits for the drop sent at the tap`, `settle retries a failed drop before the next turn`(첫 요청 실패, 두 번째 성공 → `settle` 성공, 요청 두 번), `settle throws when the retry fails and tries again next time`, `settle with nothing to drop asks nothing`.
- [ ] **Step 2: 돌려 실패를 본다.** `cd app && npx jest src/flow/talk.test.ts src/flow/talkDrop.test.ts` → FAIL.
- [ ] **Step 3: 구현한다.** `redo`와 `redoTarget`의 주석에 스펙 경로와 「소희 찬스를 누르면 사라진다」(스펙 4)를 적는다.
- [ ] **Step 4: 돌려 통과를 본다.** `cd app && npx jest && npx tsc --noEmit` → PASS.
- [ ] **Step 5: 커밋한다.** `feat(app): add the free-talk redo flow and the drop request`

### Task 5: 대화 화면의 「↻ 다시 말하기」

**Files:**
- Modify: `app/src/screens/TalkScreen.tsx`, `docs/guide/APP_버튼_색과_모양_20261108.md`

**Interfaces:**
- Consumes: 작업 4의 `redoTarget`, `redo`, `createDropper`, `api.dropTurn`.

화면이 정하는 것(스펙 1, 2):
- `myBubble`은 `b.idx === redoTarget(s, (i) => chances[i] !== undefined)`일 때 말풍선 바로 아래 오른쪽에 `<Button small kind="secondary" label="↻ 다시 말하기" />`를 둔다.
- 「🎤 말하기」와 「↻ 다시 말하기」는 같은 `mic.start()`를 쓴다. 누른 쪽을 `useRef<number | null>`(`redoAt`)에 적고 `mic.start()`를 부른다(「🎤 말하기」는 `null`을 적는다). `canStart`는 `redoAt`이 있으면 `redoTarget(now.current, chancesNow) === redoAt`, 없으면 지금처럼 `canSpeak`. `beforeStart`는 `redoAt`을 읽고 비운 뒤, 있으면 `sounds.clear()`, 들은 소리 기록 비우기, `dropper.drop(idx)`, `act({ type: "redo", idx })`; 없으면 지금처럼 `recordStart`.
- `chancesNow`: 소희 찬스의 `onChange`에서 상태와 함께 고치는 ref. 다시 그리기 전의 두 번째 누름도 지금 찬스를 본다.
- `send`와 `askEnd`는 요청 앞에서 `await dropper.settle()`을 하고, 실패하면 지금 실패와 같은 액션(`failed`, `endFailed`)으로 알린다.
- 버튼 가이드의 「정한 것」에 한 줄: 「↻ 다시 말하기」는 덜 주된 버튼의 작은 판으로 내 마지막 말풍선 아래 오른쪽에 둔다, 이유(고칠 글 옆, 엄지), 스펙 경로.

- [ ] **Step 1: 시험.** 화면 시험 틀이 없으므로 규칙은 작업 4의 순수 함수 시험이 지킨다. 이 작업은 `npx tsc --noEmit`과 `npx jest` 전체, 그리고 아래 폰 확인으로 본다.
- [ ] **Step 2: 구현한다.** 위 「화면이 정하는 것」대로. 화면 맨 위 주석 블록에 「다시 말하기」 한 단락(스펙 경로).
- [ ] **Step 3: 돌려 통과를 본다.** `cd app && npx jest && npx tsc --noEmit` → PASS.
- [ ] **Step 4: 커밋한다.** `feat(app): add the redo button under my last free-talk bubble`(가이드는 `docs(guide): ...`로 따로 커밋해 `&&`로 잇는다).

## 구현 뒤 시험 (카드가 직접, PR 전에)

- worktree 서버를 8791/8792에 녹음을 뺀 데이터 복사본으로 띄우고(`docs/guide/DEVENV_맥서버_저절로_띄우기_20261107.md` 「옆 포트」), 학습자 목소리로 지어낸 영어 녹음 둘로 `try_talk.py --port 8791 --drop a.m4a b.m4a`를 돌린다. 지운 차례의 흐름이 1초 안에 끝나는지, 다시 말한 차례의 첫 소리가 지우지 않은 차례와 비슷한지, 데이터 복사본의 기록에 지운 표시가 있는지 본다. 끝나면 서버를 멈추고 복사본과 녹음을 지운다.
- 폰(main에 차례를 물은 뒤): 스펙 「확인 방법」의 폰 화면 목록.
