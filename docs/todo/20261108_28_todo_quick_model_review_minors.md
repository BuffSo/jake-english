# TODO: 추천 모델 PR의 마지막 리뷰가 남긴 작은 것

> 작성: 2026-11-08 (quick-model-review 카드, 마지막 리뷰의 Minor)
> 상태: **완료** (2026-11-08 small-sweep 카드)

1. `server/scripts/compare_quick_models.py`의 `rec_flags`가 끝말만 다른 되풀이를 놓친다. 「…환전소를 묻는 상황을 골라 봤어요.」를 피하라고 넘겼는데 「…환전소를 묻는 상황을 추천해요.」가 오면 걸리지 않는다. 두 쪽 모두 `strip_endings(x) or x`로 견준다. 시험을 먼저 쓴다.
2. `server/je_server/claude.py`의 `MESSAGE_LABELS`는 `recommend`의 메시지 줄 이름표를 손으로 옮긴 것이다. 메시지의 「끝말:」을 다른 이름으로 바꾸면 이름표 걷기가 소리 없이 꺼진다. 만든 메시지의 `X:` 줄 이름이 모두 `MESSAGE_LABELS`에 있는지 보는 시험을 더한다.
3. 잔손질:
   - `server/tests/test_check_jake_recommend.py`가 최근 상황을 「6개 이상」으로 보는데, 주석과 문서는 열 개라고 한다. `== 10`으로 맞춘다.
   - `server/je_server/claude.py` 맨 위 `HAIKU`, `SONNET` 근처 주석이 아직 `JE_CLAUDE_WRITER`, `JE_CLAUDE_QUICK` 둘만 말한다.
   - 가격표 `PRICE`가 `check_jake_recommend.py`와 `compare_quick_models.py`에 두 번 있다. 뒤쪽은 앞쪽을 이미 가져오니 그것을 쓴다.
