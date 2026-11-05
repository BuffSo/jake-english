import { Pressable, StyleSheet, Text } from "react-native";

import { colors } from "./theme";

type Props = { label: string; onPress: () => void; disabled?: boolean; kind?: "primary" | "plain"; small?: boolean };

export function Button({ label, onPress, disabled, kind = "primary", small }: Props) {
  return (
    <Pressable
      accessibilityRole="button"
      onPress={onPress}
      disabled={disabled}
      style={({ pressed }) => [
        styles.base,
        kind === "primary" ? styles.primary : styles.plain,
        small && styles.small,
        (disabled || pressed) && styles.dim,
      ]}
    >
      <Text style={[styles.label, kind === "plain" && styles.plainLabel, small && styles.smallLabel]}>{label}</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  base: { paddingVertical: 14, paddingHorizontal: 18, borderRadius: 12, alignItems: "center", marginVertical: 4 },
  primary: { backgroundColor: colors.primary },
  plain: { backgroundColor: colors.ryan },
  small: { paddingVertical: 8, paddingHorizontal: 12 },
  dim: { opacity: 0.5 },
  label: { color: "#FFFFFF", fontSize: 18, fontWeight: "600" },
  plainLabel: { color: colors.text },
  smallLabel: { fontSize: 15 },
});
