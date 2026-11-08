# TODO: 읽는 법 기다리지 않기(dont-wait-for-line-notes) 최종 리뷰의 작은 것

> 작성: 2026-11-08
> 상태: **완료** (2026-11-08 minors-sweep 카드 서버 PR, 브랜치 `fix/minors-sweep-server`. 1, 2번은 이 PR, 3번은 앱 PR #43에서 고쳤다. 2번의 주석은 그 전에 이미 맞춰져 있었다)

## 왜 하나

브랜치 전체 리뷰가 짚었지만 쓰는 사람에게 생기는 문제가 거의 없어 그 PR에서 고치지 않았다. 스펙은 `docs/superpowers/specs/2026-11-08-dont-wait-for-line-notes-design.md`.

## 할 일

1. (고침, `_keep`) 읽는 법 일(`Engine._three_task`)이 실패로 끝나고 그 정리 콜백이 돌기 전에 새 일이 들어오면, 옛 콜백이 새 일을 `self.threes`에서 지운다. 그 뒤 묻는 쪽은 Claude를 한 번 더 부른다. 드물지만 줄 받기도 이제 이 길을 탄다. 콜백을 `lambda t: self.threes.get(key) is t and self.threes.pop(key)`처럼 자기 일일 때만 지우게 하고, 통역(`self.kos`)도 같게 한다.
2. (고침) 줄 받기 경로(`server/je_server/app.py`의 `line`)의 `except ClaudeUnavailable`은 이제 닿지 않는다(`Engine.line`이 그 오류를 내지 않는다). 지우고, 그 위의 「waits for a rebuild」 주석도 지금 동작에 맞춘다.
3. (PR #43에서 고침) 앱에서 줄이 나온 첫 화면에는 아직 받으러 가기 전이라 「읽는 법 보기」가 없다가 한 프레임 뒤에 생겨 「통역」과 ☆가 옆으로 밀린다. 받지 못한 줄은 「다시 해 보기」 때마다 다시 받으러 가, Claude가 안 될 때 버튼이 깜빡인다. 받지 못한 것을 따로 표시하고, 아직 받으러 가기 전을 「받는 중」으로 보면 둘 다 없어진다(`app/src/ui/notesView.ts`의 `lineNotes`, `needsNotes`).
