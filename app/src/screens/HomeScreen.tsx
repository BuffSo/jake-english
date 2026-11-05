import { useCallback, useEffect, useState } from "react";
import { StyleSheet, Text, View } from "react-native";

import { api } from "../api";
import type { Home } from "../api/types";
import type { SoundQueue } from "../audio/player";
import { Button } from "../ui/Button";
import { RyanPortrait } from "../ui/RyanFace";
import { colors, top } from "../ui/theme";
import { messageOf, styles as common } from "./common";

type Props = { sounds: SoundQueue; home: Home | null; setHome: (h: Home) => void; onRoleplay: () => void };

export function HomeScreen({ sounds, home, setHome, onRoleplay }: Props) {
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const h = await api.getHome();
      setHome(h);
      sounds.clear();
      sounds.enqueue(api.audioSource(h.lines.greeting.audio));
      sounds.enqueue(api.audioSource(h.lines.ask_mode.audio));
    } catch (e) {
      setError(messageOf(e));
    }
  }, [sounds, setHome]);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <View style={styles.wrap}>
      {home && (
        <View style={styles.face}>
          {/* the front picture stays after Ryan has spoken (2026-11-05 user; it used to turn to the listening one) */}
          <RyanPortrait source={api.imageSource(home.images.front)} />
        </View>
      )}
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
  // from the top: centring left a wide gap above the picture (2026-11-05, user)
  wrap: { flex: 1, paddingTop: top, paddingHorizontal: 20, paddingBottom: 20, backgroundColor: colors.bg },
  face: { marginBottom: 16 },
  say: { marginBottom: 8 },
});
