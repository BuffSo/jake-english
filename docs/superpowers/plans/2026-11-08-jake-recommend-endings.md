# 제이크 추천의 끝말 세 가지 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 제이크 추천 문장의 끝말을 「…상황으로 연습해 보면 어때요?」 하나에서 「…상황을 골라 봤어요.」, 「…상황을 추천해요.」, 「…상황으로 연습해 볼까요?」 셋으로 섞는다. 「볼까요」는 가장 드물게 나온다.

**Architecture:** 맥 서버가 추천마다 끝말 하나를 무게를 두고 골라(`pick_ending`) Claude에 넘기고, Claude는 그 끝말 그대로 문장을 쓴다. 방금 거절한 문장과 같은 끝말은 바로 다시 고르지 않는다. 주제별 예문은 끝말 없이 「…상황」까지만 둬서 한 끝말로 끌리지 않게 한다. Claude 호출은 추천마다 한 번 그대로다.

**Tech Stack:** Python(맥 서버, pytest). 새 꾸러미 없음. 앱은 바꾸지 않는다.

**Spec:** `docs/superpowers/specs/2026-11-07-situation-topics-design.md` 4(제이크 추천)를 이 계획과 함께 고친다. 할 일은 원래 폴더의 `docs/todo/20261108_06_todo_jake_recommend_endings.md`(아직 커밋하지 않은 파일, 마지막 커밋에 「완료」로 넣는다).

## Global Constraints

- 끝말 셋과 무게: 「상황을 골라 봤어요.」 2, 「상황을 추천해요.」 2, 「상황으로 연습해 볼까요?」 1. 끝말은 사용자가 2026-11-08 제이크 목소리로 듣고 골랐다. 글자를 바꾸지 않는다.
- Claude 호출 수를 늘리지 않는다. 끝말을 지키지 않은 답도 다시 묻지 않는다.
- 목록 상황(PR #34의 고정 대본, `topics.Pick`)은 건드리지 않는다.
- 새로 설치하는 것이 없다. 테스트 문장은 지어낸 것을 쓴다(공개 저장소, ADR-0005).
- 커밋은 `/usr/bin/git`, `git commit -F - <<'EOF'`, 앞 커밋이 성공해야 다음이 돌게 `&&`로 잇는다. 첫 줄 72자 이내, 커밋 하나에 type 하나.
- 테스트: 서버 `cd server && uv run pytest -q`.
- 같이 도는 three-line-listen 카드는 주로 앱을 고친다. 이 계획은 서버와 문서만 고치고, 겹치는 PRD는 「상황 정하기」의 제이크 추천 줄만 고친다.

## 정한 것 (AI 판단)

- **고르는 쪽: 서버.** 지시문에 셋을 주고 Claude가 고르게 하면 한쪽으로 쏠리기 쉽고, 「볼까요」를 가장 드물게 하는 비율도 지킬 수 없다. 서버가 고르면 비율이 정해지고, 실제 모델 시험은 끝말을 지키는지만 보면 되어 횟수도 줄어든다(예순 번쯤에서 스무 번쯤). 호출 수는 두 안 모두 한 번이다.
- **바로 되풀이하지 않기:** 앱이 보내는 「방금 거절한 상황」의 마지막 문장(가장 최근)의 끝말은 이번에 고르지 않는다. 「다른 걸로요」를 눌러 연달아 들을 때 같은 끝말이 이어지지 않게 하려는 것이다. 이렇게 해도 「볼까요」가 가장 드물다(오래 누르면 대략 37.5%, 37.5%, 25%).
- **예문:** `Topic.example_ko`를 끝말 없는 「…상황」으로 바꾼다. 문장 모양은 지시문과 끝말이 정한다.
- **끝말을 어긴 답:** 그대로 쓰고 로그에 한 줄 남긴다(문장은 남기지 않는다). 실제 모델 시험에서 어긋남이 나오면 그때 고친다.
  - 실행 중 바뀜: 실제 모델이 다섯 번 어기고, 지시문을 고친 뒤에도 네 번 끝말을 겹쳐 써서, 맥이 알려진 끝말을 걷어 내고 고른 것을 붙이게 했다(`swap_ending`). 스펙 4에 적었다.
- **실제 모델 시험:** 저장소 스크립트(`server/scripts/check_jake_recommend.py`)로 한다. 주제 셋마다 「다른 걸로요」를 일곱 번 누르는 것처럼 스물한 번 부르고, 고른 끝말, 지킨 수, 연달아 같은 끝말, 비용을 낸다. 다음에 추천 지시문을 고치는 카드도 다시 돌릴 수 있게 둔다.
- **실행 방식:** 이 세션이 직접 고친다(executing-plans). 작업이 작고 서버의 추천 한 길 둘레라, 작업마다 새 에이전트를 띄우면 같은 맥락을 다시 읽는 데 더 든다. 끝에 브랜치 전체를 pr-review로 본다.

## Review Focus

- 옛 앱이나 옛 기록의 거절 문장(「…어때요?」로 끝남): 어느 끝말과도 맞지 않으니 셋 다 나올 수 있어야 한다 → Task 1.
- 거절 문장 끝에 공백이 붙어 올 때: 끝말을 알아보고 피해야 한다 → Task 1.
- 모델이 끝말을 지키지 않을 때(예: 「어때요?」로 끝냄): 오류 없이 그 문장으로 추천하고 로그만 남겨야 한다 → Task 2.
- 주제 예문에 끝말이 남아 한쪽으로 끌리는 것: 예문 셋이 「상황」으로 끝나고 끝말이 없어야 한다 → Task 2.
- 끝말이 메시지에만 있고 지시문은 그것을 따르라고 말하지 않는 것: 지시문에 「끝말」을 따르라는 말이 있어야 한다 → Task 2.

---

### Task 1: 끝말 고르기 `pick_ending`

**Files:**
- Modify: `server/je_server/claude.py` (추천 절 위에 상수와 함수)
- Test: `server/tests/test_claude.py`

**Interfaces:**
- Produces: `JAKE_ENDINGS: tuple[tuple[str, int], ...]` (끝말, 무게), `pick_ending(turned_down: Sequence[str], rng: random.Random | None = None) -> str` (`rng`가 없으면 `random` 모듈)

- [ ] **Step 1: Write the failing tests**

```python
def test_endings_are_the_three_the_user_chose():
    assert JAKE_ENDINGS == (("상황을 골라 봤어요.", 2), ("상황을 추천해요.", 2), ("상황으로 연습해 볼까요?", 1))

def test_pick_ending_weights_bolkkayo_least():
    rng = random.Random(7)
    got = Counter(pick_ending([], rng) for _ in range(5000))
    share = {e: got[e] / 5000 for e, _ in JAKE_ENDINGS}
    assert abs(share["상황을 골라 봤어요."] - 0.4) < 0.03 and abs(share["상황을 추천해요."] - 0.4) < 0.03
    assert abs(share["상황으로 연습해 볼까요?"] - 0.2) < 0.03

def test_pick_ending_skips_the_last_turned_down_ending():
    rng = random.Random(3)
    for ending, _ in JAKE_ENDINGS:
        down = ["카페에서 주문하는 상황을 추천해요.", f"공항에서 짐을 찾는 {ending} "]  # last one counts, spaces too
        got = {pick_ending(down, rng) for _ in range(300)}
        assert ending not in got and len(got) == 2

def test_pick_ending_any_after_an_old_form():
    rng = random.Random(5)
    got = {pick_ending(["카페에서 주문하는 상황으로 연습해 보면 어때요?"], rng) for _ in range(300)}
    assert got == {e for e, _ in JAKE_ENDINGS}
```

- [ ] **Step 2: Run to verify they fail**

Run: `cd server && uv run pytest -q tests/test_claude.py -k "ending"`
Expected: FAIL (ImportError: `JAKE_ENDINGS`, `pick_ending`)

- [ ] **Step 3: Implement `JAKE_ENDINGS` and `pick_ending` in `server/je_server/claude.py`**

`random.choices`로 무게를 둬 고르고, 마지막 거절 문장을 `strip()`해서 그 끝말로 끝나면 후보에서 뺀다. 상수 위 주석에 사용자가 고른 날짜와 「볼까요」가 라이언의 끝말이라 가장 드물게 둔다는 것을 적는다.

- [ ] **Step 4: Run to verify they pass**

Run: `cd server && uv run pytest -q tests/test_claude.py -k "ending"`
Expected: 4 passed

- [ ] **Step 5: Commit** (`feat(server): pick one of three endings for jake's suggestion`)

### Task 2: 추천에 끝말 넘기기, 지시문, 예문, 문서

**Files:**
- Modify: `server/je_server/claude.py` (`Claude.recommend`), `server/je_server/prompts.py` (`RECOMMEND_SYSTEM`), `server/je_server/topics.py` (`example_ko` 셋과 그 필드 주석), `server/je_server/engine.py` (`Engine.recommend`)
- Modify: `server/tests/fakes.py` (`FakeClaude.recommend`), `server/tests/test_claude.py`, `server/tests/test_claude_models.py:93`, `server/tests/test_api.py:110-123`, `server/tests/test_engine.py:80-91`, `server/tests/test_topics.py`
- Modify (문서, 따로 커밋): `docs/PRD.md` 「상황 정하기」 제이크 추천 줄, `docs/superpowers/specs/2026-11-07-situation-topics-design.md` 4, `docs/superpowers/specs/2026-11-05-speaking-practice-design.md` 「상황 정하기(역할극)」 3

**Interfaces:**
- Consumes: Task 1의 `JAKE_ENDINGS`, `pick_ending`
- Produces: `Claude.recommend(recent: list[str], turned_down: Sequence[str], topic: Topic, ending: str) -> str`. 메시지의 `예:` 다음 줄에 `끝말: {ending}`을 넣는다. `FakeClaude.recommend(recent, turned_down, topic, ending)`은 `self.calls`의 튜플은 그대로 두고 `self.endings`에 끝말을 더하며, `f"카페에서 커피를 주문하는 {ending}"`을 돌려준다.

- [ ] **Step 1: Write the failing tests** (기존 「어때요?」 단언을 바꾸고 더한다)

```python
# test_claude.py
async def test_recommend_passes_the_ending():
    fake = FakeAnthropic([json.dumps({"request_ko": "카페에서 주문하는 상황을 골라 봤어요."})])
    text = await Claude(fake).recommend([], [], OTHER, "상황을 골라 봤어요.")
    assert text == "카페에서 주문하는 상황을 골라 봤어요."
    content = fake.requests[0]["messages"][0]["content"]
    assert f"예: {OTHER.example_ko}\n끝말: 상황을 골라 봤어요.\n" in content
    system = str(fake.requests[0]["system"])
    assert "끝말" in system and "어때요" not in system and "볼까요" not in system

async def test_recommend_keeps_an_answer_with_another_ending(caplog):
    fake = FakeAnthropic([json.dumps({"request_ko": "카페에서 주문하는 상황으로 연습해 보면 어때요?"})])
    with caplog.at_level(logging.WARNING, logger="je_server"):
        text = await Claude(fake).recommend([], [], OTHER, "상황을 추천해요.")
    assert text.endswith("어때요?") and "ending" in caplog.text and "카페" not in caplog.text
# test_recommend_system_has_no_scene_of_its_own: 「상황으로 연습해 보면 어때요?」 대신 "끝말" in RECOMMEND_SYSTEM
# 다른 recommend 시험은 넷째 인자로 끝말을 넘기고 「어때요?」 단언을 지운다.

# test_topics.py
def test_examples_end_at_the_situation_without_an_ending():
    for t in TOPICS:
        assert t.example_ko.endswith("상황") and "어때요" not in t.example_ko

# test_engine.py
async def test_recommend_is_jake_korean(engine, fake_voice, fake_claude):
    said = await engine.recommend()
    assert fake_claude.endings[-1] in {e for e, _ in JAKE_ENDINGS} and said.text.endswith(fake_claude.endings[-1])
    # 나머지 단언(제이크 목소리, 다시 듣기)은 그대로

async def test_recommend_does_not_repeat_the_last_turned_down_ending(engine, fake_claude):
    for _ in range(20):
        await engine.recommend(["카페에서 주문하는 상황을 추천해요."])
    assert "상황을 추천해요." not in fake_claude.endings

# test_api.py test_recommend_route: j["text"]가 JAKE_ENDINGS 가운데 하나로 끝난다
```

- [ ] **Step 2: Run to verify they fail**

Run: `cd server && uv run pytest -q tests/test_claude.py tests/test_topics.py tests/test_engine.py tests/test_api.py tests/test_claude_models.py`
Expected: FAIL (`recommend()` takes 4 positional arguments, `endings` 없음, 예문이 「어때요?」로 끝남)

- [ ] **Step 3: Implement**

- `Claude.recommend`: 넷째 인자 `ending`을 메시지에 넣고, 답이 `ending`으로 끝나지 않으면 `log.warning("recommendation did not keep the given ending")`(문장은 남기지 않는다).
- `RECOMMEND_SYSTEM`: 「…어때요?」 줄과 「in the same form as the topic's example」을 빼고, 문장은 상황 다음에 사용자가 준 끝말(`"끝말"`)을 글자 그대로 붙인 해요체 한 문장이라고 쓴다. 끝말이 「상황」으로 시작하니 상황은 그 앞 낱말까지 쓴다는 것을 장면 없는 예(`"…묻는" + "상황을 추천해요." → "…묻는 상황을 추천해요."`)로 보인다. 끝말 셋을 지시문에 늘어놓지 않는다(고르는 것은 서버다).
  - (나중에 뺐다, 2026-11-08) 이 예는 Task 3의 두 번째 실제 하이쿠 시험에서 빠졌다. 모델이 예의 「상황을 추천해요.」를 쓰고 넘긴 끝말을 또 붙였기 때문이다. 지금 지시문에는 끝말이 든 예가 없다(`docs/guide/PROMPT_정해진_말투를_섞기_20261108.md` 「지시문의 예를 쓰고 꼴을 또 붙였다」).
- `topics.py`: 예문 셋을 「인사동에서 외국인 관광객이 한복 빌리는 곳을 묻는 상황」, 「뉴욕 지하철역에서 역무원에게 표 사는 법을 묻는 상황」, 「외국 회사에 전화해서 주문한 물건이 언제 오는지 묻는 상황」으로. 필드 주석은 「one situation Jake might suggest, without his ending (the server picks it)」.
- `Engine.recommend`: `pick_ending(turned_down)`으로 고른 끝말을 넘긴다. docstring에 한 줄.
- `FakeClaude`: 위 Interfaces대로.

- [ ] **Step 4: Run the whole server suite**

Run: `cd server && uv run pytest -q`
Expected: 모두 통과

- [ ] **Step 5: Commit** (`feat(server): let jake's suggestion end in the ending the server picks`)

- [ ] **Step 6: 문서를 고친다**

- PRD 제이크 추천 줄: 예를 「…상황을 골라 봤어요.」로 바꾸고, 끝말 셋을 섞는다(2026-11-08 사용자, 처음에는 「…어때요?」 하나), 「볼까요」는 라이언도 자주 써 가장 드물게(AI 추천을 사용자가 받아들임), 서버가 고른다(AI 판단)를 쓴다.
- 스펙 4 「문장 모양」 줄: 같은 내용과 고르는 방법(무게 2, 2, 1, 방금 거절한 끝말은 피함)으로. 예 둘의 끝말도 바꾼다.
- 말하기 스펙 3의 예: 「…상황을 골라 봤어요.」로 바꾸고, 끝말은 situation-topics 스펙 4를 따른다고 한 줄.

- [ ] **Step 7: Commit** (`docs: mix three endings in jake's suggestion`)

### Task 3: 실제 모델 시험 스크립트와 결과

**Files:**
- Create: `server/scripts/check_jake_recommend.py`

**Interfaces:**
- Consumes: `Claude.recommend`(Task 2), `pick_ending`(Task 1), `topics.TOPICS`

- [ ] **Step 1: 스크립트를 쓴다**

`check_ryan_wording.py`처럼 서버의 `Claude`를 실제 클라이언트로 쓴다(`load_settings()`의 키, 출력에 키를 남기지 않는다). `--presses N`(기본 7). 주제마다 빈 거절 목록에서 시작해 `pick_ending` → `recommend([], turned_down, topic, ending)` → 문장을 거절 목록에 더하기를 N번 한다(앱의 「다른 걸로요」와 같다). 사용자의 실제 기록(`recent`)은 쓰지 않는다. 줄마다 주제, 고른 끝말, 지켰는지, 문장(모델이 지은 것이라 출력해도 된다)을 내고, 끝에 끝말별 고른 수, 지킨 수, 연달아 같은 끝말 수, 토큰과 비용(하이쿠 $0.10/$0.50 per million, 저장소 스크립트와 같은 값)을 낸다. docstring에 돌리기 전에 횟수와 비용을 사용자에게 알린다는 것을 적는다.

- [ ] **Step 2: 돌린다** (스물한 번, 1센트 안쪽)

Run: `cd server && uv run python scripts/check_jake_recommend.py`
Expected: 스물한 줄 모두 끝말을 지키고, 연달아 같은 끝말 0. 어긋난 것이 있으면 지시문을 고치고 다시 돌리기 전에 그 횟수와 비용을 다시 알린다.

- [ ] **Step 3: Commit** (`test(server): add a real-model check for jake's endings`), 본문에 돌린 횟수와 결과.

### 마무리 (계획 밖, AGENTS.md 흐름)

- worktree 서버(8791, 8792, 복사한 데이터)에 `POST /recommend`를 주제 셋으로 한 번씩 보내 문장과 제이크 소리를 확인한다.
- PR을 열고 pr-review, devlog, 할 일 파일 「완료」를 넣고 머지 결정을 묻는다. 머지 뒤 `autostart.sh restart`와 폰 확인.
