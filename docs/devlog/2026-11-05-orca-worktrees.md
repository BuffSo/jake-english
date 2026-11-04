# 2026-11-05 오르카로 세션과 worktree 나누기

- PR: #7
- 문서: PRD 기능과 상관없는 작업 방식 변경이라 스펙, 계획, ADR은 없다. 규칙은 `AGENTS.md` 「세션과 worktree」, 「worktree와 비공개 파일」과 `CLAUDE.md` 「worktree」에 있다.

## 한 일

- 오르카 사이드바에 Claude Code가 만든 worktree가 보이게 했다(오르카 설정 「일반 → 소스 → Claude Code: 표시」).
- 오르카의 jake-english 「설정 스크립트」에 비공개 파일 복사를 넣고, 「실행 시기」를 「기본적으로 실행」으로 했다.
- main 세션은 의논과 결정, worktree 세션은 그 일의 작업을 맡도록 규칙을 적었다.

## 흐름

| 정할 것 | AI 추천 | 사용자 판단 | 결과 |
|---|---|---|---|
| 작업 중인 파일을 에디터에서 보기 | worktree는 VS Code에서 그 폴더를 새 창으로 열어야 보인다고 설명했다. 새 창을 열어 드렸다. | 오르카에서도 worktree를 보고 싶다. | 아래 두 줄 |
| 오르카에 worktree가 안 보임 | 「외부 worktree 표시」 설정을 바꾸면 된다고 보고 바꿨다. 효과가 없었다. 오르카 코드를 찾아보니 `.claude/worktrees`는 「Claude Code」 출처로 따로 숨겨지고 있었다. 화면에서 켜는 방법을 길게 안내했다. | 길다, computer use로 직접 하라. | AI가 오르카 화면을 조작해 「Claude Code: 표시」로 바꿨다. |
| 대화 카드가 main 밑에 있음 | 작업에는 문제가 없으니 이대로 두고, 오르카로 worktree를 만드는 방법은 todo로 미루자고 했다. | 이 문제를 먼저 해결하자. | 설정 스크립트로 비공개 파일 복사를 확인했다. |
| worktree마다 새 세션을 띄우는 것 | 사용자가 먼저 짚었다. AI는 main 세션(의논)과 worktree 세션(작업)을 섞어 쓰자고 추천했다. 한 세션이 계속 일하고 카드 위치는 감수하는 안도 냈다. | 추천대로 섞어 쓰기 | `AGENTS.md` 「세션과 worktree」 |
| worktree를 만들 때 VS Code 창 열기 | 규칙으로 넣자고 했다. | 안 볼 거라 필요 없다. | 넣지 않았다. |

## 바로잡은 것

- **원인을 확인하지 않고 설정부터 바꿨다.** 오르카의 「외부 worktree 표시」를 바꿨지만 원인은 다른 설정(「Claude Code」 출처)이었다. 바꾼 프로젝트 설정 「외부 작업 트리: 표시」는 그대로 남아 있다. 지금은 영향이 없다.
- **오르카 화면을 조작하다 프로젝트를 접었다.** 메뉴 버튼 대신 접기 버튼을 눌렀다. 다시 펼쳐 두었다.
- **확인하지 않고 「셋 다 머지한 PR」이라고 말했다.** 지울 worktree를 고를 때 PR #4는 열려 있었다. 지우기 전에 머지 여부와 사본만 있는 파일을 확인해서 잃은 것은 없다.
- **머지한 뒤 정리하지 않았다.** PR #6을 머지하고도 worktree가 머지한 브랜치에 남아, 오르카와 VS Code에 옛 브랜치 이름이 보였다. 사용자가 짚었다.
  - 더한 장치: 에이전트 메모리에 「머지하면 묻지 않고 main을 맞추고, 머지한 로컬 브랜치를 지우고, worktree를 다음 브랜치로 바꾸거나 지운다」를 적었다. 이번 규칙의 「worktree 세션은 머지한 뒤 정리한다」도 같은 일이다.
- **`REVIEW.md` 「고치는 방법」 점검:** 문서만 바꾼 PR이라 pr-review가 건너뛴다. 넣을 것이 없다.

## 검증

- `orca worktree create --name orca-setup-test --no-parent --setup run`: 만든 worktree의 `docs/private/`가 원래 폴더와 같았다(`diff -rq`). `core.hooksPath`는 `.githooks` 그대로였다. 시험용 worktree와 브랜치는 지웠다.
- `node --test 'scripts/**/*.test.mjs'`: 54개 통과, 0개 실패
- `node scripts/check-sensitive.mjs --all`: 통과

## 다음

- 머지한 뒤, 라이언의 말을 만드는 AI를 정하는 ADR을 오르카 worktree 세션으로 넘긴다. 처음으로 이 방식을 쓴다.
- 이 대화는 원래 폴더의 main 세션으로 돌아가고, 지금 쓰는 Claude Code worktree는 지운다.
