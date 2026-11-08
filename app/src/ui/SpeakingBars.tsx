// Ryan's sound mark on a bubble whose words are hidden (spec free-talk-design 9): five bars that move while he speaks
// and stand still after. React Native's own Animated, as in ThinkingFace; nothing new installed.
import { useEffect, useRef } from "react";
import { Animated, StyleSheet, View } from "react-native";

import { colors } from "./theme";

const BARS = 5;
const LOW = 0.35; // the scale a bar rests at; the still bars are drawn at the same heights
const STILL = [0.5, 0.8, 1, 0.7, 0.45]; // how tall each bar stands when still, as a share of the full height
const BEAT = 420; // ms a bar takes up or down; the bars start at different points so they do not move together
const FULL = 22;
const WIDTH = 5;

export function SpeakingBars({ moving }: { moving: boolean }) {
  const scale = useRef(Array.from({ length: BARS }, (_, i) => new Animated.Value(STILL[i]))).current;

  useEffect(() => {
    if (!moving) {
      scale.forEach((v, i) => v.setValue(STILL[i]));
      return;
    }
    const loops = scale.map((v, i) => {
      const up = i % 2 === 0;
      const hi = Animated.timing(v, { toValue: 1, duration: BEAT + i * 60, useNativeDriver: true });
      const lo = Animated.timing(v, { toValue: LOW, duration: BEAT + i * 60, useNativeDriver: true });
      const loop = Animated.loop(Animated.sequence(up ? [hi, lo] : [lo, hi]));
      loop.start();
      return loop;
    });
    return () => loops.forEach((l) => l.stop()); // leaving the bubble or the screen stops them
  }, [moving, scale]);

  return (
    <View style={styles.row} accessible={false}>
      {scale.map((v, i) => (
        <Animated.View key={i} style={[styles.bar, { transform: [{ scaleY: v }] }]} />
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: "row", alignItems: "center", gap: 4, height: FULL },
  bar: { width: WIDTH, height: FULL, borderRadius: WIDTH / 2, backgroundColor: colors.sub },
});
