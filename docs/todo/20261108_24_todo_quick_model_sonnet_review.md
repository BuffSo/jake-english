# TODO: 짧은 말 모델(Haiku)을 Sonnet으로 바꿀 때의 품질 견주기

> 작성: 2026-11-08
> 상태: **완료** (2026-11-08 quick-model-review 카드). 사용자가 추천만 Sonnet으로 정했다(`JE_CLAUDE_RECOMMEND`, 기본 sonnet). 통역과 평가는 Haiku 그대로다. 결과는 `docs/guide/PROMPT_일마다_모델_견주기_20261108.md`와 devlog `docs/devlog/2026-11-08-quick-model-review.md`.

## 왜 하나

2026-11-08 사용자가 API 크레딧을 넉넉히 채우고 「지금 하이쿠로 하는 것을 소넷으로 바꾸었을 때의 품질을 체크해 줘」라고 했다. 전에는 값 때문에 Haiku를 골랐다(소희 통역은 sohee-prepared에서 Sonnet이 스무 배 비싸 Haiku 그대로, 따라 말하기 평가는 feedback-explanation에서 고친 뒤 되풀이되지 않아 그대로). 이제 값보다 품질과 기다리는 시간으로 다시 본다.

짧은 말 모델(`server/.env`의 `JE_CLAUDE_QUICK`, 지금 Haiku)이 맡은 일은 셋이다(`server/je_server/claude.py`의 `self.quick`).

1. 소희 통역(`interpret`): 대사마다 한 번, 목록 대본은 써 둔 것을 쓴다.
2. 제이크 추천(`recommend`): 상황 추천과 끝말.
3. 라이언의 따라 말하기 평가(`feedback`): 녹음마다 바로 흘려 보낸다. 기다리는 시간이 가장 중요하다.

## 할 일

1. 세 일마다 같은 입력으로 Haiku와 Sonnet을 견준다. 품질(뜻, 말투, 규칙 지키기, 알려진 실수)과 기다리는 시간(첫 글자, 끝까지)을 표로 낸다.
2. 일마다 바꿀지 추천한다. 하루 쓰는 만큼으로 늘어나는 값도 함께 적는다.
3. 사용자가 정한 대로 바꾼다. `JE_CLAUDE_QUICK`은 셋을 한꺼번에 바꾸니, 일부만 바꾸려면 코드에서 일마다 모델을 고르게 한다.
