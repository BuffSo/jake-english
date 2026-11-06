# ADR-0010 화면 위아래 여백은 react-native-safe-area-context로 받아 앱 바깥 틀 한 곳에서 띄운다

- 상태: 채택
- 날짜: 2026-11-06

## 배경

- 폰을 세 버튼 내비게이션으로 두면, 역할극 화면과 끝 화면 맨 아래의 「처음으로」가 폰의 아래 버튼 줄에 반쯤 가렸다(2026-11-06 폰 확인).
- 이 앱은 안드로이드에서 화면 끝까지 그린다(edge-to-edge). 상태 줄과 아래 버튼 줄 밑까지 그린다는 뜻이다. Expo SDK 58의 prebuild는 이 설정을 끌 수 없게 해 두었다. `app.json`에 `edgeToEdgeEnabled`를 쓰면 「Android 16 makes edge-to-edge mandatory」 경고를 내고 무시한다(`@expo/prebuild-config`의 `withEdgeToEdge.js`). React Native 0.88의 목표 SDK는 36(Android 16)이다.
- 그래서 화면마다 아래 버튼 줄 높이만큼 띄워야 한다. 그런데 화면마다 위쪽만 띄우고(상태 줄 높이 + 12) 아래쪽은 띄우지 않았다.
- 아래 줄 높이는 내비게이션 방식(세 버튼, 제스처)과 기기마다 다르다. 2026-11-06 에뮬레이터에서 세 버튼은 48dp였다.

## 검토한 안

React Native 0.88의 소스에서 설치 없이 높이를 알 수 있는지 먼저 확인했다.

- **화면 높이와 창 높이의 차이(`Dimensions`):** 화면 끝까지 그리는 모드에서는 창 높이가 아래 줄까지 포함한다(`ReactAndroid/.../deviceinfo/DeviceInfoModule.kt`의 `getWindowDisplayMetrics`). 차이가 0이라 쓸 수 없다.
- **`StatusBar.currentHeight`:** 위쪽(상태 줄) 높이만 준다.
- **React Native에 든 안전 영역 부품:** 안드로이드용 네이티브 부품(`ReactSafeAreaView.kt`)이 들어 있다. 하지만 공개된 `SafeAreaView`는 안드로이드에서 그냥 `View`이고, 「deprecated, react-native-safe-area-context를 써라」라고 적혀 있다. 네이티브 부품은 내부 경로(`react-native/src/private/...`)로만 불러올 수 있다. 문서에 없는 경로라 업그레이드하면 말없이 바뀌거나 사라질 수 있다.
- **고정 여백(예: 48):** 제스처 내비게이션(얇은 줄)에서는 빈자리가 생기고, 다른 기기에서는 맞지 않는다.
- **`react-native-safe-area-context`를 설치:** Expo가 권하는 방법이고, React Native도 자기 `SafeAreaView` 대신 이것을 쓰라고 한다. Expo SDK 58이 맞춰 둔 판(~5.11.1, `expo/bundledNativeModules.json`)이 있다. 내비게이션 방식을 바꾸면 여백도 바로 따라 바뀐다. MIT 라이선스.

## 판단

AI는 `react-native-safe-area-context` 설치를 추천했다. 설치 없이 쓸 수 있는 방법은 내부 경로뿐이라 업그레이드 때 위험하다는 이유다. 사용자가 「추천대로」 정했다. 다른 점은 없다.

## 결정

- `react-native-safe-area-context`를 `npx expo install`로 설치한다. 판은 Expo SDK가 맞춘 것을 따른다.
- 화면 위아래 여백은 `App.tsx`의 바깥 틀 한 곳에서 띄운다. `SafeAreaProvider` 안의 `SafeAreaView`가 모든 화면을 감싸고, 상태 줄과 아래 버튼 줄을 피한다.
- 화면은 시스템 줄을 직접 피하지 않는다. `app/src/ui/theme.ts`의 `top`은 틀 아래의 간격(12)만 뜻한다.

## 영향

- 네이티브 모듈이라 설치하거나 판을 바꾸면 APK를 다시 빌드해야 한다. Expo SDK를 올릴 때는 `npx expo install --fix`로 함께 올린다.
- 새 화면은 이 틀 안에 두면 따로 할 일이 없다. 화면 배경을 시스템 줄 밑까지 칠하고 싶어지면 틀을 바꿔야 한다. 지금은 모든 화면 배경이 흰색이라 문제가 없다.
- 확인 방법과 겪은 문제는 `docs/guide/APP_Expo_앱_뼈대와_서버_연결_20261105.md` 「문제: 맨 아래 버튼이 폰의 아래 버튼 줄에 가려진다」에 있다.
