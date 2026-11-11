# 2026-11-11 빈 JE_DATA_DIR을 기본값으로 읽기

- PR: #86
- 문서: PRD 기능이 아니라 맥 서버 설정과 설치 안내를 고친 것이다. 스펙, 계획, ADR은 없다. 할 일 `docs/todo/20261111_09_todo_empty_data_dir_fallback.md`.

## 한 일

- `server/je_server/config.py`: 기본값이 있는 줄을 `_value`로 읽는다. 줄이 없을 때뿐 아니라 비었거나 공백만 있어도 기본값이 된다.
  - `JE_DATA_DIR`: 전에는 빈 값이 `Path("")`, 곧 서버를 띄운 폴더(대개 저장소의 `server/`)가 됐다. 이제 맥의 앱 데이터 폴더(`~/Library/Application Support/jake-english`)다.
  - `JE_PORT`, `JE_WHISPER_PORT`: 빈 값이면 `int("")` 오류로 서버가 멈췄다. 이제 8787, 8788이다.
  - `JE_HOST`, `JE_WHISPER_SERVER`: 빈 값이면 빈 주소, 빈 실행 파일 이름이 됐다. 이제 `127.0.0.1`, `whisper-server`다.
  - `JE_ASSETS_DIR`과 Claude 모델 줄은 이미 빈 값을 기본값으로 읽었고, 같은 함수로 옮겼다.
  - 값의 앞뒤 공백을 걷는다(`.env` 파일은 원래 걷었고, 환경 변수로 준 값도 같게 했다).
- 시험 `server/tests/test_config.py`.
- `server/README.md`에 「녹음과 기록」 절을 더했다. 녹음과 기록이 있는 곳, 여는 법, 서버를 끄고 그 폴더 하나를 지우면 모두 사라진다는 것, `JE_DATA_DIR`로 옮기는 법이다. 맨 위 `README.md`는 한 줄로 그 절을 가리킨다.
- 공개 설치 안내에서 「비공개 메모를 본다」를 새로 클론한 사람이 혼자 따를 수 있는 안내로 바꿨다. `server/README.md` 두 곳, `app/README.md`, `server/.env.example`, `app/.env.example`이다. 규칙 문서, devlog, 가이드의 「비공개 메모 참고」는 그대로 뒀다.
- `server/.env.example`에 기본값이 있는 줄마다 비우면 무엇이 되는지 적었다.

## 흐름

| 정할 것 | AI 추천 | 사용자 판단 | 결과 |
|---|---|---|---|
| 빈 값을 기본값으로 읽을 줄의 범위 | 할 일이 짚은 `JE_HOST`, `JE_PORT`, `JE_WHISPER_SERVER`, `JE_WHISPER_PORT`까지. 기본값이 빈 글인 줄(`JE_TTS_PYTHON` 등)은 그대로 | 묻지 않음(main 세션이 넘긴 글이 정함) | `_value` 하나로 모았다 |
| 강세 스크립트(`measure_stress.py`, `stress_report.py`)도 고칠지 | 고치지 않는다. 이미 `or DEFAULT_DATA_DIR`로 빈 값을 기본값으로 읽는다. 공백만 있는 환경 변수는 `roleplays/`가 없다며 폴더를 만들지 않고 멈춘다 | 묻지 않음(AI 판단) | PR 본문 「한계」에 적었다 |
| 녹음과 기록 안내를 둘 곳 | 설치 안내가 있는 `server/README.md`에 절을 두고, 맨 위 README에서 한 줄로 가리킨다 | 묻지 않음(AI 판단) | 두 곳 |
| 안드로이드 SDK 안내 | 위치만 적지 않고 빌드 명령에 `export ANDROID_HOME` 줄을 더한다. 새 worktree에는 `android/local.properties`가 없어 빌드가 `SDK location not found`로 멈춘 일이 여러 번 있었다 | 묻지 않음(AI 판단) | `app/README.md` |

## 바로잡은 것

- 첫 커밋의 제목이 79자라 commit-msg 훅에 걸렸다. 줄여 다시 커밋했다. 훅이 막을 것을 막았고, 더한 장치는 없다.

## 검증

- 새 시험이 먼저 실패: `uv run pytest tests/test_config.py` 9개 중 7개 실패. 빈 `JE_DATA_DIR`은 `PosixPath('.')`, 빈 포트는 `invalid literal for int() with base 10: ''`, 공백 있는 `JE_HOST`는 걷히지 않았다.
- 고친 뒤 서버 전체: `uv run pytest` 1035 passed, 4 skipped.
- 이 맥에서 바뀌는 것이 없는지: 원래 폴더의 `server/.env`와 맨 위 `.env`를 옛 코드(`main`)와 새 코드의 `load_settings`에 넣어 `Settings` 값을 견줬다. 다른 항목이 없었다(값은 찍지 않았다). 원래 `server/.env`에는 `JE_DATA_DIR` 줄이 없고, launchd 에이전트는 환경 변수로 `PATH`만 넣는다. 원래 `server/.env`는 고치지 않았다.
- 실제 읽는 길로: `HOME`을 임시 폴더로 바꾸고 `JE_DATA_DIR=`을 비운 채 `load_settings()`(파일과 환경 변수를 합치는 길)와 `Store`를 불렀다. 임시 홈의 `Library/Application Support/jake-english`에 `roleplays/`, `audio/`, `tmp/`가 생기고, `server/`에는 아무것도 생기지 않았다. 사용자 실제 앱 데이터 폴더와 원래 서버(8787)는 건드리지 않았다. 서버를 띄우지 않아 포트도 쓰지 않았다.
- 문서에 적은 `tailscale ip -4`, `/usr/libexec/java_home -v 17`, SDK 기본 위치(`~/Library/Android/sdk`)가 이 맥에서 되는 것을 봤다(값은 찍지 않았다).
- 앱 코드는 바꾸지 않아 폰 시험은 하지 않았다.
- 커밋 전 공개 금지 검사 통과. push 전에 `git log -p origin/main..HEAD`를 다시 읽었다.

## 리뷰

pr-review(Full, 코드 축 리뷰어 다섯과 스펙 축 하나)를 돌렸다.

- 코드 축: 넷이 0건이었다. 공개 노출(문서에 적은 경로와 명령), 녹음 처리, 다른 곳에서 `JE_DATA_DIR`을 읽는 스크립트, 문서에 적은 명령과 폴더 이름이 코드와 맞는지를 봤다. 이전 PR 코멘트 리뷰어가 하나를 냈다. `Settings` 필드와 `load_settings()`에 같은 기본값이 따로 적혀 있다는 것이다. 점수는 0점이었다. PR 전부터 있던 것이고, 줄이 없을 때와 비었을 때가 같은 `_value`를 거쳐 어긋날 수 없다는 이유였다. 게시하지 않았고 고치지 않았다.
- 스펙 축(기준 PR 본문, 약): 둘.
  - 실제 문제 하나를 게시했다. PR 본문이 가리킨 할 일 09와 devlog가 아직 PR에 없다는 것이다. 처음부터 마지막 커밋에 넣기로 한 파일이라 이 일지와 함께 넣었다.
  - 표현 차이 하나는 고치지 않았다. 맨 위 README의 한 줄과 `config.py` 모듈 설명이 본문에 없다는 것인데, README 줄은 본문이 이미 말하고, 모듈 설명은 동작과 무관하다.
- `REVIEW.md`에 더할 것은 없다. 되풀이된 오탐도, 리뷰가 놓친 문제도 없었다.

## 다음

- 원래 폴더의 할 일 09 사본(untracked)은 머지 뒤 정리 때 지운다.
