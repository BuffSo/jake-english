// 「☆ 모아 두기」 / 「★ 모아 둠」 on a line, and the small ★ a folded line keeps (spec review-practice 5)
import { Pressable, StyleSheet, Text } from "react-native";

import { colors } from "./theme";

export function StarButton({ saved, onPress, disabled }: { saved: boolean; onPress: () => void; disabled?: boolean }) {
  return (
    <Pressable onPress={onPress} disabled={disabled} hitSlop={8} accessibilityRole="button">
      <Text style={[styles.button, saved && styles.on, disabled && styles.off]}>{saved ? "★ 모아 둠" : "☆ 모아 두기"}</Text>
    </Pressable>
  );
}

export function StarMark() {
  return <Text style={styles.mark}>★</Text>;
}

const styles = StyleSheet.create({
  button: { fontSize: 15, color: colors.primary, fontWeight: "600" },
  on: { color: colors.stress },
  off: { opacity: 0.4 },
  mark: { fontSize: 14, color: colors.stress },
});
