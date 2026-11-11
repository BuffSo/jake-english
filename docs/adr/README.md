# ADR (결정 기록)

되돌리기 어렵거나 여러 기능에 걸치는 결정을 한 건씩 남긴다. 무엇을, 언제 쓰는지와 결정을 바꾸는 법은 `AGENTS.md` 「결정 기록: ADR」을 따른다. 규칙이 두 곳에서 어긋나지 않게 여기에는 다시 적지 않는다.

## 양식

```markdown
# ADR-NNNN 제목

- 상태: 제안 | 채택 | 대체됨(ADR-XXXX)
- 날짜: YYYY-MM-DD

## 배경

## 검토한 안

## 판단

AI가 처음 추천한 안과 사용자가 정한 것. 둘이 다르면 그 차이와 이유.

## 결정

## 영향
```

새 ADR을 쓰면 아래 「목록」에 한 줄 더한다.

## 목록

- [ADR-0001 계산은 맥에서 하고, 앱과는 API로 나눈다](0001-mac-does-the-computing.md) (채택)
- [ADR-0002 앱은 리액트 네이티브와 Expo로 만들고, 맥에서 빌드해 직접 설치한다](0002-app-build-and-install.md) (채택)
- [ADR-0003 연습 자료는 저작권 걱정이 없는 것만 쓴다](0003-copyright-free-practice-material.md) (대체됨(ADR-0005))
- [ADR-0004 라이언의 말은 외부 API(Claude)로 만든다](0004-ryan-ai-on-claude-api.md) (채택)
- [ADR-0005 연습 자료는 사용자가 맥에 넣은 영상으로, 혼자 공부하는 범위에서 쓴다](0005-practice-material-for-private-study.md) (채택)
- [ADR-0006 맥 서버는 파이썬(FastAPI)으로 만들고, 앱과 한 저장소에 둔다](0006-mac-server-in-python.md) (채택)
- [ADR-0007 집 밖에서는 Tailscale로 폰을 집의 맥에 잇는다](0007-remote-access-over-tailscale.md) (채택)
- [ADR-0008 앱 고유 ID는 dev.jakeso.english로 한다](0008-android-application-id.md) (채택)
- [ADR-0009 음성 합성은 맥의 기존 음성 환경에서 따로 도는 작업 프로세스로 부른다](0009-voice-worker-on-existing-tts.md) (채택)
- [ADR-0010 화면 위아래 여백은 react-native-safe-area-context로 받아 앱 바깥 틀 한 곳에서 띄운다](0010-safe-area-insets.md) (채택)
- [ADR-0011 다시 연습의 목록과 비교는 맥에 저장된 기록으로 만들고, 같은 대본의 회차를 원본 ID로 묶는다](0011-review-from-stored-records.md) (채택)
- [ADR-0012 맥 서버는 launchd 사용자 에이전트로 띄운다](0012-server-autostart-with-launchd.md) (채택)
- [ADR-0013 목록 상황의 대본은 저장소에 두고, 같은 목록 상황의 회차를 원본 ID로 묶는다](0013-fixed-scripts-for-list-picks.md) (채택)
- [ADR-0014 시험은 GitHub Actions에서도 돌린다(APK는 만들지 않는다)](0014-tests-on-github-actions.md) (채택)
