# 자유 대화: 한국어 질문을 한국어일 확률로 가려내기 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 자유 대화의 「🎤 말하기」로 한 한국어가 영어로 옮겨져 받아써져도, 받아쓰기가 준 한국어일 확률이 0.98 이상이면 한국어로 다시 받아써 한국어 차례로 다룬다.

**Architecture:** 맥 서버만 고친다. `Whisper`에 영어로 고정해 받아쓰면서 언어별 확률(`verbose_json`의 `language_probabilities`)에서 한국어 값을 함께 돌려주는 메서드를 더한다. `Talks._hear`가 그것을 써서 「한글이 섞임 또는 한국어일 확률 ≥ 0.98」이면 한국어로 다시 받아쓴다. 그다음은 지금의 한국어 차례 길(`kind "ask"`, `TALK_KOREAN`, 고쳐 주기에서 뺌) 그대로다. 앱은 서버가 보내는 `korean`과 글만 쓰므로 바꾸지 않는다.

**Tech Stack:** Python 3.12, httpx, pytest(`cd server && uv run pytest -q`).

**Spec:** `docs/superpowers/specs/2026-11-08-free-talk-design.md` 「잰 것」의 「한국어 질문의 뜻과 한국어일 확률」, 3 「영어로 번역되어 나오면」, 「확인 방법」의 「한국어 질문의 뜻에서 더 하는 것」, 「한계」.

## Global Constraints

- 기준값은 `0.98`이고, 같거나 크면 한국어다(스펙 3).
- 확률이 오지 않으면(키가 없거나, 한국어 값이 없거나, 숫자가 아님) `0.0`으로 보고 영어 차례로 다룬다(스펙 3).
- 로그에는 시간, 개수, 확률 숫자만 남긴다. 받아쓴 글과 라이언의 답은 남기지 않는다(`REVIEW.md` 「녹음 처리」).
- 공개 저장소: 시험 문장은 지어낸다. 학습자 목소리 녹음과 그것을 받아쓴 글, 폰 시험에서 들린 글은 시험, 주석, 커밋 메시지에 쓰지 않는다(`REVIEW.md` 「공개 저장소 노출」).
- 커밋: Conventional Commits 영어, 제목 72자 안쪽, AI 서명 없음. `git`은 `/usr/bin/git`으로 부르고, 파일을 지정해 `git add`하고, 커밋을 이을 때는 `&&`로 잇는다.
- talk-resay 카드가 같은 `talk.py`를 고친다. `_hear`와 `_turn`의 로그 줄 밖은 건드리지 않는다.

## Review Focus

1. whisper-server가 확률 없이 답한다(옛 판, `-nlp`로 띄움, 영어 녹음이라 한국어가 목록에 없음): 영어 차례로 다루고 멈추지 않는다(작업 1 `test_transcribe_english_without_probabilities_is_zero`, `test_transcribe_english_without_korean_is_zero`).
2. 확률로 한국어라 했는데 한국어로 다시 받아쓰기가 실패한다: 영어 글을 보이고 영어 차례로 다룬다. 한글이 없는 글에 「(in Korean)」이 붙지 않는다(작업 2 `test_korean_by_probability_falls_back_to_english_when_korean_fails`).
3. 확률로 한국어라 했는데 한국어 받아쓰기에 한글이 없다(영어를 한국어로 고정했을 때 영어 글이 그대로 나오는 경우): 영어 차례로 다룬다(작업 2 `test_korean_by_probability_without_hangul_stays_english`).
4. 기준값 바로 위아래(0.98, 0.979): 0.98은 한국어, 0.979는 영어(작업 2 `test_korean_probability_at_the_bar`).
5. 로그에 확률 숫자는 남고 받아쓴 글은 남지 않는다(작업 2 `test_turn_log_has_times_and_counts_only` 고침).

---

### Task 1: 영어로 받아쓰며 한국어일 확률도 받기

**Files:**
- Modify: `server/je_server/asr.py`(모듈 설명, 새 메서드)
- Modify: `server/tests/fakes.py`(`FakeWhisper`)
- Test: `server/tests/test_asr.py`

**Interfaces:**
- Produces: `Whisper.transcribe_english(wav: Path) -> tuple[str, float]`: 영어로 고정한 받아쓰기 글(`_clean`을 거친 것)과 한국어일 확률. `_infer(wav, "en", "verbose_json")` 한 번이다. 확률은 `language_probabilities["ko"]`이고, 없거나 숫자가 아니면 `0.0`이다. 실패는 지금처럼 `WhisperError`.
- Produces: `FakeWhisper.transcribe_english(wav)`: `calls`를 하나 늘리고 `langs`에 `"en"`을 더한다(그래서 `langs == ["en", "ko"]`인 지금 시험이 그대로 맞다). `fail_lang == "en"`이면 `WhisperError`. 글은 `by_lang.get("en", text)`, 확률은 새 속성 `korean_p`(기본 `0.0`).

- [ ] **Step 1: 실패하는 시험을 쓴다** (`server/tests/test_asr.py`)

```python
async def test_transcribe_english_returns_text_and_korean_probability(tmp_path):
    seen = {}

    def handler(request: httpx.Request):
        seen["body"] = request.read()
        return httpx.Response(200, json={"text": " Is the bakery open today? [BLANK_AUDIO]\n", "language": "english",
                                         "language_probabilities": {"ko": 0.993, "en": 0.004}})

    wav = tmp_path / "a.wav"
    wav.write_bytes(b"RIFF")
    assert await whisper_with(handler).transcribe_english(wav) == ("Is the bakery open today?", 0.993)
    assert b"\r\n\r\nen\r\n" in seen["body"] and b"verbose_json" in seen["body"]


async def test_transcribe_english_without_probabilities_is_zero(tmp_path):
    # a whisper-server started with -nlp, or an older one
    wav = tmp_path / "a.wav"
    wav.write_bytes(b"RIFF")
    w = whisper_with(lambda r: httpx.Response(200, json={"text": "I had pizza."}))
    assert await w.transcribe_english(wav) == ("I had pizza.", 0.0)


async def test_transcribe_english_without_korean_is_zero(tmp_path):
    wav = tmp_path / "a.wav"
    wav.write_bytes(b"RIFF")
    for probs in ({"en": 0.97}, {"ko": "high"}, None, []):
        w = whisper_with(lambda r, p=probs: httpx.Response(200, json={"text": "Hi.", "language_probabilities": p}))
        assert await w.transcribe_english(wav) == ("Hi.", 0.0)
```

- [ ] **Step 2: 실패를 본다**

Run: `cd server && uv run pytest -q tests/test_asr.py`
Expected: 새 시험 셋이 `AttributeError: 'Whisper' object has no attribute 'transcribe_english'`로 실패.

- [ ] **Step 3: `Whisper.transcribe_english`를 `server/je_server/asr.py`에 쓰고, `FakeWhisper`에 같은 이름과 `korean_p`를 더한다**

모듈 설명에 「자유 대화는 영어로 고정해 받아쓰며 한국어일 확률도 받는다(free-talk 스펙 3)」를 더한다. `bool`은 숫자로 치지 않는다(`isinstance(x, (int, float)) and not isinstance(x, bool)`).

- [ ] **Step 4: 통과를 본다**

Run: `cd server && uv run pytest -q tests/test_asr.py`
Expected: 모두 통과.

- [ ] **Step 5: 커밋**

```bash
/usr/bin/git add server/je_server/asr.py server/tests/fakes.py server/tests/test_asr.py
/usr/bin/git commit -F - <<'EOF'
feat(server): return the korean probability with an english transcript
...
EOF
```

### Task 2: 자유 대화가 한국어일 확률로 한국어 차례를 가린다

**Files:**
- Modify: `server/je_server/talk.py`(`KOREAN_P`, `_hear`, `_turn`의 로그 줄, 모듈 설명)
- Modify: `docs/superpowers/specs/2026-11-08-free-talk-design.md` 3(한국어 받아쓰기에 한글이 없을 때 한 줄)
- Test: `server/tests/test_talk.py`

**Interfaces:**
- Consumes: `Whisper.transcribe_english(wav) -> tuple[str, float]`, `FakeWhisper.korean_p`(작업 1).
- Produces: `talk.KOREAN_P = 0.98`. `Talks._hear(...) -> tuple[str, bool, float]`(보일 글, 한국어인지, 한국어일 확률). `_turn`만 부른다.

`_hear`의 판단(스펙 3):

- 영어 받아쓰기에 한글이 있으면: 지금과 같다. 한국어로 다시 받아쓰고, 실패하면 영어 글을 보이되 한국어 차례로 둔다.
- 한글이 없고 확률 ≥ `KOREAN_P`이면: 한국어로 다시 받아쓴다. 다시 받아쓴 글에 한글이 있으면 그 글로 한국어 차례. 실패하거나 한글이 없으면 영어 글로 영어 차례(실패는 지금처럼 `log.info("korean transcription failed: %s", e)`).
- 둘 다 아니면 영어 차례.

- [ ] **Step 1: 실패하는 시험을 쓴다** (`server/tests/test_talk.py`, 지어낸 문장만)

```python
async def test_korean_by_probability_is_heard_again_in_korean(talks, engine, speech_bytes, fake_whisper, fake_claude):
    # Korean the English transcript translated: no Hangul, but whisper says it is Korean
    fake_whisper.by_lang = {"en": "How do you say I went to the river?", "ko": "강가에 갔다는 말은 어떻게 해요?"}
    fake_whisper.korean_p = 0.995
    rp = await talks.create()
    ev = await run(talks, rp.id, speech_bytes)
    assert fake_whisper.langs == ["en", "ko"]
    assert ev[0] == {"type": "heard", "text": "강가에 갔다는 말은 어떻게 해요?", "n": 1, "idx": 1, "korean": True}
    assert [l.kind for l in engine.load(rp.id).lines[1:]] == ["ask", "reply"]
    assert fake_claude.talk_calls[-1][-1]["content"] == TALK_KOREAN + "강가에 갔다는 말은 어떻게 해요?"


async def test_korean_probability_at_the_bar(talks, engine, speech_bytes, fake_whisper):
    fake_whisper.by_lang = {"en": "I like rainy days.", "ko": "비 오는 날이 좋아요."}
    for p, korean in ((0.98, True), (0.979, False)):
        fake_whisper.korean_p = p
        fake_whisper.langs = []
        rp = await talks.create()
        ev = await run(talks, rp.id, speech_bytes)
        assert ev[0]["korean"] is korean
        assert fake_whisper.langs == (["en", "ko"] if korean else ["en"])


async def test_korean_by_probability_falls_back_to_english_when_korean_fails(talks, engine, speech_bytes,
                                                                            fake_whisper, fake_claude):
    fake_whisper.by_lang = {"en": "I like rainy days."}
    fake_whisper.korean_p = 0.99
    fake_whisper.fail_lang = "ko"
    rp = await talks.create()
    ev = await run(talks, rp.id, speech_bytes)
    assert ev[0] == {"type": "heard", "text": "I like rainy days.", "n": 1, "idx": 1, "korean": False}
    assert engine.load(rp.id).lines[1].kind == "turn"
    assert fake_claude.talk_calls[-1][-1]["content"] == "I like rainy days."


async def test_korean_by_probability_without_hangul_stays_english(talks, engine, speech_bytes, fake_whisper):
    fake_whisper.by_lang = {"en": "I like rainy days.", "ko": "I like rainy days."}
    fake_whisper.korean_p = 0.99
    rp = await talks.create()
    ev = await run(talks, rp.id, speech_bytes)
    assert ev[0] == {"type": "heard", "text": "I like rainy days.", "n": 1, "idx": 1, "korean": False}
    assert engine.load(rp.id).lines[1].kind == "turn"
```

`test_turn_log_has_times_and_counts_only`(지금 있음)에 `fake_whisper.korean_p = 0.25`를 두고 `f"korean=False korean_p=0.250 "`이 로그에 있는지 더한다. 그 시험의 「글이 로그에 없다」 확인은 그대로 둔다.

- [ ] **Step 2: 실패를 본다**

Run: `cd server && uv run pytest -q tests/test_talk.py`
Expected: 새 시험 넷과 로그 시험이 실패(`korean`이 `False`이거나 `langs`에 `"ko"`가 없음, 로그에 `korean_p`가 없음). 다른 시험은 통과.

- [ ] **Step 3: `talk.py`를 고친다**

`KOREAN_P = 0.98`(스펙 3의 까닭을 짧은 주석으로). `_hear`는 위 판단대로 `transcribe_english`를 쓰고 `(shown, korean, korean_p)`를 돌려준다. `_turn`의 로그 줄은 `korean=%s korean_p=%.3f helped=%s …` 차례다. 모듈 설명의 「my Korean turns」에 「Hangul in the English transcript or whisper's Korean probability」를 더한다. 스펙 3의 「한국어로 다시 받아쓰기가 실패하면」 줄에 「다시 받아쓴 글에 한글이 없을 때도」를 더한다.

- [ ] **Step 4: 통과를 본다**

Run: `cd server && uv run pytest -q`
Expected: 모두 통과.

- [ ] **Step 5: 커밋**

```bash
/usr/bin/git add server/je_server/talk.py server/tests/test_talk.py docs/superpowers/specs/2026-11-08-free-talk-design.md
/usr/bin/git commit -F - <<'EOF'
feat(server): hear free-talk turns again in korean by whisper's probability
...
EOF
```

### 시험 (작업 2 뒤, 스펙 「확인 방법」)

- 실제 모델: 뜻을 잃던 꼴의 지어낸 한국어 질문(어떻게 말하는지 묻는 것)을 한국어 차례로 넣은 대화를 Sonnet에 보내, 물은 뜻에 맞게 영어로만 답하는지 본다. `compare_talk_models.py`에 같은 경우가 있으면 그것을 쓴다.
- 녹음: 이 카드의 지어낸 한국어 20개와 영어 8개를 worktree 서버(`JE_PORT=8793`, `JE_WHISPER_PORT=8794`, 녹음을 뺀 데이터 사본)에 `scripts/try_talk.py`로 보내, 한국어 차례가 몇 개인지, 영어가 영어 차례로 남는지, 첫 소리가 얼마나 늦어지는지 잰다.
- 폰: main 세션에 차례를 물은 뒤, 맥 스피커로 튼 한국어 질문이 한국어 차례가 되는지 한 번 본다.
