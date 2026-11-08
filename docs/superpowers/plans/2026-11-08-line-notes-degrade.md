# 읽는 법(세 줄)이 덜 된 채 남는 비율 줄이기 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 맥 서버가 만든 읽는 법이 기계 검사를 통과하지 못해 덜 된 채 남는 비율(서버 로그 29%)과 그 때문에 다시 부르는 횟수를 줄이고, 목록 대본과 「이 상황 다시 하기」가 덜 된 읽는 법을 굳히지 않게 한다.

**Architecture:** 원인은 대부분 검사다(아래 「진단」). 지시문(`prompts.THREE_SYSTEM`)은 그대로 두고, `threeline.check`의 `ref` 검사를 한글 글자 기준으로 고치고, 모델이 받침을 뺀 센 글자(`hi`)를 검사 전에 맞춰 주는 `threeline.tidy`를 `Claude.annotate`에 넣는다. 다시 쓸 읽는 법은 한글과 설명이 모두 있는 것(`threeline.settled`)만이다. 고치기 전과 뒤는 새 측정 스크립트로 같은 대사에서 잰다.

**Tech Stack:** Python 3 + FastAPI(서버, `cd server && uv run pytest -q`). 새 꾸러미 없음. 앱은 바꾸지 않는다.

**Spec:** 스펙 문서 없이 할 일로 한다. 할 일 원래 폴더 `docs/todo/20261108_16_todo_three_line_notes_degrade_rate.md`(「할 일」 1~4). 규칙의 원본은 `docs/guide/PRONUNCIATION_한글발음_세줄표시_20261105.md` 「규칙」과 「기계로 검사할 수 있는 것」. 다시 쓰기 규칙은 `docs/superpowers/specs/2026-11-08-fixed-list-scripts-design.md` 2 「예외」와 `docs/superpowers/specs/2026-11-05-roleplay-practice-design.md` 6.

**실행 방식:** 이 세션이 직접 한다(executing-plans). 작업이 `threeline.py` 한 파일과 그 둘레라 작업마다 새 에이전트를 띄우면 같은 맥락을 다시 읽는 데 더 든다. 끝에 새 리뷰어 한 명이 브랜치 전체를 보고, PR을 열면 pr-review로 본다(`AGENTS.md` 「PR과 머지」).

## 진단 (2026-11-08, 실제 대사로 첫 시도만 61번, $0.63)

맥 데이터의 실제 대사 61줄(덜 된 채 남은 31줄과 다른 30줄)로 서버와 같은 첫 요청을 한 번씩 보내고 답을 그대로 남겨 봤다. 대사와 답은 비공개라 여기에는 지어낸 예만 쓴다.

- 첫 시도 실패 35/61. 문제는 `ref` 47건, `hi` 16건, `stress` 8건, `words` 4건.
- `ref` 47건 중 37건은 한글 글자가 한글 줄과 같다. 지금 검사는 `[[…]]`를 하이픈으로 잘라 각 조각이 음절(`ko`) 하나와 꼭 같기를 바란다. 그래서 낱말 사이를 띄어 쓴 것(한글 줄 「굿 모닝」에 `[[굿 모닝]]`꼴, 14건), 하이픈을 음절과 다르게 넣은 것(`ko` 「펜|슬」에 `[[펜슬]]`꼴, 14건), 센 글자 하나만 가리킨 것(`ko` 「스테이」에 `[[테]]`, 9건)이 걸렸다. 나머지 10건은 정말 다른 소리다(읽는 법은 이어 읽기를 적었는데 한글 줄은 끊어 적은 것 등).
- `hi` 16건은 모두 받침을 뺀 글자다(`ko` 「잼」에 `hi` 「재」, 「스프링」에 「리」). 지시문의 「the single Hangul letter in ko that carries the vowel」을 받침 없는 글자로 읽었다. 모음이 같은 글자가 `ko`에 하나뿐이라 맞출 글자가 정해진다.
- `stress` 8건 중 5건은 모델이 틀렸다. 2건은 모델이 세 음절 낱말을 두 음절로 나눠 사전의 다른 발음(두 음절)과 비교된 것, 1건은 사전(CMU)의 강세가 일반 사전과 다른 낱말이다. `words` 4건은 모델이 낱말을 빼거나 더한 것이다.
- 검사만 고치면 같은 답의 첫 시도 통과가 26/61 → 43/61이다. 지시문을 고치는 길은 모델이 엄한 형식을 지켜야 해 다시 어긋날 수 있고, 지금 통과하는 것도 바뀔 수 있어 버렸다. 덜 된 부분만 다시 묻는 길은 첫 시도 실패를 줄이지 못해 이 계획에서는 하지 않는다(뒤 측정을 보고 다시 정한다, Task 5).

## Global Constraints

- 공개 파일(시험, 가이드, 스펙, devlog, 커밋, 스크립트 출력)에는 지어낸 예만 쓴다. 맥 기록의 대사와 모델 답을 옮기지 않는다(`REVIEW.md` 「공개 저장소 노출」).
- 측정 스크립트는 대사와 읽는 법을 찍지 않고 수만 찍는다(`scripts/measure_claude.py`와 같다).
- 실제 모델 호출은 돌리기 전에 횟수와 어림 값을 main 세션에 알린다. 합쳐 1달러가 넘으면 먼저 묻는다(넘길 글).
- 앱이 받는 응답 모양(`ThreeLine`의 필드)은 바꾸지 않는다.
- 커밋은 영어 Conventional Commits, scope `server`(문서는 `guide`, 스펙은 생략), 본문에 이유와 시험 결과, 끝에 `Refs: docs/superpowers/plans/2026-11-08-line-notes-degrade.md`. AI 서명 줄 없음. git은 `/usr/bin/git`, `git add`는 파일을 지정한다.

## Review Focus

1. **띄어쓰기를 넣은 `[[…]]`가 한글 줄에 없는 글자를 숨기는 것:** `[[카 페]]`는 글자가 다르니 여전히 걸려야 한다. → Task 2 시험 `test_ref_letters_must_still_match`.
2. **글자를 건너뛴 `[[…]]`:** 한글 줄 「아이 라익 카피」에 `[[아이카]]`는 이어진 글자가 아니니 걸려야 한다. → Task 2 같은 시험.
3. **`hi`를 맞출 글자가 둘 이상이거나 없는 것:** 모음이 같은 글자가 둘(「빌빌」에 「비」)이거나 없으면(「압」에 「옵」) 그대로 두고 검사가 잡는다. → Task 3 시험 `test_tidy_leaves_what_it_cannot_tell`.
4. **센 음절이 아닌 음절의 `hi`:** `tidy`는 `m == "s"`만 본다. 「n」 음절에 남은 `hi`는 검사가 그대로 잡는다. → Task 3 같은 시험.
5. **설명 없는 읽는 법을 다시 만드는 비용:** 늘 걸리는 줄은 고를 때마다 다시 부른다. 뒤 측정의 `ref` 비율로 판단해 스펙에 적는다. → Task 5, Task 4의 스펙 문장.

---

### Task 1: 측정 스크립트와 고치기 전 측정

**Files:**
- Create: `server/scripts/check_three_lines.py`
- Test: `server/tests/test_check_three_lines.py`

**Interfaces:**
- Produces: `noted_lines(records: list[dict]) -> list[tuple[str, str]]` (글, 맥락. 같은 글은 가장 나중 기록의 맥락), `sample(lines, n: int, seed: int) -> list`, `outcome(message: str) -> str` (로그 줄 → 「1」, 「2」, 「3」 또는 「degraded:ref,hi」), `summary(rows: list[dict]) -> str`. 실행: `uv run python scripts/check_three_lines.py [--lines 20] [--seed 7] [--only FILE] [--budget 0.7]`. `--only`는 한 줄에 대사 하나인 파일로, 기록 가운데 그 대사만 잰다(파일은 저장소 밖에 둔다).

- [ ] **Step 1: 시험 쓰기** (지어낸 기록으로)
  - `test_noted_lines_keeps_lines_with_notes_once`: 기록 둘에 같은 글의 줄이 있으면 한 번만, 맥락은 `Engine.context`와 같은 꼴(「장소: …. ryan: … / ryan: …」)이고 나중 기록의 것. 읽는 법(`three`)이 없는 줄은 빠진다.
  - `test_sample_is_the_same_for_the_same_seed`: 같은 seed는 같은 줄, n이 줄 수보다 크면 모든 줄.
  - `test_outcome_reads_the_server_log_line`: 「three-line note: 2 tries, 3.1s」 → 「2」, 「three-line note degraded after 3 tries, 9.0s: hi,ref」 → 「degraded:hi,ref」.
  - `test_summary_counts_without_lines`: 줄 글이 결과에 없고, 첫 시도 통과·두 번·세 번·덜 됨(이유별)·부른 수·값이 든다.
- [ ] **Step 2: 시험이 실패하는 것을 본다** — `cd server && uv run pytest tests/test_check_three_lines.py -q` → 모듈 없음.
- [ ] **Step 3: 스크립트 쓰기.** 기록은 `load_settings().data_dir / "roleplays" / */roleplay.json`. 서버의 `Claude.annotate`를 그대로 부르고(작가 모델은 `WRITERS[settings.claude_writer]`), 호출 수와 토큰은 `measure_claude.Counting`처럼 감싼 클라이언트로, 결과는 `je_server` 로거의 「three-line note」 줄로 센다. 동시에 4줄. 값은 Sonnet $2/$10 (백만 토큰), 상한을 넘으면 새 줄을 시작하지 않는다. 맨 위 설명에 한 번 값(약 $0.01)과 20줄 어림(약 $0.3~0.6)을 적는다.
- [ ] **Step 4: 시험 통과** — 같은 명령 → PASS, 전체 `uv run pytest -q` 통과.
- [ ] **Step 5: 커밋** `chore(server): add a script that measures three-line note retries`.
- 고치기 전 값은 따로 재지 않는다(사용자, main 세션 2026-11-08 「ㅇㅋ 추천대로」). 진단의 첫 시도 답(61줄)과 서버 로그(덜 됨 29%, 줄마다 2.0번)를 쓰고, 고친 검사를 같은 답에 대 본 수(26/61 → 43/61)도 PR에 적는다.

### Task 2: `ref` 검사를 한글 글자로

**Files:**
- Modify: `server/je_server/threeline.py` (`REF_OK`, `_is_run` 지움, `check`의 `ref` 부분, 모듈 설명)
- Test: `server/tests/test_threeline.py`

**Interfaces:**
- Produces: `check(text, three)`의 `ref` 규칙 — `[[…]]` 안은 한글 덩이를 하이픈 하나나 빈칸 하나로 이은 것(`^[가-힣]+([- ][가-힣]+)*$`)이고, 하이픈과 빈칸을 뺀 글자가 한글 줄의 모든 `ko`를 이은 글자 안에 이어서 있어야 한다.

- [ ] **Step 1: 시험 쓰기** (`I like coffee.`, 한글 줄 「아이 라익 카피」)
  - `test_ref_may_span_words_with_a_space`: `[[라익 카-피]]` → 문제 없음.
  - `test_ref_hyphens_need_not_follow_syllables`: `[[카피]]`, `[[아-이]]` → 문제 없음.
  - `test_ref_may_point_at_one_letter_inside_a_syllable`: `[[이]]` → 문제 없음.
  - `test_ref_letters_must_still_match`: `[[카 페]]`, `[[아이카]]`, `[[피카]]`, `[[카--피]]`, `[[카-피 ]]` → 모두 `ref`.
  - 있는 시험(`[[카-페]]`, `[[ka-피]]`)은 그대로 걸린다.
- [ ] **Step 2: 새 시험 셋이 실패하는 것을 본다.**
- [ ] **Step 3: 고치기.** 한글 줄 글자는 `"".join(kos)`.
- [ ] **Step 4: `uv run pytest tests/test_threeline.py -q` 통과, 전체 통과.**
- [ ] **Step 5: 커밋** `fix(server): check three-line reading sounds by their Hangul letters` — 본문에 진단 수(47건 중 37건)와 지어낸 꼴.

### Task 3: 받침을 뺀 센 글자를 맞추기

**Files:**
- Modify: `server/je_server/threeline.py` (`tidy` 더함), `server/je_server/claude.py` (`annotate`가 검사 전에 `tidy`)
- Test: `server/tests/test_threeline.py`, `server/tests/test_claude.py`

**Interfaces:**
- Produces: `tidy(three: ThreeLine) -> ThreeLine` — `m == "s"`이고 `hi`가 `ko`에 없는 한글 한 글자인 음절에서, `ko` 안에 `hi`와 모음(가운뎃소리)이 같은 글자가 하나뿐이면 `hi`를 그 글자로 바꾼다. 그 밖은 그대로.

- [ ] **Step 1: 시험 쓰기**
  - `test_tidy_puts_the_final_consonant_back`: `ko` 「딛」 `hi` 「디」 → 「딛」, `ko` 「스프링」 `hi` 「리」 → 「링」, 나머지 음절과 `reading`은 그대로.
  - `test_tidy_leaves_what_it_cannot_tell`: 「빌빌」에 「비」, 「압」에 「옵」, `m == "n"`인 음절의 `hi`는 그대로(검사가 `hi`로 잡는다).
  - `test_annotate_tidies_hi_before_checking` (test_claude): 지어낸 한 낱말 줄 「Stop.」 답(`ko` 「스탑」, `m` 「s」, `hi` 「타」) 하나로 요청 한 번, 결과 `hi` 「탑」.
- [ ] **Step 2: 실패를 본다.**
- [ ] **Step 3: 구현.** 모음 번호는 `(ord(ch) - 0xAC00) // 28 % 21`.
- [ ] **Step 4: 통과, 전체 통과.**
- [ ] **Step 5: 커밋** `fix(server): restore the final consonant the model drops from a highlight`.

### Task 4: 다시 쓸 읽는 법은 한글과 설명이 모두 있는 것만

**Files:**
- Modify: `server/je_server/threeline.py` (`blank`를 `settled`로), `server/je_server/engine.py` (`_prepared`, `copy`)
- Modify: `server/tests/fakes.py` (`noted`의 `reading`을 「[[가]]」로)
- Test: `server/tests/test_picks.py`, `server/tests/test_engine.py`
- Modify: `docs/superpowers/specs/2026-11-08-fixed-list-scripts-design.md` 2 「예외」, `docs/superpowers/specs/2026-11-05-roleplay-practice-design.md` 6 (고침 줄)

**Interfaces:**
- Produces: `settled(three: ThreeLine) -> bool` — 한글이 하나라도 있고 `reading`이 빈칸만이 아니다. 강세 표시 몇 개만 지운 것(`hi`, `stress` 덜 됨)은 가려낼 수 없어 그대로 다시 쓴다.

- [ ] **Step 1: 시험 쓰기**
  - `test_note_without_reading_is_kept`를 `test_note_without_reading_is_made_again`으로: 앞 회차의 읽는 법에서 `reading`을 비우면 다음 고르기에서 `three is None`이고 소리는 가져오며, 준비가 끝나면 새 읽는 법이 있다.
  - `test_settled_note_is_reused` (test_picks): `noted`처럼 한글과 설명이 있는 것은 그대로 가져온다.
  - `test_copy_makes_an_unsettled_note_again` (test_engine): 설명 없는 읽는 법은 복사본에서 `None`이 되어 다시 만들고, 다른 줄의 읽는 법과 소리는 그대로.
- [ ] **Step 2: 실패를 본다.**
- [ ] **Step 3: 구현.** `copy`는 `_current_sounds`와 함께 읽는 법이 `settled`가 아니면 `three=None`.
- [ ] **Step 4: 통과, 전체 통과.**
- [ ] **Step 5: 스펙 고치기.** 목록 대본 스펙 2 「예외」: 설명이 빠진 것도 다시 만든다. 이유는 이 일로 `ref` 덜 됨이 드물어졌고(Task 5의 수), 덜 된 것이 회차마다 굳기 때문. 역할극 뒤 연습 스펙 맨 위 「고침」 줄에 6의 「그대로 쓴다」에 이 예외를 적는다.
- [ ] **Step 6: 커밋** `fix(server): make a reused note again when it has no reading` (스펙은 같은 커밋, 이유가 같다).

### Task 5: 고친 뒤 측정과 다음 판단

- [ ] **Step 1:** 진단한 61줄에서 seed 7로 20줄을 골라 저장소 밖 파일에 두고, main 세션에 횟수와 값을 알린 뒤 `uv run python scripts/check_three_lines.py --only <그 파일>`.
- [ ] **Step 2:** 같은 20줄의 진단 첫 시도(고치기 전), 그 답에 고친 검사를 대 본 것, 고친 뒤 실제를 견준다: 첫 시도 통과, 덜 됨(이유별), 줄마다 부른 수, 값, 걸린 시간. 서버 로그의 고치기 전 수(덜 됨 29%, 줄마다 2.0번)와도 나란히 적는다.
- [ ] **Step 3:** 남은 덜 됨이 주로 `stress`나 정말 다른 소리(`ref`)면, 그 실제 예를 비공개로 보고 지시문이나 「덜 된 부분만 다시 묻기」가 필요한지 정한다. 필요하면 이 PR에서 하지 않고 할 일로 남긴다(지금 PR을 먼저 마무리, `AGENTS.md` 「열린 PR을 놓치지 않는다」).

### Task 6: 가이드와 서버 시험

**Files:**
- Modify: `docs/guide/PRONUNCIATION_한글발음_세줄표시_20261105.md` (규칙 5의 음절 나눔, 「기계로 검사할 수 있는 것」, 새 절 「겪은 문제와 해결」), `docs/guide/README.md` (그 줄)

- [ ] **Step 1: 가이드.** 규칙 5: 같은 낱말은 같은 글자로 쓴다. 하이픈과 띄어쓰기, 센 글자 하나만 가리키기는 자유다(화면의 한글 줄에는 하이픈이 없다). 「겪은 문제와 해결」: 검사가 형식까지 막아 맞는 설명을 버린 것, 지시문의 「모음을 실은 글자」를 받침 없는 글자로 읽은 것, 고치기 전에 첫 시도 답을 그대로 남겨 이유를 가른 방법(지어낸 예만).
- [ ] **Step 2: 커밋** `docs(guide): record why three-line notes failed the checks`.
- [ ] **Step 3: 서버 시험.** worktree 서버를 `JE_HOST=127.0.0.1 JE_PORT=8791 JE_WHISPER_PORT=8792`, 녹음을 뺀 데이터 복사본(`JE_DATA_DIR`)으로 띄운다. 목록 상황을 하나 골라 내 대사의 읽는 법을 받고(설명이 있는지), 학습자 목소리로 만든 녹음을 한 줄에 보낸다(`docs/guide/DEVENV_폰없이_녹음_시험하기_20261108.md`). 끝나면 서버를 끄고 복사본과 녹음을 지운다.
