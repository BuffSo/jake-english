import { useCallback, useEffect, useState } from "react";
import { StyleSheet, Text, View } from "react-native";

import { api } from "../api";
import type { Home, Said } from "../api/types";
import type { SoundQueue } from "../audio/player";
import { homeLines } from "../flow/homeLines";
import { Button } from "../ui/Button";
import { RyanPortrait } from "../ui/RyanFace";
import { colors, top } from "../ui/theme";
import { messageOf, styles as common } from "./common";

type Props = {
  sounds: SoundQueue;
  home: Home | null;
  setHome: (h: Home) => void;
  onRoleplay: () => void;
  onReview: () => void;
};

export function HomeScreen({ sounds, home, setHome, onRoleplay, onReview }: Props) {
  const [error, setError] = useState<string | null>(null);
  // App keeps `home` for as long as the app runs, so having it when this screen opens means Ryan has greeted
  // already and the learner came back, whichever way. Kept as it was at opening: `home` arriving from `load`
  // below must not count as coming back. Coming back, `/home` is not asked again: the fixed lines and their
  // sound names stay the same while the server runs and across restarts.
  const [opened] = useState(home);
  const returning = opened !== null;

  const say = useCallback(
    (lines: Said[]) => {
      sounds.clear();
      for (const l of lines) sounds.enqueue(api.audioSource(l.audio));
    },
    [sounds],
  );

  const load = useCallback(async () => {
    setError(null);
    try {
      const h = await api.getHome();
      setHome(h);
      say(homeLines(h.lines, false));
    } catch (e) {
      setError(messageOf(e));
    }
  }, [say, setHome]);

  useEffect(() => {
    if (opened) say(homeLines(opened.lines, true));
    else load();
  }, [opened, say, load]);

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
          {homeLines(home.lines, returning).map((l) => (
            <Text key={l.audio} style={[common.body, styles.say]}>
              {l.text}
            </Text>
          ))}
          <Button label="상황 역할극" onPress={onRoleplay} />
          {/* new or again: the first screen splits only these two (spec review-practice 1) */}
          <Button label="다시 연습" onPress={onReview} />
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
