# 폰 앱

갤럭시에 직접 까는 Expo 앱이다(ADR-0002, ADR-0008). 화면, 녹음, 재생만 하고 계산은 맥 서버가 한다(ADR-0001).

## 준비

```sh
cd app
npm install
cp .env.example .env   # 맥 서버 주소와 토큰(server/.env 의 JE_TOKEN)
npm test && npx tsc --noEmit
```

## 빌드와 설치

JDK 17과 안드로이드 SDK 위치는 비공개 메모를 본다.

```sh
export JAVA_HOME="$(/usr/libexec/java_home -v 17)"
npx expo prebuild -p android --no-install
cd android && ./gradlew assembleRelease -PreactNativeArchitectures=arm64-v8a --info
adb install -r app/build/outputs/apk/release/app-release.apk   # adb 는 SDK 의 platform-tools
```

- 처음 빌드는 React Native 본체(170MB쯤)를 받느라 오래 걸린다. 멈춘 것 같으면 `docs/guide/APP_Expo_앱_뼈대와_서버_연결_20261105.md`를 본다.
- `app/.env`의 주소와 토큰이 APK에 들어간다. APK는 커밋하지 않고 남에게 주지 않는다.
- `android/`는 prebuild가 만드는 폴더라 git에서 뺐다. 손으로 고치지 않는다.
