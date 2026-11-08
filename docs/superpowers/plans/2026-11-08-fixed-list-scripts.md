# 목록 상황의 정해 둔 대본 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 목록에서 고른 상황은 저장소에 써 둔 대본으로 Claude 없이 바로 시작하고, 같은 목록 상황의 회차는 한 묶음(원본 ID)이 된다.

**Architecture:** 목록 줄(`topics.Pick`)에 상황 틀과 대본을 더한다. `Engine.create_pick`이 그 대본으로 역할극을 만들고, 같은 목록 줄의 지난 회차에서 원본 ID와 준비된 것(읽는 법, 본보기 소리, 통역)을 가져온다. 목록 상황의 「이 상황 다시 하기」(`Engine.copy`)도 이 길로 간다. 앱은 약속 시험의 키 목록만 맞춘다.

**Tech Stack:** Python 3 + FastAPI + pydantic(서버, `cd server && uv run pytest`), TypeScript(앱 약속 시험, `cd app && npx jest src/api/contract.test.ts && npm run typecheck`).

**Spec:** `docs/superpowers/specs/2026-11-08-fixed-list-scripts-design.md` (결정: `docs/adr/0013-fixed-scripts-for-list-picks.md`)

## Global Constraints

- 대본은 「처음 대본」 절의 글을 그대로 옮긴다. 낱말은 다듬어도 되지만 사실을 바꾸거나 더하지 않는다. 사실은 그 목록 줄의 자세한 설명에 든 것만 쓴다.
- 대본은 `Claude.script_problems(draft, pick.first) == []`를 지키고, 내 대사는 12낱말 이하다.
- 상황 틀의 `title_ko`는 그 목록 줄의 카드 이름(`Pick.title_ko`)과 같다.
- 지난 역할극 기록의 대사를 옮기지 않는다. 실제 사람 이름을 쓰지 않는다(공개 저장소).
- 목록에서 고를 때 대본을 쓰려고 Claude를 부르지 않는다.
- 한 목록 줄의 묶음은 하나다. 기록을 읽고 새 역할극을 저장할 때까지 `await`를 두지 않는다. 그래서 같은 목록 줄의 두 요청이 거의 동시에 와도 이벤트 루프에서 하나씩 끝난다(스펙 2 「한 번에 하나씩」).
- 화면은 고치지 않는다. APK를 새로 빌드하지 않는다.
- 이 worktree에서는 git을 `/usr/bin/git`으로 부른다. 커밋은 `git commit -F - <<'EOF'`로 하고, Conventional Commits 영어, 본문에 이유와 시험 결과, 끝에 `Refs:` 줄을 쓴다. AI 서명 줄은 넣지 않는다.

## Review Focus

1. **빠르게 두 번 고르기:** 같은 목록 줄을 거의 동시에 두 번 고르면 묶음이 둘로 갈리지 않는다. 시험: Task 3의 `test_two_picks_at_once_share_one_group`.
2. **앞선 회차가 아직 준비 중:** 처음 고른 회차의 읽는 법이 다 만들어지기 전에 다시 고르면, 새 회차는 준비된 줄만 가져오고 나머지는 스스로 만든다. 두 회차 모두 결국 읽는 법을 가진다. 시험: Task 3의 `test_pick_while_the_first_is_preparing`.
3. **한글 없는 읽는 법:** 앞선 회차의 읽는 법이 한글 없이 남았으면 가져오지 않고 다시 만든다. 설명만 빠진 것은 가져온다. 시험: Task 3의 `test_blank_note_is_made_again`, `test_note_without_reading_is_kept`.
4. **목록에서 빠진 줄의 「이 상황 다시 하기」:** 목록에서 그 줄을 지웠어도 지난 회차를 다시 할 수 있다. 시험: Task 4의 `test_copy_of_a_pick_gone_from_the_list`.
5. **대본을 고친 뒤:** 고친 줄만 새로 만들고 묶음은 그대로다. 시험: Task 3의 `test_changed_line_is_made_again`.

---

### Task 1: 목록 줄의 상황 틀과 대본

**Files:**
- Modify: `server/je_server/topics.py` (`Pick`, `TOPICS`, 모듈 설명)
- Test: `server/tests/test_topics.py`

**Interfaces:**
- Produces: `Pick.frame: Frame`, `Pick.script: tuple[tuple[Speaker, str], ...]`. `Pick`은 지금처럼 `frozen=True` dataclass이고 두 필드는 `first` 뒤에 온다. `topics.pick(topic_id, pick_id) -> Pick`은 그대로다.

- [ ] **Step 1: 시험을 쓴다** (`server/tests/test_topics.py`에 더한다)

```python
from je_server.claude import Claude

ALL = [p for t in TOPICS for p in t.picks]


def test_every_pick_has_a_script_that_passes_the_script_checks():
    # spec fixed-list-scripts 1: the same checks as a script Claude writes
    for p in ALL:
        assert Claude.script_problems(list(p.script), p.first) == [], p.id
        assert all(len(t.split()) <= 12 for s, t in p.script if s == "user"), p.id


def test_script_title_is_the_card_title():
    # the past list shows the frame's title; it must read as the card that was picked
    assert all(p.frame.title_ko == p.title_ko for p in ALL)


def test_script_keeps_the_facts_of_its_description():
    # spec fixed-list-scripts 1: the facts in each list description, as said in the script
    said = {p.id: " ".join(t for _, t in p.script) for p in ALL}
    assert all(w in said["t-gyeongbokgung"] for w in ("Line 4", "one stop", "Chungmuro", "Line 3", "Exit 5"))
    assert "only takes cash" in said["t-tmoney"] and "convenience store" in said["t-tmoney"]
    assert "samgyeopsal" in said["t-samgyeopsal"] and "two servings" in said["t-samgyeopsal"]
    assert all(w in said["u-shrimp-truck"] for w in ("Giovanni's", "shrimp scampi", "hot and spicy",
                                                     "lemon butter", "two scoops of rice"))
    assert all(w in said["u-hotel-checkin"] for w in ("passport", "credit card", "checkout", "Wi-Fi"))
    assert "270" in said["u-sneaker-size"] and "men's 9" in said["u-sneaker-size"]


def test_script_has_no_hangul_or_braces():
    import re
    assert not any(re.search(r"[가-힣{}]", t) for p in ALL for _, t in p.script)
```

- [ ] **Step 2: 실패를 본다**

Run: `cd server && uv run pytest tests/test_topics.py -q`
Expected: FAIL, `AttributeError: 'Pick' object has no attribute 'script'`

- [ ] **Step 3: `Pick`에 `frame`과 `script`를 더하고, 여섯 목록 줄에 스펙 「처음 대본」의 상황 틀과 대사를 넣는다**

상황 틀의 다섯 값은 스펙 「처음 대본」의 「틀:」 줄을 그대로 쓴다(`title_ko`는 카드 이름). 모듈 설명(docstring)에 「대본도 이 파일에 있고, 사실을 바꿀 때는 설명, 대본, `test_topics.py`를 함께 고친다」를 더한다.

- [ ] **Step 4: 통과를 본다**

Run: `cd server && uv run pytest tests/test_topics.py -q`
Expected: PASS

- [ ] **Step 5: 커밋**

```bash
/usr/bin/git add server/je_server/topics.py server/tests/test_topics.py
/usr/bin/git commit -F - <<'EOF'
feat(server): write a fixed script for every list pick
...(이유와 시험 결과)
Refs: docs/superpowers/specs/2026-11-08-fixed-list-scripts-design.md
EOF
```

### Task 2: 기록에 목록 줄 id

**Files:**
- Modify: `server/je_server/models.py` (`Roleplay`)
- Modify: `contract/roleplay.json`
- Modify: `app/src/api/types.ts` (`Roleplay`, `ROLEPLAY_KEYS`)
- Test: `server/tests/test_contract.py`(그대로 돌린다), `app/src/api/contract.test.ts`(그대로 돌린다), `server/tests/test_store.py`

**Interfaces:**
- Produces: `Roleplay.pick: str | None = None`(목록 줄 id, 목록이 아닌 역할극과 옛 기록은 `None`). 앱 `Roleplay.pick: string | null`.

- [ ] **Step 1: 시험을 쓴다** (`server/tests/test_store.py`에 더한다)

```python
def test_old_record_without_pick_is_read(tmp_path):
    # spec fixed-list-scripts 5: a field with a default, so records from before keep loading
    from je_server.models import Roleplay
    raw = {"id": "a" * 12, "created": "2026-11-07T10:00:00", "situation": "길 묻기",
           "frame": {"title_ko": "길", "user_role_ko": "나", "ryan_role_ko": "R", "place_ko": "역", "goal_ko": "묻기"},
           "lines": []}
    assert Roleplay.model_validate(raw).pick is None
```

그리고 `contract/roleplay.json`에 `"pick": null`을 `"topic"` 뒤에 더한다.

- [ ] **Step 2: 실패를 본다**

Run: `cd server && uv run pytest tests/test_store.py tests/test_contract.py -q`
Expected: FAIL (`pick` 속성이 없고, 약속 예시가 모델과 다르다)

- [ ] **Step 3: `Roleplay`에 `pick`을 더하고(주석: 「목록 줄 id, spec fixed-list-scripts 5」), 앱 `types.ts`의 `Roleplay` 타입과 `ROLEPLAY_KEYS`에 `pick`을 더한다**

- [ ] **Step 4: 통과를 본다**

Run: `cd server && uv run pytest tests/test_store.py tests/test_contract.py -q` 와 `cd app && npx jest src/api/contract.test.ts && npm run typecheck`
Expected: 모두 PASS, 타입 검사 오류 0

- [ ] **Step 5: 커밋** (`feat(server): record the list pick on a roleplay`)

### Task 3: 목록에서 고르면 저장소의 대본으로 만든다

**Files:**
- Modify: `server/je_server/threeline.py` (새 함수 `blank`)
- Modify: `server/je_server/engine.py` (`create`에서 `first` 인자를 뺀다, 새 `create_pick`과 `_prepared`)
- Modify: `server/je_server/app.py` (`POST /roleplays`의 목록 갈래)
- Modify: `server/tests/fakes.py` (`FakeClaude.annotate`가 한글이 든 읽는 법을 돌려준다)
- Create: `server/tests/test_picks.py`
- Modify: `server/tests/test_api.py` (`test_create_from_a_pick`)

**Interfaces:**
- Consumes: `topics.pick(topic_id, pick_id) -> Pick`(Task 1의 `frame`, `script`), `Roleplay.pick`(Task 2).
- Produces:
  - `threeline.blank(three: ThreeLine) -> bool`: 음절 어디에도 한글(`ko`)이 없으면 참(`plain`이 만든 것).
  - `Engine.create_pick(topic_id: str, pick_id: str) -> Roleplay`: 목록 줄이 그 주제에 없으면 `KeyError`(경로가 먼저 걸러 422로 돌려준다).
  - `Engine._prepared(runs: list[Roleplay], line: ScriptLine) -> ScriptLine`: `runs`는 같은 목록 줄의 회차, 만든 때 순. 같은 `idx`, 같은 `speaker`, 같은 `text`인 줄을 가장 최근 회차부터 찾아 필드마다 처음 만난 값을 넣는다. `three`는 `blank`가 아닐 때만, `audio`는 있을 때, `ko`와 `ko_audio`는 `ko`가 있는 같은 회차에서 함께 가져온다.
  - `Engine.create(situation: str, topic: str = topics.OTHER) -> Roleplay`: `first` 인자를 뺀다. 목록만 그것을 넘겼다.

`create_pick`의 순서: 목록 줄을 찾는다 → `self.store.all()`에서 `pick`이 같은 회차를 만든 때 순으로 모은다 → 원본 ID는 가장 이른 회차의 `group_of`(없으면 `None`) → 대본으로 줄을 만들고 `_prepared`로 채운다 → `Roleplay(situation=pick.situation, frame=pick.frame, topic=topic_id, pick=pick_id, origin=...)`을 저장 → 준비되지 않은 줄을 `schedule`. 저장할 때까지 `await`가 없다(Global Constraints).

- [ ] **Step 1: 가짜 읽는 법에 한글을 넣는다**

`fakes.py`에 `noted(text) -> ThreeLine`(낱말마다 음절 하나, `ko="가"`, `m="n"`, `reading=""`)을 두고 `FakeClaude.annotate`가 그것을 돌려준다. `plain`을 돌려주면 모든 가짜 읽는 법이 `blank`라 가져오는 시험을 할 수 없다.

Run: `cd server && uv run pytest -q`
Expected: 지금과 같은 수가 PASS(가짜 읽는 법의 내용을 보는 시험은 `test_engine.py:58` 하나이고, 자기 자신과 견준다)

- [ ] **Step 2: 시험을 쓴다** (`server/tests/test_picks.py`)

시험마다 대본이 내 대사로 시작하는 `("usa", "u-sneaker-size")`와 라이언으로 시작하는 `("tourist", "t-gyeongbokgung")` 가운데 하나를 쓴다. 준비가 끝나기를 기다릴 때는 `for l in rp.lines: await engine.line(rp.id, l.idx)`.

```python
async def test_pick_makes_no_claude_script(engine, fake_claude):
    p = pick("usa", "u-sneaker-size")
    rp = await engine.create_pick("usa", "u-sneaker-size")
    assert not any(n == "make_script" for n, _ in fake_claude.calls)
    assert [(l.speaker, l.text) for l in rp.lines] == list(p.script)
    assert rp.frame == p.frame and rp.situation == p.situation
    assert (rp.topic, rp.pick, rp.origin) == ("usa", "u-sneaker-size", None)

async def test_pick_again_joins_the_group_and_calls_no_claude(engine, fake_claude):
    first = await engine.create_pick("usa", "u-sneaker-size"); await ready(engine, first)
    calls = len(fake_claude.calls)
    second = await engine.create_pick("usa", "u-sneaker-size")
    third = await engine.create_pick("usa", "u-sneaker-size")
    assert second.origin == first.id and third.origin == first.id  # a copy of a copy points at the first
    assert all(engine.ready(l) for l in second.lines)               # notes and sounds came with it
    assert fake_claude.calls[calls:] == []

async def test_picked_runs_are_one_row_in_the_past_list(engine):
    runs = [await engine.create_pick("usa", "u-sneaker-size") for _ in range(2)]
    for rp in runs:  # a followed turn at a learner line makes the run 「해 본 상황」 (review.spoken)
        await engine.save_attempt(rp.id, 0, Attempt(n=1, mode="turn", heard="x", followed=True, issues=[],
                                                    say_ko="", audio=[], timings={}), pos=1)
    rows = [r for r in engine.past() if r["title_ko"] == "알라모아나 센터에서 운동화 사이즈"]
    assert len(rows) == 1 and rows[0]["group"] == runs[0].id

async def test_two_picks_at_once_share_one_group(engine):
    a, b = await asyncio.gather(engine.create_pick("usa", "u-sneaker-size"),
                                engine.create_pick("usa", "u-sneaker-size"))
    firsts = [r for r in (a, b) if r.origin is None]
    assert len(firsts) == 1 and {a.origin, b.origin} == {None, firsts[0].id}

async def test_pick_while_the_first_is_preparing(engine, fake_claude):
    fake_claude.annotate_gate = asyncio.Event()
    first = await engine.create_pick("usa", "u-sneaker-size")
    second = await engine.create_pick("usa", "u-sneaker-size")
    assert second.origin == first.id and all(l.three is None for l in second.lines if l.speaker == "user")
    fake_claude.annotate_gate.set(); await ready(engine, first); await ready(engine, second)
    assert all(engine.store.load(r.id).lines[i].three for r in (first, second)
               for i, l in enumerate(r.lines) if l.speaker == "user")

async def test_changed_line_is_made_again(engine, fake_claude, monkeypatch):
    first = await engine.create_pick("usa", "u-sneaker-size"); await ready(engine, first)
    old = pick("usa", "u-sneaker-size")
    new_script = (("user", "Excuse me, could I try these in another size?"),) + old.script[1:]
    monkeypatch.setattr(topics, "pick", lambda t, i: dataclasses.replace(old, script=new_script))
    second = await engine.create_pick("usa", "u-sneaker-size")
    assert second.origin == first.id and second.lines[0].three is None and second.lines[0].audio is None
    assert all(engine.ready(l) for l in second.lines[1:])

async def test_blank_note_is_made_again(engine, fake_claude):
    # spec fixed-list-scripts 2: a note left with no Korean is not reused
    first = await engine.create_pick("usa", "u-sneaker-size"); await ready(engine, first)
    rec = engine.store.load(first.id); rec.lines[0] = rec.lines[0].model_copy(update={"three": plain(rec.lines[0].text)})
    engine.store.save(rec)
    second = await engine.create_pick("usa", "u-sneaker-size")
    assert second.lines[0].three is None and second.lines[0].audio == rec.lines[0].audio

async def test_note_without_reading_is_kept(engine):
    # a note with Korean but no reading (the 「ref」 degrade) is reused: `noted` already has reading=""
    first = await engine.create_pick("usa", "u-sneaker-size"); await ready(engine, first)
    second = await engine.create_pick("usa", "u-sneaker-size")
    assert second.lines[0].three == engine.store.load(first.id).lines[0].three

async def test_ko_comes_with_its_sound(engine):
    first = await engine.create_pick("usa", "u-sneaker-size"); await ready(engine, first)
    await engine.ko(first.id, 1)
    key = await engine.ko_audio(first.id, 1)
    second = await engine.create_pick("usa", "u-sneaker-size")
    assert second.lines[1].ko == engine.store.load(first.id).lines[1].ko and second.lines[1].ko_audio == key
```

`ready(engine, rp)`는 이 파일의 도우미로 둔다. `pick`, `topics`, `plain`, `Attempt`, `dataclasses`, `asyncio`를 불러온다.

`test_api.py`의 `test_create_from_a_pick`을 고친다: `make_script` 부름이 없고, `rp["pick"] == "u-hotel-checkin"`, `rp["frame"]["title_ko"] == "뉴욕 호텔 체크인"`, 대사가 `pick("usa", "u-hotel-checkin").script`와 같다. 같은 요청을 한 번 더 보내면 `origin`이 첫 응답의 `id`다.

- [ ] **Step 3: 실패를 본다**

Run: `cd server && uv run pytest tests/test_picks.py tests/test_api.py -q`
Expected: FAIL, `AttributeError: 'Engine' object has no attribute 'create_pick'`

- [ ] **Step 4: `blank`, `create_pick`, `_prepared`를 쓰고, 경로를 바꾸고, `create`에서 `first`를 뺀다**

경로의 목록 갈래는 `rp = await engine().create_pick(body.topic, body.pick)`. `Claude.make_script`의 `first`는 그대로 둔다(주제의 첫 사람과 시험이 쓴다).

- [ ] **Step 5: 통과를 본다**

Run: `cd server && uv run pytest -q`
Expected: 모두 PASS

- [ ] **Step 6: 커밋** (`feat(server): start a list pick from its fixed script`)

### Task 4: 목록 상황의 「이 상황 다시 하기」

**Files:**
- Modify: `server/je_server/engine.py` (`copy`)
- Test: `server/tests/test_picks.py`

**Interfaces:**
- Consumes: `Engine.create_pick`(Task 3).
- Produces: `Engine.copy(rp_id)`의 모양은 그대로다. 목록 상황이면 `create_pick(old.topic, old.pick)`의 결과를, 그 줄이 목록에 없으면(`KeyError`) 지금처럼 복사한 결과를 돌려준다. 복사본도 `pick=old.pick`을 가진다.

- [ ] **Step 1: 시험을 쓴다**

```python
async def test_copy_of_a_pick_uses_the_current_script(engine, monkeypatch):
    first = await engine.create_pick("usa", "u-sneaker-size"); await ready(engine, first)
    old = pick("usa", "u-sneaker-size")
    new_script = (("user", "Excuse me, could I try these in another size?"),) + old.script[1:]
    monkeypatch.setattr(topics, "pick", lambda t, i: dataclasses.replace(old, script=new_script))
    again = await engine.copy(first.id)
    assert [(l.speaker, l.text) for l in again.lines] == list(new_script)
    assert (again.origin, again.pick) == (first.id, "u-sneaker-size")

async def test_copy_of_a_pick_gone_from_the_list(engine, monkeypatch):
    first = await engine.create_pick("usa", "u-sneaker-size"); await ready(engine, first)
    def gone(t, i): raise KeyError(i)
    monkeypatch.setattr(topics, "pick", gone)
    again = await engine.copy(first.id)
    assert again.lines == engine.store.load(first.id).lines
    assert (again.origin, again.pick) == (first.id, "u-sneaker-size")
```

지금 `test_engine.py`의 복사 시험들(목록이 아닌 역할극)은 그대로 통과해야 한다.

- [ ] **Step 2: 실패를 본다**

Run: `cd server && uv run pytest tests/test_picks.py -q`
Expected: FAIL(`copy`가 옛 대사를 복사하고 `pick`이 비어 있다)

- [ ] **Step 3: `copy`를 고친다**

- [ ] **Step 4: 통과를 본다**

Run: `cd server && uv run pytest -q`
Expected: 모두 PASS

- [ ] **Step 5: 커밋** (`feat(server): replay a list pick from its current script`)

### Task 5: 문서

**Files:**
- Modify: `docs/PRD.md` (맨 위 「고침」 줄, 「상황 정하기」의 「목록에서 고르기」)
- Modify: `docs/superpowers/specs/2026-11-07-situation-topics-design.md` (머리의 안내 줄, 「하지 않을 것」의 「대본을 미리 써 두기」, 3, 5, 7, 8)
- Modify: `docs/guide/DEVENV_맥서버_저절로_띄우기_20261107.md` (「카드가 서버를 시험할 때」에 launchd 서버를 멈추지 않고 시험하는 길)
- Create: `docs/todo/20261108_02_todo_list_pick_fixed_script.md` (원래 폴더의 파일을 옮겨 상태를 완료로)

- [ ] **Step 1: PRD를 고친다.** 「목록에서 고르기」에 「목록 상황은 대화도 정해 둔다. 고르면 Claude를 부르지 않고 바로 시작하고, 같은 상황을 다시 고르면 같은 대본의 다음 회차가 된다」와 바꾼 이유(스펙 「왜 만드나」의 사용자 말)를 쓰고 스펙과 ADR-0013을 가리킨다. 맨 위 「고침」 줄에 2026-11-08 한 문장을 더한다.
- [ ] **Step 2: 상황 주제 스펙을 고친다.** 「하지 않을 것」의 「대본을 미리 써 두기」 줄은 지우지 않고 「2026-11-08 뒤집음」과 까닭(사용자 말, 받아들인 뜻이 달랐다)을 붙여 새 스펙을 가리킨다. 3(목록 줄에 담는 것), 5(목록 상황의 대본), 7(기록), 8(토큰)에 새 스펙을 가리키는 한 줄씩을 더한다. 본문의 옛 결정은 그대로 둔다(그 스펙의 머리 안내 방식과 같다).
- [ ] **Step 3: DEVENV 가이드에 「launchd 서버를 멈추지 않고 시험하기」를 더한다.** worktree의 `server/`를 `JE_HOST=127.0.0.1`, 빈 `JE_PORT`, 빈 `JE_WHISPER_PORT`, 앱 데이터 폴더 복사본의 `JE_DATA_DIR`로 띄운다. 8790은 답 읽기 도구가 쓰는 포트라 피한다(2026-11-08 겪음). 띄우기 전에 `lsof -nP -iTCP -sTCP:LISTEN`으로 빈 포트를 본다. 이 맥의 경로와 주소는 쓰지 않는다. `docs/guide/README.md` 색인 줄이 이 가이드를 이미 가리키면 설명만 고친다.
- [ ] **Step 4: 할 일 파일을 옮긴다.** 원래 폴더 `docs/todo/20261108_02_todo_list_pick_fixed_script.md`를 이 worktree의 같은 자리에 복사하고, 상태 줄을 「**완료** (2026-11-08, fixed-list-scripts 카드 PR)」로, 할 일 1~4 아래에 어떻게 끝났는지 한 줄씩(3은 원본 ID로 묶여 화면을 고치지 않음) 고친다. 원래 폴더의 파일은 머지 뒤 정리할 때 지운다(그대로 두면 main을 fast-forward할 때 막힌다).
- [ ] **Step 5: 커밋** (`docs: record fixed scripts for list picks in the PRD and specs`). 공개 금지 검사가 통과하는지 본다.

### Task 6: 실제 서버로 시험하고 시간을 잰다

**Files:** 없음(결과는 devlog와 PR 본문에 쓴다)

- [ ] **Step 1: 빈 포트를 보고 시험 서버를 띄운다.** 앱 데이터 폴더를 임시 폴더에 새로 복사하고, worktree `server/`를 `JE_HOST=127.0.0.1 JE_PORT=8791 JE_WHISPER_PORT=8792 JE_DATA_DIR=<복사본>`으로 띄운다. 로그는 임시 폴더에 둔다. 원래 폴더 서버는 멈추지 않는다.
- [ ] **Step 2: 앱과 같은 요청으로 잰다.** 「운동화 사이즈」와 「경복궁」을 각각 두 번 고른다(`POST /roleplays {"topic", "pick"}`). 매번 고르기 요청과, 첫 내 대사까지 줄마다 `GET /roleplays/{id}/lines/{idx}`이 돌아오는 시간을 잰다.
  Expected: 고르기 요청 1초 아래(Claude 부름 없음). 첫 회차의 첫 내 대사는 읽는 법을 기다린다(고치기 전과 비슷). 두 번째 회차는 첫 내 대사까지 1초 아래. 두 번째 회차의 `origin`은 첫 회차의 `id`. 시험 서버 로그에 대본을 쓰는 Claude 부름(`make_script`의 요청)이 없고, 두 번째 회차에는 `three-line note` 줄도 없다.
- [ ] **Step 3: 시험 서버를 끈다.** 포트 8791과 8792가 비었는지 본다. 복사본 폴더는 지운다.
- [ ] **Step 4: 잰 값을 남긴다.** 고치기 전(스펙 6)과 뒤를 표로 devlog 초안에 적는다.

## PR 뒤 (계획 밖, `AGENTS.md`)

push하고 PR을 연 뒤 pr-review로 리뷰하고, 확인된 문제를 고쳐 같은 PR에 push한다. devlog(`docs/devlog/2026-11-08-fixed-list-scripts.md`, 색인 `docs/devlog/README.md`)를 같은 PR에 커밋한다. 머지 전에 origin/main을 다시 merge한다. 앱 화면이 바뀌지 않으니 APK는 빌드하지 않고, 폰 확인은 부탁하지 않는다.
