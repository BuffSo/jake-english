# TODO: 다시 연습(review-practice) 최종 리뷰에서 미룬 것

> 작성: 2026-11-07
> 상태: **완료** (2026-11-08 review-screens 카드, PR #31. 계획 `docs/superpowers/plans/2026-11-08-review-minors.md`)

## 왜 하나

review-practice 구현의 최종 리뷰(브랜치 전체)가 짚은 것 중 드물거나 다듬기라 미룬 것이다. 중요한 넷은 같은 PR에서 고쳤다. PR 리뷰가 다시 짚은 셋(잃은 줄의 문장 다시 모으기, 펼친 줄 스크롤, 접힌 말풍선에 남는 읽는 법과 통역)도 같은 PR에서 고쳐 목록에서 뺐다. 스펙은 `docs/superpowers/specs/2026-11-07-review-practice-design.md`.

## 할 일

1. **처음 녹음 두 개 사이의 쉼:** 스펙 4는 「둘 사이에 짧게 쉰다」인데 이어서 튼다. 녹음 앞뒤의 빈 소리로 지금은 구별되는지 폰에서 들어 보고 정한다.
2. **`Engine.saved`가 읽지 못하는 역할극에서 멈춘다:** `KeyError`만 건너뛰어, `roleplay.json` 하나가 깨지면 `GET /saved` 전체가 실패한다. `Store.all`처럼 건너뛴다. 깨진 `saved.json`도 같다.
3. **`Engine.latest`가 기록을 두 번 읽는다:** 묶음을 고를 때와 `summary`에서. 기록이 많아지면 묶음을 넘겨 한 번만 읽는다(ADR-0011 「영향」).
