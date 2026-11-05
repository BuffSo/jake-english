# 상황 역할극 MVP 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 폰 앱을 열면 라이언이 인사하고, 상황을 정해 역할극을 하며, 내 대사를 세 줄로 보고 본보기를 듣고 녹음해 바로 평가를 듣는다. 집 밖에서도 Tailscale로 쓴다.

**Architecture:** 맥 서버(파이썬 FastAPI)가 받아쓰기(whisper-server를 띄워 둠), 라이언과 제이크 목소리(맥의 기존 음성 환경에서 따로 도는 작업 프로세스), Claude 호출, 기록 저장을 맡는다. 폰 앱(Expo, 타입스크립트)은 화면, 녹음, 재생만 하고 모든 요청에 토큰을 붙인다. 평가는 줄 단위 NDJSON으로 흘려 받아, 글은 오는 대로 보이고 목소리는 문장마다 튼다.

**Tech Stack:** Python 3.14(uv), FastAPI, uvicorn, anthropic(공식 SDK 1.x), cmudict, httpx, pytest / whisper.cpp `whisper-server` large-v3 / Qwen3-TTS(맥에 이미 있는 환경) / ffmpeg, afconvert / Expo SDK 58(blank-typescript), expo-audio, expo-file-system, expo-build-properties, jest-expo / Tailscale

**Spec:** `docs/superpowers/specs/2026-11-05-speaking-practice-design.md` (「첫 구현 범위 (2026-11-05)」만). 함께 읽을 것: `docs/PRD.md` 「첫 판: 말하기」, 「강세 기준」, ADR-0001, 0002, 0004, 0006, 0007, 0008, `docs/guide/PRONUNCIATION_한글발음_세줄표시_20261105.md`.

## 이 계획에서 정한 것

스펙이 빌더에게 맡긴 것과, 스펙과 다르게 정한 것이다. 모두 AI 판단이다.

- **음성 모델을 한 번 더 올린다(스펙 「제약」과 다름):** 서버가 맥의 기존 음성 환경(venv와 처리 코드, 비공개 메모 참고)을 그대로 쓰는 작업 프로세스를 하나 띄운다. 답 읽기 데몬이 떠 있으면 같은 모델이 메모리에 둘 올라간다. 데몬에는 파일로 만드는 명령이 없고, 전역 hooks 파일은 고치지 않기로 했기 때문이다. 메모리는 둘을 함께 올려도 넉넉하다(비공개 메모 참고). ADR-0009로 남기고 스펙 「제약」을 고친다(Task 4).
- **받아쓰기:** `whisper-server`를 서버가 `127.0.0.1`에 띄워 둔다. 요청마다 `language`를 준다(차례 녹음은 `en`, 상황 설명은 `auto`). 2026-11-05 시험에서 요청마다 언어가 바뀌었고, 띄워 둔 large-v3는 2초 녹음을 0.3초에 받아썼다.
- **조용한 녹음:** 같은 시험에서 2초 무음을 「you」로, 작은 잡음을 「Okay.」로 받아썼다. 그래서 받아쓰기 전에 소리 크기를 재서, 말소리가 없으면 받아쓰지 않고 「잘 안 들렸어요」로 답한다.
- **세 줄 형식:** 아래 「세 줄 형식」대로 낱말마다 영어 음절과 한글의 짝을 남겨, 가이드의 기계 검사 셋을 돌린다. 검사에 두 번 더 걸리면 틀린 표시만 지우고 보여 준다. 틀리게 칠하는 것보다 칠하지 않는 편이 낫다(PRD 「실패로 볼 것」 1).
- **대본 만들기를 둘로 나눈다:** 먼저 대사 글만 만들고(빠름), 사용자 대사의 세 줄은 줄마다 따로 동시에 만든다. 라이언 대사의 세 줄은 화면에서 누를 때 만든다. 앞줄부터 준비되므로 첫 차례를 빨리 시작한다.
- **다르게 말했을 때:** 대답(짚을 것 한 가지와 영어 대답)을 먼저 받고, 남은 대본은 라이언이 대답하는 동안 한 번에 다시 만든다(스펙 「역할극의 한 차례」 5의 「대답하는 동안 다음 사용자 대사를 먼저 만든다」를 따름). 발음 짐작은 맥이 사전 발음으로 확인하고, 설명은 소리 설명 목록의 글을 그대로 쓴다.
- **다시 해 보기:** 같은 대사를 다시 녹음하면 `mode=retry`로 보낸다. 이때는 다르게 말해도 대본을 바꾸지 않고 「대사를 따라 말해 볼까요?」라고만 한다.
- **기록 위치와 형식:** 맥의 앱 데이터 폴더(`~/Library/Application Support/jake-english`, `JE_DATA_DIR`로 바꿀 수 있다) 아래 역할극마다 폴더 하나. `roleplay.json`(상황, 틀, 대본, 차례마다 평가), `rec/`(녹음). 만든 소리는 `audio/`에 글의 해시 이름으로 둔다. 녹음은 지우지 않는다(스펙 「녹음과 기록」).
- **API 모양을 맞추는 법(ADR-0006 「영향」):** 저장소 맨 위 `contract/`에 예시 JSON을 두고, 서버 시험은 pydantic 모델로 읽고, 앱 시험은 타입스크립트 타입으로 읽는다(`tsc`가 어긋남을 잡는다). 새 도구를 들이지 않는다.
- **접속 주소와 토큰:** 서버는 `server/.env`의 `JE_HOST`에만 붙는다(Tailscale 주소, 시험 때는 `127.0.0.1`). 집 와이파이 주소로는 열지 않는다(ADR-0007). 앱은 빌드할 때 `app/.env`의 주소와 토큰을 넣는다. 두 `.env`는 git에서 뺀다. APK는 커밋하지 않는다.
- **평문 HTTP:** Tailscale 안에서는 기기 사이가 이미 암호화되므로, 안드로이드 릴리스 빌드에 `usesCleartextTraffic`를 켠다. `tailscale serve`의 HTTPS는 쓰지 않는다.
- **라이언 그림:** 서버가 비공개 폴더의 그림 둘(`ryan-front.png`, `ryan-listening.png`)만 토큰을 거쳐 내준다. 앱과 저장소에는 넣지 않는다.
- **빠르기:** 서버가 ffmpeg `atempo`로 0.6, 0.8배 소리를 만들어 둔다(높이는 그대로).
- **업로드:** 앱은 녹음 파일을 multipart가 아니라 바이트 그대로 보낸다(`Content-Type: audio/mp4`). 서버는 5MB까지만 받고, 60초가 넘는 녹음은 받지 않는다. 앱은 60초에 녹음을 멈춘다.
- **거절(refusal):** Claude가 거절하면 API 실패와 같게 「지금은 대답할 수 없다」고 알린다. 서버 측 fallback은 쓰지 않는다.
- **서버 켜 두기:** 이번에는 터미널에서 띄운다. 맥을 켤 때 저절로 띄우는 것(launchd)은 todo로 남긴다.

## Global Constraints

모든 Task의 요구 사항에 들어 있는 것으로 본다.

- 계산은 맥에서 하고, 앱은 화면, 녹음, 재생만 한다(ADR-0001). 앱은 Claude를 부르지 않는다(ADR-0004).
- Anthropic에는 대사, 받아쓴 글, 맥이 정한 짚을 것과 소리 설명, 사용자가 쓴 상황만 보낸다. 녹음 소리, 소리 특징값, 파일 경로, 기기 정보는 보내지 않는다(ADR-0004, 스펙 「평가」 공통).
- 녹음은 폰에서 맥으로 보내 맥에만 둔다. 폰에는 남기지 않는다. 정하기 전까지 지우지 않는다(스펙 「녹음과 기록」).
- 모델: 녹음 평가의 말 옮기기와 상황 추천은 `claude-haiku-5-5`, `thinking={"type": "disabled"}`. 대본, 세 줄, 다르게 말했을 때의 대답은 `claude-sonnet-5-5`, `thinking={"type": "between_tools"}`, `output_config={"effort": "low"}`. `temperature`, `top_p`, `top_k`는 보내지 않는다.
- 짚는 개수: 따라 말한 차례는 한두 가지, 다르게 말한 차례는 한 가지(스펙 「실패로 볼 것」 4).
- 강세는 녹음만 보고 짚지 않는다. 대사에 미리 표시한다.
- 소리 설명은 목록에서만 쓴다. 목록의 소리: R과 L, F와 P, V와 B, TH(θ, ð)와 S, D, Z와 J. 라이언은 설명을 다듬기만 하고 지어내지 않는다.
- 차례 녹음의 받아쓰기는 영어로 고정하고, 대사를 힌트로 주지 않는다.
- 본보기 빠르기는 0.6배, 0.8배, 1배. 목소리 높이는 그대로 둔다.
- 대본의 사용자 차례는 4~6번.
- 라이언의 한국어는 존댓말(해요체)이다. 지시문에 예시를 함께 준다.
- 기다림 목표: 녹음이 끝나고 평가 글의 첫 문장 2~3초, 라이언 목소리 4~5초.
- 맥이 인터넷에 연결되지 않거나 API가 실패하면, 앱은 지금은 대화와 평가를 할 수 없다고 알린다. 맥에 닿지 않으면 맥에 연결할 수 없다고 알린다.
- 서버의 모든 경로는 토큰 인증을 거친다. Tailscale Funnel, 포트 전달, 공개 터널을 쓰지 않는다(ADR-0007).
- 받은 값(id, 파일 이름, 소리 이름)으로 맥의 다른 파일에 닿지 못하게, 정해진 꼴(정규식)만 받는다. 받은 값을 셸 명령에 넣지 않는다(subprocess는 인자 목록으로만).
- 로그에는 시간과 개수만 남긴다. 받아쓴 글, 대사, 녹음 경로, 키를 찍지 않는다(`REVIEW.md` 「녹음 처리」).
- 앱 고유 ID는 `dev.jakeso.english`, 화면 이름은 `Jake English`(ADR-0008).
- 공개 저장소: 홈 폴더 절대 경로, Tailscale 주소와 기기 이름, 토큰, 라이언 그림, 녹음, 소리 파일을 커밋하지 않는다. 시험 소리는 시험 중에 임시 폴더에 만든다. 시험 문장은 지어낸 것을 쓴다.
- git은 `/usr/bin/git`으로 부른다. `git add`는 파일을 지정한다. 커밋 메시지는 Conventional Commits 영어, scope는 `server`, `app`, 문서는 `adr` 등. AI 서명을 넣지 않는다. `git commit -F - <<'EOF'`로 쓴다.

## Review Focus

시험이 따로 다루지 않으면 쓰다가 가장 먼저 부딪힐 것이다. 줄마다 그 코드를 맡은 Task에 시험을 넣었다.

1. **말소리 없는 녹음:** 버튼을 눌렀다 바로 떼거나 주머니 속 잡음만 녹음되면, 받아쓰기가 「you」, 「Okay.」를 지어낸다. 그대로 두면 다르게 말한 것으로 보고 라이언이 엉뚱하게 대답하고 대본을 바꾼다. 「잘 안 들렸어요」로 답하고 대본은 그대로 둬야 한다(Task 6).
2. **Claude 실패(인터넷 끊김, 429, 5xx, 거절):** 대본을 만들거나 평가하는 중에 실패하면 앱이 멈추거나 500만 받지 않고, 「지금은 라이언이 대답할 수 없어요」를 듣는다. `roleplay.json`은 반쯤 바뀐 채 남지 않는다(Task 3, 5, 6).
3. **역할극 중 서버를 다시 띄움:** 맥을 다시 켜거나 서버를 다시 띄우면 메모리의 준비 작업이 사라진다. 다음 줄을 열면 `roleplay.json`을 보고 빠진 세 줄과 소리를 다시 만들어야 한다(Task 5).
4. **두 번 누르기:** 녹음 버튼이나 「다음」을 평가가 흐르는 중에 다시 누르면, 녹음이 두 번 가거나 줄을 건너뛴다. 하는 중에는 버튼을 막는다(Task 9).
5. **밖에서 연결이 끊김:** 모바일 데이터가 끊기면 앱이 끝없이 기다리지 않고, 시간 제한 뒤 「맥에 연결할 수 없어요」와 「다시 시도」를 보여 준다(Task 8).

## 세 줄 형식

대사 한 줄(`ThreeLine`)은 낱말 목록과 읽는 법 글이다. 서버 `server/je_server/models.py`와 앱 `app/src/api/types.ts`가 같은 모양을 쓴다.

```json
{
  "words": [
    {"syl": [{"en": "I'd", "ko": "아잇", "m": "n", "hi": ""}], "emph": false, "link": false},
    {"syl": [{"en": "like", "ko": "라이", "m": "n", "hi": ""}], "emph": false, "link": true},
    {"syl": [{"en": "a", "ko": "커", "m": "w", "hi": ""}], "emph": false, "link": false},
    {"syl": [{"en": "cup", "ko": "커", "m": "n", "hi": ""}], "emph": false, "link": true},
    {"syl": [{"en": "of", "ko": "퍼", "m": "w", "hi": ""}], "emph": false, "link": false},
    {"syl": [{"en": "cof", "ko": "카", "m": "s", "hi": "카"}, {"en": "fee.", "ko": "피", "m": "w", "hi": ""}], "emph": false, "link": false}
  ],
  "reading": "coffee는 앞을 세게, [[카-피]]. 뒤 [[피]]는 짧고 약하게."
}
```

- `m`: `s` 노란 칠(센 음절), `w` 작은 회색(약한 음절), `n` 그대로.
- `hi`: `m`이 `s`일 때만, `ko` 안에서 칠할 한글 한 글자(모음이 든 글자). 나머지는 빈 글.
- `emph`: 뜻 때문에 힘준 낱말. 사전 검사에서 뺀다.
- `link`: 이 낱말의 한글을 다음 낱말에 띄어 쓰지 않고 붙인다(이어 읽기).
- 영어 줄은 낱말마다 `syl[].en`을 이어 붙이고 낱말 사이를 띄운다. 문장부호는 마지막 음절의 `en`에 붙인다.
- 한글 줄은 낱말마다 `syl[].ko`를 이어 붙이고, `link`가 아니면 띄운다.
- `reading`의 `[[...]]`는 발음 글이다. 화면에는 「...」로 보인다. 뜻을 적는 「」는 그대로 쓴다.

기계 검사(`threeline.check`, 가이드 「기계로 검사할 수 있는 것」):

| 검사 | 걸리는 것 |
|---|---|
| words | 영어 음절을 이어 붙인 낱말들이 대사 글과 다르다(대소문자, 문장부호는 빼고 견준다) |
| hi(규칙 2) | `m`이 `s`인데 `hi`가 한글 한 글자가 아니거나 `ko`에 없다. `s`가 아닌데 `hi`가 있다 |
| stress(규칙 7) | 두 음절 이상이고 `emph`가 아닌 낱말에서 `s` 음절의 자리가 CMUdict 어느 발음의 1차 강세와도 다르다. 사전에 없거나, 음절 수가 사전 모음 수와 맞는 발음이 없으면 검사하지 않는다 |
| ref(규칙 5) | `[[...]]`를 `-`로 나눈 조각이 한글 줄의 음절 `ko`가 이어진 한 구간과 같지 않다 |

## 파일 구조

```
.gitignore                       server/.venv, app/node_modules 등 더함
contract/                        앱과 서버가 함께 쓰는 예시 JSON
  roleplay.json  line-user.json  attempt-events.ndjson
server/
  pyproject.toml  uv.lock  .env.example  README.md
  je_server/
    __main__.py      설정을 읽고 uvicorn을 띄운다
    config.py        server/.env와 저장소 맨 위 .env를 읽는 Settings
    app.py           FastAPI 앱, 경로, 시작과 종료(whisper, 목소리, 고정 문구)
    auth.py          Bearer 토큰 검사
    models.py        pydantic 모델(세 줄, 대본, 차례, 이벤트)
    phrases.py       늘 같은 라이언 말(인사, 질문, 마무리, 오류)
    store.py         데이터 폴더, roleplay.json 읽기와 쓰기
    cmu.py           CMUdict 발음 찾기
    threeline.py     세 줄 검사와 표시 지우기
    compare.py       받아쓴 글과 대사 맞대기, 바뀐 소리 찾기, 잘한 점 후보
    sounds.py        소리 설명 목록 읽기
    data/sounds.json 소리 설명 목록(사람 검토 전 초안)
    sentences.py     흘러오는 글을 문장으로 끊기
    claude.py        Claude 호출(대본, 세 줄, 추천, 평가 말, 다르게 말했을 때)
    prompts.py       지시문과 JSON 스키마
    audio.py         ffmpeg 바꾸기, 소리 크기, 빠르기
    asr.py           whisper-server 띄우기와 받아쓰기
    tts.py           목소리 작업 프로세스와 우선순위 줄, 소리 캐시
    tts_worker.py    맥의 기존 음성 환경 파이썬으로 도는 작업 프로세스
    engine.py        역할극 흐름(만들기, 준비, 차례 평가, 다시 만들기, 마무리)
  tests/             pytest
  scripts/
    measure_claude.py     대본과 세 줄 만드는 시간 재기(실제 API)
    check_false_flags.py  시험 녹음으로 헛짚기 세기(맥 안에서만)
app/                 create-expo-app blank-typescript
  app.json  .env.example  App.tsx
  src/config.ts
  src/api/  types.ts  ndjson.ts  client.ts
  src/audio/  player.ts  useRecorder.ts
  src/flow/state.ts
  src/ui/  threeLineSegments.ts  ThreeLine.tsx  Button.tsx
  src/screens/  HomeScreen.tsx  SituationScreen.tsx  RoleplayScreen.tsx  EndScreen.tsx
  src/**/*.test.ts
docs/adr/0009-voice-worker-on-existing-tts.md
```

## 서버 API

모든 경로는 `Authorization: Bearer <JE_TOKEN>`가 없거나 틀리면 401이다. `Said`는 `{"text": str, "audio": str}`이고 `audio`는 소리 이름(sha256 16진수 64자)이다.

| 경로 | 돌려주는 것 |
|---|---|
| `GET /health` | `{"ok": true}` |
| `GET /home` | `{"lines": {"greeting": Said, "ask_mode": Said, "ask_situation": Said, "ask_recommend": Said}, "images": {"front": "/assets/ryan-front.png", "listening": "/assets/ryan-listening.png"}}` |
| `GET /assets/{name}` | 그림. `name`은 위 두 이름만 |
| `GET /audio/{key}?rate=1.0` | m4a. `key`는 `^[0-9a-f]{64}$`, `rate`는 0.6, 0.8, 1.0만 |
| `POST /transcribe` | 몸은 녹음 바이트. `{"text": str}`. 받아쓴 뒤 녹음을 지운다 |
| `POST /recommend` | `{"text": 한국어 부탁 글, "audio": 제이크 목소리}` |
| `POST /roleplays` | 몸 `{"situation": str}`(1~300자). `Roleplay`(세 줄과 소리는 아직 없음) |
| `GET /roleplays/{id}/lines/{idx}` | 준비가 끝날 때까지 기다렸다가 `ScriptLine`(사용자 줄은 세 줄과 본보기, 라이언 줄은 소리) |
| `GET /roleplays/{id}/lines/{idx}/three` | 라이언 줄의 세 줄을 그때 만들어 `ThreeLine` |
| `POST /roleplays/{id}/lines/{idx}/attempts?mode=turn\|retry` | 몸은 녹음 바이트. NDJSON 이벤트 흐름(아래) |
| `GET /roleplays/{id}/summary` | `{"say": Said, "retry": [idx, ...]}` |

`id`는 `^[0-9a-f]{12}$`. 실패는 JSON `{"code": str, "say": Said | null}`로 돌려준다. `code`: `claude_unavailable`(503), `no_speech`, `too_long`(413), `not_found`(404).

차례 이벤트(한 줄에 JSON 하나):

```
{"type": "heard", "text": "I'm learning to the station", "followed": true}
{"type": "text", "delta": "station까지 또렷하게"}
{"type": "audio", "key": "<64자>"}
{"type": "reply", "line": ScriptLine}
{"type": "error", "code": "no_speech", "say": Said}
{"type": "done", "next": 3, "issues": 1}
```

---

### Task 1: 서버 뼈대와 토큰 인증

**Files:**
- Modify: `.gitignore`
- Create: `server/pyproject.toml`, `server/.env.example`, `server/README.md`, `server/je_server/__init__.py`, `server/je_server/__main__.py`, `server/je_server/config.py`, `server/je_server/auth.py`, `server/je_server/app.py`
- Test: `server/tests/test_auth.py`, `server/tests/conftest.py`

**Interfaces:**
- Produces: `Settings`(dataclass: `token: str`, `host: str = "127.0.0.1"`, `port: int = 8787`, `data_dir: Path`, `anthropic_api_key: str`, `tts_python: str`, `tts_module: str`, `whisper_exe: str = "whisper-server"`, `whisper_model: str`, `whisper_port: int = 8788`, `assets_dir: Path`), `load_settings(env: Mapping[str, str] | None = None) -> Settings`, `create_app(settings: Settings, services: Services | None = None) -> FastAPI`, `require_token`(FastAPI 의존성). `Services`는 Task 5에서 채우는 묶음이고, 여기서는 빈 dataclass로 둔다.

- [ ] **Step 1: `.gitignore`에 더한다**

`server/.venv/`, `__pycache__/`, `.pytest_cache/`, `app/node_modules/`, `app/android/`, `app/ios/`, `app/.expo/`, `app/dist/`, `*.apk`.

- [ ] **Step 2: uv 프로젝트를 만든다**

`server/pyproject.toml`: 이름 `je-server`, `requires-python = ">=3.12"`, 의존성 `fastapi`, `uvicorn`, `anthropic`, `cmudict`, `httpx`, 개발 의존성 그룹 `pytest`. `[tool.pytest.ini_options] testpaths = ["tests"]`.

Run: `cd server && uv sync`
Expected: `.venv`가 생기고 오류 없음.

- [ ] **Step 3: 실패하는 시험을 쓴다**

```python
# server/tests/test_auth.py
from fastapi.testclient import TestClient
from je_server.app import create_app

def test_health_needs_token(settings):
    c = TestClient(create_app(settings))
    assert c.get("/health").status_code == 401
    assert c.get("/health", headers={"Authorization": "Bearer wrong"}).status_code == 401

def test_health_with_token(settings):
    c = TestClient(create_app(settings))
    r = c.get("/health", headers={"Authorization": f"Bearer {settings.token}"})
    assert r.status_code == 200 and r.json() == {"ok": True}

def test_settings_require_token(tmp_path):
    import pytest
    from je_server.config import load_settings
    with pytest.raises(ValueError, match="JE_TOKEN"):
        load_settings({"JE_DATA_DIR": str(tmp_path)})
```

`conftest.py`의 `settings` fixture는 `tmp_path`를 데이터 폴더로, 토큰은 `"t" * 32`로 둔 `Settings`다.

- [ ] **Step 4: 시험이 실패하는지 본다**

Run: `cd server && uv run pytest tests/test_auth.py -v`
Expected: FAIL(`ModuleNotFoundError: je_server.app`)

- [ ] **Step 5: 구현한다**

- `load_settings`: `env`가 없으면 `server/.env`와 저장소 맨 위 `.env`를 읽어(줄마다 `KEY=VALUE`, `#` 줄은 넘김, 이미 있는 환경 변수가 앞섬) 만든다. `JE_TOKEN`이 없거나 32자보다 짧으면 `ValueError("JE_TOKEN ...")`. `JE_DATA_DIR` 기본값은 `~/Library/Application Support/jake-english`.
- `require_token`: `Authorization` 머리에서 토큰을 꺼내 `secrets.compare_digest`로 견준다.
- 모든 경로를 `APIRouter(dependencies=[Depends(require_token)])` 밑에 둔다.
- `__main__.py`: `uvicorn.run(create_app(load_settings()), host=s.host, port=s.port)`.
- `.env.example`: 키 이름과 설명만 쓴다(값, 경로 없음). 실제 경로는 비공개 메모 참고.
- `README.md`: `uv sync`, `uv run python -m je_server`, `uv run pytest`, 토큰 만들기(`python3 -c "import secrets; print(secrets.token_hex(24))"`).

- [ ] **Step 6: 시험이 통과하는지 본다**

Run: `cd server && uv run pytest -v`
Expected: 3 passed

- [ ] **Step 7: 커밋한다**

`/usr/bin/git add .gitignore server/pyproject.toml server/uv.lock server/.env.example server/README.md server/je_server server/tests`
메시지: `feat(server): add FastAPI skeleton with bearer token auth`

---

### Task 2: 세 줄 모델과 기계 검사

**Files:**
- Create: `server/je_server/models.py`, `server/je_server/cmu.py`, `server/je_server/threeline.py`
- Test: `server/tests/test_cmu.py`, `server/tests/test_threeline.py`

**Interfaces:**
- Produces:
  - `models.py`: `Syllable(en: str, ko: str, m: Literal["s","w","n"], hi: str = "")`, `Word(syl: list[Syllable], emph: bool = False, link: bool = False)`, `ThreeLine(words: list[Word], reading: str)`. Task 5가 더할 모델도 이 파일에 둔다.
  - `cmu.prons(word: str) -> list[list[str]]`(소문자로 찾는다, 없으면 `[]`), `cmu.primary_index(pron: list[str]) -> int | None`(1차 강세 모음이 몇 번째 모음인지), `cmu.vowel_count(pron) -> int`, `cmu.strip_stress(pron) -> list[str]`
  - `threeline.Problem(kind: Literal["words","hi","stress","ref"], word: int | None, detail: str)`, `threeline.check(text: str, three: ThreeLine) -> list[Problem]`, `threeline.degrade(three: ThreeLine, problems: list[Problem]) -> ThreeLine`, `threeline.plain(text: str) -> ThreeLine`, `threeline.korean_line(three) -> str`, `threeline.refs(reading: str) -> list[str]`

- [ ] **Step 1: 실패하는 시험을 쓴다**

```python
# server/tests/test_threeline.py
from je_server.models import ThreeLine, Word, Syllable as S
from je_server.threeline import check, degrade, plain, korean_line

def coffee(stress_first=True, hi="카"):
    m1, m2 = ("s", "w") if stress_first else ("w", "s")
    return Word(syl=[S(en="cof", ko="카", m=m1, hi=hi if m1 == "s" else ""),
                     S(en="fee.", ko="피", m=m2, hi="피" if m2 == "s" else "")])

def line(*words, reading=""):
    return ThreeLine(words=list(words), reading=reading)

I = Word(syl=[S(en="I", ko="아이", m="n")])
LIKE = Word(syl=[S(en="like", ko="라익", m="n")])

def test_good_line_has_no_problems():
    assert check("I like coffee.", line(I, LIKE, coffee(), reading="[[카-피]]")) == []

def test_stress_on_wrong_syllable():
    p = check("I like coffee.", line(I, LIKE, coffee(stress_first=False)))
    assert [x.kind for x in p] == ["stress"] and p[0].word == 2

def test_record_noun_and_verb_both_pass():
    noun = Word(syl=[S(en="re", ko="레", m="s", hi="레"), S(en="cord.", ko="커드", m="w")])
    verb = Word(syl=[S(en="re", ko="리", m="w"), S(en="cord.", ko="코드", m="s", hi="코")])
    assert check("record.", line(noun)) == [] and check("record.", line(verb)) == []

def test_highlight_must_be_one_hangul_in_ko():
    w = Word(syl=[S(en="ob", ko="압", m="s", hi="아브"), S(en="ject?", ko="젝트", m="w")])
    assert [x.kind for x in check("object?", line(w))] == ["hi"]

def test_emphasis_and_unknown_words_skip_stress_check():
    namsan = Word(syl=[S(en="Nam", ko="남", m="n"), S(en="san", ko="산", m="s", hi="산")])
    did = Word(syl=[S(en="did", ko="딛", m="s", hi="딛")], emph=True)
    assert check("Namsan", line(namsan)) == [] and check("did", line(did)) == []

def test_words_must_match_text():
    assert [x.kind for x in check("I like tea.", line(I, LIKE, coffee()))] == ["words"]

def test_reading_ref_must_match_korean_syllables():
    p = check("I like coffee.", line(I, LIKE, coffee(), reading="[[카-페]] 말고"))
    assert [x.kind for x in p] == ["ref"]

def test_degrade_removes_only_bad_marks():
    bad = line(I, LIKE, coffee(stress_first=False), reading="[[카-페]]")
    fixed = degrade(bad, check("I like coffee.", bad))
    assert all(s.m != "s" for s in fixed.words[2].syl) and fixed.reading == ""
    assert check("I like coffee.", fixed) == []

def test_korean_line_joins_linked_words():
    a = Word(syl=[S(en="cup", ko="커", m="n")], link=True)
    of = Word(syl=[S(en="of", ko="퍼", m="w")])
    assert korean_line(line(a, of, coffee())) == "커퍼 카피"

def test_plain_line_passes():
    assert check("Where is it?", plain("Where is it?")) == []
```

`test_cmu.py`: `prons("record")`에 1차 강세 자리 0과 1이 모두 있고, `prons("namsan") == []`, `primary_index(["K","AA1","F","IY0"]) == 0`.

- [ ] **Step 2: 시험이 실패하는지 본다**

Run: `cd server && uv run pytest tests/test_threeline.py tests/test_cmu.py -v`
Expected: FAIL(모듈 없음)

- [ ] **Step 3: 구현한다**

- `cmu.py`: `cmudict.dict()`를 처음 쓸 때 한 번 읽는다. 낱말은 소문자로 바꾸고 앞뒤 문장부호를 뗀다(`'`는 둔다).
- `check`: 표의 네 검사. `words`는 대사 글과 음절을 이어 붙인 글을 소문자로 바꾸고 `[^a-z0-9' ]`를 지운 낱말 목록으로 견준다. `ref`는 모든 음절의 `ko`를 차례로 늘어놓은 목록에서, `[[...]]`를 `-`로 나눈 조각이 이어진 한 구간과 같은지 본다. `[[...]]` 안에 한글과 `-` 말고 다른 글자가 있어도 `ref`다.
- `degrade`: `stress`와 `hi` 문제가 난 낱말의 `s`를 `n`으로 바꾸고 `hi`를 지운다. `ref` 문제가 하나라도 있으면 `reading`을 빈 글로 한다. `words` 문제가 있으면 `plain(text)`를 돌려준다.
- `plain`: 대사의 낱말마다 음절 하나(`en`=낱말, `ko`="", `m`="n"), `reading` 빈 글.

- [ ] **Step 4: 시험이 통과하는지 본다**

Run: `cd server && uv run pytest -v`
Expected: 모두 통과

- [ ] **Step 5: 커밋한다**

메시지: `feat(server): add three-line model with dictionary stress checks`

---

### Task 3: Claude로 대본, 세 줄, 상황 추천 만들기와 시간 재기

**Files:**
- Create: `server/je_server/claude.py`, `server/je_server/prompts.py`, `server/scripts/measure_claude.py`
- Modify: `server/je_server/models.py`
- Test: `server/tests/test_claude.py`, `server/tests/fakes.py`

**Interfaces:**
- Consumes: `ThreeLine`, `threeline.check/degrade/plain`(Task 2)
- Produces:
  - `models.py`에 더함: `Frame(title_ko: str, user_role_ko: str, ryan_role_ko: str, place_ko: str, goal_ko: str)`, `Speaker = Literal["ryan","user"]`, `Draft = list[tuple[Speaker, str]]`
  - `class ClaudeUnavailable(Exception)`
  - `class Claude(client: anthropic.AsyncAnthropic)` 메서드:
    - `async make_script(situation: str, recent: list[str]) -> tuple[Frame, Draft]`
    - `async annotate(text: str, context: str) -> ThreeLine`(검사와 두 번까지 다시 만들기, 그래도 걸리면 `degrade`)
    - `async recommend(recent: list[str]) -> str`
  - `HAIKU`, `SONNET`(요청에 펼쳐 넣는 dict, Global Constraints의 모델 설정)
  - `tests/fakes.py`: `FakeAnthropic`(요청을 기록하고, 정해 둔 답을 차례로 돌려준다. 답이 예외면 그 예외를 올린다. `messages.create`와 `messages.stream`을 흉내 낸다), 답 만들기 도우미 `script_json(user_turns: int) -> str`, `three_json_with_wrong_stress(text: str) -> str`, `refusal_response()`, `connection_error() -> anthropic.APIConnectionError`, 그리고 `FakeClaude`(`Claude`와 같은 메서드. `make_script`는 늘 같은 대본을 돌려준다: 라이언 「Excuse me, where is the subway station?」, 사용자 「It's right over there.」로 시작해 사용자 차례 4번, 라이언 마무리로 끝남. `fail_next = True`면 다음 호출에서 `ClaudeUnavailable`)

- [ ] **Step 1: 실패하는 시험을 쓴다**

```python
# server/tests/test_claude.py  (anyio 플러그인: @pytest.mark.anyio)
async def test_make_script_validates_turns():
    # 사용자 차례가 3번뿐인 대본 → 한 번 다시 요청, 두 번째 답(5번)을 쓴다
    fake = FakeAnthropic([script_json(user_turns=3), script_json(user_turns=5)])
    frame, draft = await Claude(fake).make_script("길 묻기", [])
    assert sum(1 for s, _ in draft if s == "user") == 5 and len(fake.requests) == 2
    assert draft[0][0] == "ryan" and draft[-1][0] == "ryan"
    assert all(a[0] != b[0] for a, b in zip(draft, draft[1:]))  # 번갈아

async def test_requests_use_spec_model_settings():
    fake = FakeAnthropic([script_json(user_turns=4)])
    await Claude(fake).make_script("길 묻기", [])
    r = fake.requests[0]
    assert r["model"] == "claude-sonnet-5-5" and r["thinking"] == {"type": "between_tools"}
    assert r["output_config"]["effort"] == "low" and "temperature" not in r

async def test_annotate_retries_then_degrades():
    bad = three_json_with_wrong_stress("I like coffee.")
    fake = FakeAnthropic([bad, bad, bad])
    three = await Claude(fake).annotate("I like coffee.", "카페에서")
    assert len(fake.requests) == 3
    assert check("I like coffee.", three) == []          # 틀린 칠은 지워졌다
    assert "stress" in fake.requests[1]["messages"][-1]["content"]  # 문제를 알려 주고 다시 요청

async def test_api_failure_becomes_unavailable():
    fake = FakeAnthropic([connection_error()])
    with pytest.raises(ClaudeUnavailable):
        await Claude(fake).recommend([])

async def test_refusal_becomes_unavailable():
    fake = FakeAnthropic([refusal_response()])
    with pytest.raises(ClaudeUnavailable):
        await Claude(fake).make_script("길 묻기", [])

async def test_recommend_uses_haiku_and_avoids_recent():
    fake = FakeAnthropic([json.dumps({"request_ko": "카페에서 주문하는 상황으로 연습하고 싶어."})])
    text = await Claude(fake).recommend(["길에서 케이블카 타는 곳을 묻는 상황"])
    assert text.endswith("싶어.") and fake.requests[0]["model"] == "claude-haiku-5-5"
    assert fake.requests[0]["thinking"] == {"type": "disabled"}
    assert "케이블카" in fake.requests[0]["messages"][0]["content"]
```

- [ ] **Step 2: 시험이 실패하는지 본다**

Run: `cd server && uv run pytest tests/test_claude.py -v`
Expected: FAIL(모듈 없음)

- [ ] **Step 3: 구현한다**

- 호출은 `client.messages.create(**SONNET 또는 **HAIKU, max_tokens=..., system=..., messages=..., output_config={..., "format": {"type": "json_schema", "schema": ...}})`. 스키마는 `prompts.py`에 손으로 쓴다(모든 객체에 `additionalProperties: false`와 `required`). 받은 글은 `json.loads` 뒤 pydantic으로 확인한다. `max_tokens`: 대본 4000, 세 줄 4000, 추천 300.
- `stop_reason == "refusal"`, `anthropic.APIConnectionError`, `anthropic.RateLimitError`, `anthropic.APIStatusError`(500 이상), `anthropic.APITimeoutError`는 `ClaudeUnavailable`로 바꾼다. `BadRequestError`는 그대로 올린다(코드 잘못). 클라이언트는 `max_retries=2`, `timeout=60`.
- 대본 검사: 첫 줄과 끝 줄이 라이언, 화자가 번갈아, 사용자 차례 4~6번, 사용자 대사는 14낱말 이하. 어기면 문제를 적어 한 번 다시 요청하고, 그래도 어기면 `ClaudeUnavailable`.
- 지시문(`prompts.py`)에 넣을 것:
  - 대본: 상황의 틀(누가, 어디서, 무엇을), 라이언은 상대역으로 영어로 대화를 이끈다, 사용자 대사는 실제로 쓰는 짧고 자연스러운 말, 마지막 라이언 줄은 짧은 마무리 인사, 틀은 한국어.
  - 세 줄: 가이드의 규칙 1~7을 줄여 옮기고, 가이드의 예 두 줄(`I'd like a cup of coffee.`, `I want to record it.`)을 위 형식으로 보여 준다. 앞뒤 대사를 `context`로 준다. 다시 요청할 때는 `Problem` 목록을 한 줄씩 적는다.
  - 추천: PRD 「문제」의 장면처럼 실제 생활에서 영어로 말해야 하는 상황 하나를, 사용자가 부탁하듯 한국어 한 문장으로(「~ 상황으로 연습하고 싶어.」). 최근 상황 목록과 겹치지 않게.

- [ ] **Step 4: 시험이 통과하는지 본다**

Run: `cd server && uv run pytest -v`
Expected: 모두 통과

- [ ] **Step 5: 시간 재기 스크립트를 쓰고 실제 API로 잰다(비용 승인 뒤)**

`scripts/measure_claude.py`: 지어낸 상황 하나(「길에서 외국인이 지하철역 가는 길을 묻는 상황」)로 `make_script`를 3번, 그 대본의 첫 사용자 대사로 `annotate`를 3번 부른다. Sonnet 5.5와 Haiku 5.5(같은 설정 자리에 Haiku 값을 넣음)로 각각 한다. 모델마다 걸린 시간의 가운데 값, 입력과 출력 토큰, 비용, `annotate`가 검사에 걸린 횟수를 찍는다. 대사 글은 찍지 않는다.

Run: `cd server && uv run python scripts/measure_claude.py`
Expected: 표 하나가 찍힌다. 대본은 한 번에 15초 안쪽이면 그대로 Sonnet으로 간다. 넘으면 Haiku의 값과 검사 통과율을 보고 사용자에게 알린 뒤 정한다.

- [ ] **Step 6: 잰 값을 스펙 「잰 것」에 더한다**

`docs/superpowers/specs/2026-11-05-speaking-practice-design.md` 「잰 것」 밑에 「대본과 세 줄 만드는 시간 (2026-11-05)」 표를 더한다. 스펙 「역할극의 한 차례」 5의 「대본을 만드는 시간은 재지 않았다」 줄을 잰 값으로 고친다.

- [ ] **Step 7: 커밋한다**

메시지: `feat(server): generate roleplay scripts and three-line notes with Claude`(본문에 잰 값). 스펙은 따로 `docs: record script generation timing in speaking practice spec`.

---

### Task 4: 소리(받아쓰기, 목소리, 빠르기)

**Files:**
- Create: `server/je_server/audio.py`, `server/je_server/asr.py`, `server/je_server/tts.py`, `server/je_server/tts_worker.py`, `docs/adr/0009-voice-worker-on-existing-tts.md`
- Modify: `docs/adr/README.md`, `docs/superpowers/specs/2026-11-05-speaking-practice-design.md`(「제약」의 음성 모델 줄)
- Test: `server/tests/test_audio.py`, `server/tests/test_tts.py`, `server/tests/test_asr.py`

**Interfaces:**
- Produces:
  - `audio.to_wav16k(src: Path, dst: Path) -> float`(초), `audio.has_speech(wav: Path) -> bool`, `audio.with_rate(src: Path, rate: float, dst: Path) -> None`(모두 `async`, ffmpeg는 인자 목록으로)
  - `asr.Whisper(exe: str, model: str, port: int)`: `async start()`, `async transcribe(wav: Path, lang: Literal["en","auto"]) -> str`, `async stop()`
  - `tts.audio_key(voice: str, lang: str, text: str) -> str`(sha256 16진수), `tts.Voice(python: str, module: str, audio_dir: Path)`: `async start()`, `async say(text: str, voice: Literal["ryan","jake"], lang: Literal["english","korean"], urgent: bool) -> str`(소리 이름, 있으면 다시 만들지 않음), `async rate_file(key: str, rate: float) -> Path`, `path(key) -> Path`, `async stop()`
  - 작업 프로세스 약속(줄마다 JSON): 띄운 뒤 `{"ready": true}`. 요청 `{"id": int, "text": str, "voice": str, "lang": str, "out": str}`, 답 `{"id": int, "ok": true, "seconds": float}` 또는 `{"id": int, "ok": false, "error": str}`

- [ ] **Step 1: 실패하는 시험을 쓴다**

```python
# server/tests/test_audio.py  (시험 소리는 tmp_path에 ffmpeg lavfi로 만든다. 커밋하지 않는다)
async def test_silence_and_faint_noise_have_no_speech(tmp_path):
    assert not await audio.has_speech(make_wav(tmp_path, "anullsrc=r=16000:cl=mono", 2))
    assert not await audio.has_speech(make_wav(tmp_path, "anoisesrc=r=16000:a=0.01", 2))

async def test_tone_has_speech(tmp_path):
    assert await audio.has_speech(make_wav(tmp_path, "sine=f=220:r=16000", 2))

async def test_too_short_has_no_speech(tmp_path):
    assert not await audio.has_speech(make_wav(tmp_path, "sine=f=220:r=16000", 0.3))

async def test_rate_keeps_length_ratio(tmp_path):
    src = make_m4a(tmp_path, "sine=f=220:r=24000", 2)
    await audio.with_rate(src, 0.8, tmp_path / "slow.m4a")
    assert 2.4 < duration(tmp_path / "slow.m4a") < 2.6
```

```python
# server/tests/test_tts.py  (가짜 작업 프로세스: tests/fake_tts_worker.py가 약속대로 답하고 ffmpeg로 짧은 소리를 쓴다)
async def test_say_caches_by_text(tmp_path):
    v = Voice(sys.executable, FAKE_WORKER, tmp_path); await v.start()
    k1 = await v.say("Hello.", "ryan", "english", urgent=False)
    k2 = await v.say("Hello.", "ryan", "english", urgent=True)
    assert k1 == k2 == audio_key("ryan", "english", "Hello.") and worker_calls(tmp_path) == 1

async def test_urgent_jumps_the_queue(tmp_path):
    v = Voice(sys.executable, FAKE_WORKER, tmp_path); await v.start()
    slow = [asyncio.create_task(v.say(f"line {i}", "ryan", "english", urgent=False)) for i in range(3)]
    fast = asyncio.create_task(v.say("평가", "ryan", "korean", urgent=True))
    await asyncio.gather(*slow, fast)
    assert worker_order(tmp_path).index("평가") <= 1   # 처음 하나가 돌고 있으면 그다음

async def test_worker_error_raises(tmp_path): ...  # 답이 ok=false면 VoiceError
```

`test_asr.py`: `Whisper.transcribe`가 `/inference`에 `language`와 `response_format=json`을 보내고 `text`의 앞뒤 공백과 `[BLANK_AUDIO]` 같은 괄호 표시를 지우는지, httpx의 `MockTransport`로 본다.

- [ ] **Step 2: 시험이 실패하는지 본다**

Run: `cd server && uv run pytest tests/test_audio.py tests/test_tts.py tests/test_asr.py -v`
Expected: FAIL(모듈 없음)

- [ ] **Step 3: 구현한다**

- `has_speech`: 16kHz 모노 wav를 `wave`와 `array("h")`로 읽어 50ms 창마다 RMS를 잰다. 길이 0.4초 미만이거나, 가장 큰 창이 -35 dBFS 미만이면 `False`. 기준값은 Task 6의 시험 녹음으로 맞춘다.
- `Whisper.start`: `whisper-server -m <model> --host 127.0.0.1 --port <port> -nt`를 띄우고 `GET /`가 200이 될 때까지 60초 기다린다. 출력은 버린다(받아쓴 글이 로그에 남지 않게).
- `tts_worker.py`: 맥의 기존 음성 환경 파이썬으로 `-I`를 붙여 띄운다. 인자로 받은 처리 코드 파일을 `importlib.util.spec_from_file_location`으로 불러, 답 읽기 처리와 같은 순서로 만든다: `voice_conf` → `Player(load_model(MODELS[conf["model"]]), conf["model"])` → `lang_chunks(text, lang)` 조각마다 `make`, 목소리 점수가 `VOICE_MIN` 미만이면 `VOICE_RETRIES`번까지 다시 만들어 점수가 높은 쪽, `conf.get("pitch", True)`면 `match_pitch`, `even_pauses` → 이어 붙이고 마지막 쉼을 뗀다 → wav → `afconvert -f m4af -d aac`. 라이브러리가 stdout에 찍는 글이 약속을 깨지 않게, 시작하자마자 `sys.stdout`을 stderr로 돌리고 답은 원래 stdout 파일로만 쓴다. 띄운 뒤 영어 한 문장을 한 번 만들어 데운다.
- `Voice`: 작업 프로세스 하나에 `asyncio.PriorityQueue`(급한 것 0, 미리 만드는 것 1, 같은 우선순위는 들어온 순서). 같은 소리 이름을 만드는 중이면 그 작업을 함께 기다린다. 작업 프로세스가 죽으면 다시 띄운다.
- `rate_file`: `audio/<key>@<rate>.m4a`가 없으면 `with_rate`로 만든다.

- [ ] **Step 4: 시험이 통과하는지 본다**

Run: `cd server && uv run pytest -v`
Expected: 모두 통과

- [ ] **Step 5: 실제 도구로 한 번 확인한다(맥 안에서만, 커밋하지 않는 임시 폴더)**

`server/.env`에 비공개 메모의 음성 환경과 whisper 모델 경로를 넣는다. 짧은 확인 스크립트를 scratchpad에 두고 돌린다: `Voice.say("Where is the subway station?", "ryan", "english")`, `Voice.say("잘했어요. 다음으로 넘어가요.", "ryan", "korean")`, `Voice.say("카페에서 주문하는 상황으로 연습하고 싶어.", "jake", "korean")`를 만들고 `afplay`로 듣는다. 맥 `say`로 만든 영어 문장을 `Whisper.transcribe(..., "en")`로 받아쓴다.
Expected: 세 소리가 나고, 받아쓴 글이 문장과 같다. 걸린 시간을 적어 둔다(devlog에 쓴다).

- [ ] **Step 6: ADR-0009를 쓰고 스펙 「제약」을 고친다**

ADR-0009 「음성 합성은 맥의 기존 음성 환경에서 따로 도는 작업 프로세스로 부른다」(상태: 채택, 사용자가 계획 검토에서 받아들인 경우). 배경(답 읽기 데몬에는 파일로 만드는 명령이 없고 전역 파일은 고치지 않는다), 검토한 안(데몬에 부탁, 서버 환경에 음성 라이브러리를 새로 깔기, 작업 프로세스), 판단, 결정, 영향(데몬이 떠 있으면 모델이 둘 올라간다. 처리 코드가 바뀌면 서버도 따라 바뀐다. 경로는 `server/.env`). 경로와 맥 사양은 쓰지 않는다. 스펙 「제약」의 「음성 모델을 메모리에 두 번 올리지 않는다」 항목을 ADR-0009를 가리키게 고친다.

- [ ] **Step 7: 커밋한다**

`feat(server): add whisper transcription and voice worker on the existing TTS`, `docs(adr): add ADR-0009 voice worker on the existing TTS setup`, 스펙 고침은 `docs: point speaking practice spec voice constraint to ADR-0009`.

---

### Task 5: 역할극 만들기, 미리 준비, 앱이 부르는 경로

**Files:**
- Create: `server/je_server/store.py`, `server/je_server/engine.py`, `server/je_server/phrases.py`, `contract/roleplay.json`, `contract/line-user.json`
- Modify: `server/je_server/models.py`, `server/je_server/app.py`
- Test: `server/tests/test_store.py`, `server/tests/test_engine.py`, `server/tests/test_api.py`, `server/tests/test_contract.py`

**Interfaces:**
- Consumes: `Claude`/`FakeClaude`(Task 3), `Voice`, `Whisper`, `audio`(Task 4), `threeline`(Task 2)
- Produces:
  - `models.py`에 더함: `ScriptLine(idx: int, speaker: Speaker, text: str, kind: Literal["script","reply"] = "script", three: ThreeLine | None = None, audio: str | None = None)`, `Issue(target: str, heard: str, sound: tuple[str, str], explain: str)`, `Attempt(n: int, mode: Literal["turn","retry"], heard: str, followed: bool, issues: list[Issue], say_ko: str, audio: list[str], timings: dict[str, float])`, `Roleplay(id: str, created: str, situation: str, frame: Frame, lines: list[ScriptLine], attempts: dict[int, list[Attempt]] = {}, pos: int = 0)`, `Said(text: str, audio: str)`
  - `Store(root: Path)`: `new_id() -> str`, `save(rp) -> None`(임시 파일에 쓰고 `os.replace`), `load(rp_id) -> Roleplay`(없으면 `KeyError`), `recent_situations(n: int = 10) -> list[str]`, `rec_path(rp_id, idx, n) -> Path`, `audio_dir: Path`
  - `phrases.PHRASES: dict[str, str]`: `greeting`, `ask_mode`, `ask_situation`, `ask_recommend`, `closing_retry`, `closing_clean`, `no_speech`, `retry_offscript`, `claude_down`, `too_long`. 서버가 시작할 때 모두 라이언 한국어로 미리 만든다.
  - `Engine(store, claude, voice, whisper)`: `async create(situation: str) -> Roleplay`, `async line(rp_id: str, idx: int) -> ScriptLine`, `async three(rp_id: str, idx: int) -> ThreeLine`, `async recommend() -> Said`, `async transcribe(body: bytes) -> str`, `said(name: str) -> Said`
  - `Services(engine: Engine, voice: Voice, whisper: Whisper)`. `create_app(settings, services)`에 가짜를 넣어 시험한다.

- [ ] **Step 1: 실패하는 시험을 쓴다**

```python
# server/tests/test_engine.py  (FakeClaude, FakeVoice는 소리 이름만 돌려준다)
async def test_create_then_lines_are_prepared(engine):
    rp = await engine.create("길 묻기")
    user_idx = next(l.idx for l in rp.lines if l.speaker == "user")
    line = await engine.line(rp.id, user_idx)
    assert line.three is not None and line.audio is not None
    ryan = await engine.line(rp.id, 0)
    assert ryan.audio is not None and ryan.three is None

async def test_prep_survives_restart(engine_factory):
    e1 = engine_factory(); rp = await e1.create("길 묻기")
    e2 = engine_factory()                     # 같은 데이터 폴더, 준비 작업 없음
    assert (await e2.line(rp.id, 1)).three is not None

async def test_claude_down_on_create_leaves_no_roleplay(engine, fake_claude):
    fake_claude.fail_next = True
    with pytest.raises(ClaudeUnavailable):
        await engine.create("길 묻기")
    assert engine.store.recent_situations() == []

async def test_ryan_three_on_demand(engine):
    rp = await engine.create("길 묻기")
    assert (await engine.three(rp.id, 0)).words
```

```python
# server/tests/test_api.py
def test_unknown_roleplay_is_404(client): assert client.get("/roleplays/000000000000/lines/0").status_code == 404
def test_bad_ids_rejected(client):
    assert client.get("/roleplays/..%2Fx/lines/0").status_code in (404, 422)
    assert client.get("/audio/../../etc").status_code in (404, 422)
    assert client.get("/assets/secret.png").status_code == 404
    assert client.get("/audio/" + "a" * 64 + "?rate=2.0").status_code == 422
def test_home_lists_fixed_lines(client):
    j = client.get("/home").json()
    assert set(j["lines"]) == {"greeting", "ask_mode", "ask_situation", "ask_recommend"}
def test_create_roleplay_claude_down_is_503(client, fake_claude):
    fake_claude.fail_next = True
    r = client.post("/roleplays", json={"situation": "길 묻기"})
    assert r.status_code == 503 and r.json()["code"] == "claude_unavailable" and r.json()["say"]["audio"]
def test_situation_length_limited(client):
    assert client.post("/roleplays", json={"situation": "가" * 301}).status_code == 422
def test_upload_size_limited(client):
    assert client.post("/transcribe", content=b"0" * (5 * 1024 * 1024 + 1)).status_code == 413
```

`test_contract.py`: `contract/roleplay.json`을 `Roleplay.model_validate`로, `contract/line-user.json`을 `ScriptLine`으로 읽고, `model_dump(mode="json")`이 원래 JSON과 같은지 본다.

- [ ] **Step 2: 시험이 실패하는지 본다**

Run: `cd server && uv run pytest tests/test_engine.py tests/test_api.py tests/test_contract.py -v`
Expected: FAIL

- [ ] **Step 3: 구현한다**

- `create`: `make_script` → `Roleplay` 저장 → 줄마다 준비 작업을 띄운다. 사용자 줄은 `annotate`(동시에 3개까지) 뒤 `voice.say(text, "ryan", "english", urgent=False)`, 라이언 줄은 `voice.say`만. 끝날 때마다 역할극마다 하나인 `asyncio.Lock` 안에서 읽고 고쳐 저장한다.
- `line`: 준비 작업이 없으면(다시 띄운 뒤) 빠진 것만 다시 만든다. 기다리는 시간은 120초까지.
- `annotate`의 `context`는 그 줄 앞뒤의 대사 두 줄과 틀의 장소.
- 경로: 몸으로 받는 녹음은 `request.stream()`으로 읽으며 5MB를 넘으면 413. `ClaudeUnavailable`은 503과 `say=claude_down`.
- `/audio`는 `FileResponse(media_type="audio/mp4")`. 서버가 시작할 때 `whisper.start()`, `voice.start()`, 고정 문구 미리 만들기를 하고, 끝날 때 둘을 멈춘다(FastAPI lifespan).
- `contract/` 예시는 지어낸 문장으로 손으로 쓴다(세 줄 예는 위 「세 줄 형식」).

- [ ] **Step 4: 시험이 통과하는지 본다**

Run: `cd server && uv run pytest -v`
Expected: 모두 통과

- [ ] **Step 5: 커밋한다**

메시지: `feat(server): create roleplays and prepare lines in the background`

---

### Task 6: 따라 말한 차례 평가

**Files:**
- Create: `server/je_server/compare.py`, `server/je_server/sounds.py`, `server/je_server/data/sounds.json`, `server/je_server/sentences.py`, `server/scripts/check_false_flags.py`, `contract/attempt-events.ndjson`
- Modify: `server/je_server/claude.py`, `server/je_server/prompts.py`, `server/je_server/engine.py`, `server/je_server/app.py`
- Test: `server/tests/test_compare.py`, `server/tests/test_sentences.py`, `server/tests/test_attempt.py`

**Interfaces:**
- Consumes: `cmu`(Task 2), `Engine`, `Store`, `Attempt`, `Issue`(Task 5), `Whisper`, `Voice`, `audio.has_speech`(Task 4)
- Produces:
  - `compare.words(text) -> list[str]`, `compare.similarity(target: str, heard: str) -> float`(낱말 목록의 `difflib.SequenceMatcher.ratio()`), `compare.word_pairs(target, heard) -> list[tuple[str, str]]`(1:1로 바뀐 낱말), `compare.sound_pairs(target_word, heard_word) -> list[tuple[str, str]]`(강세 숫자를 뗀 음소의 1:1 바뀜, 두 낱말의 사전 발음 조합 중 바뀐 것이 가장 적은 것), `compare.find_issues(target, heard, limit: int) -> list[Issue]`(목록에 있는 소리만), `compare.praise_candidates(target, heard) -> list[str]`, `FOLLOW_MIN = 0.6`
  - `sounds.SOUNDS: list[Sound]`(`a: str`, `b: str`, `name: str`, `explain: str`), `sounds.find(a, b) -> Sound | None`(순서 상관없음)
  - `sentences.SentenceBuffer`: `feed(delta: str) -> list[str]`, `flush() -> list[str]`
  - `Claude.feedback(line: str, heard: str, praise: list[str], issues: list[Issue]) -> AsyncIterator[str]`(Haiku, 흘러오는 글 조각)
  - `Engine.attempt(rp_id, idx, body: bytes, mode) -> AsyncIterator[dict]`(위 「차례 이벤트」)

- [ ] **Step 1: 실패하는 시험을 쓴다**

`conftest.py`에 더하는 fixture: `engine_with_rp`(가짜 Claude, 가짜 목소리, 가짜 받아쓰기로 역할극 하나를 만들어 `(engine, rp_id, user_idx)`를 돌려준다. 시험마다 첫 줄에서 풀어 쓴다), `fake_whisper`(`text`를 돌려주고 `calls`를 센다, 기본 `text`는 그 줄의 대사), `fake_claude`, `speech_bytes`(ffmpeg `sine`으로 tmp_path에 만든 2초 m4a), `silent_bytes`(ffmpeg `anullsrc` 2초 m4a). Task 7도 같은 fixture를 쓴다.

```python
# server/tests/test_compare.py
def test_running_heard_as_learning_is_r_l():
    issues = find_issues("I'm running to the station.", "I'm learning to the station", limit=2)
    assert [(i.target, i.heard, set(i.sound)) for i in issues] == [("running", "learning", {"R", "L"})]
    assert "혀" in issues[0].explain

def test_unlisted_sound_change_is_not_flagged():
    assert find_issues("I want the red one.", "I want the bed one.", limit=2) == []   # R→B는 목록에 없다

def test_limit_caps_issues():
    assert len(find_issues("Right, the river is very far.", "Light, the liver is belly par.", limit=2)) == 2

def test_same_words_no_issues_and_full_similarity():
    assert find_issues("Turn left here.", "turn left here", limit=2) == []
    assert similarity("Turn left here.", "turn left here") == 1.0

def test_different_answer_is_not_followed():
    assert similarity("It's right over there.", "Sorry, I don't know this area.") < FOLLOW_MIN

def test_one_misheard_word_still_followed():
    assert similarity("I'm running to the station.", "I'm learning to the station") >= FOLLOW_MIN

def test_unknown_word_has_no_sound_pairs():
    assert sound_pairs("namsan", "namsang") == []
```

`test_sentences.py`: `feed("잘했어요. 다")` → `["잘했어요."]`, 이어서 `feed("음은 R이에요!")` → `["다음은 R이에요!"]`, `flush()` → 남은 글.

```python
# server/tests/test_attempt.py  (FakeWhisper는 정해 둔 글을, has_speech는 시험 녹음 크기로)
async def test_followed_attempt_streams_text_then_audio(engine_with_rp, speech_bytes):
    ev = [e async for e in engine.attempt(rp_id, user_idx, speech_bytes, "turn")]
    kinds = [e["type"] for e in ev]
    assert kinds[0] == "heard" and ev[0]["followed"] and "text" in kinds and "audio" in kinds
    assert kinds[-1] == "done" and ev[-1]["next"] == user_idx + 1
    saved = engine.store.load(rp_id).attempts[user_idx][0]
    assert saved.say_ko and saved.timings["first_text"] > 0 and saved.audio

async def test_silent_recording_says_no_speech_and_keeps_script(engine_with_rp, silent_bytes):
    before = engine.store.load(rp_id).lines
    ev = [e async for e in engine.attempt(rp_id, user_idx, silent_bytes, "turn")]
    assert ev[-1] == {"type": "error", "code": "no_speech", "say": engine.said("no_speech").model_dump()}
    assert engine.store.load(rp_id).lines == before and fake_whisper.calls == 0

async def test_feedback_prompt_gets_only_text(engine_with_rp, speech_bytes, fake_claude):
    [e async for e in engine.attempt(rp_id, user_idx, speech_bytes, "turn")]
    sent = json.dumps(fake_claude.feedback_calls[0], ensure_ascii=False)
    assert "rec" not in sent and ".m4a" not in sent and str(engine.store.root) not in sent

async def test_claude_down_during_feedback_still_ends(engine_with_rp, speech_bytes, fake_claude):
    fake_claude.fail_next = True
    ev = [e async for e in engine.attempt(rp_id, user_idx, speech_bytes, "turn")]
    assert ev[-1]["type"] == "error" and ev[-1]["code"] == "claude_unavailable"

async def test_recording_is_kept_on_mac(engine_with_rp, speech_bytes):
    [e async for e in engine.attempt(rp_id, user_idx, speech_bytes, "turn")]
    assert engine.store.rec_path(rp_id, user_idx, 1).exists()
```

- [ ] **Step 2: 시험이 실패하는지 본다**

Run: `cd server && uv run pytest tests/test_compare.py tests/test_sentences.py tests/test_attempt.py -v`
Expected: FAIL

- [ ] **Step 3: 구현한다**

- `sounds.json`: 소리 여섯 쌍(R-L, F-P, V-B, TH-S, DH-D, Z-JH)마다 `name`(「R과 L」)과 `explain` 한두 문장. 몸으로 따라 할 수 있는 한 가지를 헷갈린 소리와 맞대어 쓴다. R-L은 스펙의 문장(「L은 혀끝이 윗잇몸에 닿지만, R은 혀가 어디에도 닿지 않게 하고 입술을 살짝 동그랗게 모은다.」)을 쓴다. 나머지는 초안이고 PR에서 사람이 검토한다.
- `praise_candidates`: 목록의 소리가 든 낱말을 맞게 받아쓴 것(「right의 R」), 다르게 들린 낱말이 없으면 「문장 전체를 또렷하게」, 많이 맞으면 「대사를 거의 다 맞게」. Claude는 이 가운데 하나만 고른다.
- `attempt`(따라 말한 것): 녹음을 `rec_path`에 쓴다 → 임시 wav(끝나면 지움) → 60초 넘으면 `too_long` → `has_speech`가 아니면 `no_speech` → `transcribe(..., "en")` → 빈 글이면 `no_speech` → `followed = similarity >= FOLLOW_MIN` → `heard` 이벤트. 따라 말했으면 `find_issues(limit=2)`, `praise_candidates` → `Claude.feedback`을 흘려 `text` 이벤트로 내보내고, `SentenceBuffer`로 끊은 문장마다 `voice.say(sentence, "ryan", "korean", urgent=True)`를 차례로 기다려 `audio` 이벤트로 내보낸다. 글과 소리는 한 `asyncio.Queue`로 합쳐 내보낸다. 끝나면 `Attempt`를 저장하고 `pos`를 고친다. `timings`: `transcribed`, `first_text`, `first_audio`, `total`(녹음을 받은 때부터 초). 로그에는 이 숫자만 찍는다.
- `mode=retry`이고 따라 말하지 않았으면 `retry_offscript` 고정 문구로 답하고 `next`는 같은 줄.
- `Claude.feedback` 지시문: 라이언, 존댓말(해요체) 예시 두세 개, 순서(잘한 점 하나 → 고칠 것 한두 가지 → 소리 내는 법), 소리 내는 법은 받은 `explain`만 다듬어 쓰고 새로 지어내지 않는다, 받은 짚을 것 말고 다른 것을 짚지 않는다, 강세는 말하지 않는다, 짚을 것이 없으면 잘한 점을 말하고 다음으로 넘어가자고 한다, 서너 문장 이내. `max_tokens=800`.
- 경로: `POST /roleplays/{id}/lines/{idx}/attempts`는 `StreamingResponse(media_type="application/x-ndjson")`.

- [ ] **Step 4: 시험이 통과하는지 본다**

Run: `cd server && uv run pytest -v`
Expected: 모두 통과

- [ ] **Step 5: 시험 녹음으로 헛짚기를 센다(맥 안에서만)**

`scripts/check_false_flags.py <녹음 파일> <대본 파일>`: 녹음을 받아쓰고(영어, 힌트 없음), 대본 전체와 맞대어 `find_issues`가 짚은 수, `has_speech` 결과를 찍는다. 받아쓴 글은 찍지 않는다. 대본 파일은 가이드의 2차 시험 문장 8줄을 scratchpad에 적어 쓴다. 녹음은 원래 폴더의 비공개 녹음 폴더에 있는 2차 시험 녹음이다(파일 이름은 비공개 메모 참고). Anthropic에는 보내지 않는다.

Run: `cd server && uv run python scripts/check_false_flags.py <비공개 녹음> <scratchpad 대본>`
Expected: 짚은 수가 0이거나 아주 적다. 짚었으면 무엇 때문인지(낱말 쌍과 소리 쌍만) 보고, 헛짚기면 사용자에게 알린다. `has_speech`가 `True`가 아니면 -35 dBFS 기준을 고친다.

- [ ] **Step 6: 커밋한다**

메시지: `feat(server): evaluate followed lines with dictionary sound checks`(본문에 헛짚기 센 결과, 숫자만).

---

### Task 7: 다르게 말했을 때, 다시 해 보기, 마무리

**Files:**
- Modify: `server/je_server/claude.py`, `server/je_server/prompts.py`, `server/je_server/engine.py`, `server/je_server/app.py`
- Test: `server/tests/test_offscript.py`, `server/tests/test_summary.py`

**Interfaces:**
- Consumes: `compare.sound_pairs`, `sounds.find`(Task 6), `Engine`(Task 5, 6)
- Produces:
  - `models.Offscript(point_kind: Literal["none","expression","pronunciation"], point_ko: str, meant: str, heard_word: str, reply_en: str)`
  - `Claude.offscript(frame: Frame, history: Draft, expected: str, heard: str) -> Offscript`(Sonnet), `Claude.continue_script(frame: Frame, history: Draft, user_turns: int) -> Draft`(Sonnet)
  - `Engine.summary(rp_id) -> dict`(`{"say": Said, "retry": list[int]}`)

- [ ] **Step 1: 실패하는 시험을 쓴다**

```python
# server/tests/test_offscript.py
async def test_offscript_reply_then_new_script(engine_with_rp, fake_whisper, fake_claude):
    fake_whisper.text = "Sorry, I don't know this area."
    ev = [e async for e in engine.attempt(rp_id, user_idx, speech_bytes, "turn")]
    reply = next(e for e in ev if e["type"] == "reply")["line"]
    assert reply["speaker"] == "ryan" and reply["kind"] == "reply" and reply["audio"]
    assert ev[-1]["next"] == reply["idx"] + 1
    rp = engine.store.load(rp_id)
    nxt = await engine.line(rp_id, reply["idx"] + 1)          # 새 대본의 다음 사용자 줄
    assert nxt.speaker == "user" and nxt.three and nxt.audio
    assert rp.lines[user_idx].text == "It's right over there."   # 지나간 줄은 그대로

async def test_pronunciation_guess_needs_listed_sound(engine_with_rp, fake_claude):
    fake_claude.offscript_out = Offscript(point_kind="pronunciation", point_ko="…", meant="bed", heard_word="red", reply_en="OK.")
    ev = [e async for e in engine.attempt(rp_id, user_idx, speech_bytes, "turn")]
    assert not any(e["type"] == "text" for e in ev)          # R→B는 목록에 없어 짚지 않는다

async def test_pronunciation_guess_uses_list_explanation(engine_with_rp, fake_claude):
    fake_claude.offscript_out = Offscript(point_kind="pronunciation", point_ko="지어낸 설명", meant="running", heard_word="learning", reply_en="Oh, you're running late?")
    ev = [e async for e in engine.attempt(rp_id, user_idx, speech_bytes, "turn")]
    said = "".join(e["delta"] for e in ev if e["type"] == "text")
    assert sounds.find("R", "L").explain in said and "지어낸 설명" not in said

async def test_retry_mode_never_changes_script(engine_with_rp, fake_whisper):
    fake_whisper.text = "Something totally different here."
    before = engine.store.load(rp_id).lines
    ev = [e async for e in engine.attempt(rp_id, user_idx, speech_bytes, "retry")]
    assert ev[-1]["next"] == user_idx and engine.store.load(rp_id).lines == before
```

`test_summary.py`: 짚을 것이 남은 사용자 줄만 `retry`에 들어간다(같은 줄을 다시 해서 짚을 것이 없어졌으면 빠진다). 남은 것이 없으면 `say`가 `closing_clean`이다.

- [ ] **Step 2: 시험이 실패하는지 본다**

Run: `cd server && uv run pytest tests/test_offscript.py tests/test_summary.py -v`
Expected: FAIL

- [ ] **Step 3: 구현한다**

- 다르게 말했을 때(`mode=turn`, `followed`가 아님): `Claude.offscript`. `point_kind`가 `pronunciation`이면 `sound_pairs(meant, heard_word)` 가운데 목록에 있는 쌍이 있을 때만 「{meant}, {heard_word}처럼 들렸어요. {explain}」를 말하고, 없으면 짚지 않는다. `expression`이면 `point_ko`를 그대로 쓴다. 짚을 말은 `text`, `audio`(라이언 한국어, 급함) 이벤트로 먼저 낸다. 이어서 `reply_en`을 라이언 줄(`kind="reply"`)로 지금 줄 바로 뒤에 넣고, 그 뒤 대본을 지운다. `voice.say(reply_en, "ryan", "english", urgent=True)` 뒤 `reply` 이벤트, `done`(`next`는 대답 줄 다음).
- 남은 대본: 대답을 저장한 뒤 뒤에서 `continue_script`(사용자 차례 수는 지운 대본에 남아 있던 수, 적어도 1)를 부르고, 받은 줄을 붙여 저장하고 준비 작업을 띄운다. 다음 사용자 줄의 준비를 먼저 한다. `line()`은 이 작업이 끝날 때까지 기다린다. 실패하면 마무리 라이언 줄 하나(「Thanks for your help!」 같은 고정 영어 문장)를 붙여 역할극을 끝낸다.
- `history`: 지나간 줄은 대사 글, 사용자가 다르게 말한 줄은 받아쓴 글.
- 지시문: 대답은 사용자가 실제로 한 말에 맞춘 짧은 영어 한두 문장, 짚을 것은 한 가지만 한국어 존댓말로, 확실하지 않으면 `none`, 발음 짐작은 앞뒤 말로 보아 하려던 낱말이 분명할 때만.
- `summary`: 사용자 줄마다 마지막 차례의 `issues`가 남아 있으면 `retry`에 넣는다. `say`는 `closing_retry` 또는 `closing_clean`.

- [ ] **Step 4: 시험이 통과하는지 본다**

Run: `cd server && uv run pytest -v`
Expected: 모두 통과

- [ ] **Step 5: 커밋한다**

메시지: `feat(server): answer off-script lines and rebuild the rest of the script`

---

### Task 8: 앱 뼈대, 서버 연결, API 모양 맞추기

**Files:**
- Create: `app/`(create-expo-app), `app/.env.example`, `app/src/config.ts`, `app/src/api/types.ts`, `app/src/api/ndjson.ts`, `app/src/api/client.ts`
- Modify: `app/app.json`, `app/package.json`(test 스크립트, jest 설정)
- Test: `app/src/api/ndjson.test.ts`, `app/src/api/client.test.ts`, `app/src/api/contract.test.ts`

**Interfaces:**
- Consumes: 서버 API와 `contract/`(Task 5, 6)
- Produces:
  - `types.ts`: `Mark`, `Syllable`, `Word`, `ThreeLine`, `ScriptLine`, `Roleplay`, `Said`, `Home`, `Summary`, `AttemptEvent`(서버 모델과 같은 이름과 키)
  - `class NdjsonSplitter { push(chunk: string): unknown[]; flush(): unknown[] }`
  - `class ApiError extends Error { code: "offline" | "claude_unavailable" | "no_speech" | "too_long" | "not_found" | "unknown"; say?: Said }`
  - `api.getHome(): Promise<Home>`, `api.recommend(): Promise<Said>`, `api.transcribe(fileUri: string): Promise<string>`, `api.createRoleplay(situation: string): Promise<Roleplay>`, `api.getLine(id: string, idx: number): Promise<ScriptLine>`, `api.getThree(id, idx): Promise<ThreeLine>`, `api.attempt(id, idx, fileUri, mode: "turn" | "retry", onEvent: (e: AttemptEvent) => void): Promise<void>`, `api.summary(id): Promise<Summary>`, `api.audioSource(key: string, rate?: 0.6 | 0.8 | 1): { uri: string; headers: Record<string, string> }`, `api.imageSource(path: string)`(같은 꼴)

- [ ] **Step 1: 앱을 만든다**

Run: `npx create-expo-app@latest app --template blank-typescript` 그리고 `cd app && npx expo install expo-audio expo-file-system expo-build-properties && npx expo install -- --save-dev jest-expo jest @types/jest`
Expected: `app/`에 Expo SDK 58 프로젝트. 만들어진 `.gitignore`는 두고, 저장소 맨 위 `.gitignore`와 겹치는 것은 그대로 둔다.

- [ ] **Step 2: 설정을 쓴다**

`app.json`: `name` `Jake English`, `slug` `jake-english`, `android.package`와 `ios.bundleIdentifier` `dev.jakeso.english`, `android.permissions` `["RECORD_AUDIO"]`, plugins `["expo-audio", {"microphonePermission": "라이언에게 말을 들려주려고 마이크를 씁니다."}]`, `["expo-build-properties", {"android": {"usesCleartextTraffic": true}}]`. `.env.example`: `EXPO_PUBLIC_SERVER_URL=http://127.0.0.1:8787`, `EXPO_PUBLIC_SERVER_TOKEN=`. `package.json`: `"test": "jest"`, `"jest": {"preset": "jest-expo"}`.

- [ ] **Step 3: 실패하는 시험을 쓴다**

```ts
// app/src/api/ndjson.test.ts
test("splits lines across chunks", () => {
  const s = new NdjsonSplitter();
  expect(s.push('{"type":"heard","te')).toEqual([]);
  expect(s.push('xt":"hi","followed":true}\n{"type":"done"')).toEqual([{ type: "heard", text: "hi", followed: true }]);
  expect(s.push(',"next":2,"issues":0}\n')).toEqual([{ type: "done", next: 2, issues: 0 }]);
  expect(s.flush()).toEqual([]);
});
test("ignores blank lines", () => {
  expect(new NdjsonSplitter().push("\n\n")).toEqual([]);
});
```

```ts
// app/src/api/client.test.ts  (global fetch를 jest.fn으로 바꾼다)
test("sends bearer token", async () => { /* getHome → headers.Authorization === `Bearer ${token}` */ });
test("503 becomes claude_unavailable with say", async () => { /* code, say.audio */ });
test("network failure becomes offline", async () => { /* fetch reject → ApiError code offline */ });
test("timeout becomes offline", async () => { /* jest fake timers, 30s → code offline */ });
test("audioSource adds rate and token header", () => {
  expect(api.audioSource("a".repeat(64), 0.8)).toEqual({ uri: `${URL}/audio/${"a".repeat(64)}?rate=0.8`, headers: { Authorization: `Bearer ${TOKEN}` } });
});
```

`contract.test.ts`: `contract/roleplay.json`을 `Roleplay`로, `contract/line-user.json`을 `ScriptLine`으로 들여와 몇 키를 확인하고, `contract/attempt-events.ndjson`을 `NdjsonSplitter`로 읽어 모든 이벤트의 `type`이 `AttemptEvent`의 값 안에 있는지 본다.

- [ ] **Step 4: 시험이 실패하는지 본다**

Run: `cd app && npm test`
Expected: FAIL(모듈 없음)

- [ ] **Step 5: 구현한다**

- `client.ts`는 `expo/fetch`의 `fetch`를 쓴다(응답 몸을 흘려 읽을 수 있다). 녹음은 `expo-file-system`의 `File(uri).bytes()`로 읽어 `Content-Type: audio/mp4`로 보낸다. 시간 제한: 보통 30초, `createRoleplay`와 `getLine` 120초, `attempt`는 이벤트 사이 30초. 넘으면 `AbortController`로 끊고 `offline`.
- `config.ts`: `process.env.EXPO_PUBLIC_SERVER_URL`, `EXPO_PUBLIC_SERVER_TOKEN`. 비어 있으면 첫 화면이 「서버 설정이 없어요」를 보여 준다.

- [ ] **Step 6: 시험과 타입 검사가 통과하는지 본다**

Run: `cd app && npm test && npx tsc --noEmit`
Expected: 모두 통과, 타입 오류 없음

- [ ] **Step 7: 커밋한다**

`/usr/bin/git add app/` 대신 만든 파일을 지정한다(`app/package.json`, `app/package-lock.json`, `app/app.json`, `app/tsconfig.json`, `app/App.tsx`, `app/index.ts`, `app/assets/`(템플릿 아이콘), `app/.gitignore`, `app/.env.example`, `app/src/`, `contract/`). 메시지: `feat(app): scaffold Expo app with authenticated server client`

---

### Task 9: 앱 화면(첫 화면, 상황 정하기, 역할극, 마무리)

**Files:**
- Create: `app/src/ui/threeLineSegments.ts`, `app/src/ui/ThreeLine.tsx`, `app/src/ui/Button.tsx`, `app/src/audio/player.ts`, `app/src/audio/useRecorder.ts`, `app/src/flow/state.ts`, `app/src/screens/HomeScreen.tsx`, `app/src/screens/SituationScreen.tsx`, `app/src/screens/RoleplayScreen.tsx`, `app/src/screens/EndScreen.tsx`
- Modify: `app/App.tsx`
- Test: `app/src/ui/threeLineSegments.test.ts`, `app/src/flow/state.test.ts`

**Interfaces:**
- Consumes: `api`, 타입(Task 8)
- Produces:
  - `type Seg = { text: string; style: "strong" | "weak" | "plain" }`, `englishSegments(t: ThreeLine): Seg[][]`(낱말마다), `koreanSegments(t: ThreeLine): Seg[][]`(이어 읽기로 붙은 낱말은 한 묶음), `readingSegments(reading: string): Seg[]`(`[[x]]` → `「x」` plain)
  - `class SoundQueue { enqueue(src: AudioSource): void; clear(): void; onIdle(cb: () => void): void }`(expo-audio `createAudioPlayer`)
  - `useRecorder(): { start(): Promise<void>; stop(): Promise<string /* uri */>; recording: boolean }`(60초에 저절로 멈춤)
  - `flow/state.ts`: `State`, `Action`, `reduce(s: State, a: Action): State`. 화면: `home` → `situation` → `recommendAsk` → `preparing` → `roleplay` → `end`. 역할극 단계: `loading` | `ryan` | `ready` | `recording` | `evaluating` | `evaluated` | `error`.

- [ ] **Step 1: 실패하는 시험을 쓴다**

```ts
// app/src/ui/threeLineSegments.test.ts  (contract/line-user.json의 세 줄)
test("english marks strong and weak syllables", () => {
  expect(englishSegments(three).at(-1)).toEqual([{ text: "cof", style: "strong" }, { text: "fee.", style: "weak" }]);
});
test("korean highlights only hi char", () => {
  const w = { syl: [{ en: "sta", ko: "스테이", m: "s", hi: "테" }, { en: "tion", ko: "션", m: "n", hi: "" }], emph: false, link: false };
  expect(koreanSegments({ words: [w], reading: "" })[0]).toEqual([
    { text: "스", style: "plain" }, { text: "테", style: "strong" }, { text: "이", style: "plain" }, { text: "션", style: "plain" }]);
});
test("linked words share one korean group", () => { /* cup(link) of → 한 묶음 "커" + "퍼"(weak) */ });
test("reading refs show as corner brackets", () => {
  expect(readingSegments("앞을 세게, [[카-피]].")).toEqual([{ text: "앞을 세게, 「카-피」.", style: "plain" }]);
});
```

```ts
// app/src/flow/state.test.ts
test("record is ignored while evaluating", () => {
  const s = { ...roleplayState, phase: "evaluating" } as State;
  expect(reduce(s, { type: "recordStart" })).toBe(s);
});
test("next is ignored until evaluation is done", () => {
  const s = { ...roleplayState, phase: "evaluating" } as State;
  expect(reduce(s, { type: "next" })).toBe(s);
});
test("done event moves to next line index from server", () => {
  const s = reduce({ ...roleplayState, phase: "evaluating" }, { type: "event", e: { type: "done", next: 5, issues: 1 } });
  expect(s.phase).toBe("evaluated"); expect(s.nextIdx).toBe(5);
});
test("no_speech returns to ready", () => { /* error code no_speech → phase ready, message set */ });
test("next past last line goes to end", () => { /* nextIdx === lines.length → screen end */ });
test("retry from end comes back to end", () => { /* retry idx → roleplay mode retry → done → end */ });
test("offline error keeps line and offers retry", () => { /* phase error, retryable true */ });
```

- [ ] **Step 2: 시험이 실패하는지 본다**

Run: `cd app && npm test`
Expected: FAIL

- [ ] **Step 3: 구현한다**

- **첫 화면:** `getHome` → 라이언 정면 그림, 인사와 질문 글, 두 소리를 차례로 틀고 끝나면 듣는 얼굴로 바꾼다. 버튼은 「상황 역할극」 하나.
- **상황 정하기:** `ask_situation`을 튼다. 글 입력, 🎤(녹음 → `transcribe` → 입력칸에 채움), 「추천해 줘」. 입력이 `/모르겠|추천/`에 맞거나 「추천해 줘」를 누르면 `ask_recommend`를 틀고 「좋아요」/「아니요」. 「좋아요」면 `recommend` → 제이크 소리를 틀고 글을 보여 준 뒤 그 글로 `createRoleplay`. 「시작」을 누르면 입력한 글로 `createRoleplay`. 그동안 「라이언이 대본을 만들고 있어요」.
- **역할극:** 위쪽에 틀(제목, 내 역할, 라이언 역할). 지나간 줄을 말풍선으로 쌓는다.
  - 라이언 줄: `getLine` → 영어 글, 소리를 튼다. 글을 누르면 `getThree`로 세 줄을 펼친다. 소리가 끝나면 다음 줄로.
  - 사용자 줄: `getLine` → 세 줄 카드, 본보기를 한 번 튼다. 「다시 듣기」, 빠르기 0.6/0.8/1(누른 빠르기로 다음 재생), 녹음 버튼(누르면 시작, 다시 누르면 멈춤). 멈추면 `attempt`. `heard`는 「들린 말」로 작게, `text`는 이어 붙여 보여 주고, `audio`는 `SoundQueue`에 넣는다. `reply`는 라이언 말풍선으로 더하고 소리를 큐에 넣는다. 끝나면 「다시 해 보기」(`mode=retry`)와 「다음」.
  - 오류: `no_speech`, `too_long`은 고정 문구를 틀고 같은 줄에 머문다. `claude_unavailable`은 `say`를 틀고 「다시 시도」. `offline`은 「맥에 연결할 수 없어요」와 「다시 시도」.
- **마무리:** `summary` → `say`를 튼다. `retry` 줄마다 버튼(누르면 그 줄을 `mode=retry`로, 끝나면 마무리로 돌아옴). 「처음으로」.
- 녹음 파일은 `attempt`가 끝나면(성공이든 실패든) 폰에서 지운다(`File(uri).delete()`).
- 하는 중에는 버튼을 막는다(`reduce`가 무시한다). 큰 버튼, 한국어 글, 노란 칠은 `#FFE066` 배경, 약한 음절은 작고 회색.

- [ ] **Step 4: 시험과 타입 검사가 통과하는지 본다**

Run: `cd app && npm test && npx tsc --noEmit`
Expected: 모두 통과

- [ ] **Step 5: 커밋한다**

메시지: `feat(app): add home, situation, roleplay and end screens`

---

### Task 10: 안드로이드 빌드와 폰에서 끝까지 해 보기(USB)

**Files:**
- Modify: `server/README.md`(띄우는 법), `app/README.md`(빌드와 설치)
- 커밋하지 않는 것: `app/.env`, `server/.env`, `app/android/`, APK

**Interfaces:**
- Consumes: Task 1~9 전부

- [ ] **Step 1: 빌드 도구를 확인한다**

Run: `/usr/libexec/java_home -v 17`
Expected: JDK 17 경로가 나온다. 없으면 env-setup 카드의 진행을 사용자에게 묻고 기다린다.

- [ ] **Step 2: 서버를 띄운다**

`server/.env`: `JE_TOKEN`(새로 만듦), `JE_HOST=127.0.0.1`, 음성 환경, whisper 모델, 그림 폴더(비공개 메모 참고). `cd server && uv run python -m je_server`.
Expected: 시작 로그에 whisper와 목소리 준비, 고정 문구 미리 만들기가 끝났다고 나온다. `curl -H "Authorization: Bearer $T" http://127.0.0.1:8787/health`가 `{"ok":true}`.

- [ ] **Step 3: APK를 만들어 깐다**

`app/.env`: `EXPO_PUBLIC_SERVER_URL=http://127.0.0.1:8787`, `EXPO_PUBLIC_SERVER_TOKEN=<JE_TOKEN>`.
Run: `cd app && npx expo prebuild -p android && cd android && JAVA_HOME=$(/usr/libexec/java_home -v 17) ./gradlew assembleRelease` 그리고 `adb reverse tcp:8787 tcp:8787 && adb install -r app/build/outputs/apk/release/app-release.apk`(adb는 SDK의 platform-tools)
Expected: 빌드 성공(처음에는 Gradle이 SDK platform, build-tools, NDK, CMake를 받는다), 폰에 「Jake English」가 깔린다.

- [ ] **Step 4: 폰에서 역할극 하나를 끝까지 한다**

사용자에게 부탁한다: 앱을 열어 인사를 듣고, 「추천해 줘」로 상황을 받고, 한 차례는 대사대로, 한 차례는 다르게 말하고, 한 번은 아무 말 없이 녹음을 멈춘다. 마무리에서 한 줄을 다시 해 본다.
Expected: 모든 화면이 돌아간다. `roleplay.json`의 `timings`에서 평가 글 첫 문장과 첫 목소리까지의 시간을 모은다. 목표(2~3초, 4~5초)를 넘으면 어디서 걸렸는지 숫자로 본다.

- [ ] **Step 5: 잰 값과 고친 것을 남기고 커밋한다**

스펙 「잰 것」에 「끝에서 끝까지(2026-11-05, 폰)」를 더한다. 이 Task에서 고친 코드가 있으면 그 Task의 scope로 커밋한다. 문서는 `docs: record end-to-end timing for roleplay MVP`.

---

### Task 11: Tailscale로 집 밖에서 쓰기

**Files:**
- Modify: `server/README.md`(Tailscale 주소로 띄우는 법, 주소는 쓰지 않음)
- 커밋하지 않는 것: `server/.env`, `app/.env`

**Interfaces:**
- Consumes: Task 10의 APK와 서버

- [ ] **Step 1: Tailscale이 준비됐는지 본다**

원래 폴더의 비공개 메모에서 env-setup 카드가 적은 맥의 Tailscale 주소를 읽는다. 없으면 사용자에게 묻고 기다린다. `tailscale status`로 맥과 폰이 같은 망에 있는지 본다.

- [ ] **Step 2: 서버를 Tailscale 주소에만 띄운다**

`server/.env`의 `JE_HOST`를 맥의 Tailscale 주소로 바꾸고 다시 띄운다.
Run: `lsof -nP -iTCP:8787 -sTCP:LISTEN`
Expected: Tailscale 주소에만 듣고 있다(`*:8787`이나 집 와이파이 주소가 아님). Tailscale Funnel은 꺼져 있다(`tailscale funnel status`).

- [ ] **Step 3: 앱을 Tailscale 주소로 다시 빌드해 깐다**

`app/.env`의 주소를 `http://<Tailscale 주소>:8787`로 바꾸고 Task 10 Step 3을 되풀이한다(`adb reverse`는 빼고).

- [ ] **Step 4: 모바일 데이터로 확인한다**

사용자에게 부탁한다: 폰의 와이파이를 끄고 모바일 데이터로 앱을 열어 한 차례를 해 본다. 다음으로 맥 서버를 잠시 끄고 앱이 「맥에 연결할 수 없어요」를 보여 주는지 본다.
Expected: 모바일 데이터로 평가까지 받는다. 서버가 꺼지면 30초 안에 알림이 나온다.

- [ ] **Step 5: README를 고쳐 커밋한다**

메시지: `docs(server): document running the server on the Tailscale address`

---

## 계획을 마친 뒤(superpowers 흐름과 AGENTS.md)

- PR을 열고 pr-review로 리뷰한다. 리뷰 요청에 `REVIEW.md`와 `AGENTS.md`를 넘긴다. PR 「한계」에 소리 설명 목록이 사람 검토 전 초안이라는 것을 적는다.
- `docs/guide/`에 구현하며 겪은 문제를 쓴다(예: 조용한 녹음의 받아쓰기, 작업 프로세스의 stdout).
- 미룬 일은 `docs/todo/`에 남긴다(예: 맥을 켤 때 서버 저절로 띄우기, 스펙의 미루는 것 4~8).
- devlog를 쓰고 머지 결정을 묻는다.
