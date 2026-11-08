# TODO: 소희 통역 최종 리뷰에서 미룬 작은 것

> 작성: 2026-11-06 (korean-translation 카드, 최종 리뷰)
> 상태: **완료** (2026-11-08 three-line-listen 카드. 1, 3, 4를 고쳤다. 2와 5는 고치지 않고 닫았다: PR #29가 대본 다시 쓰기를 없애 같은 번호의 줄이 바뀌지 않고, 5의 시험은 그때 옛 기록을 바로 만드는 시험으로 바뀌었다. 6은 재어 봤다(처음 통역하는 줄에서 글 1.2초, 소리 6.5초쯤, 목소리 닮음 검사 포함). 소희 소리를 미리 만드는 일은 sohee-prepared 카드가 맡았다. 스펙 `docs/superpowers/specs/2026-11-08-three-line-listen-design.md` 「같은 화면의 작은 일」)

소희 통역(브랜치 `feat/korean-translation`)의 최종 리뷰가 짚었지만, 작은 것이라 고치지 않고 남긴 것이다. 스펙은 `docs/superpowers/specs/2026-11-06-korean-translation-design.md`.

1. **실패 안내가 남는 범위:** 통역 글을 못 만들면 「지금은 통역할 수 없어요」가 다음에 누를 때까지 남는다. 같은 줄 번호의 접힌 말풍선(지난 「나」 말풍선과 「다시 해 보기」의 「내 차례」)에도 나온다. 스펙은 「짧게 보이고 접는다」라서, 몇 초 뒤 사라지게 할지 정한다(`app/src/flow/interpret.ts`의 `koView`).
2. **줄 번호로만 찾는 통역:** 앱의 통역(`koFetch`의 `got`)과 서버의 진행 중 작업(`Engine.kos`)이 줄 번호로만 찾는다. 평가 흐름이 라이언 대답 뒤에 끊기고, 다시 해서 다른 대답이 같은 번호에 들어오면 앞 대답의 통역이 보일 수 있다. 영어 글을 함께 저장해 다르면 버리게 한다. `Engine.threes`도 같은 모양이다.
3. **화면 안에서 만든 부품:** `RoleplayScreen`의 `Ko`와 `RyanBubble`이 그릴 때마다 새로 만들어진다. 함수로 불러 그리게 바꾼다.
4. **낡은 주석:** `server/je_server/tts_worker.py` 맨 위의 약속 설명이 목소리를 `ryan`, `jake`만 적는다. `RoleplayScreen`의 `PractiseLink` 주석이 이제 누르지 않는 라이언 말풍선을 말한다. `_quiet`가 통역 실패를 "line prep failed"로 적는다.
5. **시험 순서:** `server/tests/test_engine.py`의 `test_ko_of_a_reply_sees_what_was_said_and_does_not_wait_for_the_rebuild`가 시도를 저장한 뒤 대답을 넣는다. 실제 흐름은 대답이 먼저다.
6. **소희 소리가 늦다:** 한 문장에 7초쯤 걸렸다(스펙 「잰 것」). 폰에서 늦게 느껴지면 원인(목소리 닮음 검사의 다시 만들기, 끝소리 받아쓰기)부터 잰다.
