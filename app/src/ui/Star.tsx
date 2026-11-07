// 「☆ 모아 두기」 / 「★ 모아 둠」 on a line, and the small ★ a folded line keeps (spec review-practice 5). While the
// change is on its way it dims; the saved store ignores the tap then.
import { StyleSheet, Text } from "react-native";

import { InRowButton } from "./InRowButton";
import { colors } from "./theme";

export function StarButton({ saved, onPress, busy }: { saved: boolean; onPress: () => void; busy?: boolean }) {
  return (
    <InRowButton label={saved ? "★ 모아 둠" : "☆ 모아 두기"} onPress={onPress} dim={busy} textStyle={[styles.button, saved && styles.on]} />
  );
}

export function StarMark() {
  return <Text style={styles.mark}>★</Text>;
}

const styles = StyleSheet.create({
  button: { fontSize: 15, color: colors.primary, fontWeight: "600" },
  on: { color: colors.stress },
  mark: { fontSize: 14, color: colors.stress },
});
