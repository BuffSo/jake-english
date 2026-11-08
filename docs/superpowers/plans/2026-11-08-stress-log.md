# 녹음마다 강세 값 남기기 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 손으로 돌리는 스크립트가 아직 재지 않은 영어 녹음을 MFA와 Praat로 재서 앱 데이터 폴더의 `stress/`에 녹음마다 남기고, 다른 스크립트가 쌓인 값으로 강세 시험 가이드의 표를 다시 낸다.

**Architecture:** 판정, 고르기, 기록 만들기, 표 셈은 서버 패키지의 순수 함수(`je_server/stress.py`, `je_server/stress_report.py`)라 uv 환경의 pytest로 시험한다. 소리를 읽는 일만 MFA 환경의 파이썬이 돌리는 독립 스크립트(`scripts/stress_features.py`)가 한다. `scripts/measure_stress.py`가 둘을 잇는다: 녹음을 WAV로 바꾸고, MFA 정렬과 특징 스크립트를 낮은 우선순위로 부르고, 값 파일을 쓰고, 작업 폴더를 지운다.

**Tech Stack:** Python 3.12(uv, 서버 환경), MFA 3.4.3 + parselmouth 0.4.7 + praatio(MFA micromamba 환경, Python 3.14), ffmpeg, CMUdict(`je_server.cmu`), `taskpolicy -b`.

**Spec:** `docs/superpowers/specs/2026-11-08-stress-log-design.md`

## Global Constraints

- 기존 `roleplays/*/roleplay.json`과 `rec/*.m4a`는 읽기만 한다. 쓰는 곳은 `{data}/stress/`와 `{data}/tmp/stress-*/`(끝나면 지움)뿐이다.
- 스크립트 출력, 로그, 오류 메시지에 들린 말, 대사, 낱말, 녹음 경로를 찍지 않는다. 개수, 비율, 시간만.
- 시험 자료의 문장은 지어낸다. 맥의 기록에서 옮기지 않는다(`REVIEW.md`).
- `server/pyproject.toml`과 `uv.lock`은 바꾸지 않는다. MFA 환경 쪽 코드는 표준 라이브러리, numpy, parselmouth, praatio만 쓴다.
- 판정 무게: 세기 3dB, 음높이 2반음, 길이 0.04초가 같은 1점. 음높이는 100Hz 기준 반음(`12*log2(hz/100)`). Praat 기본 음높이 범위(75~600Hz).
- MFA: `english_us_arpa` 사전과 모델, `--single_speaker -j 1 --clean`, `--temporary_directory`는 작업 폴더 안. MFA 환경의 `bin`을 PATH 맨 앞에 둔다(없으면 `fstcompile`을 못 찾는다).
- MFA와 특징 스크립트는 `/usr/sbin/taskpolicy -b`로 부른다.
- 앱을 쓰는 중: 최근 600초 안에 바뀐 `roleplay.json`이나 `rec/` 파일. `--now`가 없으면 알리고 멈춘다(종료 코드 2).
- MFA 환경 위치는 `JE_MFA_ENV`(기본값 없음), 앱 데이터 폴더는 `JE_DATA_DIR`(기본 `config.DEFAULT_DATA_DIR`). 둘 다 서버와 같이 저장소 `.env`, `server/.env`, 환경 변수 순으로 읽는다.
- 값 파일 형식 번호 `v: 1`.
- git은 `/usr/bin/git`으로 부른다. 커밋 scope는 `server`.

## Review Focus

1. 같은 녹음을 두 번 재지 않는다: 값 파일이 이미 있는 녹음, 정렬에 실패해 실패 파일을 남긴 녹음은 다시 돌려도 건너뛴다(Task 2, 4 시험).
2. 작업 중 오류(MFA 실패, 특징 스크립트 실패, ffmpeg 실패)가 나도 `tmp/stress-*`가 남지 않고, 그 묶음의 녹음은 값 파일 없이 남아 다음에 다시 잰다(Task 4 시험).
3. 들린 말에 MFA 사전에 없는 낱말이 섞이면 그 낱말만 값이 비고 나머지는 잰다(Task 3 실제 정렬에서 확인, Task 1 판정 시험).
4. 기록 파일 하나가 깨져 읽히지 않아도 나머지는 잰다(`Store.all`이 건너뜀, Task 2 시험).
5. 음높이가 잡히지 않은 모음이 있는 낱말도 세기와 길이로 판정한다(Task 1 시험).

---

### Task 1: 판정과 사전, 대사 표시 (`je_server/stress.py` 앞부분)

**Files:**
- Create: `server/je_server/stress.py`
- Test: `server/tests/test_stress.py`

**Interfaces:**
- Produces:
  - `FORMAT = 1`, `DB_STEP = 3.0`, `ST_STEP = 2.0`, `DUR_STEP = 0.04`
  - `FUNCTION_WORDS: frozenset[str]`: 관사, 전치사, 인칭·지시·의문 대명사와 소유격, be·have·do 동사, 조동사, 접속사, 긍정 축약(`i'm`, `it's`, `i'd` …). 부정 축약(`don't`, `can't` …)과 `not`, `no`는 넣지 않는다(대개 세게 읽는다).
  - `is_vowel(phone: str) -> bool`: 끝이 숫자.
  - `judge(syl: list[dict]) -> tuple[int | None, float | None]`: `syl`의 각 dict는 `db`, `st`, `dur`(`st`는 None일 수 있음). 모음이 둘 미만이거나 `db`/`dur`이 없는 모음이 있으면 `(None, None)`. 하나라도 `st`가 None이면 모든 모음을 음높이 없이 센다. 점수 `db/3 + st/2 + dur/0.04`, 가장 큰 자리와 1·2위 차.
  - `dict_stress(word: str, phones: list[str]) -> dict | None`: CMU 발음 가운데 `phones`와 모음 수가 같은 것들의 1차 강세 자리 `{"primary": [정렬한 자리], "secondary": bool}`. 같은 모음 수의 발음이 없으면 None.
  - `line_marks(three: ThreeLine | None, heard: list[str]) -> list[dict | None]`: `heard`와 길이가 같다. 세 줄 낱말(`threeline.word_text`를 소문자, `’`→`'`, `[a-z0-9']` 밖 글자 지움)과 `heard`를 `difflib.SequenceMatcher(autojunk=False)`의 같은 덩어리로 맞대어 `{"s": 센 음절 자리|None, "w": [약한 자리], "emph": bool, "n": 음절 수}`.
  - `sentence_scores(words: list[dict]) -> list[float | None]`: 낱말 dict는 `phones`, `syl`. 낱말의 센 모음(`phones`에서 `1`인 모음, 없고 모음이 하나면 그것)의 `db`, `st`, `dur`을 녹음 안 낱말들로 표준화(평균 0, 표준편차 1; 표준편차 0이면 0)해 더한다. `st`가 없는 낱말은 음높이 항을 0으로 둔다. 센 모음이 없으면 None.

- [ ] **Step 1: 실패하는 시험 쓰기** `tests/test_stress.py`

```python
def test_judge_picks_the_strongest_vowel_with_the_guide_weights():
    syl = [{"db": 70, "st": 10, "dur": 0.10}, {"db": 64, "st": 8, "dur": 0.08}]
    pick, margin = judge(syl)
    assert pick == 0 and margin == pytest.approx(2 + 1 + 0.5)

def test_judge_drops_pitch_for_the_whole_word_when_one_vowel_has_none():
    syl = [{"db": 70, "st": None, "dur": 0.10}, {"db": 64, "st": 30, "dur": 0.20}]
    assert judge(syl) == (1, pytest.approx(-2 + 2.5))

def test_judge_needs_two_measured_vowels():
    assert judge([{"db": 70, "st": 10, "dur": 0.1}]) == (None, None)
    assert judge([{"db": None, "st": 1, "dur": 0.1}, {"db": 60, "st": 1, "dur": 0.1}]) == (None, None)

def test_dict_stress_keeps_the_prons_with_the_same_vowel_count():
    assert dict_stress("coffee", ["K", "AA1", "F", "IY0"]) == {"primary": [0], "secondary": False}
    assert dict_stress("record", ["R", "EH1", "K", "ER0", "D"])["primary"] == [0, 1]  # noun and verb
    assert dict_stress("qwzx", ["K", "AH0"]) is None

def test_line_marks_follow_the_words_heard():
    three = ThreeLine(words=[Word(syl=[Syllable(en="I'd", ko="아잇", m="n")]),
                             Word(syl=[Syllable(en="cof", ko="카", m="s", hi="카"), Syllable(en="fee", ko="피", m="w")])],
                      reading="")
    marks = line_marks(three, ["i'd", "like", "coffee"])
    assert marks[0] == {"s": None, "w": [], "emph": False, "n": 1}
    assert marks[1] is None
    assert marks[2] == {"s": 0, "w": [1], "emph": False, "n": 2}
    assert line_marks(None, ["a"]) == [None]

def test_sentence_scores_are_standardised_within_the_recording():
    w = lambda db, ph: {"phones": ph, "syl": [{"p": ph[-1], "db": db, "st": 5, "dur": 0.1}]}
    s = sentence_scores([w(70, ["K", "AH1"]), w(60, ["AH0"]), {"phones": ["S"], "syl": []}])
    assert s[0] > s[1] and s[2] is None
```

- [ ] **Step 2: 돌려서 실패 보기** — `cd server && uv run pytest tests/test_stress.py -q` → `ModuleNotFoundError: je_server.stress`
- [ ] **Step 3: 위 Interfaces대로 구현**
- [ ] **Step 4: 통과 보기** — 같은 명령, 모두 통과
- [ ] **Step 5: 커밋** — `feat(server): add stress judging, dictionary stress and line marks`

### Task 2: 고르기, 쓰는 중 보기, 기록 만들기 (`je_server/stress.py` 뒷부분)

**Files:**
- Modify: `server/je_server/stress.py`
- Test: `server/tests/test_stress.py`

**Interfaces:**
- Consumes: Task 1 전부, `Store(data_dir).all()`, `compare.words`, `threeline.word_text`.
- Produces:
  - `@dataclass(frozen=True) class Job`: `rp_id: str, idx: int, n: int, mode: str, followed: bool, aside: bool, at: str | None, words: list[str], rec: Path, three: ThreeLine | None`, 속성 `key -> f"{rp_id}_{idx}_{n}"`.
  - `out_path(data_dir: Path, rp_id: str, idx: int, n: int) -> Path` = `data_dir/"stress"/rp_id/f"{idx}-{n}.json"`
  - `pending(data_dir: Path) -> tuple[list[Job], int]`: 잴 시도들과, 들린 말에 한글이 있거나 영어 낱말이 없어 뺀 수. `rec/{idx}-{n}.m4a`가 없거나 `out_path`가 이미 있으면 뺀다(세지 않음). `three`는 `rp.lines`에서 `idx`가 같은 줄의 것(없으면 None).
  - `in_use(data_dir: Path, now: float, window: float = 600) -> bool`
  - `build(job: Job, aligned: dict | None, tools: dict, measured: str) -> dict`: `aligned`는 Task 3 출력의 파일 하나(`{"words": [{"w","start","end","phones","syl"}], "quality": {...}}`). None이면 `status: "unaligned"`, `words: []`. 낱말마다 `content`(`w`가 `FUNCTION_WORDS`에 없음), `dict`, `mark`, `pick`, `margin`, `score`를 더한다. 위쪽 키: `v, rp, idx, n, mode, followed, aside, at, measured, tools, status, quality, words`.
  - `write(path: Path, record: dict) -> None`: 폴더를 만들고 `Store._write`로 쓴다.

- [ ] **Step 1: 실패하는 시험 쓰기** — 시험 데이터 폴더는 `Store(tmp_path)`와 `Roleplay`/`Attempt` 모델로 만든다(대사와 들린 말은 지어낸 것).

```python
def test_pending_takes_english_tries_with_a_recording_not_yet_measured(tmp_path):
    # 시도 넷: 영어(잴 것), 한국어, 녹음 없음, 이미 잰 것
    jobs, skipped = pending(tmp_path)
    assert [j.key for j in jobs] == [f"{RP}_1_1"] and skipped == 1
    assert jobs[0].words == ["i'd", "like", "two", "coffees"]  # "2 coffees" heard

def test_pending_skips_an_unreadable_roleplay(tmp_path): ...  # 깨진 roleplay.json 옆의 다른 역할극은 고른다

def test_in_use_looks_at_records_changed_in_the_last_ten_minutes(tmp_path):
    assert in_use(tmp_path, now=t0 + 599) and not in_use(tmp_path, now=t0 + 601)

def test_build_adds_judgement_and_keeps_the_try(tmp_path):
    rec = build(job, aligned, tools={"mfa": "3.4.3"}, measured="2026-11-08T10:00:00")
    assert rec["v"] == 1 and rec["status"] == "ok" and rec["followed"] is True
    word = rec["words"][2]
    assert word["dict"] == {"primary": [0], "secondary": False} and word["mark"]["s"] == 0
    assert word["pick"] in (0, 1) and word["content"] is True and rec["words"][0]["content"] is False

def test_build_without_alignment_is_a_failure_record(): 
    assert build(job, None, {}, "t")["status"] == "unaligned"

def test_write_puts_the_file_beside_nothing_else(tmp_path):
    write(out_path(tmp_path, RP, 1, 1), {"v": 1})
    assert json.loads(out_path(tmp_path, RP, 1, 1).read_text()) == {"v": 1}
    assert not (tmp_path / "roleplays" / RP / "stress").exists()
```

- [ ] **Step 2: 실패 보기** — `uv run pytest tests/test_stress.py -q`
- [ ] **Step 3: 구현**
- [ ] **Step 4: 통과 보기**
- [ ] **Step 5: 커밋** — `feat(server): pick unmeasured tries and build stress records`

### Task 3: 소리 특징 스크립트 (MFA 환경)

**Files:**
- Create: `server/scripts/stress_features.py`
- Test: `server/tests/test_stress_features.py`

**Interfaces:**
- Produces: `python -I stress_features.py <corpus 폴더> <TextGrid 폴더> <출력 json>`. 출력 `{"praat": "<Praat 판>", "files": {<파일 이름(확장자 뺌)>: {"words": [...], "quality": {"speech_log_likelihood": float|None, "phone_duration_deviation": float|None}}}}`. 낱말은 `{"w", "start", "end", "phones": [소리 이름], "syl": [{"p", "start", "end", "dur", "db", "st", "st_med"}]}`(모음만, 시각은 소수 셋째 자리). TextGrid가 없는 파일은 넣지 않는다. 정렬 점수는 `<TextGrid 폴더>/alignment_analysis.csv`에서(없으면 None).
- 구현 메모: praatio `openTextgrid(includeEmptyIntervals=False)`로 `words`, `phones` 층을 읽고, 소리는 시작 시각이 낱말 안에 드는 낱말에 붙인다. `parselmouth.Sound(wav)`의 `to_intensity()`, `to_pitch()`(기본값). 모음 구간 안 프레임의 세기 최댓값, 유성 프레임 음높이의 최댓값과 가운데 값(반음). 프레임이 없으면 구간 가운데 시각의 값, 그것도 없으면 None. 표준 라이브러리, numpy, parselmouth, praatio만 쓴다. 들린 말은 찍지 않는다.

- [ ] **Step 1: 실패하는 시험 쓰기** — `JE_MFA_ENV`가 없으면 건너뛴다. 200Hz 사인파 1초(`wave`로 씀)와 손으로 쓴 TextGrid(낱말 하나 `ah`, 소리 `AA1` 0.2~0.6초)를 만들어 MFA 환경 파이썬으로 돌린다.

```python
def test_features_of_a_200_hz_tone(tmp_path):
    out = run_features(tmp_path)
    syl = out["files"]["tone"]["words"][0]["syl"][0]
    assert syl["p"] == "AA1" and syl["dur"] == pytest.approx(0.4, abs=0.001)
    assert syl["st"] == pytest.approx(12.0, abs=0.2) and syl["st_med"] == pytest.approx(12.0, abs=0.2)
    assert syl["db"] > 40
    assert out["files"]["tone"]["quality"] == {"speech_log_likelihood": None, "phone_duration_deviation": None}
```

- [ ] **Step 2: 실패 보기** — `JE_MFA_ENV=<MFA 환경> uv run pytest tests/test_stress_features.py -q` (환경 위치는 비공개 메모)
- [ ] **Step 3: 구현**
- [ ] **Step 4: 통과 보기**, `JE_MFA_ENV` 없이 돌리면 skipped
- [ ] **Step 5: 커밋** — `feat(server): measure vowel loudness, pitch and length with praat`

### Task 4: 재는 스크립트 (`scripts/measure_stress.py`)

**Files:**
- Create: `server/scripts/measure_stress.py`
- Modify: `server/.env.example` (`JE_MFA_ENV=` 자리와 설명)
- Test: `server/tests/test_measure_stress.py`

**Interfaces:**
- Consumes: `stress.pending`, `in_use`, `build`, `write`, `out_path`; `audio.to_wav16k`; Task 3 스크립트.
- Produces:
  - `run(data_dir: Path, mfa_env: Path, now: bool = False, chunk: int = 20, align=mfa_align, features=praat_features, version=mfa_version) -> dict` — 반환 `{"measured": int, "unaligned": int, "korean_or_empty": int, "failed": int, "busy": bool}`. `busy`면 아무것도 하지 않고 돌려준다. 묶음마다 작업 폴더 `data_dir/tmp/stress-{os.getpid()}-{묶음 번호}/`(`corpus/learner/{key}.wav`와 `.lab`, `out/`, `mfa/`)를 만들고 `finally`에서 지운다. 묶음에서 `align`이나 `features`가 예외를 내면 그 묶음은 값 파일을 쓰지 않고 `failed`에 센다. 파일 하나의 ffmpeg 실패도 `failed`.
  - `mfa_align(mfa_env: Path, corpus: Path, out: Path, work: Path) -> None`: `taskpolicy -b {env}/bin/mfa align --clean --single_speaker -j 1 --temporary_directory {work} {corpus} english_us_arpa english_us_arpa {out}`, PATH 맨 앞에 `{env}/bin`. 출력은 버리고 실패하면 `RuntimeError("mfa align failed")`.
  - `praat_features(mfa_env: Path, corpus: Path, out: Path, dest: Path) -> dict`: `taskpolicy -b {env}/bin/python -I scripts/stress_features.py …` 뒤 `dest`를 읽어 돌려준다.
  - `mfa_version(mfa_env: Path) -> str`: `mfa version` 마지막 줄.
  - `main()`: 저장소 `.env`, `server/.env`, 환경 변수 순으로 합쳐 `JE_DATA_DIR`, `JE_MFA_ENV`를 읽는다. `JE_MFA_ENV`가 없거나 `{env}/bin/mfa`가 없으면 알리고 종료 1. `--now`. 끝에 개수와 걸린 초를 한 줄로 찍는다. 쓰는 중이면 「앱을 쓰는 중이라 멈췄다(--now로 그래도 돈다)」를 찍고 종료 2.
  - 값 파일의 `tools`: `{"mfa": version, "model": "english_us_arpa", "praat": features 출력의 praat}`.

- [ ] **Step 1: 실패하는 시험 쓰기** — 가짜 `align`(TextGrid 대신 아무것도 안 함)과 가짜 `features`(정해 둔 dict를 돌려줌), 가짜 `version`. 녹음은 `conftest`나 `audiotools`의 소리 바이트로 m4a 대신 ffmpeg가 읽는 파일을 쓴다(`tests/audiotools.py` 참고).

```python
def test_run_writes_one_record_per_try_and_cleans_tmp(data): 
    counts = mod.run(data, Path("/env"), now=True, align=fake_align, features=fake_features, version=lambda e: "3.4.3")
    assert counts["measured"] == 1 and counts["unaligned"] == 1  # features가 한 파일만 돌려줌
    assert sorted(p.name for p in (data / "stress" / RP).iterdir()) == ["1-1.json", "3-1.json"]
    assert not list((data / "tmp").glob("stress-*"))

def test_a_second_run_measures_nothing(data): ...  # 두 번째 run은 measured == unaligned == 0, align을 부르지 않음

def test_a_failing_align_leaves_no_records_and_no_tmp(data):
    counts = mod.run(data, ..., align=boom)
    assert counts["failed"] == 2 and not (data / "stress").exists() and not list((data / "tmp").glob("stress-*"))

def test_records_and_recordings_are_unchanged(data): ...  # 돌기 전과 뒤의 roleplays/ 아래 파일 sha256이 같다

def test_busy_stops_unless_now(data):  # 방금 쓴 roleplay.json
    assert mod.run(data, ..., now=False)["busy"] is True and not (data / "stress").exists()

def test_the_lab_holds_the_normalised_heard_words(data): ...  # 가짜 align이 .lab을 읽어 "i'd like two coffees" 확인

def test_main_needs_the_mfa_env(monkeypatch, capsys): ...  # JE_MFA_ENV 없음 → SystemExit(1), 출력에 JE_MFA_ENV
```

- [ ] **Step 2: 실패 보기** — `uv run pytest tests/test_measure_stress.py -q`
- [ ] **Step 3: 구현**과 `.env.example`
- [ ] **Step 4: 통과 보기**, 전체 `uv run pytest -q`
- [ ] **Step 5: 커밋** — `feat(server): add the hand-run stress measuring script`

### Task 5: 표 내기 (`je_server/stress_report.py`, `scripts/stress_report.py`)

**Files:**
- Create: `server/je_server/stress_report.py`, `server/scripts/stress_report.py`
- Test: `server/tests/test_stress_report.py`

**Interfaces:**
- Consumes: Task 2의 값 파일 모양.
- Produces:
  - `load(data_dir: Path, since: str | None = None) -> list[dict]`: `stress/*/*.json`, `v == 1`만, `since`는 `at`(없으면 `measured`)의 날짜로 거름. 깨진 파일은 건너뛰고 수만 센다.
  - `auc(pos: list[float], neg: list[float]) -> float | None`: 짝마다 큼 1, 같음 0.5.
  - `word_rows(records: list[dict]) -> list[tuple[str, int, float | None, float | None]]`: (줄 이름, 낱말 수, 맞은 비율, 첫 음절 찍기). 줄: 사전과(모음 둘 이상, `pick`이 있고 `dict.primary`가 하나), 2차 강세 없는 것만, 확실도 위 25%(`margin` 75번째 백분위 이상), 대사 표시와(`mark.s`가 있고 `mark.n`이 모음 수와 같음; 찍기 칸은 표시가 0인 비율).
  - `weak_forms(records) -> dict[str, tuple[int, int]]`: for, a, to, of, the마다 (약형 수, 전체 수). 약형은 그 낱말 `phones`의 모음이 모두 `0`.
  - `render(records: list[dict]) -> str`: 마크다운. 첫 줄에 녹음 수(잼/정렬 실패), 낱말 수. 「대사를 따라 말한 것」(`followed`)과 「다르게 말한 영어」 두 절에 낱말 강세 표, 문장 강세 AUC(`score`, 내용어 대 기능어), 약형 표. 낱말 글자, 들린 말은 찍지 않는다.
  - `scripts/stress_report.py`: `--since`, `JE_DATA_DIR`을 measure와 같게 읽고 `render(load(...))`를 찍는다.

- [ ] **Step 1: 실패하는 시험 쓰기** — 손으로 만든 값 dict 몇 개로.

```python
def test_auc():
    assert auc([3, 2], [1]) == 1.0 and auc([1], [1]) == 0.5 and auc([], [1]) is None

def test_word_rows_count_only_words_with_one_dictionary_stress(): ...  # primary [0,1] 낱말은 빠짐
def test_mark_row_needs_the_same_syllable_count(): ...
def test_weak_forms(): assert weak_forms(recs)["for"] == (1, 2)
def test_render_prints_numbers_not_words():
    out = render(recs)
    assert "| 낱말 강세" in out and "coffee" not in out and "zebra" not in out  # 지어낸 낱말
```

- [ ] **Step 2: 실패 보기**
- [ ] **Step 3: 구현**
- [ ] **Step 4: 통과 보기**
- [ ] **Step 5: 커밋** — `feat(server): print the stress test tables from stored values`

### Task 6: 끝에서 끝까지와 실제 기록

**Files:**
- Modify: `docs/guide/PRONUNCIATION_녹음으로_강세평가_시험_20261105.md` (「잰 값 남기기 (2026-11-08)」 절: 돌리는 법, 첫 표의 숫자, 겪은 문제)
- Modify: `docs/guide/README.md` (색인 줄 설명), `server/README.md` (스크립트 두 줄)
- Modify(비공개, 원래 폴더): `docs/private/mac-env.md` (MFA 환경 위치, parselmouth 설치), `server/.env` (`JE_MFA_ENV`)

- [ ] **Step 1: 학습자 목소리 시험 폴더** — scratchpad에 지어낸 역할극 하나(대사 셋, 세 줄 표시 포함)와 학습자 목소리 녹음(`tts-render.py --voice jake`, 문장 넷: 따라 말함 둘, 강세를 바꿔 읽게 쓴 것 하나, 사전에 없는 지어낸 낱말이 든 것 하나)과 한국어 하나. `JE_DATA_DIR=<그 폴더> JE_MFA_ENV=… uv run python scripts/measure_stress.py --now` → 영어 녹음마다 값 파일, 한국어 0, `tmp/stress-*` 없음, 낱말·모음 시각이 녹음 길이 안. 다시 돌리면 measured 0. 강세를 바꿔 읽은 문장의 판정은 결과로만 적는다.
- [ ] **Step 2: 실제 기록 사본** — 앱 데이터 폴더의 `roleplays/`를 scratchpad로 복사(`cp -R`), 원래 폴더의 `roleplays/` sha256 목록을 저장. 사본으로 measure → report. 원래 폴더 sha256 목록이 같은지, 사본 `tmp/`가 비었는지 본다. 걸린 시간 기록.
- [ ] **Step 3: 가이드에 숫자만 더하기**, 비공개 메모와 `server/.env` 고치기, 커밋 — `docs(guide): add how to measure and report stored stress values`
- [ ] **Step 4: (리뷰를 마친 뒤) 실제 앱 데이터 폴더로 한 번 돌리기** — 같은 sha256 확인, `tmp/` 확인. 사본 폴더 지우기(`rm -rf "${SP:?}"/…`).
