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

## 집 밖에서 쓰기 (Tailscale, ADR-0007)

- `server/.env`의 `JE_HOST`를 맥의 Tailscale 주소로 둔다(주소는 비공개 메모). 서버는 그 주소에만 붙고, 집 와이파이 주소로는 열리지 않는다.
  - 확인: `lsof -nP -iTCP:8787 -sTCP:LISTEN`에 Tailscale 주소만 보여야 한다.
- 앱의 `app/.env`에도 같은 주소와 토큰을 넣고 빌드한다(`app/README.md`).
- Tailscale Funnel, 포트 전달, 공개 터널은 쓰지 않는다. 확인: `tailscale funnel status`가 비어 있어야 한다.
- 집 밖에서 쓰는 동안 맥은 켜져 있고 잠들지 않아야 한다. 맥을 다시 켜면 서버를 다시 띄운다(저절로 띄우기는 todo).
