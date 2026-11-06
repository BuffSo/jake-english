# 따라 말한 차례 평가 고치기 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 따라 말한 차례에서 대사와 다르게 들린 곳(목록에 없는 소리, 빠진 낱말, 더한 낱말, 개수가 다른 바뀜)을 짚고, 맥이 확인한 것만 칭찬한다.

**Architecture:** 맥 서버의 `compare.py`가 대사와 받아쓴 글의 표기를 맞춘 뒤 다른 곳을 모두 찾고(`compare`), 많아야 두 가지를 고르고(`find_issues`), 확인한 칭찬 후보를 만든다(`praise_candidates`). `engine.attempt`는 같은 줄의 지난 시도에서 짚은 것을 넘겨 「나아진 점」을 찾게 한다. 끝 화면 요약은 짚은 것마다 보여 줄 한국어 한 줄(`say_ko`)을 서버가 만들어 보내고, 앱은 그것을 그대로 보인다.

**Tech Stack:** 서버 Python 3 + FastAPI + pytest(`uv`), CMUdict. 앱 React Native + Expo + Jest + TypeScript. 새 의존성 없음.

**Spec:** `docs/superpowers/specs/2026-11-05-speaking-practice-design.md` 「평가」의 따라 말했을 때, 잘한 점 후보, 받아쓰기가 틀릴 때, 「잰 것」의 「따라 말한 차례에서 짚는 수」 (함께 읽을 것: `docs/PRD.md` 「평가」, 「실패로 볼 것」)

## Global Constraints

- 이 worktree에서 git은 `/usr/bin/git`으로 부른다. `git add`는 파일을 지정한다(`-A`, `.` 금지). 커밋은 `git commit -F - <<'EOF'`, Conventional Commits 영어, scope는 `server`, `app`(둘에 걸치면 생략). AI 서명 줄을 넣지 않는다. 본문에 왜, 어떻게 확인했는지(명령과 결과)를 쓰고 끝에 `Refs: docs/superpowers/specs/2026-11-05-speaking-practice-design.md`를 단다.
- 테스트 문장은 지어낸 것만 쓴다(`REVIEW.md`, ADR-0005). 사용자 녹음과 그것을 받아쓴 글(기록의 `heard`, 스펙 「잰 것」을 잴 때 본 줄)을 코드, 테스트, 문서, 커밋 메시지에 쓰지 않는다. 홈 폴더 경로도 쓰지 않는다.
- 녹음은 맥 밖으로 보내지 않는다. Anthropic에는 대사, 받아쓴 글, 맥이 정한 짚을 것과 소리 설명, 칭찬 후보만 간다(ADR-0004).
- 짚는 것은 많아야 두 가지다(스펙 「실패로 볼 것」 4). 소리 설명은 「소리 설명 목록」(`server/je_server/data/sounds.json`)에서만 쓴다.
- 라이언은 「~처럼 들렸어요」, 「~가 들리지 않았어요」로 말하고 「~라고 말했어요」라고 하지 않는다(스펙 「평가」 6).
- 서버 시험: `cd server && uv run pytest -q`(시작 전 178 passed). 앱 시험: `cd app && npm test && npx tsc --noEmit`. 둘 다 매 작업 끝에 통과해야 한다.
- 문서(가이드, devlog, PR 본문)는 한국어, 코드와 주석은 영어.
- 맥 서버의 포트는 하나다. 서버를 끄거나 띄우기 전에 사용자에게 알리고, 다른 카드가 시험 중인지 묻는다.

## Review Focus

1. **받아쓰기가 돈, 시각, 퍼센트를 숫자로 적는다:** 「five dollars」를 「$5」로, 「five thirty」를 「5:30」으로 적어도 짚지 않아야 한다 → Task 1 `test_numbers_and_short_forms_are_not_differences`.
2. **말하다 막혀 앞부분을 되풀이한다:** 「I'd like a, um, I'd like a cup of tea」는 짚을 것이 없어야 한다 → Task 1 `test_restart_and_fillers_are_not_differences`.
3. **고치기 전에 저장한 기록:** `sound`가 늘 있던 옛 `Issue`가 그대로 읽히고, 끝 화면 요약이 그것으로 `say_ko`를 만든다 → Task 4 `test_summary_says_each_issue_in_korean`.
4. **대사에 같은 낱말이 두 번 나온다:** 두 번째 for를 빠뜨린 뒤 다시 해서 또 빠뜨리면, 첫 for가 맞게 들렸다고 「나아졌다」고 하면 안 된다 → Task 3 `test_improvement_needs_the_same_issue_gone`.
5. **맞게 들린 낱말이 하나도 없다:** 칭찬 후보가 빈 목록이어도 평가가 끝까지 나와야 한다 → Task 3 `test_praise_can_be_empty`.

---

## 파일 지도

| 파일 | 맡는 것 | 작업 |
|---|---|---|
| `server/je_server/models.py` | `Issue`(빠진 낱말, 더한 낱말, 목록에 없는 소리) | 1 |
| `server/je_server/compare.py` | 표기 맞추기, 다른 곳 찾기, 고르기, 칭찬 후보, 한국어 한 줄 | 1, 3 |
| `server/scripts/check_false_flags.py` | 시험 녹음과 기록으로 짚는 수 재기 | 2 |
| `server/je_server/engine.py` | `attempt`의 지난 시도 넘기기, `summary`의 `say_ko` | 3, 4 |
| `server/je_server/prompts.py` | `FEEDBACK_SYSTEM` | 3 |
| `contract/summary.json`, `app/src/api/types.ts`, `app/src/api/contract.test.ts`, `app/src/screens/EndScreen.tsx` | 끝 화면의 짚은 것 | 4 |

---

### Task 1: 다른 곳 찾기와 고르기

**Files:**
- Modify: `server/je_server/models.py` (`Issue`)
- Modify: `server/je_server/compare.py`
- Test: `server/tests/test_compare.py`

**Interfaces:**
- Produces:
  - `Issue(target: str, heard: str, sound: tuple[str, str] | None = None, explain: str = "")`. `target`은 대사 쪽 낱말(여럿이면 빈칸으로 이음, 더한 낱말이면 `""`), `heard`는 들린 쪽(빠진 낱말이면 `""`). `sound`는 목록에 있는 소리일 때만 `(대사 쪽 음소, 들린 쪽 음소)`.
  - `compare.words(text: str) -> list[str]`: 표기를 맞춘 소문자 낱말 목록(아래 Step 3).
  - `compare.Comparison`(dataclass): `diffs: list[Issue]`(문장 순서, 다른 곳 전부), `matched: int`(맞게 들린 대사 낱말 수), `total: int`(대사 낱말 수), `matched_words: set[str]`.
  - `compare.compare(target: str, heard: str) -> Comparison`
  - `compare.find_issues(target: str, heard: str, limit: int) -> list[Issue]`
  - `compare.sound_diff(target_word: str, heard_word: str) -> tuple[int, list[tuple[str, str]]] | None`: 사전 발음 조합 가운데 바뀐 음소가 가장 적은 것의 (바뀐 수, 1:1로 바뀐 음소 쌍). 한쪽이라도 사전에 없으면 `None`. `sound_pairs`는 이것의 쌍만 돌려준다(시그니처 그대로).
  - `compare.issue_ko(i: Issue) -> str`: 끝 화면의 한 줄.
  - `similarity`, `FOLLOW_MIN`, `word_pairs`, `praise_candidates`는 이 작업에서 시그니처와 동작을 바꾸지 않는다(`similarity`는 새 `words`를 쓴다).

- [ ] **Step 1: 실패하는 시험을 쓴다** (`server/tests/test_compare.py`)

`test_unlisted_sound_change_is_not_flagged`는 지우고 아래로 바꾼다. 나머지 기존 시험은 둔다.

```python
from je_server.compare import compare, issue_ko
from je_server.models import Issue


def test_unlisted_sound_change_is_flagged_without_explain():
    assert find_issues("I want the red one.", "I want the bed one.", limit=2) == [Issue(target="red", heard="bed")]


def test_missing_and_added_words_are_flagged():
    assert find_issues("It's on the left.", "It's the left.", limit=2) == [Issue(target="on", heard="")]
    assert find_issues("Turn left, then go straight.", "Turn left and then go straight.", limit=2) == [
        Issue(target="", heard="and")]


def test_count_changed_span_is_one_issue():
    issues = find_issues("I'll grab a coffee.", "I will grab coffee.", limit=2)
    assert [(i.target, i.heard) for i in issues] == [("i'll", "i will"), ("a", "")]


def test_listed_sound_found_inside_count_changed_span():
    [i] = find_issues("Turn right here.", "Turn a light here.", limit=2)
    assert (i.target, i.heard, set(i.sound)) == ("right", "a light", {"R", "L"}) and "혀" in i.explain


def test_far_apart_words_in_a_span_get_no_sound():
    [i] = compare("We close at nine.", "We'll go so at nine.").diffs
    assert (i.target, i.heard, i.sound) == ("we close", "we'll go so", None)


def test_numbers_and_short_forms_are_not_differences():
    for line, heard in [("It's about ten minutes.", "It's about 10 minutes"),
                        ("I want to go at eleven a.m.", "I wanna go at 11 AM."),
                        ("That's five dollars.", "That's $5."),
                        ("OK, see you at five thirty.", "Okay, see you at 5:30.")]:
        assert compare(line, heard).diffs == [], (line, heard)


def test_joined_and_split_words_are_the_same():
    assert compare("Check-in is at noon.", "Checkin is at noon.").diffs == []
    assert compare("Where is the checkout?", "Where is the check out?").diffs == []


def test_i_am_is_a_real_difference():
    assert find_issues("I'm ready.", "I am ready.", limit=2) == [Issue(target="i'm", heard="i am")]


def test_restart_and_fillers_are_not_differences():
    assert compare("I'd like a cup of tea.", "I'd like a, um, I'd like a cup of tea.").diffs == []


def test_two_at_most_front_first():
    issues = find_issues("Go left, then right, then left again.", "Go lift, then light, then lift again.", limit=2)
    assert [i.target for i in issues] == ["left", "right"]


def test_all_issues_kept_when_within_limit_even_same_sound():
    issues = find_issues("The rock is on the right.", "The lock is on the light.", limit=2)
    assert [(i.target, set(i.sound)) for i in issues] == [("rock", {"R", "L"}), ("right", {"R", "L"})]


def test_comparison_counts_matched_words():
    c = compare("Go left, then right.", "Go lift, then light.")
    assert (c.matched, c.total, c.matched_words) == (2, 4, {"go", "then"})


def test_issue_ko_says_what_was_heard():
    assert issue_ko(Issue(target="right", heard="light")) == "「right」 → 「light」처럼 들렸어요"
    assert issue_ko(Issue(target="on", heard="")) == "「on」 → 들리지 않았어요"
    assert issue_ko(Issue(target="", heard="and")) == "대사에 없는 「and」 들렸어요"
```

`test_limit_caps_issues_and_one_per_sound`(네 곳이 다르고 둘을 고름)는 그대로 통과해야 한다.

- [ ] **Step 2: 시험이 실패하는지 본다**

Run: `cd server && uv run pytest tests/test_compare.py -q`
Expected: FAIL (`ImportError: cannot import name 'compare'`)

- [ ] **Step 3: 구현한다**

`models.Issue`의 `sound`와 `explain`에 기본값을 준다. 옛 기록(`sound`가 늘 있음)은 그대로 읽힌다.

`words(text)`: 소문자, `’`를 `'`로 바꾼 뒤 낱말로 나누기 전에 글을 맞춘다. 낱말은 지금처럼 `[a-z0-9']+`(하이픈과 콜론에서 나뉜다).
- `a.m.`과 `p.m.`(마침표가 있든 없든, 대소문자와 상관없이) → `am`, `pm`
- `$5` → `5 dollars`(1이면 `dollar`), `5%` → `5 percent`
- 0~99의 숫자 낱말 → 영어 낱말(`10` → `ten`, `30` → `thirty`, `21` → `twenty one`). 100 이상은 그대로 둔다.
- `wanna` → `want to`, `gonna` → `going to`, `ok` → `okay`

`compare(target, heard)`: 대사 낱말 `a = words(target)`, 들린 낱말 `b`는 `words(heard)`에서 군말 `{"um", "uh", "uhm", "umm", "er", "erm", "hmm", "mm"}` 가운데 `a`에 없는 것을 뺀 것. `SequenceMatcher(None, a, b, autojunk=False).get_opcodes()`를 앞에서부터 본다.
- `equal`: 그 대사 낱말들은 맞게 들렸다(`matched`, `matched_words`).
- 같지 않은 곳이라도 양쪽 낱말을 빈칸 없이 이었을 때 같으면 차이가 아니고 맞게 들린 것으로 센다(checkout과 check out).
- `insert`(더한 낱말)인데 더한 낱말들이 바로 앞 대사 낱말 `a[i1-n:i1]`이나 바로 뒤 `a[i1:i1+n]`과 같으면 다시 시작한 것이라 차이가 아니다.
- `replace`이고 양쪽 개수가 같으면 낱말 짝마다 `Issue` 하나. 짝의 `sound_diff`에서 목록에 있는 첫 음소 쌍이 있으면 `sound`와 `explain`을 채운다(지금 `find_issues`와 같은 방식).
- `replace`이고 개수가 다르면 그곳 전체가 `Issue` 하나(`target`, `heard`는 낱말을 빈칸으로 이음). 그 안의 낱말 짝 가운데 `sound_diff`의 바뀐 수가 2 이하이고 목록에 있는 음소 쌍이 있는 첫 짝이 있으면 그 소리와 설명을 붙인다.
- `delete`는 `Issue(target=…, heard="")`, 나머지 `insert`는 `Issue(target="", heard=…)`.

`find_issues(target, heard, limit)`: `diffs`가 `limit` 이하이면 다 돌려준다. 넘으면 앞에서부터 고르되, 이미 고른 것과 같은 목록 소리(`frozenset(sound)`)인 것은 건너뛴다.

- [ ] **Step 4: 시험이 통과하는지 본다**

Run: `cd server && uv run pytest -q`
Expected: 모두 통과. `test_attempt.py`의 기존 시험(`It's light over there.`에서 R/L 하나)도 통과한다.

- [ ] **Step 5: 커밋한다** — `feat(server): flag every difference from the line in followed turns`. 본문에 표기 맞추기 목록, 다시 시작과 군말, 개수가 다른 곳 안의 소리 찾기(바뀐 수 2 이하)를 쓴다.

---

### Task 2: 짚는 수 다시 재기

**Files:**
- Modify: `server/scripts/check_false_flags.py`
- Modify(필요하면): `docs/superpowers/specs/2026-11-05-speaking-practice-design.md` 「잰 것」의 「따라 말한 차례에서 짚는 수」

**Interfaces:**
- Consumes: Task 1 `compare`, `Comparison`, `similarity`, `words`. `config.load_settings().data_dir`, `models.Roleplay`.

- [ ] **Step 1: worktree에 `.env`를 둔다** — 원래 폴더(`git worktree list`의 첫 줄)의 `server/.env`와 `app/.env`를 같은 자리에 복사한다. git에 들어가지 않는다(`.gitignore`의 `.env`). 내용을 출력하지 않는다.
- [ ] **Step 2: 스크립트를 고친다**
  - 녹음 모드(지금의 인자 `<recording> <script file>`): 대본 줄을 이어 받아쓴 글 전체와 `compare`한다. 찍는 것: 길이, 세기, `has_speech`, 낱말 수, `similarity`, `differences N`, 다른 곳마다 `target -> heard (sound)`. 받아쓴 글 전체는 찍지 않는다. `word_pairs`를 더는 쓰지 않는다.
  - 기록 모드(`--records`): `data_dir/roleplays/*/roleplay.json`을 `Roleplay`로 읽어, `followed`인 시도마다 그 줄의 대사와 저장된 `heard`를 `compare`한다. 찍는 것은 숫자뿐이다: `followed turns N`, `old rule flagged K`(저장된 `issues`가 있는 시도 수), `new rule flagged M`, 한 차례의 다른 곳 수 분포(`1: x, 2: y, 3+: z`). 낱말과 받아쓴 글은 찍지 않는다.
  - 녹음 모드는 받아쓰기 서버를 따로 띄운다. 돌고 있는 맥 서버와 포트가 겹치지 않게 `JE_WHISPER_PORT`를 다른 값으로 주고 돌린다.
- [ ] **Step 3: 잰다**

Run: `cd server && uv run python scripts/check_false_flags.py --records`
Expected: `old rule flagged 0`, `new rule flagged`가 0보다 크고, `3+`는 0(스펙 「잰 것」은 18번 가운데 5번, 그 뒤 기록이 늘었으면 숫자가 다를 수 있다).

Run: `cd server && JE_WHISPER_PORT=8799 uv run python scripts/check_false_flags.py <비공개 녹음 폴더의 2차 시험 녹음> <scratchpad의 2차 대본 8줄>` (파일 위치는 비공개 메모와 이 세션의 scratchpad를 본다)
Expected: `differences 2` 언저리. 스펙에 적은 2줄은 문장마다 나눠 센 것이라, 이어 붙인 한 덩어리에서는 수가 조금 다를 수 있다.

- [ ] **Step 4: 숫자가 스펙과 다르면 스펙 「잰 것」을 고친다** — 숫자만 쓰고 받아쓴 글은 쓰지 않는다. 같으면 고치지 않는다.
- [ ] **Step 5: 커밋한다** — `feat(server): count follow-turn flags on recordings and saved records`. 본문에 잰 숫자를 쓴다(낱말 없이).

---

### Task 3: 확인한 것만 칭찬하기와 라이언의 말

**Files:**
- Modify: `server/je_server/compare.py` (`praise_candidates`, 지울 것: `word_pairs`, `PRAISE_PHONES`, `FUNCTION_WORDS`)
- Modify: `server/je_server/engine.py` (`attempt`)
- Modify: `server/je_server/prompts.py` (`FEEDBACK_SYSTEM`)
- Test: `server/tests/test_compare.py`, `server/tests/test_attempt.py`

**Interfaces:**
- Consumes: Task 1 `compare`, `Comparison`, `Issue`.
- Produces: `compare.praise_candidates(target: str, heard: str, before: list[Issue], limit: int = 2) -> list[str]`. `before`는 같은 역할극 같은 줄의 바로 전 `followed` 시도에서 짚은 것(없으면 `[]`).

- [ ] **Step 1: 실패하는 시험을 쓴다**

`test_compare.py`에서 `test_praise_names_a_listed_sound_heard_right`, `test_praise_always_has_something`, `test_word_pairs_only_one_to_one`을 지우고 아래를 더한다.

```python
from je_server.compare import praise_candidates


def test_praise_only_what_was_checked():
    assert praise_candidates("Turn right at the corner.", "turn right at the corner", []) == ["대사를 빠짐없이 알아듣게 말했어요"]
    assert praise_candidates("Turn right at the corner.", "turn light at the corner", []) == ["나머지 낱말은 다 알아들었어요"]


def test_praise_when_not_every_difference_was_named():
    line = "Go left, then right, then left again."
    assert praise_candidates(line, "Go lift, then light, then lift again.", []) == ["대사의 낱말 대부분을 알아들었어요"]
    assert praise_candidates("Red and blue and green.", "Bed an glue and green.", []) == ["대사 5낱말 가운데 2낱말을 알아들었어요"]


def test_improvement_names_the_listed_sound_or_the_word():
    before = [Issue(target="right", heard="light", sound=("R", "L"), explain="…")]
    assert praise_candidates("Turn right here.", "Turn right here.", before)[0] == "이번에는 right의 R 소리가 제대로 났어요"
    before = [Issue(target="on", heard="")]
    assert praise_candidates("It's on the left.", "It's on the left.", before)[0] == "이번에는 on, 대사대로 들렸어요"


def test_improvement_needs_the_same_issue_gone():
    line = "This is for you. This is for you."
    before = [Issue(target="for", heard="")]
    assert not any(p.startswith("이번에는") for p in praise_candidates(line, "This is for you. This is you.", before))


def test_praise_can_be_empty():
    assert praise_candidates("Hello.", "Yellow.", []) == []
```

`test_attempt.py`에 더한다.

```python
async def test_praise_never_claims_unchecked_things(engine_with_rp, speech_bytes, fake_claude):
    engine, rp_id, user_idx = engine_with_rp
    await run(engine, rp_id, user_idx, speech_bytes)
    assert fake_claude.feedback_calls[0]["praise"] == ["대사를 빠짐없이 알아듣게 말했어요"]


async def test_fixed_word_from_last_try_is_praised(engine_with_rp, speech_bytes, fake_whisper, fake_claude):
    engine, rp_id, user_idx = engine_with_rp
    fake_whisper.text = "It's light over there."
    await run(engine, rp_id, user_idx, speech_bytes)
    fake_whisper.text = "It's right over there."
    await run(engine, rp_id, user_idx, speech_bytes, "retry")
    assert fake_claude.feedback_calls[1]["praise"][0] == "이번에는 right의 R 소리가 제대로 났어요"
```

- [ ] **Step 2: 시험이 실패하는지 본다**

Run: `cd server && uv run pytest tests/test_compare.py tests/test_attempt.py -q`
Expected: FAIL (`praise_candidates() takes 2 positional arguments but 3 were given`)

- [ ] **Step 3: `praise_candidates`를 다시 쓴다** — `c = compare(target, heard)`. 순서대로 담는다.
  1. 나아진 점: `before`의 `i` 가운데 `i.target`이 있고, 그 낱말이 모두 `c.matched_words`에 있고, `c.diffs`에 `target`이 같은 것이 없으면. `i.sound`가 있으면 `f"이번에는 {i.target}의 {이름} 소리가 제대로 났어요"`(이름은 `sound[0]`을 `{"R": "R", "L": "L", "F": "F", "P": "P", "V": "V", "B": "B", "TH": "TH", "DH": "TH", "S": "S", "D": "D", "Z": "Z", "JH": "J"}`로), 없으면 `f"이번에는 {i.target}, 대사대로 들렸어요"`.
  2. 맞댄 결과 하나: 다른 곳이 없으면 「대사를 빠짐없이 알아듣게 말했어요」. 다른 곳이 `limit` 이하이고 `matched > 0`이면 「나머지 낱말은 다 알아들었어요」. `limit`을 넘고 `matched * 2 > total`이면 「대사의 낱말 대부분을 알아들었어요」. 넘고 `matched > 0`이면 `f"대사 {total}낱말 가운데 {matched}낱말을 알아들었어요"`. `matched == 0`이면 담지 않는다.
  - 「끝까지 자신 있게 말했어요」와 낱말이 맞게 적혔다는 것만 보고 하는 소리 칭찬은 없앤다. `word_pairs`, `PRAISE_PHONES`, `FUNCTION_WORDS`를 지운다.
- [ ] **Step 4: `engine.attempt`에서 지난 시도를 넘긴다** — `followed`일 때 `rp.attempts.get(idx, [])` 가운데 `followed`인 마지막 시도의 `issues`를 `before`로(지금 시도는 아직 저장 전이다). 종류(`turn`, `retry`, `practice`, `shadow`)는 가리지 않는다. 다른 역할극(「처음부터 다시 하기」로 만든 복사본)의 기록은 보지 않는다(스펙 「잘한 점 후보」).
- [ ] **Step 5: `FEEDBACK_SYSTEM`을 고친다** — 지금 규칙에서 바꾸고 더할 것:
  - 「짚을 것」의 「들린 낱말」이 비어 있으면 그 낱말이 들리지 않은 것이고, 「대사 낱말」이 비어 있으면 대사에 없는 말이 더 들린 것이다. 「대사」와 「들린 말」을 보고 어디인지 말해도 된다.
  - 들린 대로 말한다: 「X가 Y처럼 들렸어요」, 「X가 들리지 않았어요」, 「then 앞에 and가 들렸어요」. 「~라고 말했어요」, 「~라고 하셨어요」라고 하지 않는다. 받아쓰기가 틀렸을 수도 있기 때문이다.
  - 「소리 내는 법」이 비어 있으면 소리 내는 법을 말하지 않는다.
  - 잘한 점은 받은 후보 가운데 하나만 말한다. 후보가 없으면 잘한 점을 말하지 않는다. 자신 있게, 또렷하게, 자연스럽게처럼 받지 않은 칭찬을 지어내지 않는다.
  - 예를 바꾼다: 짚을 것이 하나일 때 「나머지 낱말은 다 알아들었어요. 그런데 running이 learning처럼 들렸어요. L은 … 한 번 더 해 볼까요?」, 빠진 낱말일 때 「나머지 낱말은 다 알아들었어요. 그런데 on이 들리지 않았어요. 한 번 더 해 볼까요?」, 없을 때 「대사를 빠짐없이 알아듣게 말했어요. 다음 대사로 넘어가요.」
- [ ] **Step 6: 시험이 통과하는지 본다**

Run: `cd server && uv run pytest -q`
Expected: 모두 통과.

- [ ] **Step 7: 커밋한다** — `feat(server): praise only what the Mac checked in followed turns`.

---

### Task 4: 끝 화면의 짚은 것

**Files:**
- Modify: `server/je_server/engine.py` (`summary`)
- Modify: `contract/summary.json`, `server/tests/test_contract.py`, `server/tests/test_summary.py`
- Modify: `app/src/api/types.ts`, `app/src/api/contract.test.ts`, `app/src/screens/EndScreen.tsx`

**Interfaces:**
- Consumes: Task 1 `issue_ko`.
- Produces: 요약의 시도마다 `issues: [{"target": str, "heard": str, "say_ko": str}]`. 앱 `Try.issues`는 `{ target: string; heard: string; say_ko: string }[]`, `Issue.sound`는 `[string, string] | null`.

- [ ] **Step 1: 실패하는 시험을 쓴다**
  - `test_summary.py`의 `test_summary_says_each_issue_in_korean`: 한 시도에 옛 모양 `Issue(target="coffee", heard="copy", sound=("F", "P"), explain="…")`과 `Issue(target="on", heard="")`를 저장하고 `engine.summary`를 부르면, 그 시도의 `issues`가 `[{"target": "coffee", "heard": "copy", "say_ko": "「coffee」 → 「copy」처럼 들렸어요"}, {"target": "on", "heard": "", "say_ko": "「on」 → 들리지 않았어요"}]`다.
  - `test_contract.py`의 요약 시험: 짚은 것의 키가 `{"target", "heard", "say_ko"}`.
  - `contract.test.ts`: `ISSUE_KEYS = ["target", "heard", "say_ko"]`를 `types.ts`에서 가져와, 요약 예시의 짚은 것마다 키가 같은지 본다. `types.ts`의 `KEYS_MATCH`에 `Same<keyof Try["issues"][number], (typeof ISSUE_KEYS)[number]>`를 더한다.
- [ ] **Step 2: 실패를 본다** — `cd server && uv run pytest tests/test_summary.py tests/test_contract.py -q`가 FAIL(`say_ko` 없음), `cd app && npm test`가 FAIL(`ISSUE_KEYS` 없음).
- [ ] **Step 3: 고친다**
  - `engine.summary`가 짚은 것마다 `say_ko: issue_ko(i)`를 넣는다.
  - `contract/summary.json`의 짚은 것 예시에 `"say_ko": "「coffee」 → 「copy」처럼 들렸어요"`를 더한다.
  - `types.ts`: `Issue.sound`를 `[string, string] | null`로, `Try.issues`에 `say_ko`를 더하고 `ISSUE_KEYS`를 내보낸다.
  - `EndScreen.tsx` `TryView`: 짚은 것은 `i.say_ko`를 그대로 보인다. 다른 줄은 건드리지 않는다. 다른 작업도 이 화면을 고치고 있어, 바꾸는 줄을 이것 하나로 둔다.
- [ ] **Step 4: 통과를 본다** — `cd server && uv run pytest -q`, `cd app && npm test && npx tsc --noEmit` 모두 통과.
- [ ] **Step 5: 커밋한다** — `feat: show missing and added words on the end screen` (서버와 앱에 걸쳐 scope 생략).

---

### Task 5: 폰에서 확인하고 마무리

- [ ] **Step 1: 서버를 이 worktree에서 다시 띄운다** — 끄기 전에 사용자에게 알리고, 다른 카드가 시험 중인지 묻는다. 원래 폴더에서 돌던 서버를 끄고 `cd server && uv run python -m je_server`. 서버 로그(위치는 비공개 메모 참고)에서 `ready`를 본다.
- [ ] **Step 2: APK를 빌드해 깐다** — `app/README.md`와 비공개 메모 `mac-env.md`대로(JDK 17, `-PreactNativeArchitectures=arm64-v8a`), `adb install -r`.
- [ ] **Step 3: 사용자와 폰에서 본다** (PR 본문의 테스트 체크리스트로 옮긴다)
  - 대사를 그대로 말하면 「빠짐없이 알아듣게」 칭찬만 하고, 낱말 소리 칭찬(「R 소리를 잘 냈어요」)이 없다.
  - 낱말 하나를 빼고 말하면 「~가 들리지 않았어요」라고 짚고, 「~라고 말했어요」라고 하지 않는다.
  - 낱말을 하나 더하거나 다른 낱말로 말하면 짚는다. 목록에 없는 소리면 소리 내는 법을 붙이지 않는다.
  - 숫자가 든 대사를 그대로 말하면 짚지 않는다.
  - 짚힌 줄을 「다시 해 보기」로 맞게 말하면 「이번에는 ~」으로 나아진 점을 말한다.
  - 끝 화면의 「주고받은 말」에 빠진 낱말이 「「on」 → 들리지 않았어요」 꼴로 보인다.
- [ ] **Step 4: 원래 폴더의 서버로 돌린다** — 사용자가 머지 전에 계속 쓰려면 원래 폴더에서 다시 띄운다(머지 뒤에는 원래 폴더 main을 당긴 뒤 다시 띄운다).
- [ ] **Step 5: 마무리는 `AGENTS.md`대로 한다**
  - 가이드: `docs/guide/PRONUNCIATION_따라말하기_짚기_20261106.md`(표기 맞추기 목록과 이유, 다시 시작과 군말, 목록 소리만 짚던 문제와 원인, 받아쓴 글만 보고 칭찬하던 문제, 짚는 수 재는 명령), `docs/guide/README.md` 색인. 받아쓴 실제 글은 쓰지 않는다.
  - PR(본문 한국어, `## 한계`에 맞게 읽은 시험 녹음 2줄을 아직 듣지 않은 것과 시험 녹음 1차 대본이 없는 것), pr-review, 고친 뒤 devlog `docs/devlog/2026-11-06-follow-feedback.md`.
  - 끝내는 커밋에 `docs/todo/20261105_12_todo_follow_feedback_misses.md`의 상태를 완료로 고쳐 넣는다(원래 폴더에 untracked로 있다. worktree로 옮겨 커밋한다).
  - 위키로 넘길 교훈은 원래 폴더의 `docs/private/wiki-outbox.md`에 쓴다.
