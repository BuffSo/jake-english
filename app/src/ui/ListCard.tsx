// One row of a list as a gray rounded card, with 「›」 at the end (spec review-screens 3, 4, 5). The past situations,
// the saved sentences (no 「›」: they start a practice, not another screen) and the situation list share it, so the
// lists look alike. The rows used to be plain text with a line under each, which looked bare (2026-11-07 user).
import type { ReactNode } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";

import { colors } from "./theme";

type Props = { onPress: () => void; children: ReactNode; chevron?: boolean };

export function ListCard({ onPress, children, chevron = true }: Props) {
  return (
    <Pressable
      accessibilityRole="button"
      onPress={onPress}
      style={({ pressed }) => [styles.card, pressed && styles.pressed]}
    >
      <View style={styles.body}>{children}</View>
      {chevron && <Text style={styles.chevron}>›</Text>}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.ryan,
    borderRadius: 12,
    paddingVertical: 14,
    paddingHorizontal: 16,
    marginBottom: 8,
    flexDirection: "row",
    alignItems: "center",
  },
  pressed: { opacity: 0.6 },
  body: { flex: 1 },
  chevron: { fontSize: 22, color: colors.weak, marginLeft: 8 },
});
