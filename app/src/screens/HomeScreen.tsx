import { useCallback, useEffect, useState } from "react";
import { Image, StyleSheet, Text, View } from "react-native";

import { api } from "../api";
import type { Home } from "../api/types";
import type { SoundQueue } from "../audio/player";
import { Button } from "../ui/Button";
import { colors } from "../ui/theme";
import { messageOf, styles as common } from "./common";

type Props = { sounds: SoundQueue; home: Home | null; setHome: (h: Home) => void; onRoleplay: () => void };

export function HomeScreen({ sounds, home, setHome, onRoleplay }: Props) {
  const [face, setFace] = useState<"front" | "listening">("front");
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const h = await api.getHome();
      setHome(h);
      setFace("front");
      sounds.clear();
      sounds.enqueue(api.audioSource(h.lines.greeting.audio));
      sounds.enqueue(api.audioSource(h.lines.ask_mode.audio));
      sounds.onIdle(() => setFace("listening")); // listening face until the learner chooses (PRD 「첫 화면」)
    } catch (e) {
      setError(messageOf(e));
    }
  }, [sounds, setHome]);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <View style={styles.wrap}>
      {home && <Image source={api.imageSource(home.images[face])} style={styles.face} resizeMode="cover" />}
      {home && (
        <>
          <Text style={[common.body, styles.say]}>{home.lines.greeting.text}</Text>
          <Text style={[common.body, styles.say]}>{home.lines.ask_mode.text}</Text>
          <Button label="상황 역할극" onPress={onRoleplay} />
        </>
      )}
      {error && (
        <>
          <Text style={common.error}>{error}</Text>
          <Button label="다시 시도" onPress={load} />
        </>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { flex: 1, justifyContent: "center", padding: 20, backgroundColor: colors.bg },
  face: { width: "100%", aspectRatio: 1, borderRadius: 20, marginBottom: 16, backgroundColor: colors.ryan },
  say: { marginBottom: 8 },
});
