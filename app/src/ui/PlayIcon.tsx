// The 🔊 of a play button, bouncing while that button's sound plays (spec play-button-feedback 1, draft A picked by
// the user): it swells and shakes once every 0.36 s, like a booming speaker. The words next to it stay as they are.
// Android cannot move a glyph inside a Text, so the 🔊 is drawn on its own next to the words.
import { useEffect, useRef } from "react";
import { Animated, Easing, StyleSheet, Text, View, type StyleProp, type TextStyle } from "react-native";

const BOUNCE_MS = 360;

export function PlayIcon({ on, style }: { on: boolean; style?: StyleProp<TextStyle> }) {
  const v = useRef(new Animated.Value(0)).current;
  useEffect(() => {
    if (!on) return;
    const loop = Animated.loop(Animated.timing(v, { toValue: 1, duration: BOUNCE_MS, easing: Easing.linear, useNativeDriver: true }));
    loop.start();
    return () => {
      loop.stop();
      v.setValue(0);
    };
  }, [on, v]);
  const scale = v.interpolate({ inputRange: [0, 0.3, 0.6, 1], outputRange: [1, 1.35, 1.1, 1] });
  const rotate = v.interpolate({ inputRange: [0, 0.3, 0.6, 1], outputRange: ["0deg", "-6deg", "4deg", "0deg"] });
  return <Animated.Text style={[style, { transform: [{ scale }, { rotate }] }]}>🔊</Animated.Text>;
}

// 「🔊 <words>」 with the 🔊 drawn apart so it can bounce
export function PlayLabel({ on, label, style }: { on: boolean; label: string; style?: StyleProp<TextStyle> }) {
  return (
    <View style={styles.row}>
      <PlayIcon on={on} style={style} />
      <Text style={style}>{label}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: "row", alignItems: "center", gap: 4 },
});
