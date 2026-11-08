# TODO: 강세 값 재기 스크립트의 남은 작은 것들

> 작성: 2026-11-08 (stress-log 카드, PR #61 리뷰에서 미룬 것)
> 상태: **완료** (2026-11-08 small-sweep-3 카드, 다섯 모두 고침. 1은 파일마다 잡는 쪽, 4는 `inclusive`로 했다)

강세 값을 다시 잴 때(`server/scripts/measure_stress.py`, `stress_report.py`) 함께 고친다. 모두 지금 기록에서는 드러나지 않았다(맥 기록 65개를 정렬 실패 0으로 쟀다).

1. **특징 스크립트에서 파일 하나가 실패하면 그 묶음 전체가 매번 실패한다.** `stress_features.py`가 한 파일에서 예외를 내면(층이 없거나 Praat 오류) 묶음 20개가 모두 「failed」로 남고, 고르는 순서가 같아 다음 실행도 같은 묶음을 만든다. 파일마다 예외를 잡아 그 파일만 빼거나, 묶음이 실패하면 한 개씩 다시 해 본다.
2. **실패가 어느 단계인지 찍지 않는다.** 묶음이 실패하면 「failed N」만 찍힌다. 단계 이름(mfa align, stress features)은 경로나 낱말이 아니라 찍어도 된다. 시작할 때 MFA 환경에서 parselmouth와 praatio를 불러올 수 있는지도 본다.
3. **`--since`가 녹음한 때가 없으면 잰 때로 거른다.** 2026-11-07 전의 시도는 `at`이 없다. `stress/`를 지우고 다시 재면 옛 녹음이 새 날짜로 들어온다. 역할극을 만든 때(`created`)를 값 파일에 함께 남겨 그것으로 거른다.
4. **표본이 아주 작으면 「확실도 위 25%」 줄이 비어 나온다.** `statistics.quantiles`의 기본(exclusive)이 낱말 둘일 때 가장 큰 값보다 큰 기준을 낸다. `method="inclusive"`나 위에서 `ceil(n/4)`개로 바꾼다.
5. **`JE_DATA_DIR`를 잘못 적으면 그 자리에 빈 앱 데이터 폴더를 만든다.** `pending()`의 `Store(data_dir)`가 `roleplays/`, `audio/`, `tmp/`를 만든다. 시작할 때 `roleplays/`가 없으면 알리고 멈춘다.
