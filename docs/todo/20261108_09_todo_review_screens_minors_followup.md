# TODO: 복습하기 작은 일(PR #33)에서 미룬 것

> 작성: 2026-11-08 (review-screens-minors 카드, 브랜치 최종 리뷰)
> 상태: **완료** (2026-11-08 minors-sweep 카드 앱 PR, 브랜치 `fix/minors-sweep`. 1번은 시험을 더했고, 2번은 `HANGUL`을 낱자까지 넓혔다)

PR #33의 브랜치 최종 리뷰가 Minor로 짚은 것이다. 계획은 `docs/superpowers/plans/2026-11-08-review-screens-minors.md`.

1. (고침) **`remove`의 두 번 누르기 막기에 테스트가 없다:** `app/src/flow/savedStore.ts`에서 `busy` 확인이 `change` 밖, `toggle`과 `remove` 각각으로 옮겨졌다. `toggle`의 것은 「pendingKeys: a second tap on the same sentence waits for the first」가 보지만, `remove`의 것은 테스트가 없다. 첫 `remove`가 끝나기 전에 두 번째 `remove`를 부르면 `set`이 한 번만 불리는지 보는 테스트를 더한다.
2. (고침) **낱자 한글을 잇지 않는다:** `app/src/ui/keepWords.ts`의 `HANGUL`이 완성 글자(가~힣)만 본다. 「ㅋㅋ」, 「ㅠㅠ」 같은 낱자 사이나 그 옆에서는 줄이 바뀔 수 있다. 라이언의 말에는 드물다. 넓히려면 `[가-힣ㄱ-ㅎㅏ-ㅣ]`.
