import { Pressable, StyleSheet, Text } from "react-native";

import { BUTTON_BORDER, buttonLook, type ButtonKind } from "./buttonLook";

// kind: primary is what to do first on the screen or in the row, secondary anything else; a disabled one is gray
// whatever its kind (spec button-colors 1, `buttonLook`)
// grow: fills what is left of its row, next to a button as wide as its words (spec record-cancel-skip 4)
type Props = { label: string; onPress: () => void; disabled?: boolean; kind?: ButtonKind; small?: boolean; grow?: boolean };

export function Button({ label, onPress, disabled, kind = "primary", small, grow }: Props) {
  return (
    <Pressable
      accessibilityRole="button"
      onPress={onPress}
      disabled={disabled}
      style={({ pressed }) => {
        const look = buttonLook(kind, { disabled, pressed });
        return [
          styles.base,
          { backgroundColor: look.background, borderColor: look.border, opacity: look.opacity },
          small && styles.small,
          grow && styles.grow,
        ];
      }}
    >
      <Text style={[styles.label, { color: buttonLook(kind, { disabled }).text }, small && styles.smallLabel]}>{label}</Text>
    </Pressable>
  );
}

// The padding is the old one less the border, so the buttons keep their size (14/18 and 8/12 before the border)
const styles = StyleSheet.create({
  base: {
    paddingVertical: 14 - BUTTON_BORDER,
    paddingHorizontal: 18 - BUTTON_BORDER,
    borderWidth: BUTTON_BORDER,
    borderRadius: 12,
    alignItems: "center",
    marginVertical: 4,
  },
  small: { paddingVertical: 8 - BUTTON_BORDER, paddingHorizontal: 12 - BUTTON_BORDER },
  grow: { flexGrow: 1, flexBasis: 0 },
  label: { fontSize: 18, fontWeight: "600" },
  smallLabel: { fontSize: 15 },
});
