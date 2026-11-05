// The on-screen back button, and the phone's back key doing the same (2026-11-05, user: the key closed the
// app mid-roleplay). The home screen has neither, so there the key is left to Android, which closes the app.
import { useEffect, useRef } from "react";
import { BackHandler, Pressable, StyleSheet, Text } from "react-native";

import { colors, top } from "./theme";

export function useBackKey(onBack: () => void): void {
  const latest = useRef(onBack);
  useEffect(() => {
    latest.current = onBack; // the handler sees this render's state
  });
  useEffect(() => {
    const sub = BackHandler.addEventListener("hardwareBackPress", () => {
      latest.current();
      return true; // handled: Android does not close the app
    });
    return () => sub.remove();
  }, []);
}

type Props = { onPress: () => void; floating?: boolean };

export function BackButton({ onPress, floating }: Props) {
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel="뒤로"
      onPress={onPress}
      hitSlop={12}
      style={({ pressed }) => [styles.base, floating && styles.floating, pressed && styles.dim]}
    >
      <Text style={styles.label}>‹ 뒤로</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  base: { alignSelf: "flex-start", paddingVertical: 6, paddingRight: 12 },
  floating: { position: "absolute", top, left: 16, zIndex: 1 },
  dim: { opacity: 0.5 },
  label: { fontSize: 17, color: colors.primary, fontWeight: "600" },
});
