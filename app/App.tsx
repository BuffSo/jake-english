import { setAudioModeAsync } from "expo-audio";
import { StatusBar } from "expo-status-bar";
import { useEffect, useMemo, useReducer, useState } from "react";
import { StyleSheet, Text } from "react-native";
import { SafeAreaProvider, SafeAreaView } from "react-native-safe-area-context";

import type { Home } from "./src/api/types";
import { SoundQueue } from "./src/audio/player";
import { CONFIGURED } from "./src/config";
import { initial, reduce } from "./src/flow/state";
import { EndScreen } from "./src/screens/EndScreen";
import { HomeScreen } from "./src/screens/HomeScreen";
import { RoleplayScreen } from "./src/screens/RoleplayScreen";
import { SituationScreen } from "./src/screens/SituationScreen";
import { laterPictures } from "./src/ui/faces";
import { Preload } from "./src/ui/Preload";
import { ThinkingFaces } from "./src/ui/ThinkingFace";
import { colors } from "./src/ui/theme";

export default function App() {
  const [state, dispatch] = useReducer(reduce, initial);
  const [home, setHome] = useState<Home | null>(null);
  const sounds = useMemo(() => new SoundQueue(), []);

  useEffect(() => {
    setAudioModeAsync({ playsInSilentMode: true, allowsRecording: true }).catch(() => {});
  }, []);

  let screen;
  if (!CONFIGURED) {
    screen = <Text style={styles.msg}>서버 설정이 없어요. app/.env를 채우고 다시 빌드해 주세요.</Text>;
  } else if (state.screen === "home" || (state.screen === "situation" && !home)) {
    screen = (
      <HomeScreen sounds={sounds} home={home} setHome={setHome} onRoleplay={() => dispatch({ type: "chooseRoleplay" })} />
    );
  } else if (state.screen === "situation" && home) {
    screen = (
      <SituationScreen
        sounds={sounds}
        home={home}
        onCreated={(roleplay, jake) => dispatch({ type: "created", roleplay, jake })}
        onBack={() => dispatch({ type: "home" })}
      />
    );
  } else if (state.screen === "roleplay") {
    screen = <RoleplayScreen state={state} dispatch={dispatch} sounds={sounds} />;
  } else {
    screen = <EndScreen state={state} dispatch={dispatch} sounds={sounds} />;
  }

  // Android draws the app edge to edge, under the status bar and the phone's bottom bar. Every screen sits inside
  // this one frame, which keeps clear of both, so no screen pads for the bars itself. The screens used to pad only
  // the top, and the three-button bar covered half of 「처음으로」 at the bottom (2026-11-06, phone).
  return (
    <SafeAreaProvider>
      <SafeAreaView style={styles.root}>
        <StatusBar style="dark" />
        {/* the roleplay and end screens get no `home`, but their waits show Ryan's thinking face */}
        <ThinkingFaces.Provider value={home?.images.thinking ?? null}>{screen}</ThinkingFaces.Provider>
        {home && <Preload paths={laterPictures(home.images)} />}
      </SafeAreaView>
    </SafeAreaProvider>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.bg },
  msg: { margin: 24, marginTop: 56, fontSize: 18, color: colors.text },
});
