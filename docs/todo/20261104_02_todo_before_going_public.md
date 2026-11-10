# TODO: 저장소를 공개로 바꾸기 전 점검

> 작성: 2026-11-04
> 상태: **보류** (2026-11-09 go-public-prep 카드: 기록 검사, README, MIT. 2026-11-11 go-public-recheck 카드: 그 뒤의 기록과 닫은 PR, PR 본문의 고친 기록까지 다시 검사하고 README에 소개 영상 링크를 넣음. 검사 결과는 비공개 메모. 같은 날 머지한 원격 브랜치를 모두 지웠다. 2026-11-11 사용자가 공개 전환을 미뤘다. 소개 영상에는 저장소 대신 개인 홈페이지의 소개 페이지를 건다. 남은 것: 공개 전환과 그 직후의 GitHub 설정, 사용자가 정할 때 한다)

## 왜 하나
저장소는 GitHub 비공개로 시작해 나중에 공개로 바꾼다. 공개하면 지금까지의 커밋 기록도 모두 드러난다. 한 번 공개된 것은 되돌리기 어렵다.

## 할 일
- [x] 라이선스를 정해 `LICENSE`를 넣는다. (2026-11-09 MIT, 앱 아이콘 그림은 README에서 뺀다고 적음, go-public-prep PR) 라이선스가 없으면 남이 코드를 쓸 수 없다(모든 권리 보유).
- [x] 쓰는 모델과 목소리의 사용 조건을 확인한다(2026-11-09 1차 출처로 확인해 README 「쓰는 모델과 사용 조건」에 적음)(TTS 모델, 받아쓰기 모델, 복제 목소리의 기준 녹음).
- [x] 공개용 `README.md`를 쓴다(2026-11-09 go-public-prep PR)(무엇인지, 어떻게 돌리는지, 맥 서버가 필요하다는 것).
- [x] README에 소개 영상 링크를 넣는다(2026-11-11 go-public-recheck PR. 썸네일 그림은 저장소에 넣지 않고 링크만).
- [x] 커밋 기록 전체에서 키, 개인 경로, 개인 정보, 녹음이 없는지 검사한다. 검사 도구를 설치해야 하면 먼저 묻는다.
  - 2026-11-09: PR #70까지 검사했다. 사용자가 기록은 그대로 두기로 정했다.
  - 2026-11-11: 그 뒤의 커밋, 머지하지 않고 닫은 PR의 커밋, PR 본문과 코멘트의 고친 기록(옛 판)까지 다시 검사했다. 새로 설치한 도구는 없다.
  - 찾은 것, 커밋 번호, 어떻게 할지 견준 길은 비공개 메모(`docs/private/`의 기록 검사 결과)에만 적었다. 공개 파일에는 옮기지 않는다.
- [x] `docs/private/`가 한 번도 커밋되지 않았는지 확인한다(2026-11-09, 2026-11-11 비어 있음)(`git log --all -- docs/private`가 비어야 한다).
- [ ] GitHub 저장소 설정에서 secret scanning과 push protection을 켠다. 공개 저장소는 무료다. 키 형식이 든 push를 GitHub 쪽에서도 거부해, 이 맥의 훅을 거치지 않은 push까지 막는다.
  - 언제: 공개로 바꾼 직후. 개인 계정의 비공개 저장소는 GitHub Team이나 Enterprise 요금제에서 Secret Protection을 사야 켤 수 있어 지금은 못 켠다(2026-11-09 확인, GitHub 문서 「About GitHub Advanced Security」). 공개 저장소는 Secret Protection을 사지 않아도 두 기능을 쓸 수 있다.
  - 방법: 저장소 Settings → 사이드바 「Security and quality」의 Advanced Security → 「Secret Protection」 오른쪽 Enable → 「Push protection」 오른쪽 Enable(GitHub 문서 「Enabling push protection for your repository」). secret scanning은 공개 저장소에서 기본으로 돈다. 계정 설정의 사용자 단위 push protection은 기본으로 켜져 있다.
  - 설정은 사용자가 승인한 뒤에 바꾼다.
- [x] `node scripts/check-sensitive.mjs --all`로 지금 파일 전체를 한 번 더 검사한다.
- [ ] 공개 전환은 사용자가 정한다.
