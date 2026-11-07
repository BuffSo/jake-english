// A bubble with the name of who says it above it, on that person's side (`SPEAKERS`, 2026-11-06 user)
import type { ReactNode } from "react";
import { StyleSheet, Text, View, type LayoutChangeEvent } from "react-native";

import { SPEAKERS, type Part } from "./speakers";
import { colors } from "./theme";

export function Named({ part, children, onLayout }: { part: Part; children: ReactNode; onLayout?: (e: LayoutChangeEvent) => void }) {
  const s = SPEAKERS[part];
  return (
    <View style={[styles.wrap, s.side === "right" ? styles.right : styles.left]} onLayout={onLayout}>
      <Text style={[styles.name, part === "now" && styles.now]}>{s.name}</Text>
      {children}
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { marginTop: 6 },
  left: { alignItems: "flex-start" },
  right: { alignItems: "flex-end" },
  name: { fontSize: 13, color: colors.sub, marginHorizontal: 4 },
  now: { fontSize: 14, color: colors.primary, fontWeight: "700" },
});
