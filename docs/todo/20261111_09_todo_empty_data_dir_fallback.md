# TODO: 비운 JE_DATA_DIR이 앱 데이터 폴더가 아니라 서버를 띄운 폴더가 된다

> 작성: 2026-11-11 (bundle-pictures 카드)
> 상태: **완료** (2026-11-11, PR #86. `config._value`로 기본값이 있는 줄을 모두 같은 꼴로 읽는다. 시험 `server/tests/test_config.py`, devlog `docs/devlog/2026-11-11-data-dir-default.md`)

## 무엇이 문제인가

- `server/.env.example`은 `JE_DATA_DIR=`를 빈 값으로 두고 「비우면 맥의 앱 데이터 폴더(~/Library/Application Support/jake-english)」라고 적었다.
- 그런데 `server/je_server/config.py`의 `load_settings`는 `Path(env.get("JE_DATA_DIR", DEFAULT_DATA_DIR))`라, 줄이 아예 없을 때만 기본값을 쓴다. 빈 값이 있으면 `Path("")`, 곧 `.`이 된다.
- 확인(2026-11-11): `load_settings({"JE_TOKEN": "x" * 32, "JE_DATA_DIR": ""}).data_dir`가 `.`이었다.
- 그래서 저장소를 받아 `cp .env.example .env`만 하고 서버를 띄우면, 녹음과 기록이 서버를 띄운 폴더(대개 `server/`) 아래에 쌓인다. 저장소 안이라 `git status`에 대화 기록(받아쓴 글)이 untracked로 보이고, 실수로 커밋될 수 있다. 녹음 파일은 `.gitignore`의 확장자 규칙과 커밋 전 검사가 막지만 기록 JSON은 막지 않는다.
- 이 맥의 `server/.env`에는 `JE_DATA_DIR` 줄이 없어 지금은 걸리지 않는다.

## 할 일

- `JE_ASSETS_DIR`처럼 빈 값도 기본값으로 읽게 고친다(`env.get("JE_DATA_DIR", "").strip() or DEFAULT_DATA_DIR`). 시험을 먼저 쓴다.
- 같은 꼴로 빈 값이 엉뚱한 값이 되는 항목이 더 있는지 본다(`JE_HOST`, `JE_PORT`, `JE_WHISPER_SERVER`, `JE_WHISPER_PORT`는 `.env.example`에 값이 들어 있지만, 비우면 `int("")` 오류나 빈 실행 파일 이름이 된다).
- 서버 코드라 PR로 한다.

## 관련

- ADR-0015(인물 그림을 저장소에 넣기): 같은 PR에서 `JE_ASSETS_DIR`의 빈 값을 저장소 폴더로 읽게 고쳤다. 범위를 넓히지 않으려고 이 일은 따로 남겼다.
