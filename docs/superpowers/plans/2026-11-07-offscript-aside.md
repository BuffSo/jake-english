# 대사와 다르게 말했을 때 선생님 라이언이 답하기 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 대사를 따라 말하지 않은 녹음에는 어느 연습에서든 선생님 라이언이 한국어로 답하고 같은 대사를 다시 하게 한다. 대본은 바꾸지 않고, 한국어로 한 말도 받아쓴다.

**Architecture:** 서버의 `Engine.attempt`가 영어 받아쓰기로 따라 말했는지 가르고, 따라 말하지 않았으면 같은 녹음을 언어 자동으로 한 번 더 받아쓴다. 그다음 새 `Claude.aside` 스트림(글쓰기 모델)으로 라이언의 한국어 답을 흘려 보낸다. 대본을 새로 쓰던 길(`offscript`, `continue_script`, `add_reply`, `reply` 이벤트)은 없앤다. 시도에는 `aside` 표시를 달아 끝 화면, 대화 흐름, 「지난 상황」에서 뺀다. 앱은 `heard.followed === false`를 보고 「다시 해 보기」만 보여 주고, 누르면 그 말을 대화에 남기지 않는다.

**Tech Stack:** Python 3 + FastAPI + pydantic + anthropic SDK(서버, `uv run pytest`), whisper.cpp whisper-server, React Native + Expo + TypeScript(앱, `npm test`, `npm run typecheck`).

**Spec:** `docs/superpowers/specs/2026-11-07-offscript-aside-design.md`

## Global Constraints

- 이 worktree에서 git은 `/usr/bin/git`으로 부른다. `git add`는 파일을 지정한다(`-A`, `.` 금지). 커밋은 `git commit -F - <<'EOF'`로 하고 AI 서명 줄을 넣지 않는다. 첫 줄은 Conventional Commits 영어, 본문 끝에 `Refs: docs/superpowers/specs/2026-11-07-offscript-aside-design.md`.
- scope: 서버만 고친 커밋은 `server`, 앱만 고친 커밋은 `app`, 둘 다면 생략. 문서는 `prd`, `guide` 등(AGENTS.md 「커밋 메시지」).
- 공개 저장소: 코드, 시험, 문서, 커밋에 녹음, 들린 말 원문, 개인 경로, 참고 앱 이름을 쓰지 않는다. 시험 문장은 지어낸 것을 쓴다.
- Anthropic에는 글만 보낸다(ADR-0004). 녹음, 파일 경로를 보내지 않는다. 받아쓴 글을 로그에 남기지 않는다.
- 선생님 라이언의 답: 한국어 해요체, 영어로 물어도 한국어, 상황 속 인물로 영어 대답을 하지 않음, 칭찬을 지어내지 않음(영어로 물은 것도 칭찬하지 않음), 소리 내는 법을 지어내지 않음(물으면 「읽는 법 보기」), 받은 자료 이름을 말하지 않음, 「~라고 말했어요」 대신 「~처럼 들렸어요」, 한두 문장(짚을 것이 있으면 서너 문장), 늘 같은 대사를 다시 해 보자고 끝냄.
- 짚을 것은 많아야 두 가지, 넘으면 문장 앞쪽부터(`compare.find_issues(line, heard, limit=2)`).
- 따라 말한 녹음의 길은 바꾸지 않는다. 받아쓰기는 한 번(`"en"`)이고, 이벤트 순서도 그대로다.
- Claude가 답하지 못하면 오류 대신 `PHRASES["retry_offscript"]`(「이번에는 대사를 그대로 따라 말해 볼까요?」)를 말하고 같은 흐름으로 간다.
- 옛 기록(`kind="reply"` 줄, `aside` 없는 시도, `point_ko`)은 지금처럼 읽힌다.
- 서버와 앱 테스트는 각각 `cd server && uv run pytest`, `cd app && npm test && npm run typecheck`. 이 worktree에 `server/.env`, `app/.env`가 없으면 원래 폴더(`git worktree list`의 첫 줄)에서 복사한다(시험만 돌릴 때는 필요 없다).

## Review Focus

- 한국어로만 말한 녹음: 영어 받아쓰기가 한글을 그대로 내거나 빈 글을 내도 `no_speech`가 아니라 라이언의 답이 나와야 한다. → Task 3 `test_korean_only_hangul_is_not_no_speech`.
- 선생님에게 한 말 바로 뒤 「다시 해 보기」를 누르고 대사를 따라 말한 첫 차례: 평가 뒤 「다음」이 다음 줄로 가야 한다(같은 줄로 돌아오면 안 된다). → Task 5 `aside then follow moves on to the next line`.
- 마지막 시도가 선생님에게 한 말인 줄의 끝인사: 앞의 따라 말한 시도에 고칠 것이 남았으면 `closing_retry`여야 한다. → Task 4 `test_aside_after_issue_keeps_closing_retry`.
- Claude가 글을 몇 조각 흘린 뒤 끊김: 말이 중간에 끊겨도 정해진 말로 끝나고 오류 화면이 뜨지 않아야 한다. → Task 3 `test_aside_claude_cut_midway_ends_with_fixed_phrase`.
- 한국어와 영어를 섞은 말(영어 받아쓰기에 낱말이 조금 있음): 한국어로 받아썼으면 짚을 것을 만들지 않아야 한다(「X가 들리지 않았어요」 같은 헛짚기 방지). → Task 3 `test_korean_heard_sends_no_issues`.

---

### Task 1: 언어 자동 받아쓰기가 알아낸 언어도 돌려준다

**Files:**
- Modify: `server/je_server/asr.py`
- Modify: `server/tests/fakes.py` (`FakeWhisper`)
- Test: `server/tests/test_asr.py`

**Interfaces:**
- Produces: `Whisper.transcribe_auto(wav: Path) -> tuple[str, str]` — (깨끗이 한 글, whisper가 알아낸 언어 이름 소문자, 예 `"korean"`, `"english"`, 모르면 `""`). `FakeWhisper.transcribe_auto(wav)`는 `langs`에 `"auto"`를 더하고 `(self.auto_text if self.auto_text is not None else self.text, self.auto_lang)`을 돌려준다. `FakeWhisper.__init__`에 `self.auto_text: str | None = None`, `self.auto_lang = "english"`.

- [ ] **Step 1: 실패하는 시험을 쓴다** (`server/tests/test_asr.py`)

```python
async def test_transcribe_auto_returns_text_and_language(tmp_path):
    seen = {}

    def handler(request: httpx.Request):
        seen["body"] = request.read()
        return httpx.Response(200, json={"text": " 다시 할게요 [BLANK_AUDIO]\n", "language": "korean"})

    wav = tmp_path / "a.wav"
    wav.write_bytes(b"RIFF")
    assert await whisper_with(handler).transcribe_auto(wav) == ("다시 할게요", "korean")
    assert b"\r\n\r\nauto\r\n" in seen["body"] and b"verbose_json" in seen["body"]


async def test_transcribe_auto_without_language_is_empty_name(tmp_path):
    wav = tmp_path / "a.wav"
    wav.write_bytes(b"RIFF")
    w = whisper_with(lambda r: httpx.Response(200, json={"text": "Hello"}))
    assert await w.transcribe_auto(wav) == ("Hello", "")
```

- [ ] **Step 2: 실패를 본다**

Run: `cd server && uv run pytest tests/test_asr.py -v`
Expected: FAIL, `AttributeError: 'Whisper' object has no attribute 'transcribe_auto'`

- [ ] **Step 3: `Whisper.transcribe_auto`를 만든다**

`transcribe`와 같은 `/inference` 요청에 `language="auto"`, `response_format="verbose_json"`을 보낸다. 글은 `transcribe`처럼 `BRACKETS`를 지우고 공백을 하나로 모은다. 언어는 `r.json().get("language", "")`를 소문자로 한다. 요청과 글 다듬기는 `transcribe`와 함께 쓰는 작은 도우미로 나눠도 된다. 모듈 docstring의 「turn recordings are English」 문장을 「turn recordings are English first, then auto-detected when not followed」로 고친다. `FakeWhisper`에 위 Interfaces대로 더한다.

- [ ] **Step 4: 통과를 본다**

Run: `cd server && uv run pytest tests/test_asr.py -v`
Expected: PASS

- [ ] **Step 5: 커밋**

```bash
/usr/bin/git add server/je_server/asr.py server/tests/test_asr.py server/tests/fakes.py
/usr/bin/git commit -F - <<'EOF'
feat(server): return the detected language from auto transcription

Turn recordings that do not follow the line are transcribed a second time
with the language auto-detected (spec offscript-aside 2); whisper-server
gives the language with response_format=verbose_json.

Refs: docs/superpowers/specs/2026-11-07-offscript-aside-design.md
EOF
```

### Task 2: 선생님 라이언의 답을 흘려 받는 `Claude.aside`

**Files:**
- Modify: `server/je_server/prompts.py` (`ASIDE_SYSTEM` 추가)
- Modify: `server/je_server/claude.py` (`aside` 추가, 흘려 받기를 `feedback`과 함께 쓰는 도우미로)
- Modify: `server/tests/fakes.py` (`FakeClaude.aside`)
- Test: `server/tests/test_claude.py`

**Interfaces:**
- Consumes: `models.Frame`, `models.Issue`, `models.Draft`
- Produces: `Claude.aside(frame: Frame, history: Draft, line: str, heard: str, heard_ko: str | None, issues: list[Issue], earlier: list[tuple[str, str]]) -> AsyncIterator[str]`. `heard`는 영어로 받아쓴 글, `heard_ko`는 자동 받아쓰기가 한국어였을 때의 글, `earlier`는 같은 줄에서 앞서 선생님에게 한 말과 라이언의 답 `(들린 말, 라이언의 답)` 목록(오래된 것부터, 많아야 3개). 실패하면 `ClaudeUnavailable`을 던진다(`feedback`과 같다).
- Produces: `FakeClaude.aside(...)`는 `self.aside_calls`(dict 목록: `frame`, `history`, `line`, `heard`, `heard_ko`, `issues`(dump), `earlier`)에 기록하고, `self._maybe_fail()` 뒤 `self.aside_pieces`(기본 `["괜찮아요, 말이 꼬일 수 있어요. ", "다시 해 볼까요?"]`)를 차례로 낸다. `self.aside_fail_after: int | None = None`에 수를 넣으면 그 수만큼 조각을 낸 뒤 `ClaudeUnavailable`을 던진다(0이면 조각 없이 바로). 시험이 `fail_next`를 쓰지 않는 것은, 뒤에서 도는 세 줄 준비(`annotate`)가 그것을 먼저 써 버릴 수 있어서다.

- [ ] **Step 1: 실패하는 시험을 쓴다** (`server/tests/test_claude.py`, 이 파일의 `FakeAnthropic` 쓰는 법을 따른다. `answers`에 문자열 목록을 넣으면 스트림 조각이 된다)

```python
async def test_aside_streams_korean_on_the_writer_and_sends_only_text():
    fake = FakeAnthropic([["괜찮아요. ", "다시 해 볼까요?"]])
    issue = Issue(target="large", heard="launch", sound=("R", "N"), explain="")
    out = [d async for d in Claude(fake).aside(
        Frame(**FRAME), [("ryan", "What size?")], "A large one, please.", "A launch one, peace.", None,
        [issue], [("다시 할게요", "괜찮아요. 다시 해 볼까요?")])]
    assert out == ["괜찮아요. ", "다시 해 볼까요?"]
    req = fake.requests[0]
    assert req["model"] == "claude-sonnet-5-5" and req["system"] == prompts.ASIDE_SYSTEM
    assert req["output_config"]["effort"] == "low" and fake.options[-1] == LIVE_OPTIONS
    body = json.loads(req["messages"][0]["content"])
    assert body["대사"] == "A large one, please." and body["들린 말(영어 받아쓰기)"] == "A launch one, peace."
    assert body["들린 말(한국어 받아쓰기)"] == ""
    assert body["짚을 것"] == [{"대사 낱말": "large", "들린 낱말": "launch", "소리 내는 법": ""}]
    assert body["앞서 선생님에게 한 말"] == [{"들린 말": "다시 할게요", "라이언의 답": "괜찮아요. 다시 해 볼까요?"}]
    assert body["지금까지 대화"] == [{"speaker": "ryan", "text": "What size?"}]


async def test_aside_connection_error_is_unavailable():
    fake = FakeAnthropic([connection_error()])
    with pytest.raises(ClaudeUnavailable):
        [d async for d in Claude(fake).aside(Frame(**FRAME), [], "a", "b", None, [], [])]


def test_aside_prompt_keeps_the_teacher_rules():
    p = prompts.ASIDE_SYSTEM
    for must in ("해요체", "읽는 법 보기", "처럼 들렸어요", "다시"):
        assert must in p
```

시험 파일 머리의 import에 `Issue`, `LIVE_OPTIONS`, `prompts`가 없으면 더한다.

- [ ] **Step 2: 실패를 본다**

Run: `cd server && uv run pytest tests/test_claude.py -k aside -v`
Expected: FAIL, `AttributeError: ... has no attribute 'aside'` / `ASIDE_SYSTEM`

- [ ] **Step 3: `ASIDE_SYSTEM`을 쓴다** (`prompts.py`, `FEEDBACK_SYSTEM` 다음)

한국어로 쓴다. `FEEDBACK_SYSTEM`의 말투 규칙과 예시 꼴을 따른다. 들어갈 것(스펙 「3. 선생님 라이언의 답」 그대로):
- 당신은 다정한 영어 선생님 라이언이고, 학습자가 화면의 대사를 따라 말해야 하는데 다른 말이 들렸다. 학습자가 선생님에게 한 말로 보고 한국어로 답한다. 대본은 바뀌지 않고 학습자는 같은 대사를 다시 한다.
- 받는 것: 상황, 지금까지 대화, 대사, 들린 말(영어 받아쓰기, 한국어를 영어로 번역해 적었을 수 있다), 들린 말(한국어 받아쓰기, 비어 있으면 없음), 짚을 것(맥이 대사와 견줘 찾은 것), 앞서 선생님에게 한 말.
- 갈래별로 할 말: 따라 말하려다 다르게 들림(받은 짚을 것만 「X가 Y처럼 들렸어요」, 소리 내는 법은 받은 것만 다듬어, 대사와 상관없는 말이면 짚을 것을 쓰지 않음), 말이 꼬임이나 다시 하겠다는 말, 뜻이나 방법을 묻는 말(무엇을 말하면 되는지 물으면 화면의 대사를 말하면 된다고), 소리를 묻는 말(지어내지 말고 「읽는 법 보기」를 눌러 보라고), 상황에 맞지만 다른 영어(그 말도 통한다고 짧게, 표현은 고치지 않음, 이번에는 대사대로), 그 밖.
- 하지 않는 것: 상황 속 인물로 영어 대답, 영어로 답하기(영어로 물어도 한국어), 받지 않은 칭찬(영어로 물은 것 칭찬 포함), 받은 자료의 이름이나 자료가 없다는 말, 「~라고 말했어요」, 점수.
- 존댓말(해요체)만. 한두 문장, 짚을 것을 말할 때는 서너 문장. 마크다운, 따옴표 강조, 이모지 없이. 영어 낱말은 영어 그대로. 마지막은 늘 같은 대사를 다시 해 보자는 말.
- 예시 셋: 말이 꼬였을 때, 짚을 것 둘이 있을 때(「large가 launch처럼, please가 peace처럼 들렸어요. 한 번 더 해 볼까요?」), 상황에 맞는 다른 영어일 때(「좋은 말이에요. 이번에는 대사대로 해 볼까요?」).

- [ ] **Step 4: `Claude.aside`를 만든다** (`claude.py`)

`feedback`의 흘려 받기와 오류 처리(`APIConnectionError`, `APIStatusError` → `ClaudeUnavailable`)를 `_stream(model: dict, system: str, body: dict, max_tokens: int) -> AsyncIterator[str]` 하나로 옮기고 `feedback`과 `aside`가 함께 쓴다. 모델 설정은 `_request(model, {})`로 만든다. 그러면 글쓰기 모델의 effort가 `output_config`에 들어간다. `output_config`가 비면 넣지 않는다. `feedback`은 지금처럼 `self.quick`이고 effort가 없다. `aside`는 `self.writer`, `max_tokens=600`, 클라이언트는 `self._client(live=True)`. 몸은 `json.dumps(..., ensure_ascii=False)`로, 키는 위 시험 그대로다: `상황`(frame dump), `지금까지 대화`, `대사`, `들린 말(영어 받아쓰기)`, `들린 말(한국어 받아쓰기)`(없으면 `""`), `짚을 것`(`대사 낱말`, `들린 낱말`, `소리 내는 법`), `앞서 선생님에게 한 말`(`들린 말`, `라이언의 답`). `상황`과 `지금까지 대화`는 `Claude._talk`을 쓴다. `FakeClaude`에 위 Interfaces대로 더한다.

- [ ] **Step 5: 통과를 본다**

Run: `cd server && uv run pytest tests/test_claude.py -v`
Expected: PASS (`feedback` 시험도 함께 통과해야 한다)

- [ ] **Step 6: 커밋**

```bash
/usr/bin/git add server/je_server/prompts.py server/je_server/claude.py server/tests/fakes.py server/tests/test_claude.py
/usr/bin/git commit -F - <<'EOF'
feat(server): add teacher Ryan's streamed answer to off-script speech

`Claude.aside` streams Ryan's Korean answer on the writer model with the
line, both transcripts, the Mac's points and the earlier asides on the
line; `feedback` and `aside` share one streaming helper.

Refs: docs/superpowers/specs/2026-11-07-offscript-aside-design.md
EOF
```

### Task 3: `Engine.attempt`가 따라 말하지 않은 녹음에 선생님의 답을 낸다

**Files:**
- Modify: `server/je_server/models.py` (`Attempt.aside: bool = False`)
- Modify: `server/je_server/engine.py` (`attempt`)
- Modify: `contract/roleplay.json` (시도마다 `"aside": false`)
- Create: `server/tests/test_aside.py`
- Test: `server/tests/test_attempt.py`(기존, 그대로 통과해야 함), `server/tests/test_contract.py`

**Interfaces:**
- Consumes: `Whisper.transcribe_auto` (Task 1), `Claude.aside` (Task 2)
- Produces: `Attempt.aside: bool = False` — 선생님에게 한 말(따라 말하지 않은 시도)이면 `True`. 따라 말하지 않은 시도의 이벤트: `heard`(`text`는 한국어면 한국어 글, `followed: False`) → `text` 조각들 → `audio`들 → `done`(`next`는 그 줄 `idx`, `issues`는 넘긴 짚을 것 수). `reply` 이벤트는 없다.

- [ ] **Step 1: 실패하는 시험을 쓴다** (`server/tests/test_aside.py`, `test_attempt.py`의 `run` 도우미와 `engine_with_rp`, `speech_bytes`를 쓴다)

```python
async def test_aside_answers_in_korean_and_keeps_the_line(engine_with_rp, speech_bytes, fake_whisper, fake_claude):
    engine, rp_id, user_idx = engine_with_rp
    fake_whisper.text = "Wait, let me try that again."
    before = [l.text for l in engine.store.load(rp_id).lines]
    ev = await run(engine, rp_id, user_idx, speech_bytes)
    assert ev[0] == {"type": "heard", "text": "Wait, let me try that again.", "followed": False}
    assert "".join(e["delta"] for e in ev if e["type"] == "text") == "괜찮아요, 말이 꼬일 수 있어요. 다시 해 볼까요?"
    assert not any(e["type"] == "reply" for e in ev) and ev[-1]["type"] == "done" and ev[-1]["next"] == user_idx
    rp = engine.store.load(rp_id)
    assert [l.text for l in rp.lines] == before and rp.pos == 0 and rp.attempts[user_idx][-1].aside is True
    assert fake_whisper.langs == ["en", "auto"] and fake_claude.feedback_calls == []


@pytest.mark.parametrize("mode", ["retry", "practice"])
async def test_aside_in_every_mode(engine_with_rp, speech_bytes, fake_whisper, fake_claude, mode):
    engine, rp_id, user_idx = engine_with_rp
    fake_whisper.text = "What does this mean?"
    ev = await run(engine, rp_id, user_idx, speech_bytes, mode)
    assert fake_claude.aside_calls and ev[-1]["next"] == user_idx


async def test_aside_in_shadow_uses_ryans_line(engine_with_rp, speech_bytes, fake_whisper, fake_claude):
    engine, rp_id, _ = engine_with_rp
    await engine.line(rp_id, 0)
    fake_whisper.text = "What does this mean?"
    await run(engine, rp_id, 0, speech_bytes, "shadow")
    assert fake_claude.aside_calls[-1]["line"] == engine.store.load(rp_id).lines[0].text


async def test_korean_heard_replaces_the_english_transcript(engine_with_rp, speech_bytes, fake_whisper, fake_claude):
    engine, rp_id, user_idx = engine_with_rp
    fake_whisper.text = "What does this mean?"  # whisper translated the Korean
    fake_whisper.auto_text, fake_whisper.auto_lang = "이게 무슨 뜻이에요?", "korean"
    ev = await run(engine, rp_id, user_idx, speech_bytes)
    assert ev[0]["text"] == "이게 무슨 뜻이에요?"
    sent = fake_claude.aside_calls[-1]
    assert sent["heard"] == "What does this mean?" and sent["heard_ko"] == "이게 무슨 뜻이에요?"
    assert engine.store.load(rp_id).attempts[user_idx][-1].heard == "이게 무슨 뜻이에요?"


async def test_korean_only_hangul_is_not_no_speech(engine_with_rp, speech_bytes, fake_whisper, fake_claude):
    engine, rp_id, user_idx = engine_with_rp
    fake_whisper.text = "다시 할게요"  # forced English left the Hangul as it was
    fake_whisper.auto_text, fake_whisper.auto_lang = "다시 할게요", "korean"
    ev = await run(engine, rp_id, user_idx, speech_bytes)
    assert ev[0]["text"] == "다시 할게요" and ev[-1]["type"] == "done"


async def test_korean_heard_sends_no_issues(engine_with_rp, speech_bytes, fake_whisper, fake_claude):
    engine, rp_id, user_idx = engine_with_rp
    fake_whisper.text = "meaning of over there"  # 0.5 against the line: not followed
    fake_whisper.auto_text, fake_whisper.auto_lang = "over there가 무슨 뜻이에요?", "korean"
    await run(engine, rp_id, user_idx, speech_bytes)
    assert fake_claude.aside_calls[-1]["issues"] == []


async def test_near_miss_sends_the_macs_points(engine_with_rp, speech_bytes, fake_whisper, fake_claude):
    # the line is "It's right over there."; two words heard differently fall below FOLLOW_MIN
    engine, rp_id, user_idx = engine_with_rp
    fake_whisper.text = "It's light over hair."
    ev = await run(engine, rp_id, user_idx, speech_bytes)
    assert ev[0]["followed"] is False
    issues = fake_claude.aside_calls[-1]["issues"]
    assert [(i["target"], i["heard"]) for i in issues] == [("right", "light"), ("there", "hair")]
    assert set(issues[0]["sound"]) == {"R", "L"} and issues[0]["explain"]
    assert ev[-1]["issues"] == 2


async def test_auto_language_not_korean_keeps_english(engine_with_rp, speech_bytes, fake_whisper, fake_claude):
    engine, rp_id, user_idx = engine_with_rp
    fake_whisper.text = "Can I get a latte instead?"
    fake_whisper.auto_text, fake_whisper.auto_lang = "Can I get a latte instead?", "english"
    ev = await run(engine, rp_id, user_idx, speech_bytes)
    assert ev[0]["text"] == "Can I get a latte instead?" and fake_claude.aside_calls[-1]["heard_ko"] is None


async def test_earlier_asides_on_the_line_go_to_claude(engine_with_rp, speech_bytes, fake_whisper, fake_claude):
    engine, rp_id, user_idx = engine_with_rp
    fake_whisper.text = "Wait, let me try that again."
    for _ in range(4):
        await run(engine, rp_id, user_idx, speech_bytes)
    earlier = fake_claude.aside_calls[-1]["earlier"]
    assert len(earlier) == 3 and earlier[-1] == ("Wait, let me try that again.",
                                                  "괜찮아요, 말이 꼬일 수 있어요. 다시 해 볼까요?")


async def test_aside_claude_down_says_the_fixed_phrase(engine_with_rp, speech_bytes, fake_whisper, fake_claude):
    engine, rp_id, user_idx = engine_with_rp
    fake_whisper.text = "Wait, let me try that again."
    fake_claude.aside_fail_after = 0
    ev = await run(engine, rp_id, user_idx, speech_bytes)
    said = "".join(e["delta"] for e in ev if e["type"] == "text")
    assert said == engine.said("retry_offscript").text
    assert not any(e["type"] == "error" for e in ev) and ev[-1]["type"] == "done"


async def test_aside_claude_cut_midway_ends_with_fixed_phrase(engine_with_rp, speech_bytes, fake_whisper,
                                                             fake_claude):
    engine, rp_id, user_idx = engine_with_rp
    fake_whisper.text = "Wait, let me try that again."
    fake_claude.aside_fail_after = 1
    ev = await run(engine, rp_id, user_idx, speech_bytes)
    said = "".join(e["delta"] for e in ev if e["type"] == "text")
    assert said.startswith("괜찮아요, 말이 꼬일 수 있어요.") and said.endswith(engine.said("retry_offscript").text)
    assert not any(e["type"] == "error" for e in ev) and ev[-1]["type"] == "done"


async def test_both_transcripts_empty_is_no_speech(engine_with_rp, speech_bytes, fake_whisper):
    engine, rp_id, user_idx = engine_with_rp
    fake_whisper.text = ""
    ev = await run(engine, rp_id, user_idx, speech_bytes)
    assert ev[-1]["code"] == "no_speech"
```

`test_attempt.py`의 `test_empty_transcript_is_no_speech`는 그대로 둔다(두 받아쓰기가 다 비면 `no_speech`). `test_misheard_word_is_sent_as_issue`의 `fake_whisper.langs == ["en"]`가 따라 말한 녹음은 한 번만 받아쓴다는 것을 지킨다.

- [ ] **Step 2: 실패를 본다**

Run: `cd server && uv run pytest tests/test_aside.py -v`
Expected: FAIL (`reply` 이벤트가 나오고 `aside_calls`가 비어 있다)

- [ ] **Step 3: `Attempt.aside`를 더하고 계약 예시를 맞춘다**

`models.Attempt`에 `aside: bool = False`를 더한다(주석: 따라 말하지 않아 선생님 라이언이 답한 시도, 차례로 세지 않는다, 2026-11-07 전 시도에는 없다). `contract/roleplay.json`의 시도마다 `"aside": false`를 넣는다.

- [ ] **Step 4: `Engine.attempt`를 고친다**

순서:
1. 지금처럼 녹음을 맥에 두고 WAV로 바꾸고, 길이와 소리 크기를 본다.
2. WAV를 지우기 전에(`finally` 안쪽에서) 영어로 받아쓰고 `followed = bool(words(heard)) and similarity(line.text, heard) >= FOLLOW_MIN`을 정한다. 따라 말하지 않았으면 `self.whisper.transcribe_auto(wav)`로 한 번 더 받아쓴다. 알아낸 언어가 `"korean"`이고 글에 한글(`[가-힣]`)이 있으면 그 글이 `heard_ko`, 아니면 `None`.
3. 보여 줄 들린 말 `shown = heard_ko or heard`. `words(shown)`도 비고 한글도 없으면 지금처럼 `no_speech`.
4. `heard` 이벤트(`text=shown`)를 낸다.
5. 따라 말했으면 지금 길 그대로다.
6. 따라 말하지 않았으면 방식과 관계없이:
   - `issues = find_issues(line.text, heard, limit=2)`. 단, `heard_ko`가 있거나 `words(heard)`가 비면 `[]`.
   - `earlier`: 이 줄의 시도 가운데 `aside`인 것의 최근 3개, `(a.heard, a.say_ko)`.
   - 말할 글: `self.claude.aside(rp.frame, self.history(rp, idx), line.text, heard, heard_ko, issues, earlier)`를 감싼 생성기. 조각을 낸 적 없이 `ClaudeUnavailable`이면 `PHRASES["retry_offscript"]`를 낸다. 조각을 낸 뒤 끊기면 `" "`과 그 정해진 말을 낸다. 이 생성기를 지금의 `self.speak(...)`에 넘긴다.
   - `nxt = idx`.
7. 시도를 저장할 때 `aside=not followed`, `issues=issues`, `heard=shown`. `pos`는 `mode == "turn"`이고 따라 말했고 실패하지 않았을 때만 `nxt`로 옮긴다.
8. 로그 줄은 지금처럼 글 없이 남긴다(`aside=` 값을 더해도 된다).

`reply`, `add_reply`, `point`, `claude.offscript`를 부르던 갈래는 지운다(그 함수들 자체는 Task 4에서 지운다). `elif mode != "turn"`의 정해진 말 갈래도 없어진다.

- [ ] **Step 5: 통과를 본다**

Run: `cd server && uv run pytest tests/test_aside.py tests/test_attempt.py tests/test_contract.py -v`
Expected: PASS. `tests/test_offscript.py`와 옛 길을 쓰는 시험은 여기서 실패할 수 있다. Task 4에서 고친다.

- [ ] **Step 6: 커밋**

```bash
/usr/bin/git add server/je_server/models.py server/je_server/engine.py contract/roleplay.json server/tests/test_aside.py
/usr/bin/git commit -F - <<'EOF'
feat(server): answer off-script recordings as teacher Ryan in every mode

A recording that does not follow the line is transcribed again with the
language auto-detected; a Korean transcript replaces the English one. Ryan
answers in Korean from `Claude.aside` with the Mac's points (at most two)
and the line stays: no reply line, no new script, `pos` unchanged. The try
is kept with `aside=True`. If Claude is down, Ryan says the fixed
`retry_offscript` phrase instead of an error.

Refs: docs/superpowers/specs/2026-11-07-offscript-aside-design.md
EOF
```

### Task 4: 대본을 새로 쓰던 길을 없애고, 선생님에게 한 말을 기록 읽기에서 뺀다

**Files:**
- Modify: `server/je_server/engine.py` (`add_reply`, `_continue`, `continuing`, `left`, `point`, `CLOSING_EN` 지움, `line`·`copy`의 기다림 지움, `history`, `summary`, `progress` docstring)
- Modify: `server/je_server/claude.py` (`offscript`, `continue_script`, `_talk`은 `aside`가 쓰니 남김)
- Modify: `server/je_server/prompts.py` (`OFFSCRIPT_SYSTEM`, `OFFSCRIPT_SCHEMA`, `CONTINUE_SYSTEM`, `CONTINUE_SCHEMA` 지움)
- Modify: `server/je_server/models.py` (`Offscript` 지움)
- Modify: `server/je_server/review.py` (`spoken`)
- Modify: `server/tests/fakes.py` (`offscript`, `continue_script`, `offscript_out`, `fail_continue`, `continue_gate` 지움)
- Modify: `contract/attempt-events.ndjson` (`reply` 줄 지움)
- Delete: `server/tests/test_offscript.py`
- Modify: `server/tests/test_engine.py`, `server/tests/test_summary.py`, `server/tests/test_claude.py`, `server/tests/test_review.py`

**Interfaces:**
- Consumes: `Attempt.aside` (Task 3)
- Produces: `Engine.history(rp, upto)`는 `aside` 시도를 보지 않는다. `Engine.summary`의 `tries`는 `mode in ("turn", "retry") and not a.aside`. `review.spoken`은 `aside` 시도를 세지 않는다.

- [ ] **Step 1: 실패하는 시험을 쓴다**

`server/tests/test_summary.py`에:

```python
async def test_aside_is_not_on_the_end_screen(engine_with_rp, speech_bytes, fake_whisper):
    engine, rp_id, user_idx = engine_with_rp
    fake_whisper.text = "Wait, let me try that again."
    await run(engine, rp_id, user_idx, speech_bytes)
    assert tries(engine.summary(rp_id), user_idx) == []


async def test_aside_after_issue_keeps_closing_retry(engine_with_rp, speech_bytes, fake_whisper):
    engine, rp_id, user_idx = engine_with_rp
    fake_whisper.text = "It's light over there."
    await run(engine, rp_id, user_idx, speech_bytes)
    fake_whisper.text = "Wait, let me try that again."
    await run(engine, rp_id, user_idx, speech_bytes, "retry")
    s = engine.summary(rp_id)
    assert len(tries(s, user_idx)) == 1 and s["say"] == engine.said("closing_retry").model_dump()


async def test_old_offscript_try_still_shows_its_point(engine_with_rp):
    # records from before 2026-11-07: a turn said differently, with Ryan's point and no aside mark
    from je_server.models import Attempt

    engine, rp_id, user_idx = engine_with_rp
    await engine.save_attempt(rp_id, user_idx, Attempt(n=1, mode="turn", heard="I have no idea.", followed=False,
                                                       issues=[], say_ko="이럴 때는 I'm not sure도 좋아요.",
                                                       audio=[], timings={}), None)
    [t] = tries(engine.summary(rp_id), user_idx)
    assert t["followed"] is False and t["point_ko"] == "이럴 때는 I'm not sure도 좋아요."
```

`server/tests/test_engine.py`에:

```python
async def test_history_skips_asides(engine_with_rp, speech_bytes, fake_whisper):
    engine, rp_id, user_idx = engine_with_rp
    fake_whisper.text = "Wait, let me try that again."
    [e async for e in engine.attempt(rp_id, user_idx, speech_bytes, "turn")]
    rp = engine.store.load(rp_id)
    assert engine.history(rp, user_idx + 1)[-1] == ("user", rp.lines[user_idx].text)
```

`server/tests/test_review.py`에, 이 파일의 기록 만드는 도우미를 써서: `aside=True` 시도만 있는 역할극은 `spoken`이 `False`이고 `past_items`에 없다(`test_aside_only_run_is_not_a_past_situation`).

- [ ] **Step 2: 실패를 본다**

Run: `cd server && uv run pytest tests/test_summary.py tests/test_engine.py tests/test_review.py -v`
Expected: 새 시험 FAIL(시도가 끝 화면과 대화 흐름에 들어간다)

- [ ] **Step 3: 기록 읽기에서 `aside`를 뺀다**

`Engine.history`의 `turns`, `Engine.summary`의 `tries`, `review.spoken`에서 `a.aside`인 시도를 뺀다. `summary`의 `point_ko` 줄은 옛 시도를 위해 남긴다.

- [ ] **Step 4: 대본을 새로 쓰던 길을 지운다**

위 Files 목록대로 지운다. `Engine.line`과 `Engine.copy` 맨 앞의 `continuing` 기다림, `__init__`의 `self.continuing`, `self.left`를 지운다. `progress` docstring의 「A rebuild that failed …」 문장을 「Old records may end with fewer learner lines after a failed rebuild, so no is kept within total.」로 고친다. 엔진의 `sounds`, `sound_pairs` import가 쓰이지 않으면 지운다(`compare.sound_pairs` 함수는 남긴다).

옛 길을 쓰던 시험을 고친다:
- `test_offscript.py`를 지운다(새 동작은 `test_aside.py`가 맡는다).
- `test_claude.py`의 `offscript` 시험 넷(`test_offscript_uses_sonnet_and_sends_what_was_said`, `test_offscript_empty_reply_is_unavailable`, 180줄 근처, `test_offscript_reply_drops_stray_braces`)과 `continue_script` 시험을 지운다. 대본의 괄호 지우기(`_spoken`)는 `make_script` 시험이 지킨다.
- `test_summary.py`의 `test_offscript_try_carries_ryans_point`, `test_retry_said_differently_has_no_point`, `test_pronunciation_point_is_not_repeated`를 지운다(Step 1의 옛 기록 시험이 대신한다).
- `test_engine.py`: `test_progress_never_passes_total`, `test_copy_keeps_reply_lines_in_order`, `test_ko_of_a_reply_sees_what_was_said_and_does_not_wait_for_the_rebuild`는 `add_reply`나 다시 쓰기 대신 옛 기록을 직접 만든다. `engine.store.load` → `rp.lines`를 `ScriptLine(kind="reply")`가 든 모양으로 바꾸고 `aside` 없는 시도를 넣고 → `engine.store.save`. 지키는 것은 그대로다: 진행 숫자가 total을 넘지 않음, 복사가 대답 줄을 차례대로 지님, 대답 줄의 통역이 실제로 한 말을 앞 말로 봄.
- `test_review.py:79` `test_first_try_skips_offscript_and_ryan`은 그대로 통과해야 한다.

- [ ] **Step 5: 서버 시험 전체를 돌린다**

Run: `cd server && uv run pytest`
Expected: 모두 PASS. `grep -rn "offscript\|continue_script\|add_reply\|CONTINUE_\|OFFSCRIPT_" server/je_server`가 `retry_offscript`(정해진 말 이름)만 찾는다.

- [ ] **Step 6: 커밋**

```bash
/usr/bin/git add server/je_server/engine.py server/je_server/claude.py server/je_server/prompts.py server/je_server/models.py server/je_server/review.py server/tests/fakes.py server/tests/test_engine.py server/tests/test_summary.py server/tests/test_claude.py server/tests/test_review.py contract/attempt-events.ndjson
/usr/bin/git rm server/tests/test_offscript.py
/usr/bin/git commit -F - <<'EOF'
refactor(server): drop the script rebuild and keep asides out of records

The script is given to be followed, so a line said differently no longer
gets an in-role reply and a rewritten rest (user, spec offscript-aside).
`offscript`, `continue_script`, `add_reply` and the `reply` event go.
Aside tries stay out of the end screen, its closing words, the
conversation history and the past-situation list; old records with reply
lines and unmarked tries read as before.

Refs: docs/superpowers/specs/2026-11-07-offscript-aside-design.md
EOF
```

### Task 5: 앱이 선생님에게 한 말 뒤에 「다시 해 보기」만 보여 준다

**Files:**
- Modify: `app/src/api/types.ts` (`Attempt.aside`, `AttemptEvent`와 `EVENT_TYPES`에서 `reply` 지움)
- Modify: `app/src/flow/state.ts` (`State.aside`, `reply` 지움)
- Modify: `app/src/screens/RoleplayScreen.tsx`
- Test: `app/src/flow/state.test.ts`, `app/src/api/contract.test.ts`(그대로 통과)

**Interfaces:**
- Consumes: 서버의 `heard` 이벤트 `followed`, `done.next` (Task 3)
- Produces: `State.aside: boolean` — 지금 차례가 선생님에게 한 말이면 `true`. `freshTurn`이 `false`로 돌린다. `initial.aside = false`.

- [ ] **Step 1: 실패하는 시험을 쓴다** (`app/src/flow/state.test.ts`, 이 파일의 상태 만드는 도우미를 쓴다)

```ts
test("an aside offers only 다시 해 보기 and leaves no bubbles", () => {
  let s = at("evaluating"); // a roleplay turn being evaluated, mode "turn", idx 1
  s = reduce(s, { type: "event", e: { type: "heard", text: "다시 할게요", followed: false } });
  s = reduce(s, { type: "event", e: { type: "text", delta: "괜찮아요. 다시 해 볼까요?" } });
  s = reduce(s, { type: "event", e: { type: "done", next: 1, issues: 0 } });
  expect(s.phase).toBe("evaluated");
  expect(s.aside).toBe(true);
  expect(reduce(s, { type: "next" })).toBe(s);
  const again = reduce(s, { type: "again" });
  expect(again.history).toEqual(s.history);
  expect(again.mode).toBe("turn");
  expect(again.aside).toBe(false);
  expect(again.feedback).toBe("");
  expect(again.heard).toBeNull();
});

test("aside then follow moves on to the next line", () => {
  let s = at("evaluating");
  s = reduce(s, { type: "event", e: { type: "heard", text: "Wait.", followed: false } });
  s = reduce(s, { type: "event", e: { type: "done", next: 1, issues: 0 } });
  s = reduce(reduce(s, { type: "again" }), { type: "recordStart" });
  s = reduce(s, { type: "recordStop" });
  s = reduce(s, { type: "event", e: { type: "heard", text: "It's right over there.", followed: true } });
  s = reduce(s, { type: "event", e: { type: "done", next: 2, issues: 0 } });
  expect(reduce(s, { type: "next" }).idx).toBe(2);
});

test("an aside in a retry keeps where 다음 goes", () => {
  // followed turn (next 2) → 다시 해 보기 (retry) → aside: 다음 after the next followed retry still goes to 2
  let s = at("evaluating");
  s = reduce(s, { type: "event", e: { type: "heard", text: "It's right over there.", followed: true } });
  s = reduce(s, { type: "event", e: { type: "done", next: 2, issues: 0 } });
  s = reduce(reduce(reduce(s, { type: "again" }), { type: "recordStart" }), { type: "recordStop" });
  s = reduce(s, { type: "event", e: { type: "heard", text: "Wait.", followed: false } });
  s = reduce(s, { type: "event", e: { type: "done", next: 1, issues: 0 } });
  expect(s.nextIdx).toBe(2);
  expect(reduce(s, { type: "again" }).mode).toBe("retry");
});
```

`at(phase)`는 이 파일에 이미 있는 도우미다(사용자 줄 idx 1, 방식 `turn`). `reply` 이벤트를 쓰던 시험 둘(63줄 「a reply line is shown and next skips past it」, 110줄 「again after an off-script turn keeps Ryan's reply in the conversation」)은 지운다. 407줄의 `kind: "reply"` 줄로 `practiceFor`를 보는 시험은 옛 기록을 위해 남긴다.

- [ ] **Step 2: 실패를 본다**

Run: `cd app && npm test -- state`
Expected: FAIL (`aside`가 없고, `next`가 막히지 않는다)

- [ ] **Step 3: 상태를 고친다** (`app/src/flow/state.ts`)

- `State`에 `aside: boolean`(주석: 따라 말하지 않아 선생님 라이언이 답한 차례, 스펙 offscript-aside 5). `initial`과 `freshTurn`에 `aside: false`.
- `heard` 이벤트: `aside: !e.followed`.
- `done` 이벤트: `s.aside`면 `nextIdx`를 건드리지 않는다. 아니면 지금 그대로.
- `again`: `s.aside`면 `{ ...s, ...freshTurn, phase: "ready" }`(대화에 남기지 않고 방식도 바꾸지 않음). 아니면 지금 그대로.
- `next`: `s.aside`면 `s`를 그대로 돌려준다.
- `reply` 필드, `reply` 이벤트 처리, `exchange`의 `reply` 줄을 지운다.

- [ ] **Step 4: 타입과 화면을 고친다**

- `types.ts`: `Attempt`에 `aside?: boolean`(2026-11-07 전 시도에는 없다). `AttemptEvent`와 `EVENT_TYPES`에서 `reply`를 지운다.
- `RoleplayScreen.tsx`: `onEvent`의 `reply` 소리, `lineAt`의 `state.reply`, `state.reply` 말풍선을 지운다. 평가 뒤 버튼 줄은 `state.aside`면 「다시 해 보기」 하나만(기본 버튼 모양, `kind="plain"` 아님), 아니면 지금처럼 둘이다.

- [ ] **Step 5: 앱 시험과 타입 검사를 돌린다**

Run: `cd app && npm test && npm run typecheck`
Expected: 모두 PASS, 타입 오류 0

- [ ] **Step 6: 커밋**

```bash
/usr/bin/git add app/src/api/types.ts app/src/flow/state.ts app/src/flow/state.test.ts app/src/screens/RoleplayScreen.tsx
/usr/bin/git commit -F - <<'EOF'
feat(app): show only 다시 해 보기 after teacher Ryan's answer

When the heard event says the line was not followed, the evaluated turn
offers only 「다시 해 보기」; pressing it clears what was said and Ryan's
answer instead of keeping them as bubbles, and keeps the mode, so a first
turn stays a turn and 「다음」 goes on after the line is followed. The
`reply` event and bubble go with the server's script rebuild.

Refs: docs/superpowers/specs/2026-11-07-offscript-aside-design.md
EOF
```

### Task 6: 실제 Sonnet으로 지시문 확인 (돈이 드는 호출)

**Files:**
- Create: 이 세션의 스크래치패드 폴더의 `aside_check.py` (저장소에 넣지 않는다)
- Modify(필요하면): `server/je_server/prompts.py` (`ASIDE_SYSTEM`)

- [ ] **Step 1: 사용자에게 수와 비용을 말하고 허락을 받는다**

「지어낸 말 10개로 소넷을 10번 부르고, 한 번에 0.1~0.4센트, 다 합해 4센트 안쪽」이라고 말한다. 허락 전에는 돌리지 않는다.

- [ ] **Step 2: 스크립트를 쓴다**

원래 폴더의 `server/.env`에서 키를 읽어(`je_server.config`의 읽는 법을 따른다) `anthropic.AsyncAnthropic`과 `Claude(client, writer=WRITERS["sonnet"])`를 만들고, 지어낸 상황 하나(길 묻기)와 대사 "It's right over there."로 아래 10개를 `Claude.aside`에 넣어 답을 찍는다. 들린 말은 모두 지어낸 것이다.
1. 낱말 둘이 다르게 들린 따라 말하기("It's light over hair.", 짚을 것 둘, R/L 설명 포함)
2. 말이 꼬임("It's right, uh, sorry")
3. 다시 하겠다는 영어("Wait, let me try that again.")
4. 다시 하겠다는 한국어(heard_ko "잠깐만요, 다시 할게요")
5. 뜻을 묻는 한국어(heard_ko "이게 무슨 뜻이에요?")
6. 무엇이라고 말하면 되는지 묻는 한국어(heard_ko "뭐라고 대답해야 돼요?")
7. 소리를 묻는 한국어(heard_ko "right 발음은 어떻게 해요?")
8. 상황에 맞는 다른 영어("Go straight, it's on your left.")
9. 영어로 한 요청("Can you say it slower?")
10. 앞의 답에 이어 묻기(5의 답을 `earlier`에 넣고 heard_ko "그럼 over는요?")

- [ ] **Step 3: 답을 규칙과 견준다**

10개 모두: 한국어 해요체, 영어 대답 없음, 지어낸 칭찬 없음, 소리 설명은 받은 것만(7은 「읽는 법 보기」), 자료 이름 없음, 같은 대사를 다시 해 보자고 끝남, 길이. 1은 두 곳을 「~처럼 들렸어요」로 짚는다. 어긋나면 `ASIDE_SYSTEM`을 고치고 어긋난 것만 다시 돌린다(다시 돌리는 수도 사용자에게 말한다). 들린 말과 답 원문은 공개 파일에 쓰지 않고, devlog에는 「10번 중 몇 번 규칙대로」처럼 수만 쓴다.

- [ ] **Step 4: 지시문을 고쳤으면 시험을 돌리고 커밋한다**

Run: `cd server && uv run pytest tests/test_claude.py -v`
Expected: PASS

```bash
/usr/bin/git add server/je_server/prompts.py
/usr/bin/git commit -F - <<'EOF'
fix(server): tighten teacher Ryan's prompt after a live Sonnet check

Refs: docs/superpowers/specs/2026-11-07-offscript-aside-design.md
EOF
```

(본문에 무엇이 어긋났고 몇 번 중 몇 번이 규칙대로였는지 쓴다.)

### Task 7: PRD, 앞선 스펙, 가이드를 고친다

**Files:**
- Modify: `docs/PRD.md`
- Modify: `docs/superpowers/specs/2026-11-05-speaking-practice-design.md`
- Modify: `docs/superpowers/specs/2026-11-05-roleplay-practice-design.md`
- Modify: `docs/guide/SPEECH_맥서버_받아쓰기와_목소리_20261105.md`, `docs/guide/README.md`(목록 줄)

- [ ] **Step 1: PRD를 고친다**

스펙 「8. 고칠 문서」대로:
- 「상황 역할극」: 「따라 할지 다르게 말할지는 사용자 마음이다. 다르게 말하면 … 남은 대본을 거기에 맞춰 새로 만든다」를 「대본은 따라 말하라고 준 것이라 바꾸지 않는다. 대사와 다르게 말하면 선생님 라이언이 한국어로 그 말에 맞게 답하고 같은 대사를 다시 하게 한다」로 바꾼다. 2026-11-07 사용자가 옛 문장을 「내 말에 오해가 있는 상황에서 작성되고 내가 그냥 넘어간듯하네」라고 한 것과 스펙 경로를 적는다.
- 「평가」의 「사용자가 다르게 말했거나 자유 대화일 때는 …」: 역할극과 복습에서는 위 선생님의 답이 맡고, 따라 말하려다 다르게 들린 낱말은 맥이 찾아 짚는다(많아야 두 가지)는 것을 적는다. 자유 대화 부분은 그대로 둔다.
- 「말이 막혔을 때」: 역할극에서 한국어로 물으면 선생님 라이언이 화면의 대사를 말하면 된다고 답한다는 것을 더한다.

- [ ] **Step 2: 앞선 스펙에 바뀐 곳을 적는다**

- 말하기 스펙 「역할극의 한 차례」 5와 6, 「맞댈 문장이 없을 때」의 역할극 부분 첫머리에 「2026-11-07 바뀜: `docs/superpowers/specs/2026-11-07-offscript-aside-design.md`. 대본은 바꾸지 않고 선생님 라이언이 답한다」 한 줄을 넣는다. 본문은 지우지 않는다(옛 결정의 기록).
- 역할극 뒤 연습 스펙의 1, 2, 3, 4, 5, 6, 9에서 다르게 말한 차례를 다룬 곳에 「2026-11-07부터 새 역할극에는 대답 줄이 생기지 않는다. 옛 기록은 그대로 보인다(offscript-aside 스펙 6)」를 적는다.

- [ ] **Step 3: SPEECH 가이드를 더한다**

「겪은 문제」에 한 절: 증상(한국어로 말한 차례가 「잘 안 들렸어요」로 끝남), 원인(받아쓰기 언어를 영어로 정하면 whisper large-v3가 한국어를 영어로 번역해 적거나 한글을 그대로 낸다. 2026-11-07 앱의 정해진 말 다섯 개를 라이언 목소리로 만든 소리로 시험해 넷은 번역, 하나는 한글), 고친 것(스펙 2: 영어 먼저, 따라 말하지 않았으면 `language=auto`와 `response_format=verbose_json`으로 다시, `language`가 korean이고 한글이 있으면 그 글), 확인 방법(whisper-server에 같은 WAV를 `en`과 `auto`로 보내 `text`와 `language`를 본다, 자동 받아쓰기는 0.8초쯤), 같은 실수를 막는 법(받아쓰기 언어를 하나로 정하면 다른 언어로 한 말이 번역되어 들어와 맞는 말처럼 보일 수 있다). `docs/guide/README.md`의 SPEECH 줄에 「영어로 정한 받아쓰기가 한국어를 번역해 적는 문제」를 더한다.

- [ ] **Step 4: 커밋**

```bash
/usr/bin/git add docs/PRD.md docs/superpowers/specs/2026-11-05-speaking-practice-design.md docs/superpowers/specs/2026-11-05-roleplay-practice-design.md
/usr/bin/git commit -F - <<'EOF'
docs(prd): keep the given script and let teacher Ryan answer off-script speech

Refs: docs/superpowers/specs/2026-11-07-offscript-aside-design.md
EOF
/usr/bin/git add "docs/guide/SPEECH_맥서버_받아쓰기와_목소리_20261105.md" docs/guide/README.md
/usr/bin/git commit -F - <<'EOF'
docs(guide): add forced-English transcription translating Korean speech

Refs: docs/superpowers/specs/2026-11-07-offscript-aside-design.md
EOF
```

(PRD 커밋 본문에 사용자 결정과 이유를 쓴다.)

### Task 8: 폰에서 확인할 준비 (APK와 서버)

이 작업은 구현 뒤 PR을 열고 리뷰한 다음에 한다(AGENTS.md 「PR마다」). 계획에 넣어 순서를 정해 둔다.

- [ ] **Step 1: 서버를 바꿔 띄우기 전에 묻는다**

`server/scripts/autostart.sh status`를 보고, `state`가 running이 아니면 `ListAgents`로 review-screens 카드를 확인하고 사용자에게 알린다. 사용자에게 「지금 폰으로 쓰는 중인지」 묻고, 괜찮다고 하면 `docs/guide/DEVENV_맥서버_저절로_띄우기_20261107.md` 「카드가 서버를 시험할 때」 순서로 worktree 서버를 띄운다.

- [ ] **Step 2: APK를 빌드해 깐다**

`app/README.md`대로: 원래 폴더의 `app/.env`를 복사하고, `export JAVA_HOME="$(/usr/libexec/java_home -v 17)"`, `-PreactNativeArchitectures=arm64-v8a`. adb는 PATH에 없으니 `app/README.md`대로 SDK의 `platform-tools/adb`를 부르고, 폰은 USB 쪽(이름에 `:`이 없고 `emulator-`가 아닌 것)을 `-s`로 고른다. 깔기 전에 「offscript-aside 카드의 APK이고 다른 카드의 APK를 덮는다」고 사용자에게 알린다.

- [ ] **Step 3: 사용자에게 폰에서 볼 것을 알린다**

역할극에서: 한국어로 묻기, 말이 꼬여 다시 하겠다고 하기, 상황에 맞는 다른 영어로 말하기, 일부러 낱말 하나둘 틀리게 따라 말하기. 각각 라이언이 한국어로 답하는지, 「다시 해 보기」만 나오는지, 누르면 그 말과 답이 사라지는지, 다시 따라 말하면 「다음」으로 가는지, 끝 화면에 그 말이 없는지. 복습(끝난 뒤 「내 대사 다시 연습」)에서 한국어로 묻기.

- [ ] **Step 4: 시험이 끝나면 서버를 되돌린다**

worktree 서버의 `uv` 프로세스를 끄고 `server/scripts/autostart.sh start`.

## 마무리 (계획 밖, AGENTS.md 흐름)

- Task 1~7을 마치면 superpowers의 마지막 리뷰를 거쳐 push하고 PR을 연다. 그다음 pr-review로 리뷰하고, 고칠 것을 고친 뒤 devlog(`docs/devlog/2026-11-07-offscript-aside.md`)를 쓴다. Task 8은 그 뒤에 한다.
- 할 일 파일 `docs/todo/20261107_07_todo_offscript_aside_and_korean.md`는 원래 폴더에서 이 worktree로 복사하고, 상태 줄을 「완료」로 고쳐 이 일을 끝내는 마지막 커밋(devlog 커밋)에 함께 넣는다. 「할 일」 1의 역할극 속 말과 밖의 말 가르기는 사용자 결정으로 하지 않게 됐다고 적는다.
