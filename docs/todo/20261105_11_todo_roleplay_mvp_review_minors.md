# TODO: 역할극 MVP 최종 리뷰에서 미룬 작은 문제

> 작성: 2026-11-05
> 상태: **완료** (2026-11-08 minors-sweep 카드. 남았던 1번은 해당하지 않아 닫는다: PR #29(offscript-aside)가 다르게 말한 뒤 대본을 다시 만드는 일을 없애며 `_continue`를 지웠다(커밋 af78d3c). 4번은 `app.py` `/audio`가 `engine().voice`를 거친다. 전: **진행 중** (2026-11-05 PR #12 리뷰에서 2번과 5번을 고쳤다. fix/roleplay-quick-fixes에서 3번을 고치고 6번은 생기지 않는 것을 확인했다. PR #15에서 4번을 고쳤다. 1번이 남았다))

## 왜 하나

역할극 MVP(feat/roleplay-mvp)의 최종 리뷰가 짚은 것 가운데 중요한 4건은 그 PR에서 고쳤다. 아래 6건은 드물게 생기거나 피해가 작아 미뤘다. 다음 PR에서 시험을 먼저 쓰고 고친다.

## 할 일

1. (해당 없음, PR #29가 `_continue`를 지웠다) `server/je_server/engine.py` `_continue`: 다르게 말한 뒤 남은 대본을 만드는 동안 서버를 다시 띄우면, 대본이 라이언의 대답에서 끝난 채 남는다. 다음 줄이 404라 앱은 역할극을 일찍 끝낸다. 마지막 줄이 `kind="reply"`이고 남은 사용자 차례가 있으면 `_continue`를 다시 돌린다.
2. (PR #12에서 고침) `server/je_server/tts.py` `rate_file`: 같은 소리의 0.8배를 두 요청이 동시에 만들면 임시 파일 이름이 같아 둘째가 `FileNotFoundError`로 500이 난다. 요청마다 다른 임시 이름을 쓴다.
3. (fix/roleplay-quick-fixes에서 고침. 시험해 보니 한 번이 아니라 그 뒤 모든 소리가 실패했다) `server/je_server/tts.py` `_spawn`: 작업 프로세스가 시간 안에 뜨지 않으면 반쯤 뜬 프로세스가 `self.proc`에 남아, 다음 작업이 그 프로세스의 `{"ready": true}`를 답으로 읽고 한 번 실패한다. 실패하면 프로세스를 끝내고 `self.proc = None`으로 둔다.
4. (PR #15에서 고침) `server/je_server/app.py` `/audio`: `services.voice`를 바로 써서 `engine()`의 `None` 검사를 거치지 않는다(서비스 없이 띄울 때만 문제).
5. (PR #12에서 고침) `app/src/screens/RoleplayScreen.tsx` `stopRecording`: 60초 자동 멈춤과 손으로 누른 멈춤이 겹치면 녹음을 두 번 올릴 수 있다. reducer가 `recordStop`을 받아들였는지 보고 올린다.
6. (생기지 않음, 2026-11-05 확인) 끝 화면과 역할극 화면은 다른 컴포넌트라, 끝 화면에서 다시 하기를 누를 때마다 역할극 화면이 새로 그려지고 `played`도 비워진다. `app/src/screens/RoleplayScreen.tsx` 본보기 한 번 틀기: 마무리 화면에서 같은 줄을 두 번 다시 하면 두 번째에는 본보기가 나오지 않는다(`played` 키가 줄과 mode뿐).
