# 맥 서버

폰 앱이 부르는 맥 서버다(ADR-0001, ADR-0006). 받아쓰기, 라이언과 제이크 목소리, Claude 호출, 기록 저장을 맡는다.

## 준비

```sh
cd server
uv sync
cp .env.example .env   # 값을 채운다. 경로는 비공개 메모를 본다
```

토큰 만들기: `python3 -c "import secrets; print(secrets.token_hex(24))"`

## 띄우기

```sh
uv run python -m je_server
```

## 시험

```sh
uv run pytest
```

시험 소리는 시험 중에 임시 폴더에 만든다. 녹음과 소리 파일은 커밋하지 않는다.
