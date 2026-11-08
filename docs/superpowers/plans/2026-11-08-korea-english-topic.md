# 「한국에서 영어 쓰기」 주제 넓히기 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 「외국인 관광객」 주제를 「한국에서 영어 쓰기」로 넓히고(처음 보는 외국인과의 도움 요청과 인사·이야기, 내가 먼저 말을 거는 장면), 「미국 여행」을 「미국 여행하기」로 바꾸고, 목록 맨 앞에 인사·이야기 상황 셋을 더한다.

**Architecture:** 맥 서버의 주제 목록(`server/je_server/topics.py`)만 고친다. 주제 ID와 API 모양은 그대로다. 앱은 `/home`이 주는 이름을 보인다. 실제 모델로 추천과 대본의 장면을 세는 스크립트를 하나 더한다.

**Tech Stack:** Python 3, pytest, anthropic SDK(실제 모델 시험), TypeScript(앱 시험 자료)

**Spec:** `docs/superpowers/specs/2026-11-08-korea-english-topic-design.md`. 앞선 스펙 `2026-11-07-situation-topics-design.md`, `2026-11-08-fixed-list-scripts-design.md`. 할 일은 원래 폴더 `docs/todo/20261108_45_todo_korea_english_topic.md`.

## Global Constraints

- 주제 ID `tourist`, `usa`, `other`와 순서는 그대로다. 이름만 「한국에서 영어 쓰기」, 「미국 여행하기」, 「그 밖의 상황」.
- 이 주제의 상대는 처음 보는 사람이다. 아는 사람(동료, 친구)은 넣지 않는다.
- 목록 대본: 내 대사는 정확히 3번, 12낱말 이하, 번갈아 말하기, 라이언 대사는 한두 문장, 줄마다 소희 한국어(영문자, 중괄호, 줄바꿈, 따옴표 없음). 사실은 그 줄의 설명에 든 것만 쓰고, 지어낸 값도 설명에 적는다(`REVIEW.md` 「목록 대본의 사실」).
- 공개 파일이다. 사용자 기록의 문장과 지명을 옮기지 않는다. 시험과 스크립트의 입력은 지어낸 것이다.
- 실제 모델 시험의 비용은 모두 1달러 안쪽이다.
- 공용 지시문(`prompts.SCRIPT_SYSTEM`, `prompts.RECOMMEND_SYSTEM`)은 고치지 않는다. 필요해 보이면 멈추고 main 세션에 묻는다(스펙 5).

## Review Focus

1. **아는 사람이 끼어든다:** 「이야기」를 넓히며 동료나 친구와의 잡담이 나올 수 있다 → Task 1의 지시문 시험이 「never met」과 「coworkers」를 확인하고, Task 3이 실제 모델 출력에서 센다.
2. **「그 밖의 상황」과 겹친다:** 「그 밖의 상황」의 장면 설명이 옛 「helping a foreign tourist」만 빼면, 한국에서 처음 보는 외국인과의 잡담이 두 주제에 다 든다 → Task 1 `test_other_leaves_out_the_korea_topic`.
3. **목록 순서에 기댄 코드:** 새 줄을 앞에 넣으면 `get("tourist").picks[0]`이 바뀐다. 지금 그 순서에 기대는 것은 `test_topics.py`뿐이다(찾아봄) → Task 2 `test_starting_lists`가 새 순서를 고정한다.
4. **시장 사실:** 「line for hotteok」, 「wait a long time」, 「Vegetables and noodles」가 설명과 시험에 묶여야 하고, 「not sweet」처럼 설명에 없는 맛은 말하지 않는다 → Task 2 `test_script_keeps_the_facts_of_its_description`과 `test_korean_keeps_the_facts`에 더한다.
5. **도움 요청인데 내가 먼저:** `first=None`이면 모델이 정한다. 도움을 청하는 상황에서 라이언이 먼저인지 → Task 3에서 센다(지시문의 「someone asking a stranger for help starts the talk」는 그대로).

---

### Task 1: 주제 이름과 설명 넓히기

**Files:**
- Modify: `server/je_server/topics.py` (`TOPICS`의 `tourist`, `usa`의 `name_ko`; `tourist`의 `roles_en`, `scenes_en`, `placeholder_ko`, `first`; `other`의 `scenes_en`; 모듈 설명)
- Modify: `server/je_server/claude.py:237` (docstring의 「외국인 관광객: Ryan」)
- Test: `server/tests/test_topics.py`, `server/tests/test_claude.py`

**Interfaces:**
- Produces: `get("tourist").first is None`. `Topic` 모양은 그대로다.

- [ ] **Step 1: 시험을 고친다**

```python
def test_three_topics_in_order():
    # 2026-11-07 the user named them; 2026-11-08 the user renamed two and kept the ids (spec korea-english-topic 1)
    assert [t.id for t in TOPICS] == ["tourist", "usa", "other"]
    assert [t.name_ko for t in TOPICS] == ["한국에서 영어 쓰기", "미국 여행하기", "그 밖의 상황"]


def test_korea_topic_is_strangers_and_either_may_start():
    # the user: a foreigner the learner has never met, a tourist or someone living here; asking for help or just
    # greeting and chatting; the learner may speak first (spec korea-english-topic 2, 3)
    t = get("tourist")
    assert t.first is None and get("usa").first is None and get("other").first is None
    for text in (t.roles_en, t.scenes_en):
        low = text.lower()
        assert "never met" in low and "tourist" in low and "lives in korea" in low and "coworkers" in low
    assert all(w in t.scenes_en.lower() for w in ("help", "small talk", "park", "cafe", "market", "learner speaks first"))
    assert "learner" in t.roles_en.lower() and "first" in t.roles_en.lower()


def test_other_leaves_out_the_korea_topic():
    # 「그 밖의 상황」 is what the two topics do not cover; talking with a foreigner one has never met in Korea is now
    # the first topic, chatting included
    s = get("other").scenes_en.lower()
    assert "helping a foreign tourist" not in s and "never met" in s and "united states" in s
```

`test_claude.py`의 `test_make_script_retries_when_the_first_speaker_is_wrong`은 `get("tourist")` 대신 `make_script(..., get("tourist"), first="ryan")`으로 첫 사람을 넘긴다. 새 시험 하나를 더한다:

```python
async def test_korea_topic_lets_the_situation_decide_who_starts():
    # spec korea-english-topic 3: the learner may greet first; a foreigner asking for help still starts by the rule
    fake = FakeAnthropic([lines_json("user", "ryan", "user", "ryan", "user")])
    await Claude(fake).make_script("공원에서 처음 보는 외국인에게 먼저 인사한다.", get("tourist"))
    content = fake.requests[0]["messages"][0]["content"]
    assert "Whoever would naturally speak first" in content and get("tourist").roles_en in content
```

- [ ] **Step 2: 실패를 본다**

Run: `cd server && uv run pytest -q tests/test_topics.py tests/test_claude.py`
Expected: 이름, `first`, 장면 낱말 시험이 FAIL. `test_korea_topic_lets_the_situation_decide_who_starts`는 「Ryan speaks first.」라 FAIL.

- [ ] **Step 3: `topics.py`를 고친다**

- `tourist`: `name_ko="한국에서 영어 쓰기"`, `first=None`, `placeholder_ko="예: 공원에서 외국인에게 먼저 인사하는 상황"`(main 세션에 물은 것, 답이 다르면 따른다).
- `roles_en`: 나는 한국에 사는 한국 사람, 라이언은 처음 보는(never met) 외국인으로 관광객이거나 한국에 사는 사람(lives in Korea), 동료나 친구 같은 아는 사람이 아니다(never coworkers or friends). 라이언이 도움을 청하러 오기도 하고, 둘이 인사하고 이야기하기도 하고, 내가 먼저 말을 걸기도 한다(the learner may speak first).
- `scenes_en`: 위 사람에 더해 장면 둘(도움 요청: 길, 지하철, 먹을 곳 / 공원, 카페, 시장, 헬스장, 아침 운동길에서 마주쳐 인사와 small talk. 시장은 사용자가 「외국인을 실제로 만날 만한 핫플레이스」를 원해 더한다), 「Sometimes the learner speaks first: greets the foreigner, or offers help to one who looks lost.」, 한국의 실제 장소, 아는 사람 금지.
- `example_ko`: 지금 것을 둔다. Task 3에서 센 뒤 정한다.
- `usa`: `name_ko="미국 여행하기"`만.
- `other.scenes_en`: 「other than talking in Korea with a foreigner they have never met (asking for help or chatting) or traveling in the United States」.
- 모듈 설명과 `claude.py` docstring의 「외국인 관광객: Ryan」을 지금 뜻으로 고친다(`first`를 정한 주제는 이제 없다).

- [ ] **Step 4: 통과를 본다**

Run: `cd server && uv run pytest -q`
Expected: 모두 PASS

- [ ] **Step 5: 커밋**

```bash
/usr/bin/git add server/je_server/topics.py server/je_server/claude.py server/tests/test_topics.py server/tests/test_claude.py
/usr/bin/git commit -F - <<'EOF'
feat(server): widen the tourist topic into 한국에서 영어 쓰기
...
EOF
```

### Task 2: 목록 맨 앞에 인사·이야기 상황 셋

**Files:**
- Modify: `server/je_server/topics.py` (`tourist`의 `picks` 맨 앞에 `_pick` 셋)
- Test: `server/tests/test_topics.py`

**Interfaces:**
- Consumes: `_pick(id, title_ko, situation, first, roles, lines)`
- Produces: 목록 줄 id `t-hangang-run`, `t-market-hotteok`, `t-cafe-seat`(Task 4가 화면에서 본다)

대본, 설명, 틀, 통역은 스펙 4의 표와 글 그대로다. 카드 이름은 main 세션의 답을 따른다(답 전에는 스펙의 초안).

- [ ] **Step 1: 시험을 고치고 더한다**

```python
def test_starting_lists():
    assert [len(get(t).picks) for t in ("tourist", "usa", "other")] == [6, 5, 0]
    # 2026-11-08 small talk first, so the list does not read as helping tourists only (spec korea-english-topic 4)
    assert [p.id for p in get("tourist").picks] == ["t-hangang-run", "t-market-hotteok", "t-cafe-seat",
                                                    "t-gyeongbokgung", "t-tmoney", "t-samgyeopsal"]
    assert [p.first for p in get("tourist").picks] == ["user", "ryan", "ryan", "ryan", "ryan", "ryan"]
    # usa 줄은 지금 그대로
```

`test_script_keeps_the_facts_of_its_description`에 더한다:

```python
    assert all(w in said["t-market-hotteok"] for w in ("line for hotteok", "wait a long time", "Vegetables and noodles"))
```

`test_korean_keeps_the_facts`에 더한다:

```python
    assert all(w in said["t-market-hotteok"] for w in ("호떡 줄", "오래 기다려요", "채소", "당면"))
```

새 시험:

```python
def test_small_talk_values_are_in_the_description():
    # the made-up values the scripts say are facts of their descriptions too (REVIEW.md 「목록 대본의 사실」)
    run, market, cafe = (pick("tourist", i).situation for i in ("t-hangang-run", "t-market-hotteok", "t-cafe-seat"))
    assert all(w in run for w in ("한강공원", "지난달", "2년째", "먼저 인사"))
    assert all(w in market for w in ("남대문시장", "야채호떡", "오래 줄", "채소와 당면"))
    assert all(w in cafe for w in ("처음", "일주일", "옆자리"))


def test_a_small_talk_pick_starts_with_the_learner():
    # the user: in Korea the learner may greet a foreigner first (spec korea-english-topic 3)
    p = pick("tourist", "t-hangang-run")
    assert p.first == "user" and p.script[0][0] == "user"


def test_small_talk_picks_end_on_the_learner():
    # spec fixed-list-scripts 1: Ryan's last line would only echo the goodbye, so the learner closes
    assert all(pick("tourist", i).script[-1][0] == "user" for i in ("t-hangang-run", "t-market-hotteok", "t-cafe-seat"))
```

- [ ] **Step 2: 실패를 본다**

Run: `cd server && uv run pytest -q tests/test_topics.py`
Expected: 새 id가 없어 `KeyError`와 개수 시험이 FAIL

- [ ] **Step 3: `_pick` 셋을 `tourist.picks` 맨 앞에 넣는다**

각 줄 위에 주석: 지어낸 값(한 달, 2년, 일주일)과, 남대문시장은 2026-11-08 웹에서 확인한 사실(외국인이 많이 찾음, 호떡 줄, 야채호떡에 든 채소와 당면). 모듈 설명의 「checked on the web」 목록에 시장 사실을, 대본 규칙에 「쉬운 일상 낱말」(스펙 4)을 더한다.

- [ ] **Step 4: 통과를 보고 기록과 맞댄다**

Run: `cd server && uv run pytest -q`
Expected: 모두 PASS.
넣은 영어와 한국어 줄을 앱 데이터 폴더의 모든 기록과 맞대 개수만 출력한다(같은 문장, 낱말 4·5·6 이어짐, 지명과 값 낱말). 기대: 같은 문장 0, 5·6 이어짐 0.

- [ ] **Step 5: 커밋** (`feat(server): put three small-talk scenes first on the korea list`)

### Task 3: 실제 모델로 장면 세기

**Files:**
- Create: `server/scripts/check_topic_scenes.py`
- Test: `server/tests/test_check_topic_scenes.py`
- Modify (결과에 따라): `server/je_server/topics.py`의 `tourist.example_ko`

**Interfaces:**
- Consumes: `Claude.recommend(recent, turned_down, topic, ending)`, `Claude.make_script(situation, topic)`, `pick_ending`, `scripts/check_jake_recommend.py`의 `PRICE`, `RECENT`, `Counting`
- Produces: `known_people(text: str) -> bool`, `abroad(text: str) -> bool`(시험하는 작은 함수)

- [ ] **Step 1: 작은 함수 시험을 쓴다**

```python
def test_known_people_are_flagged():
    assert cs.known_people("회사 동료에게 영어로 인사하는 상황") and cs.known_people("my coworker")
    assert cs.known_people("외국인 친구와 카페에서") and not cs.known_people("처음 보는 외국인과 인사")


def test_abroad_is_flagged():
    assert cs.abroad("뉴욕 지하철역에서") and not cs.abroad("한강공원에서 달리다")
```

- [ ] **Step 2: 실패를 본다** (`uv run pytest -q tests/test_check_topic_scenes.py` → 모듈 없음)

- [ ] **Step 3: 스크립트를 쓴다**

- 인자: `--presses N`(기본 7), `--runs R`(추천 사슬 수, 기본 2), `--recent filled|empty`(기본 filled, `RECENT["tourist"]`), `--example TEXT`(그 회차만 `dataclasses.replace(topic, example_ko=TEXT)`), `--scripts`(대본도 쓴다).
- 추천: 사슬마다 거절 목록에 쌓으며 N번. 줄마다 문장과 표시(아는 사람, 한국 밖)를 찍는다.
- 대본(`--scripts`): 지어낸 상황 글 `TYPED`(도움 요청 2, 인사 3, 한 낱말 2: 「헬스장」, 「공원」)와 그 회차의 추천 앞 세 개로 `make_script`. 줄마다 첫 사람, 틀의 제목과 라이언 역할, 첫 대사, 표시.
- 끝에 호출 수, 토큰, 비용(`PRICE`).

- [ ] **Step 4: 통과를 본다** (`uv run pytest -q`)

- [ ] **Step 5: 실제로 돌린다** (비용 어림: 추천 1건 0.003달러, 대본 1건 약 0.02달러)

1. `--recent filled` 지금 예(도움 요청), 2사슬 × 7 → 장면 셈
2. `--recent filled --example "한강공원에서 아침 운동하다 마주친 외국인과 인사하는 상황"` 2사슬 × 7
3. 고른 예로 `--recent empty` 1사슬 × 7, 그리고 `--scripts`
4. 스펙 5의 기준으로 판단한다. 아는 사람이나 한국 밖이 나오면 `roles_en`/`scenes_en`을 고치고 다시 센다. 공용 지시문이 필요해 보이면 멈추고 main 세션에 묻는다.

- [ ] **Step 6: 고른 예를 넣고 커밋** (`test(server): count korea topic scenes on the real model`, 예가 바뀌면 `feat(server)`로 따로)

### Task 4: 앱 시험 자료, 문서, 화면 확인

**Files:**
- Modify: `app/src/flow/situation.test.ts`(「미국 여행」 → 「미국 여행하기」), `contract/home-topics.json`(같다)
- Modify: `docs/PRD.md` 「상황 정하기」, `docs/superpowers/specs/2026-11-07-situation-topics-design.md`(머리 줄에 「넓힘(2026-11-08)」, 1의 주제 표, 3 목록에 새 스펙 가리키기), `docs/superpowers/specs/2026-11-08-fixed-list-scripts-design.md`(「더한 대본」 아래에 새 스펙 가리키기)

- [ ] **Step 1:** `cd app && npm ci && npm test && npm run typecheck` → PASS, `cd server && uv run pytest -q` → PASS(약속 시험 포함)
- [ ] **Step 2:** 문서를 고친다. 지난 결정 글은 그때 이름 그대로 두고, 머리 줄과 표에 지금 이름을 적는다.
- [ ] **Step 3:** 커밋 둘(`test(app): …`, `docs(prd): …` / 스펙 고침은 `docs: …`)을 `&&`로 잇는다.
- [ ] **Step 4: 화면 확인** — main 세션에 에뮬레이터 차례를 묻고 받은 뒤: worktree 서버를 `JE_HOST=127.0.0.1 JE_PORT=8793 JE_WHISPER_PORT=8794 JE_DATA_DIR=<녹음 뺀 복사본>`으로 띄우고, 그 주소를 넣은 APK를 빌드해 AVD `jake-english`에 깔고 `adb reverse tcp:8793 tcp:8793`. 주제 버튼 세 이름, 「한국에서 영어 쓰기」 → 「목록에서 고르기」의 여섯 카드 순서를 기본 폭과 360dp(`wm density 480`)에서 본다. 한강 카드를 눌러 내 대사부터 시작하는지 본다(녹음은 누르지 않는다). 끝나면 밀도를 되돌리고 에뮬레이터, 서버를 끄고 복사본을 지운다.
