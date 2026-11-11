# 오르카 worktree에 비공개 파일 복사하기

> 작성: 2026-11-11 (2026-11-05에 정한 것을 `AGENTS.md`에서 옮김)
> 관련 규칙: `AGENTS.md` 「worktree와 비공개 파일」

worktree는 git에 든 파일만 펼친다. 그래서 git에서 뺀 비공개 메모(`docs/private/`)와 환경 변수 파일(`.env`)이 새 worktree에는 없다. 오르카로 만든 worktree에는 오르카의 프로젝트 「설정 스크립트」가 원래 폴더에서 이 둘을 복사해 넣는다. 이 문서는 그 스크립트와 넣는 곳을 담는다. 다른 맥이나 새로 설치한 오르카에서 이 문서만 보고 다시 넣을 수 있게 썼다.

## 정한 기준

- 오르카의 jake-english 프로젝트 설정 「설정 스크립트」에 아래 스크립트를 넣는다. 「실행 시기」는 「기본적으로 실행」으로 둔다.
- 스크립트는 로컬 스크립트라 그 맥의 오르카에만 저장된다. 다른 맥이나 새로 설치한 오르카에는 다시 넣는다.
- 저장소에 커밋해 공유하는 `orca.yaml`은 쓰지 않는다. 오르카 전용 설정을 공개 저장소에 둘 이유가 없다(AI 판단).
- 복사본이다. worktree에서 고치면 원래 폴더에 반영되지 않고, worktree를 지우면 사라진다. 비공개 파일은 언제나 원래 폴더(`git worktree list`의 첫 줄)의 파일을 고친다.

## 스크립트

```sh
set -e
mkdir -p "$ORCA_WORKTREE_PATH/docs"
if [ -d "$ORCA_ROOT_PATH/docs/private" ]; then cp -R "$ORCA_ROOT_PATH/docs/private" "$ORCA_WORKTREE_PATH/docs/"; fi
if [ -f "$ORCA_ROOT_PATH/.env" ]; then cp "$ORCA_ROOT_PATH/.env" "$ORCA_WORKTREE_PATH/.env"; fi
```

- `ORCA_ROOT_PATH`는 원래 폴더, `ORCA_WORKTREE_PATH`는 새 worktree다. 오르카가 스크립트를 돌릴 때 채운다.
- 원래 폴더에 둘 중 하나가 없으면 그것만 건너뛴다. 새로 클론해 비공개 메모를 아직 만들지 않은 저장소에서도 worktree 만들기가 멈추지 않는다.

## 확인 방법

1. 오르카로 시험용 worktree를 하나 만든다.
2. 그 worktree에 `docs/private/private-notes.md`와 `.env`가 있는지 본다.
3. 시험용 worktree를 지운다.

2026-11-05에 이 순서로 복사되는 것을 확인했다.

## 다른 도구로 만든 worktree

- Claude Code로 만든 worktree: `.worktreeinclude`에 적은 `docs/private/`와 `.env`가 복사돼 들어간다(`CLAUDE.md`).
- `git worktree add`로 만든 worktree: 복사되지 않는다. 필요하면 원래 폴더에서 복사해 온다.
