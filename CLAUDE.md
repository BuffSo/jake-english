# jake-english

이 저장소에서 모든 AI 에이전트가 따르는 규칙은 `AGENTS.md`에 있다. Claude Code는 아래 줄로 그 파일을 불러온다. 여기에는 Claude Code에만 있는 도구와 설정만 쓴다. 공통 규칙을 고칠 때는 `AGENTS.md`를 고친다(2026-11-04 결정).

@AGENTS.md

@docs/private/private-notes.md

## superpowers (2026-11-04 결정)

superpowers 플러그인은 이 프로젝트에만 설치했다(`.claude/settings.json`의 `enabledPlugins`). 사용자가 정한 대로 **superpowers 스킬의 규칙이 전역 CLAUDE.md의 작업 방식보다 앞선다.** superpowers가 정하지 않은 것만 전역 CLAUDE.md를 따른다. 전역 CLAUDE.md와 이 저장소 규칙 사이의 순서는 `AGENTS.md` 서문을 따른다.

## worktree (2026-11-04 확인, 2026-11-05 고침)

- worktree는 오르카로 만들고, 그 worktree에 새 Claude 세션을 띄운다(`AGENTS.md` 「세션과 worktree」).
- 오르카 설정 「일반 → 소스 → Claude Code」를 「표시」로 바꿨다(2026-11-05). 기본은 숨김이라, Claude Code가 만든 `.claude/worktrees/*`가 오르카 사이드바에 보이지 않았다.
- 오르카를 쓸 수 없을 때만 Claude Code 도구(EnterWorktree, `--worktree`)로 만든다. 그러면 `.worktreeinclude`에 적은 `docs/private/`와 `.env`가 복사된다(Claude Code 2.1.318에서 시험해 확인). 복사본이라 고칠 때는 원래 폴더의 파일을 고친다(`AGENTS.md` 「worktree와 비공개 파일」).

## 카드와 main 세션 사이의 메시지 (2026-11-08 결정)

`AGENTS.md` 「카드의 질문과 머지는 main 세션을 거친다」의 메시지는 `SendMessage`로 보낸다. 카드가 main 세션에 보낼 때도, main 세션이 카드에 답과 승인을 전할 때도 같다.

- 받는 이름은 `ListAgents`가 보여 주는 이름을 그대로 쓴다. 이름은 대개 세션을 연 폴더 이름 뒤에 짧은 글자가 붙은 것이고(main 세션은 `jake-english-…`), 끝 글자는 세션마다 다르다. 카드는 넘길 글에 적힌 main 세션 이름으로 보낸다. 자기 이름은 `ListAgents` 맨 위에 나온다.
- 같은 이름의 줄이 둘 이상이면 이름 뒤에 한 칸 띄우고 그 줄의 `[ref]`를 붙여 보낸다(예: `jake-english-66 [8fa5bd]`).

## 커밋 가드 훅 (2026-11-04 결정)

`.claude/settings.json`의 PreToolUse 훅(`scripts/hooks/guard-git.mjs`)이 `git commit`과 `git push`를 실행하기 직전에 본다. git 훅이 한 겹이라면 이것이 두 번째 겹이다(`AGENTS.md` 「커밋 전 자동 검사」).

- 커밋이면 pre-commit 훅과 같은 공개 금지 검사를 미리 돌린다.
- git 훅을 건너뛰는 길을 막는다: 커밋의 `--no-verify`와 `-n`, push의 `--no-verify`, `git -c core.hooksPath=…`, `core.hooksPath`가 걸려 있지 않은 저장소.
- AI 서명이 든 커밋 명령을 막는다.
- 훅은 명령을 실행하기 전의 스테이징을 본다. `git rm --cached x && git commit`처럼 스테이징을 바꾸는 명령과 커밋을 한 명령에 묶으면 바꾸기 전 상태로 판단해 막는다. 둘을 나눠 실행한다.

## PR 리뷰: pr-review 스킬 (2026-11-04 결정)

PR을 열면 pr-review 스킬로 리뷰한다. 확인된 문제는 receiving-code-review대로 맞는지 따져 보고 고쳐 같은 PR에 push한다.

- pr-review는 `CLAUDE.md`와 함께 `AGENTS.md`도 찾아, 같은 무게의 규칙 원본으로 리뷰어와 점수 에이전트에게 넘긴다(2026-11-04 스킬 고침). 전에는 `CLAUDE.md`만 찾아서 이 줄과 `REVIEW.md`로 메웠다. `REVIEW.md`의 같은 안내는 superpowers 리뷰어를 위해 남긴다.
- pr-review는 `REVIEW.md`의 「반드시 지적할 것」을 CLAUDE.md와 같은 무게로 점수에 쓰고, 「넘길 것」을 오탐 목록에 더한다.
- pr-review가 코멘트를 게시한 뒤 수정 범위를 묻는 단계는 이 저장소에서 건너뛴다(2026-11-04 결정). 확인된 문제는 묻지 않고 고치고, 고친 것과 남긴 것은 머지 결정을 물을 때 알린다. 스킬은 여러 저장소가 같이 쓰는 것이라 고치지 않고, 이 저장소 규칙이 앞선다.
- superpowers가 작업 리뷰어나 최종 리뷰어를 띄울 때도 리뷰 요청에 `REVIEW.md`와 `AGENTS.md`를 함께 넘긴다. superpowers 규칙은 바꾸지 않고 입력만 더한다.
- 문서만 바꾼 PR은 pr-review가 건너뛴다(스킬의 고정 동작). 문서의 공개 노출은 커밋 전 자동 검사와, 사용자가 PR에서 읽는 것으로 막는다.
