# 서버의 작은 일 셋 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 목록 대본의 토막 낸 티, 제이크 추천 끝말의 남은 것, 선생님 라이언이 서버 안의 말을 하는 것을 고친다.

**Architecture:** 셋 다 맥 서버(`server/je_server/`) 안의 작은 고침이다. 대본은 `topics.py`의 글만, 끝말은 `claude.py`의 끝말 알아보기 함수 몇 개만, 선생님 답은 `prompts.ASIDE_SYSTEM`의 글만 바꾼다. 앱과 API 모양은 그대로다.

**Tech Stack:** Python 3, pytest, anthropic SDK(실제 모델 확인 스크립트)

**Spec:** 새 스펙은 없다. 할 일 파일 셋(원래 폴더 `docs/todo/`)이 고칠 방법을 정했다.
- `20261108_19_todo_list_scripts_signal_more_steps.md` → 목록 대본 스펙 `docs/superpowers/specs/2026-11-08-fixed-list-scripts-design.md` 1, 「처음 대본」
- `20261108_14_todo_jake_endings_minors.md` → 상황 주제 스펙 `docs/superpowers/specs/2026-11-07-situation-topics-design.md` 4 「끝말」
- `20261108_15_todo_aside_answer_no_internal_terms.md` → offscript-aside 스펙 `docs/superpowers/specs/2026-11-07-offscript-aside-design.md` 3

## Global Constraints

- 공개 저장소: 시험 문장, 주석, 문서에 사용자 기록의 문장(대사, 들린 말, 제이크 추천 원문)을 쓰지 않는다. 예문은 지어낸다.
- 목록 대본의 사실은 그 목록 줄의 설명(`situation`)에 든 것만 쓴다(PR #34). 영어를 바꾸면 그 줄의 소희 한국어도 같은 뜻으로 고친다. 한국어는 영어가 말하는 것만 말한다.
- 내 대사는 12낱말 이하(`test_every_pick_has_a_script_that_passes_the_script_checks`).
- 끝말 셋과 무게는 그대로다: `("상황을 골라 봤어요.", 2), ("상황을 추천해요.", 2), ("상황으로 연습해 볼까요?", 1)`.
- 추천마다 Claude는 한 번만 부른다. 어긴 답은 다시 부르지 않고 서버가 고친다. 로그에 문장을 쓰지 않는다.
- 실제 모델 호출은 할 일 파일에 적힌 만큼만 한다. 합쳐 몇 센트 안쪽이면 묻지 않고 하고, 횟수와 비용을 PR에 적는다.
- 시험 서버는 `JE_HOST=127.0.0.1 JE_PORT=8791 JE_WHISPER_PORT=8792`와 앱 데이터 폴더의 복사본(`rec/` 뺌)으로 띄운다. 원래 폴더 서버는 멈추지 않는다.

## Review Focus

1. **상황이 문장 앞에만 있는 추천:** 「카페 상황에서 주문하는 연습을 해 볼까요?」처럼 마지막 「상황」 뒤가 길면 끝말로 보지 않고 그대로 둔다. → Task 2 `test_recommend_keeps_a_long_tail_after_situation`.
2. **끝말이 아닌 짧은 꼬리:** 「…상황이에요.」처럼 짧고 「요」로 끝나는 꼬리는 끝말로 보고 고른 끝말로 갈아 끼운다(그 앞 말은 어느 끝말에도 맞는다). → Task 2 swap 표의 한 줄.
3. **끝 부호가 없거나 다른 거절 문장:** 「…상황을 추천해요」, 「…추천해요!」를 거절해도 다음 끝말이 「추천해요」가 아니다. → Task 2 `test_pick_ending_knows_an_ending_without_its_mark`.
4. **옛 앱의 「…어때요?」 거절 문장:** 셋 가운데 아무것이나 나온다(지금 시험 `test_pick_ending_any_after_an_old_form`이 그대로 지킨다).
5. **지시문을 고친 뒤에도 비슷하게 들린 낱말은 짚는다:** 선생님 답의 규칙을 더해도 「짚을 것」이 있는 녹음에는 그 낱말을 말한다. → Task 3 Step 6의 `near miss tip` 실제 확인.

---

### Task 1: 경복궁 대본의 첫 내 대사에 「먼저」

**Files:**
- Modify: `server/je_server/topics.py` (머리 설명, `t-gyeongbokgung`의 둘째 줄)
- Test: `server/tests/test_topics.py`
- Modify (문서, 따로 커밋): `docs/superpowers/specs/2026-11-08-fixed-list-scripts-design.md` 1과 「처음 대본」 표, 원래 폴더의 할 일 19(복사해 와서 상태를 「완료」로)

**Interfaces:**
- Consumes: 없음
- Produces: 없음(대본 글만 바뀐다)

- [ ] **Step 1: Write the failing test**

```python
def test_a_route_split_over_turns_says_more_is_coming():
    # 2026-11-08 the user, after the gyeongbokgung pick on the phone: the first answer sounded like the whole way,
    # so the tourist's 「And then what?」 sounded like it waited for the next piece
    p = pick("tourist", "t-gyeongbokgung")
    first = next(i for i, (s, _) in enumerate(p.script) if s == "user")
    assert "First," in p.script[first][1] and "먼저" in p.ko[first]
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd server && uv run pytest -q tests/test_topics.py -k more_is_coming`
Expected: FAIL (`assert 'First,' in 'Sure. Take Line 4 from here, just one stop to Chungmuro.'`)

- [ ] **Step 3: 대사를 고친다**

- 영어: `"Sure. First, take Line 4 one stop to Chungmuro."`(main 세션 추천)
- 한국어: `"그럼요. 먼저 4호선을 타고 충무로까지 한 정거장 가세요."`. 추천 한국어의 「여기서」는 영어에 없어 뺀다(한국어는 영어가 말하는 것만).
- 머리 설명에 한 줄: 한 덩어리 말(갈아타는 길처럼 여러 단계)을 내 대사 여럿으로 나눌 때는 첫 토막에 뒤에 더 있다는 표시(First)를 둔다.
- 나머지 다섯 대본은 앞뒤 줄을 이어 읽어 보았고, 상대가 다음 토막을 기다렸다는 듯이 묻는 곳이 없어 그대로 둔다(라이언의 질문이 모두 새 질문이다). 이 판단은 PR 본문과 devlog에 적는다.

- [ ] **Step 4: Run the topics tests**

Run: `cd server && uv run pytest -q tests/test_topics.py`
Expected: 모두 통과(사실 시험 `one stop`, `Line 4`, `Chungmuro`, `한 정거장`, `충무로`가 그대로 지켜진다)

- [ ] **Step 5: 공개 파일 확인** — 새 영어와 한국어 줄을 앱 데이터 폴더의 모든 역할극 대사와 문장 단위로 맞대어 같은 것의 개수만 출력한다. 기대: 0.

- [ ] **Step 6: Commit** — `fix(server): say the gyeongbokgung route has more steps from the first line`

- [ ] **Step 7: 문서** — 스펙 1에 규칙 한 줄(2026-11-08 사용자, 경복궁 대본), 「처음 대본」 표의 그 줄을 새 대사로 바꾸고 고친 까닭 한 줄. 할 일 19 상태를 「완료」로. Commit: `docs(server): write down splitting one answer over turns in list scripts`

(바뀐 줄만 새로 만들어지는지는 Task 4에서 시험 서버로 본다.)

### Task 2: 제이크 끝말을 짧은 꼬리로 알아보기

**Files:**
- Modify: `server/je_server/claude.py` (`_ending_at_end`, `KNOWN_ENDINGS`, `_known_at_end`, `swap_ending`을 아래 셋으로 바꾸고 `pick_ending`, `Claude.recommend`)
- Modify: `server/scripts/check_jake_recommend.py` (연달아 같은 끝말 세기를 `heard_ending`으로)
- Test: `server/tests/test_claude.py`
- Modify (문서, 따로 커밋): 상황 주제 스펙 4 「끝말」의 갈아 끼우기 줄, `docs/guide/PROMPT_정해진_말투를_섞기_20261108.md`(겪은 문제 하나, 확인 방법), `docs/PRD.md` 83줄(스펙 파일 이름), `docs/superpowers/plans/2026-11-08-jake-recommend-endings.md` Task 2 Step 3(지시문 예를 나중에 뺀 것), 할 일 14

**Interfaces:**
- Produces (모두 `claude.py`):
  - `ENDING_TAIL_MAX = 10`: 서버가 아는 가장 긴 끝말의 「상황」 뒤 글자 수(띄어쓰기, 끝 부호 빼고). 옛 「으로 연습해 보면 어때요」가 10, 걸리면 안 되는 「에서 주문하는 연습을 해 볼까요」가 13.
  - `_ending_start(text: str) -> int | None`: 마지막 「상황」의 자리. 그 뒤가 「상황」 없이 `ENDING_TAIL_MAX`자 이하이고 「요」로 끝날 때만(끝의 띄어쓰기와 `.?!~…`는 빼고 본다). 아니면 None.
  - `strip_endings(text: str) -> str | None`: 끝의 끝말을 모두(`_ending_start`가 None이 될 때까지) 걷어 낸 상황 말. 그 끝에 남은 「상황」과 쉼표, 띄어쓰기도 걷는다. 끝말이 없으면 None, 끝말만 있으면 `""`.
  - `heard_ending(text: str) -> str | None`: `text` 끝에서 들리는 `JAKE_ENDINGS`의 끝말. 끝말 꼬리(`_ending_start`부터, 띄어쓰기와 끝 부호 빼고)가 그 끝말의 마지막 낱말(봤어요, 추천해요, 볼까요)로 끝나면 그것. 아니면 None(옛 「…어때요?」).
  - `pick_ending(turned_down, rng=None) -> str`: 마지막 거절 문장의 `heard_ending`을 빼고 고른다.
  - `Claude.recommend`: `strip_endings`가 None이면 `log.warning("recommendation did not keep the given ending")`, `""`이면 `log.warning("recommendation has no situation before its ending")`, 아니면 `f"{stem} {ending}"`이 원문과 다를 때 `log.info("recommendation ending swapped")`. 문장은 로그에 쓰지 않는다. `swap_ending`은 없앤다.

- [ ] **Step 1: Write the failing tests** (`test_claude.py`)

```python
# test_recommend_swaps_a_known_ending_for_the_given_one의 표에 더한다
("호텔에서 수건을 더 달라고 하는 상황을 연습해 볼까요?", "상황을 골라 봤어요.",
 "호텔에서 수건을 더 달라고 하는 상황을 골라 봤어요."),          # 0: 섞인 끝말
("카페에서 주문하는 상황을 추천해요", "상황을 골라 봤어요.", "카페에서 주문하는 상황을 골라 봤어요."),  # 1: 부호 없음
("카페에서 주문하는 상황을 추천해요!", "상황으로 연습해 볼까요?", "카페에서 주문하는 상황으로 연습해 볼까요?"),
("카페에서 주문하는 상황이에요.", "상황을 추천해요.", "카페에서 주문하는 상황을 추천해요."),  # 짧은 꼬리
("공항에서 짐을 찾는 상황 상황을 골라 봤어요.", "상황을 골라 봤어요.", "공항에서 짐을 찾는 상황을 골라 봤어요."),  # 2
("공항에서 짐을 찾는 상황, 상황을 추천해요.", "상황을 추천해요.", "공항에서 짐을 찾는 상황을 추천해요."),

async def test_recommend_keeps_a_long_tail_after_situation(caplog):
    # 상황 only near the front: the tail is not an ending, so the sentence is said as it came
    s = "카페 상황에서 주문하는 연습을 해 볼까요?"
    fake = FakeAnthropic([json.dumps({"request_ko": s})])
    with caplog.at_level(logging.WARNING, logger="je_server"):
        assert await Claude(fake).recommend([], [], OTHER, "상황을 추천해요.") == s
    assert "did not keep" in caplog.text

async def test_recommend_logs_an_answer_that_is_only_an_ending(caplog):  # 3
    fake = FakeAnthropic([json.dumps({"request_ko": "상황을 추천해요."})])
    with caplog.at_level(logging.WARNING, logger="je_server"):
        assert await Claude(fake).recommend([], [], OTHER, "상황을 골라 봤어요.") == "상황을 추천해요."
    assert "no situation" in caplog.text and "did not keep" not in caplog.text

@pytest.mark.parametrize("down, heard", [
    ("카페에서 주문하는 상황을 추천해요", "상황을 추천해요."),
    ("카페에서 주문하는 상황을 추천해요!", "상황을 추천해요."),
    ("호텔에서 수건을 더 달라고 하는 상황을 연습해 볼까요?", "상황으로 연습해 볼까요?"),
])
def test_pick_ending_knows_an_ending_without_its_mark(down, heard):
    rng = random.Random(11)
    got = {pick_ending([down], rng) for _ in range(300)}
    assert heard not in got and len(got) == 2
```

- `test_recommend_keeps_an_answer_with_an_unknown_ending`의 답을 「카페에서 주문하는 연습을 해 봐요.」(상황 없음)로 바꾼다. 「상황이에요.」는 이제 짧은 꼬리라 갈아 끼운다.
- `test_recommend_keeps_an_answer_that_is_only_an_ending`은 위 로그 시험이 대신하니 지운다.

- [ ] **Step 2: Run to verify they fail**

Run: `cd server && uv run pytest -q tests/test_claude.py -k "ending or recommend"`
Expected: 새 줄과 새 시험이 FAIL(섞인 끝말, 부호 없음, 상황 겹침이 그대로 나오고, 「no situation」 로그가 없다)

- [ ] **Step 3: 위 Interfaces대로 구현한다.** `check_jake_recommend.py`의 `heard_before`도 `heard_ending(turned_down[-1])`로 바꾼다(스크립트 docstring은 그대로).

- [ ] **Step 4: Run the whole server suite**

Run: `cd server && uv run pytest -q`
Expected: 모두 통과

- [ ] **Step 5: Commit** — `fix(server): read jake's ending as the short tail after the last 상황`

- [ ] **Step 6: 실제 하이쿠로 다시 잰다** — `cd server && uv run python scripts/check_jake_recommend.py`(스물한 번, 약 0.3센트). 기대: MISSED 0, 연달아 같은 끝말 0. 결과(셈과 비용)만 PR과 devlog에 적고 문장은 옮기지 않는다.

- [ ] **Step 7: 문서와 할 일 14 상태 「완료」** — Commit: `docs(server): record reading jake's ending by its tail`

### Task 3: 선생님 라이언이 가른 결과를 말하지 않게

**Files:**
- Modify: `server/je_server/prompts.py` (`ASIDE_SYSTEM`)
- Modify: `server/scripts/check_ryan_wording.py` (`NAMES`, `flags`, `ASIDE` 사례 둘)
- Test: `server/tests/test_claude.py`, `server/tests/test_check_ryan_wording.py`
- Modify (문서, 따로 커밋): offscript-aside 스펙 3, 할 일 15

**Interfaces:**
- Produces: `check_ryan_wording.ASIDE`에 `Case("off app wish", …)`, `Case("off chat", …)`(이름이 `off`로 시작해 `--case off`로 둘만 돌린다). 둘 다 `issues=[]`, `heard_ko`는 지어낸 한국어.

- [ ] **Step 1: Write the failing tests**

```python
# test_claude.py
def test_aside_prompt_hides_how_the_recording_was_sorted():
    # phone test 2026-11-08: a Korean wish about the app got 「대사와 상관없는 말로 들려서 따로 짚을 곳이 없어요」
    from je_server import prompts

    p = prompts.ASIDE_SYSTEM
    assert "짚을 곳이 없어요" in p and "대사와 상관없는 말로 들렸어요" in p  # named as what not to say
    assert "앱에 바라는 것" in p and "약속하지 않아요" in p

# test_check_ryan_wording.py
def test_aside_flags_the_sorting_and_a_missing_retry():
    case = next(c for c in cw.ASIDE if c.name == "off app wish")
    bad = "대사와 상관없는 말로 들려서 따로 짚을 곳이 없어요."
    assert {"names '짚을'", "names '상관없는 말'", "does not ask to try again"} <= set(cw.flags(case, bad, aside=True))
    good = "그렇군요, 그런 게 있으면 편하겠어요. 지금은 대사를 말해야 다음으로 넘어가요. 다시 해 볼까요?"
    assert cw.flags(case, good, aside=True) == []
```

- [ ] **Step 2: Run to verify they fail**

Run: `cd server && uv run pytest -q tests/test_claude.py -k sorted tests/test_check_ryan_wording.py`
Expected: FAIL(지시문에 그 줄이 없고, `off app wish` 사례가 없다)

- [ ] **Step 3: 구현한다**

- `ASIDE_SYSTEM` 「무엇이라고 답할지」에 한 줄: 앱에 바라는 것이나 불편한 점(기능 요청, 불평)이면 짧게 받아 주고, 지금은 대사를 말해야 다음으로 넘어간다고 하고 다시 해 보자고 한다. 앱을 바꾸겠다고 약속하지 않는다.
- 「규칙」에 한 줄: 받은 말을 어떻게 갈랐는지 말하지 않는다. 「대사와 상관없는 말로 들렸어요」, 「짚을 곳이 없어요」처럼 들린 말의 종류나 짚을 것이 없다는 것을 말하지 않고, 학습자가 한 말에 바로 답한다.
- 예 하나(앱에 바라는 것): 「그렇군요, 그런 게 있으면 편하겠어요. 지금은 대사를 말해야 다음으로 넘어가요. 다시 해 볼까요?」
- `check_ryan_wording.py`: `NAMES`의 「짚을 것」을 「짚을」로 넓히고 「상관없는 말」, 「대사와 다른 말」을 더한다. `flags`에서 aside 답이 「다시」도 「한 번 더」도 없으면 `does not ask to try again`. 사례 둘을 지어 더한다.

- [ ] **Step 4: Run the whole server suite** — `cd server && uv run pytest -q`, 모두 통과

- [ ] **Step 5: Commit** — `fix(server): keep teacher ryan from saying how the recording was sorted`

- [ ] **Step 6: 실제 소넷 확인** — `uv run python scripts/check_ryan_wording.py --only aside --case off --runs 1`(두 번), `--case "near miss tip" --runs 1`, `--case "korean question" --runs 1`. 네 번, 약 3센트. 기대: 깨진 규칙 0. 녹음 시험은 Task 4.

- [ ] **Step 7: 문서와 할 일 15 상태 「완료」** — 스펙 3의 답 목록에 앱에 바라는 것, 「하지 않는 것」에 가른 결과 말하기. Commit: `docs: take app wishes and hide the sorting in teacher ryan's answer`

### Task 4: 시험 서버로 확인

- [ ] 빈 포트 확인(`lsof -nP -iTCP -sTCP:LISTEN | grep 879`), 앱 데이터 폴더의 `roleplays`(`rec/` 뺌), `audio`, `saved.json`을 scratchpad에 복사, worktree 서버를 8791/8792로 띄운다.
- [ ] **대본:** `POST /roleplays`로 「명동역에서 경복궁 가는 길」을 고른다. 바로 받은 역할극에서 둘째 줄(바뀐 줄)만 읽는 법과 소리가 비고 나머지 줄은 앞선 회차의 것이 있는지 본다(앞선 회차가 복사본에 없으면 그 사실을 적는다). 둘째 줄이 곧 만들어지는지 본다(소넷 한 번).
- [ ] **끝말:** `POST /recommend`를 서너 번(하이쿠, 0.1센트 안쪽) 거절 목록을 이어 보내 끝말이 이어지지 않는지 본다.
- [ ] **선생님 답:** 지어낸 한국어 녹음 둘(앱에 바라는 말, 상관없는 혼잣말)을 제이크 목소리로 만들어 `scripts/try_recordings.py`로 복사본에 보낸다(소넷 두 번, 약 1.4센트). 답에 「짚을」, 「상관없는 말」이 없고 다시 해 보자고 끝나는지 본다.
- [ ] 서버를 끄고 포트가 비었는지 보고, 복사한 데이터와 녹음 파일을 지운다. 결과(셈, 시간, 비용)만 PR과 devlog에 적는다.

### Task 5: PR, 리뷰, devlog

- [ ] push, PR(`fix(server): ...`, 본문은 `AGENTS.md` 「PR과 머지」의 절), pr-review, 확인된 문제 고치기, `REVIEW.md` 「고치는 방법」 보기
- [ ] devlog `docs/devlog/2026-11-08-server-small-fixes.md`, main 세션에 「머지 준비 됨」
