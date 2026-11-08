# 「미국 여행」 목록에 예약 상황 둘 더하기 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 「미국 여행」 목록에 「로스앤젤레스 호텔에서 온라인 예약 확인」과 「와이키키 해산물 식당에 예약 없이 가기」를 정해 둔 대본과 통역까지 함께 더한다.

**Architecture:** 맥 서버의 목록 파일(`server/je_server/topics.py`)의 `usa` 목록 끝에 `_pick` 두 줄을 더한다. 목록에서 고르는 길(`Engine.create_pick`), 앱 화면, API 모양은 그대로다. 앱은 `/home`이 주는 목록을 그대로 보인다.

**Tech Stack:** Python 3, pytest

**Spec:** 새 스펙은 없다. 기존 목록에 대본을 더하는 일이고, 목록 대본 스펙 `docs/superpowers/specs/2026-11-08-fixed-list-scripts-design.md`(1 「대본을 저장소에 둔다」)와 ADR-0013을 따른다. 할 일은 원래 폴더의 `docs/todo/20261108_38_todo_list_scripts_reservations.md`다. 대본은 사용자가 main 세션에서 정했다(2026-11-08, 아래 「대본」).

## Global Constraints

- 사실은 그 목록 줄의 설명(`situation`)에 든 것만 쓴다. 두 줄이 이어지며 새 사실이 되는 것도 안 된다(`REVIEW.md` 「목록 대본의 사실」).
- 두 곳 모두 이름 없는 가게다(사용자). 2박, 킹 침대 방, 12층, 30분, 예약 이름 Jake는 지어낸 작은 값이다. 주석에 적는다.
- 내 대사는 정확히 3번, 12낱말 이하다. 라이언 대사는 한두 문장이다. `Claude.script_problems`를 통과한다.
- 줄마다 소희 한국어를 둔다. 영어가 말하는 것만 말하고, 영문자, 중괄호, 줄바꿈, 따옴표를 쓰지 않는다(`test_every_line_has_sohee_korean`).
- 공개 파일이다. 대사와 통역을 앱 데이터 폴더의 모든 기록(대사, 통역, 들린 말, 상황)과 문장 단위로 맞대 보고, 개수만 출력한다. 기대: 0(초안 단계에서 한 줄을 바꿔 0이 됐다).
- 기존 「뉴욕 호텔 체크인」 대본은 그대로 둔다.

## 대본

**`u-hotel-online` 로스앤젤레스 호텔에서 온라인 예약 확인** (라이언 먼저)

- 설명: 로스앤젤레스의 호텔 프런트에서 체크인한다. 온라인으로 예약했다고 말하고 확인 번호를 보여 준다. 직원이 킹 침대 방 2박 예약을 확인해 준다. 높은 층 방을 부탁하자 직원이 12층 방을 준다.
- 틀: 나 「로스앤젤레스에 여행 온 한국 사람」, 라이언 「호텔 프런트 직원」, 장소 「로스앤젤레스의 호텔 프런트」, 목표 「온라인으로 한 예약을 확인하고 체크인하기」

| | 대사 | 통역 |
|---|---|---|
| R | Hi, welcome! Are you checking in? | 안녕하세요, 어서 오세요! 체크인하시나요? |
| 나 | Yes, I booked online. Here's my confirmation number. | 네, 온라인으로 예약했어요. 여기 확인 번호요. |
| R | Thanks. I have you down for two nights in a king room. | 감사합니다. 킹 침대 방으로 2박 예약되어 있네요. |
| 나 | That's right. Could I get a room on a high floor? | 맞아요. 높은 층 방으로 받을 수 있을까요? |
| R | Sure, you're on the twelfth floor. Here are your keys. | 그럼요, 12층으로 드릴게요. 여기 객실 키입니다. |
| 나 | Awesome, the higher the better. Thank you! | 좋네요, 높을수록 좋아요. 감사합니다! |

**`u-seafood-walkin` 와이키키 해산물 식당에 예약 없이 가기** (라이언 먼저)

- 설명: 하와이 호놀룰루 와이키키의 해산물 식당에 예약 없이 둘이 간다. 직원이 예약했는지 묻고, 자리가 거의 차서 테이블은 30분쯤 기다려야 하고 바에는 앉을 수 있다고 한다. 테이블을 기다리기로 하고 대기 명단에 제이크라는 이름을 올린다.
- 틀: 나 「하와이에 여행 온 한국 사람」, 라이언 「식당 입구의 안내 직원」, 장소 「하와이 호놀룰루 와이키키의 해산물 식당」, 목표 「예약 없이 간 식당에서 자리를 묻고 대기 명단에 이름 올리기」

| | 대사 | 통역 |
|---|---|---|
| R | Aloha, welcome in! Do you have a reservation? | 알로하, 어서 오세요! 예약하셨어요? |
| 나 | No, we don't. Do you have a table for two? | 아니요, 안 했어요. 두 명 앉을 자리 있어요? |
| R | We're pretty full right now. It's about a 30-minute wait, or you can sit at the bar. | 지금은 자리가 거의 찼어요. 30분쯤 기다리셔야 하고, 아니면 바에 앉으셔도 돼요. |
| 나 | We'll wait for a table. Can I put my name down? | 테이블 자리를 기다릴게요. 이름 올려 둘 수 있을까요? |
| R | Sure, what name should I put down? | 그럼요, 어떤 이름으로 올려 드릴까요? |
| 나 | It's Jake. Thank you! | 제이크요. 감사합니다! |
| R | Great, we'll call you when your table is ready. | 네, 자리가 나면 불러 드릴게요. |

- 예약 이름: 식당 대기 명단은 보통 이름(first name)을 올려 「Jake」로 했다(사용자 제안). 호텔은 성으로 찾는 일이 많아 기존 대본의 「Kim」은 그대로 둔다.

## Review Focus

1. **이어 읽으면 생기는 사실:** 「30-minute wait, or you can sit at the bar」가 「바는 기다리지 않는다」로 읽힌다. 설명에 「바에는 앉을 수 있다」가 있어 사실 안이다. 한국어에 영어에 없는 「바로」를 넣지 않는다. → Task 1 `test_walk_in_korean_says_no_more_than_the_english`.
2. **새 호텔이 옛 호텔과 겹치지 않는다:** 예약을 어떻게 했는지가 첫 내 대사에 나온다. → Task 1 `test_reserved_hotel_says_how_it_was_booked`.
3. **식당 직원이 먼저 예약을 묻는다(사용자가 말한 장면):** → Task 1 `test_walk_in_host_asks_for_a_reservation_first`.
4. **지어낸 값이 설명에 있다:** 대본의 2박, 킹 침대, 30분, 바가 설명에도 있어야 리뷰 기준(설명에 든 사실만)에 맞는다. → Task 1 `test_reservation_values_are_in_the_description`.
5. **목록 끝에 더한다:** 기존 시험과 앱이 `usa`의 앞 세 줄 순서에 기댄다(`get("usa").picks[0]`이 새우 트럭). → Task 1 `test_starting_lists`의 순서.

---

### Task 1: 대본 두 줄과 시험

**Files:**
- Modify: `server/je_server/topics.py` (`usa`의 `picks` 끝에 두 줄)
- Test: `server/tests/test_topics.py`

**Interfaces:**
- Consumes: `_pick(id, title_ko, situation, first, roles, lines)` (지금 있는 것)
- Produces: 목록 줄 id `u-hotel-online`, `u-seafood-walkin` (Task 2가 고르기 요청에 쓴다)

- [ ] **Step 1: 시험을 고치고 더한다**

```python
def test_starting_lists():
    # three per topic to try it first (user); 2026-11-08 two reservation scenes added to 「미국 여행」 at its end
    assert [len(get(t).picks) for t in ("tourist", "usa", "other")] == [3, 5, 0]
    assert [p.id for p in get("usa").picks] == ["u-shrimp-truck", "u-hotel-checkin", "u-sneaker-size",
                                                "u-hotel-online", "u-seafood-walkin"]
    assert [p.first for p in get("usa").picks] == ["ryan", "user", "user", "ryan", "ryan"]
    ...  # 나머지 줄은 그대로
```

`test_script_keeps_the_facts_of_its_description`에 더할 줄:

```python
    assert all(w in said["u-hotel-online"] for w in ("booked online", "confirmation number", "two nights",
                                                     "king room", "high floor"))
    assert all(w in said["u-seafood-walkin"] for w in ("reservation", "table for two", "30-minute wait", "bar",
                                                       "put my name down"))
```

`test_korean_keeps_the_facts`에 더할 줄:

```python
    assert all(w in said["u-hotel-online"] for w in ("온라인", "확인 번호", "2박", "킹 침대", "높은 층"))
    assert all(w in said["u-seafood-walkin"] for w in ("예약", "두 명", "30분", "바에", "이름"))
```

새 시험(「예약 상황」 절을 파일 끝에 둔다):

```python
def test_reserved_hotel_says_how_it_was_booked():
    # todo 38: the old hotel pick is already booked; this one says how (online) in the learner's first line
    p = pick("usa", "u-hotel-online")
    first = next(i for i, (s, _) in enumerate(p.script) if s == "user")
    assert "online" in p.script[first][1] and "온라인" in p.ko[first]

def test_walk_in_host_asks_for_a_reservation_first():
    # the user: the staff ask whether we booked
    p = pick("usa", "u-seafood-walkin")
    assert p.script[0][0] == "ryan" and "reservation" in p.script[0][1] and "예약" in p.ko[0]

def test_reservation_values_are_in_the_description():
    # the made-up values the scripts say are facts of the description too (REVIEW.md 「목록 대본의 사실」)
    hotel, food = pick("usa", "u-hotel-online").situation, pick("usa", "u-seafood-walkin").situation
    assert all(w in hotel for w in ("온라인", "확인 번호", "킹 침대", "2박", "높은 층"))
    assert all(w in food for w in ("예약 없이", "30분", "바", "대기 명단"))

def test_walk_in_korean_says_no_more_than_the_english():
    # the bar is only another place to sit; 「바로」(right away) is not in the English
    assert not any("바로" in k for k in pick("usa", "u-seafood-walkin").ko)
```

- [ ] **Step 2: 실패를 본다**

Run: `cd server && uv run pytest -q tests/test_topics.py`
Expected: FAIL (`KeyError: 'u-hotel-online'` 또는 `[3, 3, 0] == [3, 5, 0]`)

- [ ] **Step 3: `topics.py`에 두 줄을 넣는다**

위 「대본」 표 그대로. 각 줄 위에 기존 호텔처럼 주석 한 줄: 지어낸 작은 값(호텔: 2박, 킹 침대 방, 12층 / 식당: 30분, 예약 이름 Jake)이고 가게에 이름이 없다는 것(`REVIEW.md` 「목록 대본의 사실」).

- [ ] **Step 4: 시험이 통과하는지 본다**

Run: `cd server && uv run pytest -q`
Expected: 모두 통과(지금 535에 새 시험 넷이 더해진다)

- [ ] **Step 5: 공개 파일 확인** — 넣은 대사와 통역을 `topics.py`에서 읽어 앱 데이터 폴더의 모든 기록과 문장 단위로 맞댄다. 개수만 출력한다. 기대: 0.

- [ ] **Step 6: Commit** — `feat(server): add two reservation scenes to the usa list`

### Task 2: 시험 서버와 에뮬레이터로 확인

**Files:** 없음(확인만)

- [ ] **Step 1:** 빈 포트를 보고, 녹음을 뺀 데이터 복사본(`roleplays/`, `audio/`, `saved.json`)으로 `JE_HOST=127.0.0.1 JE_PORT=8791 JE_WHISPER_PORT=8792` 시험 서버를 띄운다(`docs/guide/DEVENV_맥서버_저절로_띄우기_20261107.md` 「launchd 서버를 멈추지 않고 시험하기」).
- [ ] **Step 2:** `/home`의 `usa` 목록에 새 두 줄이 이 순서로 있다.
- [ ] **Step 3:** 두 줄을 하나씩 `POST /roleplays {"topic": "usa", "pick": ...}`로 고른다. 기대: 1초 안에 돌아오고 `lines`가 `topics.py` 대본 그대로다. 뒤에서 줄마다 소희 소리(`ko_audio`)와 본보기 소리(`audio`)가, 내 대사 셋에 세 줄 표시(`three`)가 만들어진다. 같은 줄을 한 번 더 고르면 같은 묶음(`origin`)이고 Claude를 부르지 않는다.
- [ ] **Step 4:** 이 앱 전용 에뮬레이터(AVD `jake-english`)의 앱을 시험 서버에 붙여 「미국 여행」 목록에 두 카드가 보이는지 스크린샷으로 본다(`docs/guide/DEVENV_폰을_adb로_시험하기_20261108.md`). 녹음 버튼은 누르지 않는다.
- [ ] **Step 5:** 시험 서버와 에뮬레이터를 끄고, 두 포트가 비었는지 보고, 복사한 데이터를 지운다. Sonnet 부름 횟수와 금액을 적어 둔다(PR과 devlog에 쓴다).

### Task 3: 문서와 PR

**Files:**
- Modify: `docs/superpowers/specs/2026-11-07-situation-topics-design.md` 3 「미국 여행」 표(두 줄)
- Modify: `docs/superpowers/specs/2026-11-08-fixed-list-scripts-design.md` 「처음 대본」 뒤에 더한 대본 두 개(영어 표, 정한 것과 까닭)
- Create: `docs/devlog/2026-11-08-list-reservations.md`
- Modify: 할 일 `docs/todo/20261108_38_todo_list_scripts_reservations.md`(원래 폴더에서 복사해 와 상태를 「완료」로)

- [ ] **Step 1:** 두 스펙에 두 줄을 더한다. Commit: `docs(server): write down the two reservation scenes`
- [ ] **Step 2:** push, PR, 브랜치 리뷰와 pr-review를 돌리는 동안 devlog와 PR 본문을 쓴다. 리뷰에서 고친 것은 나중에 더한다.
- [ ] **Step 3:** 할 일 파일 상태를 「완료」로 고쳐 devlog와 함께 커밋한다. Commit: `docs: add list-reservations devlog and close its todo`
- [ ] **Step 4:** main 세션에 「머지 준비 됨」을 보낸다.
