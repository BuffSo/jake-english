# 맥 서버

폰 앱이 부르는 맥 서버다(ADR-0001, ADR-0006). 받아쓰기, 라이언과 제이크 목소리, Claude 호출, 기록 저장을 맡는다.

## 준비

```sh
cd server
uv sync
cp .env.example .env   # 값을 채운다. 경로는 비공개 메모를 본다
```

토큰 만들기: `python3 -c "import secrets; print(secrets.token_hex(24))"`

`ffmpeg`가 PATH에 있어야 한다. 서버가 녹음과 목소리를 다른 형식으로 바꿀 때 쓰고, 시험도 시험용 소리를 ffmpeg로 만든다. 맥은 `brew install ffmpeg`, GitHub Actions는 우분투 저장소의 것을 깐다(ADR-0014).

## 띄우기

이 맥에서는 launchd가 띄운다(ADR-0012). 로그인할 때 띄우고, 죽으면 다시 띄운다. 처음 한 번 설치한다.

```sh
server/scripts/autostart.sh install    # 원래 폴더나 worktree 어디서든. 언제나 원래 폴더의 server/를 띄운다
server/scripts/autostart.sh status
```

- 서버를 `kill`로 끄면 곧바로 다시 뜬다. 끄고 켤 때는 이 스크립트를 쓴다. 명령과 카드가 서버를 시험하는 순서는 `docs/guide/DEVENV_맥서버_저절로_띄우기_20261107.md`.
- 손으로 띄우기(worktree에서 시험할 때): `uv run python -m je_server`

## 인물 그림

앱에 나오는 라이언, 소희, 제이크의 그림은 `server/assets/`에 있고, 서버가 `/assets/<이름>`으로 내준다(ADR-0015). AI로 만든 그림이라 MIT 라이선스에 들어가지 않는다. 쓸 수 있는 범위는 그 폴더의 `README.md`에 있다.

- `server/.env`의 `JE_ASSETS_DIR`을 비우면 이 폴더를 읽는다. 값을 주면 그 폴더만 읽는다. 새 그림을 커밋하기 전에 맥에서 시험해 볼 때 쓴다.
- 서버가 내주는 이름은 `je_server/app.py`의 `ASSETS`다. 그림을 더하거나 바꿀 때는 파일과 목록을 함께 고친다. `tests/test_assets.py`가 목록의 이름마다 PNG가 있는지, 폴더에 목록 밖 파일이 없는지 본다.
- 만드는 방법과 넣기 전에 볼 것은 `docs/guide/ASSET_제미나이로_얼굴_그림_만들기_20261106.md` 「앱 그림 바꾸기」.

## Claude 모델 고르기

`server/.env`의 다섯 줄로 모델을 고른다. 비우면 기본값이고, 바꾸면 서버를 다시 띄운다.

| 항목 | 맡는 일 | 값 | 기본 |
|---|---|---|---|
| `JE_CLAUDE_WRITER` | 대본, 세 줄 설명, 대본 밖 말에 대답, 대본 이어 가기 | `haiku`, `sonnet`, `opus` | `sonnet` |
| `JE_CLAUDE_QUICK` | 녹음 평가 글, 소희 통역 | `haiku`, `sonnet` | `haiku` |
| `JE_CLAUDE_RECOMMEND` | 제이크의 상황 추천 | `haiku`, `sonnet` | `sonnet` |
| `JE_CLAUDE_TALK` | 자유 대화의 라이언 | `haiku`, `sonnet`, `opus` | `sonnet` |
| `JE_CLAUDE_HINT` | 자유 대화의 소희 찬스(답 힌트) | `haiku`, `sonnet` | `sonnet` |

- 맡은 일마다 설정은 그대로이고 모델만 바뀐다. 글쓰기는 생각하는 단계를 끄고 effort low, 짧은 말과 추천은 생각하는 단계를 끈다. Opus는 생각하는 단계를 끌 수 없어 켠 채 effort low로 쓴다.
- 추천만 따로 둔 것은 2026-11-08 세 일을 견준 결과다. 추천은 Sonnet이 확실히 나았고, 평가와 통역은 비슷한데 Sonnet이 느렸다(`docs/guide/PROMPT_일마다_모델_견주기_20261108.md`).
- Opus는 아직 써 보지 않았다. 생각하는 단계가 켜져 있어, 학습자가 기다리는 대답(대본 밖 말에 대답)이 12초 제한에 걸려 「지금은 대답할 수 없어요」로 끝날 수 있다.
- 없는 값이면 서버가 시작할 때 `JE_CLAUDE_WRITER must be one of haiku, sonnet, opus, not '…'` 오류로 멈춘다.
- 서버 로그에 `claude models: writer …, quick …, recommend …, talk …, hint …` 줄로 고른 모델이 찍힌다.

## 시험

```sh
uv run pytest
```

시험 소리는 시험 중에 임시 폴더에 만든다. 녹음과 소리 파일은 커밋하지 않는다.

실제로 돌려 보는 스크립트(`scripts/`):

| 스크립트 | 하는 일 | 돈 |
|---|---|---|
| `try_recordings.py` | 녹음 파일을 앱처럼 서버에 보낸다. 역할극 복사본에 보내고 끝나면 지운다(`docs/guide/DEVENV_폰없이_녹음_시험하기_20261108.md`) | 녹음마다 Claude 한 번 |
| `check_ryan_wording.py` | 지어낸 대사로 라이언의 말을 실제 모델에 받아 어긴 규칙을 표시한다(`docs/guide/PRONUNCIATION_따라말하기_짚기_20261106.md` 「라이언의 말을 고칠 때」) | 한 번에 몇 센트 |
| `check_jake_recommend.py` | 지어낸 최근 상황 열 개와 함께 제이크 추천을 실제 모델로 받아 끝말을 지켰는지 센다. 서버가 고친 답(끝말 갈아 끼우기, 이름표 걷기)은 「swapped」로 센다(`--model`로 모델을 바꾼다, `docs/guide/PROMPT_정해진_말투를_섞기_20261108.md`) | Sonnet 스물한 번에 6.5센트쯤 |
| `compare_quick_models.py` | 짧은 말 세 일(소희 통역, 제이크 추천, 라이언 평가)을 같은 지어낸 입력으로 두 모델에 묻고 시간, 걸림, 값을 견준다(`docs/guide/PROMPT_일마다_모델_견주기_20261108.md`) | 기본 138번에 27센트쯤 |
| `check_false_flags.py` | 맞게 읽은 녹음과 기록으로 헛짚기 수를 잰다 | 없음(맥 안에서만) |
| `measure_claude.py` | 대본과 세 줄을 만드는 시간을 잰다 | 몇 센트 |
| `measure_stress.py` | 아직 재지 않은 영어 녹음을 MFA와 Praat로 재서 앱 데이터 폴더의 `stress/`에 남긴다. 다시 돌리면 새 녹음만 잰다. `server/.env`의 `JE_MFA_ENV`가 필요하다(`docs/guide/PRONUNCIATION_녹음으로_강세평가_시험_20261105.md` 「잰 값 남기기」) | 없음(맥 안에서만) |
| `stress_report.py` | 남긴 값으로 강세 시험 가이드의 표를 다시 낸다. 개수와 비율만 찍는다 | 없음 |

돈이 드는 스크립트는 몇 번 돌릴지와 비용을 먼저 사용자에게 말한다.

## 집 밖에서 쓰기 (Tailscale, ADR-0007)

- `server/.env`의 `JE_HOST`를 맥의 Tailscale 주소로 둔다(주소는 비공개 메모). 서버는 그 주소에만 붙고, 집 와이파이 주소로는 열리지 않는다.
  - 확인: `lsof -nP -iTCP:8787 -sTCP:LISTEN`에 Tailscale 주소만 보여야 한다.
- 앱의 `app/.env`에도 같은 주소와 토큰을 넣고 빌드한다(`app/README.md`).
- Tailscale Funnel, 포트 전달, 공개 터널은 쓰지 않는다. 확인: `tailscale funnel status`가 비어 있어야 한다.
- 집 밖에서 쓰는 동안 맥은 켜져 있고 잠들지 않아야 한다. 맥을 다시 켜면 로그인할 때 Tailscale과 서버가 함께 뜬다. 서버는 Tailscale 주소가 생길 때까지 기다린다. 로그인하기 전에는 둘 다 돌지 않는다.
