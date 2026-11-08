# 자유 대화 PR 2: 소희 찬스와 라이언 자막 숨기기 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 자유 대화 안에서 라이언은 영어만 쓰고(한국어 질문도 영어로 답함), 라이언 말풍선은 자막 없이 시작하며, 「소희 찬스」가 두 단계(답 힌트, 전체 문장)로 답을 돕는다.

**Architecture:** 맥 서버(`server/je_server`)는 한국어 차례를 표시와 함께 대화 상대 Claude에 보내고, 대화 안의 정해진 말을 영어로 바꾸고, 소희 찬스 힌트(뜻 한 줄, 영어 첫마디, 전체 문장)를 구조화 출력으로 한 번 만들어 그 라이언 줄에 남긴다. 전체 문장을 본 뒤의 차례는 그 문장과 견줘 대화 돌아보기에서 뒤로 미뤄 짚는다. 앱(`app/src`)은 말풍선 자막을 접어 두고, 소희 말풍선을 대화 안에 띄운다.

**Tech Stack:** Python 3.12, FastAPI, pydantic, pytest(`uv run pytest`) / Expo React Native, TypeScript, jest(`npx jest`).

**Spec:** `docs/superpowers/specs/2026-11-08-free-talk-design.md` 목표 7, 8과 정한 것 2, 3, 4, 7, 8, 9의 PR 2 부분. 화면 초안은 비공개(scratchpad)라, 스펙 9의 글과 아래 각 작업의 글이 화면의 기준이다.

## Global Constraints

- 공개 저장소(`AGENTS.md`, `REVIEW.md`): 시험 문장과 예는 지어낸다. 녹음, 받아쓴 글, 사용자 기록의 문장, 그림 파일, 개인 경로를 커밋하지 않는다. 소희 그림은 저장소에 넣지 않는다(서버가 `JE_ASSETS_DIR`에서 내준다).
- 녹음은 맥 밖으로 나가지 않는다. Claude에는 글만 보낸다(ADR-0004). 로그에는 시간과 개수만 남긴다.
- 자유 대화 안에서 라이언은 영어만 말한다. 글로만 보이는 앱 안내(오류, 기다림)는 한국어다. 대화 돌아보기는 그대로 한국어다.
- 새 문구는 쉬운 일상 낱말로 쓴다.
- 버튼: 덜 주된 버튼 왼쪽, 주된 버튼 오른쪽. 누를 수 없는 버튼은 정해진 회색(`buttonLook`, `colors.off`). 서버에 요청을 보내는 버튼은 빠르게 두 번 눌러도 요청이 한 번(`createGate`, `REVIEW.md` 「앱 화면」).
- 모든 서버 경로는 토큰 뒤에 있고, 경로의 id와 번호는 검사한다(`ID`, `PathParam(ge=0)`).
- 커밋: Conventional Commits 영어, 제목 72자 안쪽, AI 서명 없음, `git`은 `/usr/bin/git`으로 부르고, 커밋을 이을 때는 `&&`로 잇는다. 파일은 이름을 지정해 `git add`한다.
- 시험: 서버 `cd server && uv run pytest -q`, 앱 `cd app && npx jest && npx tsc --noEmit`.

## Review Focus

1. 소희 찬스를 누르고 바로 「🎤 말하기」를 눌러, 힌트 글과 소희 소리가 녹음 중에 늦게 온다: 글은 소희 말풍선에 보이되 소리는 나지 않아야 한다(작업 A3 `test_late_hint_sound_does_not_play_while_recording`).
2. 「소희 찬스」를 빠르게 두 번 누르거나 두 요청이 동시에 온다: Claude는 한 번만 불린다(작업 S3 `test_two_hints_at_once_ask_claude_once`, 작업 A3 게이트 시험).
3. 앱을 거치지 않고 2단계를 1단계보다 먼저 부르거나, 첫 단계 응답에 전체 문장이 섞인다: 409 `no_hint`, 첫 단계 응답에는 `full`이 없다(작업 S3).
4. 전체 문장을 본 뒤 전혀 다른 말을 한다: 보통 영어 차례이고 Claude의 고쳐 주기 대상이다(작업 S4 `test_far_from_the_given_sentence_is_a_plain_turn`).
5. 소희 그림과 힌트 경로가 없는 옛 서버에 새 앱이 붙는다: 얼굴 없이 글로 보이고, 힌트 실패는 소희 말풍선의 한 줄 안내로 끝나 버튼을 다시 누를 수 있다(작업 A1 `laterPictures` 시험, 작업 A3 `chanceFailed` 시험).

---

### Task S1: 대화 안의 영어 정해진 말, 한국어 차례를 라이언에게, 되받기 차례

**Files:**
- Modify: `server/je_server/phrases.py`, `server/je_server/engine.py`(`talk_english` 지움, `warm`, `speak`), `server/je_server/talk.py`(`messages`, `_turn`), `server/je_server/prompts.py`(`TALK_SYSTEM`과 표시 상수), `server/je_server/app.py`(`talk_turn`의 `WhisperError`)
- Test: `server/tests/test_talk.py`, `server/tests/test_phrases.py`, `server/tests/test_api.py`

**Interfaces:**
- Produces: `phrases.TALK_PHRASES: dict[str, str]`(키 `no_speech`, `too_long`, `claude_down`), `Engine.talk_said(name: str) -> Said`(라이언 영어 목소리 키), `Engine.talk_error(code: str, phrase: str | None = None) -> dict`(`{"type": "error", "code", "say"}`), `Engine.speak(..., down: dict | None = None)`(Claude가 답하지 못할 때 보낼 오류 이벤트, 없으면 지금처럼 한국어 `claude_down`), `prompts.TALK_KOREAN = "(in Korean) "`, `prompts.TALK_ECHO = "(echo ok)"`.
- `phrases.TALK_ENGLISH`와 `Engine.talk_english`는 지운다. 옛 기록의 `help` 줄은 `messages`, `fix_input`, 앱이 그대로 건너뛴다.

- [ ] **Step 1: 실패하는 시험을 쓴다** (`test_talk.py`; 지금 시험 중 `TALK_ENGLISH`, 「한국어 차례는 Claude에 보내지 않는다」를 기대하는 것은 아래로 바꾼다)

```python
def test_messages_send_korean_turns_marked():
    rp = talk_with([("ryan", "reply", "How was work today?"), ("user", "ask", "야근했다고 어떻게 말해요?")])
    assert messages(rp)[-1] == {"role": "user", "content": "(in Korean) 야근했다고 어떻게 말해요?"}

def test_messages_allow_echo_on_every_second_english_turn():
    # my 1st English turn: no cue; my 2nd: the last user message ends with TALK_ECHO
    ...
    assert not messages(one_turn)[-1]["content"].endswith("(echo ok)")
    assert messages(two_turns)[-1]["content"].endswith("\n(echo ok)")
    assert "(echo ok)" not in messages(two_turns)[1:-1].__repr__()  # only on the last user message

async def test_korean_turn_gets_ryans_english_reply_from_claude(talks, engine, speech_bytes, fake_whisper, fake_claude):
    # Hangul in the English transcript → heard again in Korean → line kind "ask" → Claude asked, reply line kept
    assert [l.kind for l in rp.lines[1:]] == ["ask", "reply"]
    assert fake_claude.talk_calls[-1][-1]["content"].startswith("(in Korean) ")

async def test_no_speech_in_a_talk_is_said_in_english(talks, silent_bytes):
    ev = ...  # the error event
    assert ev["code"] == "no_speech" and ev["say"]["text"] == TALK_PHRASES["no_speech"]
    assert ev["say"]["audio"] == engine.voice.key("ryan", "english", TALK_PHRASES["no_speech"])

async def test_claude_down_in_a_talk_is_said_in_english(...):  # code claude_unavailable, say = talk_said("claude_down")
async def test_talk_phrases_are_made_ahead_in_english(engine, fake_voice):  # every TALK_PHRASES value, ("ryan", "english")
async def test_roleplay_no_speech_stays_korean(...):  # engine.error("no_speech") text == PHRASES["no_speech"]
```

`test_api.py`: 받아쓰기 서버가 실패한 자유 대화 차례(`WhisperError`)의 이벤트가 `TALK_PHRASES["no_speech"]`인지.

- [ ] **Step 2: 시험이 실패하는지 본다** — `cd server && uv run pytest -q tests/test_talk.py tests/test_phrases.py tests/test_api.py` / Expected: 위 새 시험 FAIL
- [ ] **Step 3: 구현한다**
  - `TALK_PHRASES = {"no_speech": "Sorry, I didn't catch that. Could you say it again?", "too_long": "That was a little long. Could you say it in a shorter way?", "claude_down": "Sorry, I can't answer right now. Let's try again in a moment."}`. `warm()`은 `TALK_OPENERS`와 이 값을 라이언 영어 목소리로 미리 만든다(`check=True`).
  - `_turn`: `_Unheard` → `engine.talk_error(e.code)`. 한국어 차례는 `kind="ask"` 줄로 남기고 영어 차례와 같은 Claude 길로 간다(정해진 한 줄 없음). `engine.speak(..., down=engine.talk_error("claude_unavailable", "claude_down"))`.
  - `messages`: `ask` 줄은 `TALK_KOREAN + text`인 user. 마지막 user 메시지가 내 영어 차례이고 그것이 내 영어 차례(`kind == "turn"`)의 짝수 번째이면 `"\n" + TALK_ECHO`를 붙인다.
  - `TALK_SYSTEM`의 「Never correct …」 항목 뒤에 아래 두 규칙을 넣는다(2026-11-09 실제 모델로 다듬은 문구, 스펙 4).

```text
- When the learner's message ends with (echo ok) and they made a mistake, you may use the right form yourself as
  you react, the way a friend naturally would (they say "My brother live in Seoul", you say "Oh, your brother lives
  in Seoul?"). Without (echo ok), do not. Never say that anything was wrong, and never mention (echo ok).
- The learner may speak Korean, marked (in Korean), usually to ask how to say something or what you meant. Always
  reply in English, never in Korean: give the English they need in one short, easy sentence, or say what you meant
  again in simpler words, then carry on the conversation.
```

  - `app.py` `talk_turn`의 `WhisperError`는 `engine().talk_error("no_speech")`.
- [ ] **Step 4: 시험이 통과하는지 본다** — `uv run pytest -q` / Expected: 모두 PASS
- [ ] **Step 5: 커밋** — `feat(server): keep ryan in english in free talk and answer korean turns`

### Task S2: 소희 그림을 서버 그림 목록과 첫 화면 응답에

**Files:**
- Modify: `server/je_server/app.py`(`THINKING`, `ASSETS`, `/home`)
- Test: `server/tests/test_api.py`

**Interfaces:**
- Produces: `/home`의 `images.thinking.sohee == ["/assets/sohee-thinking-1.png", "/assets/sohee-thinking-2.png"]`, `images.sohee == {"face": "/assets/sohee-face.png", "whisper": "/assets/sohee-whisper-face.png"}`.

- [ ] **Step 1: 실패하는 시험** — `test_home_lists_sohees_pictures`(위 값), `test_sohee_pictures_are_served`(시험용 그림 폴더에 지어낸 PNG 바이트를 둔 네 이름이 200), 목록 밖 이름(`sohee-front.png`)은 404.
- [ ] **Step 2: 실패를 본다** — `uv run pytest -q tests/test_api.py`
- [ ] **Step 3: 구현** — `THINKING`에 `"sohee"`를 더하고 `ASSETS`에 `sohee-face.png`, `sohee-whisper-face.png`를 더한다. `/home` `images`에 `sohee`를 더한다.
- [ ] **Step 4: 통과를 본다** — `uv run pytest -q`
- [ ] **Step 5: 커밋** — `feat(server): serve sohee's faces for the free talk`

### Task S3: 소희 찬스 힌트(1단계, 2단계)와 대화 끝의 횟수

**Files:**
- Create: `server/je_server/hints.py`, `server/tests/test_hints.py`
- Modify: `server/je_server/models.py`(`Hint`, `ScriptLine.hint`), `server/je_server/prompts.py`(`HINT_SYSTEM`, `HINT_SCHEMA`), `server/je_server/claude.py`(`hint`), `server/je_server/config.py`(`claude_hint`), `server/je_server/phrases.py`(`SOHEE_PHRASES`), `server/je_server/engine.py`(`warm`), `server/je_server/talk.py`(`Talks.hint`, `hint_audio`, `show_full`, `hint_sound`, `hint_three`, `_end_body`), `server/je_server/app.py`(경로, `Claude` 만들 때 `hinter`), `server/tests/fakes.py`(가짜 `hint`), `contract/talk-end.json`
- Test: `server/tests/test_hints.py`, `server/tests/test_talk.py`, `server/tests/test_api.py`, `server/tests/test_claude.py`, `server/tests/test_contract.py`

**Interfaces:**
- Produces:
  - `models.Hint(meaning_ko: str, starters: list[str], full: str, audio: str | None = None, full_shown: bool = False, full_three: ThreeLine | None = None)`, `ScriptLine.hint: Hint | None = None`.
  - `hints.check(data: object) -> Hint | None`, `hints.conversation(rp: Roleplay, upto: int) -> list[dict]`(`[{"말한 사람": "라이언" | "학습자", "말": str}]`, `upto` 줄까지, `help`와 `fix` 줄 빼고).
  - `Claude.hint(conversation: list[dict]) -> Hint`(`self.hinter`, `HINT_TRIES = 2`번까지 `hints.check`를 통과할 때까지, 아니면 `ClaudeUnavailable("bad hint")`).
  - `Settings.claude_hint`(`JE_CLAUDE_HINT`, `QUICKS`에서, 기본 `"sonnet"`).
  - `SOHEE_PHRASES = {"hint_start": "이렇게 시작해 보세요.", "hint_full": "이렇게 말해 봐요."}`.
  - 경로(모두 `ID`, `idx: PathParam(ge=0)`):
    - `POST /talks/{rp_id}/lines/{idx}/hint` → `{"meaning_ko": str, "starters": list[str]}`(전체 문장 없음). 자유 대화가 아니거나 그 줄이 라이언의 `reply`가 아니면 404 `not_found`, Claude 실패는 `claude_down()`(503).
    - `GET .../hint/audio` → `{"audio": key}`: 소희가 `f"{meaning_ko} {SOHEE_PHRASES['hint_start']}"`를 말한 소리(`"sohee", "korean"`, `urgent=True, check=True`), `hint.audio`에 남김. 힌트가 없으면 409 `no_hint`.
    - `POST .../hint/full` → `{"text": full, "say": Said(SOHEE_PHRASES["hint_full"], 소희 키)}`, `full_shown = True`로 남김. 힌트가 없으면 409 `no_hint`.
    - `GET .../hint/sounds/{n}`(`n: PathParam(ge=0, le=3)`) → `{"audio": key}`: `n < len(starters)`는 그 첫마디, `n == len(starters)`는 전체 문장(`full_shown`일 때만, 아니면 409 `no_hint`), 라이언 영어 목소리 `urgent=True`. 그 밖은 404.
    - `GET .../hint/three` → `ThreeLine`: 전체 문장의 세 줄(`claude.annotate(full, engine.context(rp, idx))`), `full_three`에 남김. `full_shown`이 아니면 409 `no_hint`.
  - `POST /talks/{id}/end` 응답에 `"sohee": int` = 라이언 `reply` 줄마다 `hint`가 있으면 1, `full_shown`이면 1 더.

- [ ] **Step 1: 실패하는 시험**

```python
# test_hints.py
def test_check_keeps_a_good_hint():  # 2~3 starters ending in …, Korean meaning, full starting with a starter
def test_check_normalizes_spaces_and_dots():  # "I usually …" and "I usually..." → "I usually…"
@pytest.mark.parametrize("bad", [one_starter, four_word_limit_broken_7_words, hangul_in_starter, starter_without_dots,
                                 empty_meaning, english_only_meaning, meaning_over_80_chars, full_not_from_a_starter,
                                 full_over_12_words, hangul_in_full])
def test_check_drops_a_bad_hint(bad): assert hints.check(bad) is None
def test_check_keeps_the_first_three_starters():
def test_conversation_is_text_only_and_stops_at_the_line():  # no help/fix lines, Korean turns as they were heard
# test_claude.py
async def test_hint_asks_again_once_when_the_first_is_bad():  # bad then good → Hint; bad twice → ClaudeUnavailable
# test_talk.py
async def test_hint_is_made_once_and_kept_on_the_line(...):
async def test_two_hints_at_once_ask_claude_once(...):
async def test_hint_on_a_line_that_is_not_ryans_reply_is_not_found(...):
async def test_full_before_hint_is_refused(...):           # no_hint
async def test_hint_answer_leaves_out_the_full_sentence(...)  # route body has no "full"
async def test_full_marks_the_line_and_says_sohees_line(...):
async def test_hint_sounds_starters_then_full_only_after_shown(...):
async def test_end_counts_sohee_chances(...):              # hint only → 1, hint + full → 2, two lines → sum
async def test_sohees_phrases_are_made_ahead(engine, fake_voice):
```

- [ ] **Step 2: 실패를 본다** — `uv run pytest -q tests/test_hints.py tests/test_talk.py tests/test_claude.py tests/test_api.py tests/test_contract.py`
- [ ] **Step 3: 구현**
  - `hints.check`: 따옴표 지우기, 첫마디의 `" …"`, `"..."`는 `"…"`로. 첫마디 2~3개(넷 이상이면 앞 셋), 각 2~6낱말(…빼고), `…`로 끝, 한글 없음. 뜻은 한글이 있고 80자 안쪽. 전체 문장은 한 첫마디의 앞부분(…와 끝 쉼표를 뺀 것, 대소문자 무시)으로 시작하고 12낱말 안쪽, 한글 없음.
  - `HINT_SYSTEM`은 2026-11-09 견주기에 쓴 글을 그대로 옮긴다(`scripts/compare_hint_models.py`가 같은 상수를 쓴다, 작업 S5). 소희가 친구처럼 귓속말로, 뜻 한 줄, 첫마디 두세 개(…로 끝, 다 만든 답과 학습자 대신 정한 사실 없음), 첫마디 하나로 시작하는 12낱말 안쪽 전체 문장.
  - `Talks`: 줄마다 힌트 작업 하나(`self.hinting: dict[tuple[str, int], asyncio.Task]`, `_keep`, `asyncio.shield`, `end`의 `ending`과 같은 방식). 힌트는 `engine.update_line(..., hint=...)`으로 남긴다. 로그는 시간과 개수만.
  - `warm()`은 `SOHEE_PHRASES["hint_full"]`을 소희 목소리로 미리 만든다.
- [ ] **Step 4: 통과를 본다** — `uv run pytest -q`
- [ ] **Step 5: 커밋** — 둘로 나눈다: `feat(server): add sohee chance hints to free talk lines`, `feat(server): count sohee chances at the end of a free talk`

### Task S4: 전체 문장을 본 뒤의 차례

**Files:**
- Modify: `server/je_server/models.py`(`ScriptLine.given`), `server/je_server/talk.py`(`_turn`, `messages`, `fix_input`, `_end`), `server/je_server/claude.py`(`fixes`), `server/je_server/prompts.py`(`TALK_HELPED`, `FIX_SYSTEM`), `server/je_server/fixes.py`(`check`)
- Test: `server/tests/test_talk.py`, `server/tests/test_fixes.py`, `server/tests/test_claude.py`

**Interfaces:**
- Consumes: `Hint.full`, `Hint.full_shown`(작업 S3), `compare.similarity`, `compare.find_issues`, `compare.FOLLOW_MIN`, `engine.NEAR_MIN`, `claude._points`.
- Produces: `ScriptLine.given: str | None = None`(그 차례가 말하려 한 소희의 전체 문장), `prompts.TALK_HELPED = "(said with help: a sentence Sohee showed)"`, `fix_input(rp) -> tuple[list[dict], dict[int, str], dict[int, Helped]]`, `fixes.Helped(given: str, heard: str, issues: list[Issue])`, `Claude.fixes(conversation: list[dict], helped: list[dict]) -> list[dict]`, `fixes.check(items, turns, helped: dict[int, Helped] | None = None) -> list[Found]`.

- [ ] **Step 1: 실패하는 시험**

```python
async def test_turn_after_the_full_sentence_is_compared_with_it(...):
    # the line before my turn is Ryan's reply with hint.full_shown; heard close to it (≥ NEAR_MIN)
    assert line.given == full and attempt.issues == find_issues(full, heard, 2)
    assert attempt.followed == (similarity(full, heard) >= FOLLOW_MIN)
async def test_far_from_the_given_sentence_is_a_plain_turn(...):   # < NEAR_MIN → given None, issues []
async def test_a_hint_without_the_full_sentence_gives_no_given(...):
def test_messages_tell_claude_the_turn_was_helped():               # content ends with "\n" + TALK_HELPED
def test_fix_input_keeps_helped_turns_apart():                     # not in `turns`; in `helped` only with issues
# test_fixes.py
def test_own_picks_come_before_helped_turns(): ...                 # own Found first, then helped, at most 3
def test_helped_fix_is_the_given_sentence_with_the_listed_sound(): # fixed == given, said == heard,
                                                                   # why == Claude's why_ko + issue.explain verbatim
def test_helped_fix_without_the_words_is_dropped():                # why_ko names neither target nor heard word
def test_claudes_grammar_pick_on_a_helped_turn_is_dropped():
```

- [ ] **Step 2: 실패를 본다** — `uv run pytest -q tests/test_talk.py tests/test_fixes.py tests/test_claude.py`
- [ ] **Step 3: 구현**
  - `_turn`의 영어 차례: 바로 앞 줄이 `full_shown`인 라이언 답이고 `similarity(full, heard) >= NEAR_MIN`이면 `given=full`, `issues=find_issues(full, heard, 2)`, `followed = similarity >= FOLLOW_MIN`. 그 자리에서 평가 말은 없다(라이언 답만).
  - `messages`: `given`이 있는 차례는 `text + "\n" + TALK_HELPED`. `TALK_SYSTEM`에 「(said with help: …)이 붙은 말은 학습자가 소희가 보여 준 문장으로 말한 것이니 칭찬하거나 짚지 말고 그냥 이어 간다」 한 줄.
  - `Claude.fixes`의 본문은 `{"대화": …, "도움 받은 차례": [{"차례", "알려 준 문장", "들린 말", "짚을 것": _points(issues)}]}`. `FIX_SYSTEM`에 그 차례 규칙: 문법을 보지 않고, 받은 짚을 것만 why_ko에 「X가 Y처럼 들렸어요」, 「X가 들리지 않았어요」로 쓰고, 소리 내는 법은 쓰지 않는다(맥이 붙인다), idx는 그 차례 번호.
  - `fixes.check`: 자기 차례 Found(차례 순) 다음에 도움 받은 차례 Found(차례 순), 모두 `MAX_FIXES`까지. 도움 받은 차례는 `fixed=given`, `said=heard`, why_ko는 한글이 있고 짚을 것의 낱말 하나 이상을 담아야 하며, 짚을 것의 `explain`을 겹치지 않게 그대로 붙인다.
- [ ] **Step 4: 통과를 본다** — `uv run pytest -q`
- [ ] **Step 5: 커밋** — `feat(server): compare a turn with sohee's full sentence and fix it last`

### Task S5: 실제 모델 확인 스크립트

**Files:**
- Create: `server/scripts/compare_hint_models.py`, `server/tests/test_compare_hint_models.py`
- Modify: `server/scripts/compare_talk_models.py`(한국어 차례, 되받기 경우와 세기), `server/tests/` 해당 시험

**Interfaces:**
- Consumes: `prompts.HINT_SYSTEM`, `HINT_SCHEMA`, `hints.check`(작업 S3), `talk.messages`의 표시(작업 S1).
- `compare_hint_models.py [--runs 2]`: 지어낸 대화 여덟(주말 계획, 묻지 않은 말, 긴 말, 예/아니요, 첫 질문, 되묻기, 추상 질문, 둘 중 고르기)을 Haiku와 Sonnet에 번갈아 묻고, `hints.check`에 걸린 수, 전체 문장이 첫마디로 시작하지 않은 수, 가운데 시간, 값을 찍는다.
- `compare_talk_models.py`: 경우에 한국어 차례 여섯(`TALK_KOREAN` 표시)과 실수 차례 넷(마지막 user 메시지에 `TALK_ECHO`가 붙은 판과 안 붙은 판)을 더하고, `korean` 어김 수와 되받기 수(경우마다 맞는 꼴 낱말 정규식)를 찍는다.

- [ ] **Step 1: 실패하는 시험** — 순수 함수만: `flags`(첫마디 수·길이·한글, 첫마디로 시작 안 함), 되받기 세기 정규식이 맞는 꼴을 잡고 라이언 자신의 말(「I went shopping too」)은 잡지 않는 것은 경우마다 낱말을 정해 두는 것으로 둔다.
- [ ] **Step 2: 실패를 본다** — `uv run pytest -q tests/test_compare_hint_models.py`
- [ ] **Step 3: 구현** — 스크래치에서 쓴 것을 저장소 꼴(`compare_talk_models.py`처럼 `argparse`, 번갈아 묻기, 값 계산)로 옮긴다.
- [ ] **Step 4: 통과를 본다** — `uv run pytest -q`
- [ ] **Step 5: 커밋** — `test(server): compare hint models and count recasts on made-up talks`

### Task A1: 앱 API, 소희 그림, 첫 화면 아이콘

**Files:**
- Modify: `app/src/api/types.ts`, `app/src/api/client.ts`, `app/src/ui/thinking.ts`, `app/src/ui/faces.ts`, `app/src/screens/HomeScreen.tsx`, `contract/talk-end.json`(작업 S3과 같은 값), `app/src/api/contract.test.ts`
- Test: `app/src/api/client.test.ts`, `app/src/ui/faces.test.ts`, `app/src/ui/thinking.test.ts`

**Interfaces:**
- Consumes: 작업 S2, S3의 경로와 모양.
- Produces: `type Hint = { meaning_ko: string; starters: string[] }`, `type HintFull = { text: string; say: Said }`, `Thinking = { jake: string[]; ryan: string[]; sohee?: string[] }`, `Home.images.sohee?: { face: string; whisper: string }`, `TalkEnd.sohee?: number`, `Who = "jake" | "ryan" | "sohee"`, `api.getHint(id, idx): Promise<Hint>`(POST, `LONG`), `api.getHintAudio(id, idx): Promise<{ audio: string }>`, `api.showFull(id, idx): Promise<HintFull>`(POST), `api.getHintSound(id, idx, n): Promise<{ audio: string }>`, `api.getHintThree(id, idx): Promise<ThreeLine>`.

- [ ] **Step 1: 실패하는 시험** — 클라이언트 경로 다섯의 주소와 메서드, `laterPictures`가 소희의 생각하는 얼굴 둘과 얼굴, 귓속말 얼굴을 넣고 옛 서버(`sohee` 없음)에서는 빼는 것, `framesFor(thinking, "sohee")`가 옛 서버에서 `[]`.
- [ ] **Step 2: 실패를 본다** — `cd app && npx jest src/api src/ui`
- [ ] **Step 3: 구현** — 첫 화면 「자유 대화」 카드 아이콘은 `"☕"`(2026-11-09 사용자, 갤럭시에서 🗣️가 보라 바탕에 묻힘).
- [ ] **Step 4: 통과를 본다** — `npx jest && npx tsc --noEmit`
- [ ] **Step 5: 커밋** — `feat(app): add sohee chance requests and pictures, coffee icon`

### Task A2: 라이언 말풍선 자막 숨기기와 한국어 오류 글

**Files:**
- Create: `app/src/ui/SpeakingBars.tsx`
- Modify: `app/src/flow/talk.ts`, `app/src/screens/TalkScreen.tsx`
- Test: `app/src/flow/talk.test.ts`

**Interfaces:**
- Produces: `talkErrorText(code: string): string`, `ryanSpeaking(s: TalkState, idx: number): boolean`(그 말풍선이 지금 말하는 라이언 말이고 `phase`가 `waiting`, `replying`, `ryan` 중 하나).

- [ ] **Step 1: 실패하는 시험**

```ts
test("talk errors show Korean app text, not Ryan's English words", () => {
  const s = talkReduce(recordingStopped, { type: "event", turn, e: { type: "error", code: "no_speech", say: english } });
  expect(s.message).toBe("잘 안 들렸어요. 한 번 더 말해 줄래요?");
});
// too_long → "녹음이 너무 길어요. 한 문장씩 짧게 말해 볼까요?",
// claude_unavailable → "지금은 라이언이 대답할 수 없어요. 맥의 인터넷 연결을 확인해 주세요."
test("Ryan's current bubble is speaking until his turn ends", ...)  // ryan phase → true; ready → false; past bubble → false
```

- [ ] **Step 2: 실패를 본다** — `npx jest src/flow/talk.test.ts`
- [ ] **Step 3: 구현**
  - 라이언 말풍선(지금 것과 지난 것, 글이 오는 중인 `pending` 말풍선)은 처음에 `SpeakingBars`와 글자 「자막 숨김」만 보인다. 말하는 동안(`ryanSpeaking`)은 막대가 움직이고 「라이언이 말하는 중」, 버튼은 없다.
  - 다 말한 지금 말풍선: 「🔊 다시 듣기」, 「자막 보기 ›」, 「통역 ›」가 펼쳐진 채. 지난 말풍선: 누르면 「🔊 듣기」, 「자막 보기 ›」, 「통역 ›」.
  - 「자막 보기」를 누르면 그 말풍선만 글이 펼쳐지고(`subOpen: Record<number, boolean>`, 화면 상태) 「자막 접기」, 「읽는 법 보기 ›」가 나온다. 끊은 답의 흐린 문장은 펼쳤을 때만. 「통역」은 자막과 상관없다.
  - 오류 이벤트의 `say.audio`(라이언 영어)는 지금처럼 틀고, 글은 `talkErrorText(code)`.
  - `SpeakingBars`: 막대 다섯, `Animated`로 움직임(`moving: boolean`), 새 패키지 없음.
- [ ] **Step 4: 통과를 본다** — `npx jest && npx tsc --noEmit`
- [ ] **Step 5: 커밋** — `feat(app): hide ryan's subtitles in free talk until asked`

### Task A3: 소희 찬스(소희 말풍선, 두 단계)

**Files:**
- Create: `app/src/flow/soheeChance.ts`, `app/src/flow/soheeChance.test.ts`, `app/src/ui/SoheeHint.tsx`, `app/src/ui/SoheeChanceButton.tsx`
- Modify: `app/src/screens/TalkScreen.tsx`

**Interfaces:**
- Consumes: 작업 A1의 `api.*Hint*`, `Who "sohee"`, `Home.images.sohee`; `mayListenTalk`, `canSpeak`(flow/talk).
- Produces:

```ts
export type Chance =
  | { idx: number; step: "thinking" }
  | { idx: number; step: "failed" }
  | { idx: number; step: "hint"; hint: Hint }
  | { idx: number; step: "fullLoading"; hint: Hint }
  | { idx: number; step: "full"; hint: Hint; full: HintFull };
export type Chances = Record<number, Chance>;
export function chanceTarget(s: TalkState): number | null; // the last Ryan reply bubble's idx while mayListenTalk(s)
export function canAskHint(s: TalkState, c: Chances): boolean; // target, and no chance yet (or a failed one) on it
export function canAskFull(s: TalkState, c: Chance | undefined): boolean; // step "hint" on the target, my turn
export function chanceReduce(c: Chances, a: ChanceAction): Chances; // asked, hint, failed, fullAsked, full, fullFailed
export const maySohee = (s: TalkState) => mayListenTalk(s); // her voice plays only on my turn, nothing recording
export const HINT_FAILED = "지금은 소희가 도와줄 수 없어요. 다시 눌러 볼까요?";
```

- [ ] **Step 1: 실패하는 시험** (`soheeChance.test.ts`)

```ts
test("the hint can be asked once per Ryan line, on my turn only", ...);      // ryan phase → false, ready → true, after asked → false
test("a failed hint can be asked again", ...);                               // chanceFailed
test("the full sentence only after the hint, once", ...);                    // canAskFull: hint → true, full → false
test("late hint sound does not play while recording", ...);                 // test_late_hint_sound_does_not_play_while_recording:
                                                                             // maySohee(recording state) === false
test("a hint for an older line stays but is not the target", ...);           // chanceTarget moves to the new reply
```

  화면의 두 번 누름: `createGate`로 「소희 찬스」와 「전체 문장 보기」를 하나씩 막는 것을 `gate.test.ts`의 방식으로 한 줄 더한다.
- [ ] **Step 2: 실패를 본다** — `npx jest src/flow/soheeChance.test.ts`
- [ ] **Step 3: 구현**
  - `SoheeChanceButton`: 「🎤 말하기」 줄 위 왼쪽, 소희 얼굴(`images.sohee.face`, 없으면 글만) + 「소희 찬스」, 초록(`colors.sohee`) 테두리 흰 바탕, `canAskHint`가 아니면 정해진 회색(`colors.off`, `colors.offText`)과 흐린 얼굴.
  - `SoheeHint`(라이언 말풍선 바로 아래, 왼쪽): 생각하는 동안 `ThinkingFace who="sohee"`(작게, 48) + 「소희가 생각하고 있어요」와 `Dots`; 힌트가 오면 귓속말 얼굴, 「🤫 소희 찬스」, 뜻 한 줄 + 「이렇게 시작해 보세요.」, 첫마디마다 「🔊 첫마디」 칩(누르면 `getHintSound(n)`을 라이언 소리로 `playFromBubble`), 「그래도 어려우면 전체 문장 보기 ›」(`canAskFull`). 2단계: 「이렇게 말해 봐요. 낱말을 바꿔 말해도 돼요.」, 전체 문장(크게), 「🔊 듣기」(`getHintSound(starters.length)`), 「읽는 법 보기 ›」(`getHintThree`, `ThreeLineView`). 실패: `HINT_FAILED` 한 줄. 아래에서 톡 튀어 오르는 움직임(`Animated.spring`).
  - 대상이 아닌 지난 소희 말풍선은 접혀 「🤫 소희 찬스」(전체 문장을 봤으면 「· 전체 문장 봄」)만 보이고, 누르면 펼친다.
  - 소리: 힌트 글이 오면 `getHintAudio` → `maySohee(now) && !sounds.isPlaying()`일 때만 튼다(`useInterpret`의 `allow(auto)`와 같은 방식). 전체 문장의 `say.audio`도 같다. 「🎤 말하기」의 `sounds.clear()`가 소희 소리를 멈춘다. 태그 `sohee:<idx>`로 🔊가 울린다.
  - 소희 말풍선은 녹음하는 동안에도 보인다(접지 않는다).
- [ ] **Step 4: 통과를 본다** — `npx jest && npx tsc --noEmit`
- [ ] **Step 5: 커밋** — `feat(app): add sohee chance hints and full sentence to free talk`

### Task A4: 대화 돌아보기의 「소희 찬스 N번 썼어요」와 버튼 가이드

**Files:**
- Modify: `app/src/screens/TalkFixScreen.tsx`, `app/src/flow/talkFix.ts`, `docs/guide/APP_버튼_색과_모양_20261108.md`
- Test: `app/src/flow/talkFix.test.ts`

**Interfaces:**
- Consumes: `TalkEnd.sohee`(작업 A1).
- Produces: `soheeLine(end: TalkEnd): string | null` — 1 이상이면 `` `소희 찬스 ${n}번 썼어요` ``, 0이나 없으면 `null`.

- [ ] **Step 1: 실패하는 시험** — `soheeLine({ ..., sohee: 2 }) === "소희 찬스 2번 썼어요"`, `sohee: 0`과 없음은 `null`.
- [ ] **Step 2: 실패를 본다** — `npx jest src/flow/talkFix.test.ts`
- [ ] **Step 3: 구현** — 제목 줄 아래에 소희 얼굴(작게) + 그 글의 초록 칩. 고칠 곳이 없을 때의 화면에도 같다. 버튼 가이드에 「소희 찬스」 버튼(초록 테두리, 세 모양 밖의 소희 전용, 누를 수 없을 때는 정해진 회색) 한 줄과 까닭을 더한다.
- [ ] **Step 4: 통과를 본다** — `npx jest && npx tsc --noEmit`
- [ ] **Step 5: 커밋** — `feat(app): show how many sohee chances a free talk used`

---

## 구현 뒤 확인(카드가 직접, 작업 아님)

- 실제 모델: `compare_talk_models.py`(한국어 차례 영어로만, 되받기 빈도: `(echo ok)` 있는 차례와 없는 차례), `compare_hint_models.py`(Sonnet, 어김과 시간). 숫자를 devlog와 스펙 「잰 것」에 적는다.
- 학습자 목소리 녹음: worktree 서버(8791/8792, 녹음을 뺀 데이터 복사본)에 한국어 질문 녹음과 영어 녹음을 `try_talk.py`로 보내 라이언의 답(영어인지, 뜻이 맞는지)과 시간을 본다. 힌트 경로와 전체 문장 뒤의 차례도 보낸다. 끝나면 복사본과 녹음을 지운다.
- 화면: 폰(main에 시간과 소리를 알리고 부탁)이나 `jake-english` 에뮬레이터(main에 차례를 묻고)에서 자막, 통역, 소희 찬스 두 단계, 녹음하는 동안의 소희 말풍선, 대화 돌아보기의 줄, 첫 화면 ☕. 소희 찬스를 눌러 소희 소리까지 걸린 시간.
- 가이드: `SPEECH_자유대화_기다림과_한국어_가르기_20261108.md`(한국어 차례가 라이언에게 가는 것, 2026-11-09 녹음 시험), `PROMPT_` 가이드(힌트 견주기, 되받기를 서버가 고르는 것).
