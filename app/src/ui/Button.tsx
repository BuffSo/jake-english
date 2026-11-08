import { Pressable, StyleSheet, Text, View } from "react-native";

import { BUTTON_BORDER, buttonLook, type ButtonKind } from "./buttonLook";
import { PlayIcon } from "./PlayIcon";

// kind: primary is what to do first on the screen or in the row, secondary anything else; a disabled one is gray
// whatever its kind (spec button-colors 1, `buttonLook`)
// grow: fills what is left of its row, next to a button as wide as its words (spec record-cancel-skip 4)
// playing: a play button, 「🔊 <label>」 with its 🔊 bouncing while true (spec play-button-feedback 1)
type Props = {
  label: string;
  onPress: () => void;
  disabled?: boolean;
  kind?: ButtonKind;
  small?: boolean;
  grow?: boolean;
  playing?: boolean;
};

export function Button({ label, onPress, disabled, kind = "primary", small, grow, playing }: Props) {
  const text = [styles.label, { color: buttonLook(kind, { disabled }).text }, small && styles.smallLabel];
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
      {playing === undefined ? (
        <Text style={text}>{label}</Text>
      ) : (
        <View style={styles.play}>
          <PlayIcon on={playing} style={text} />
          <Text style={text}>{label}</Text>
        </View>
      )}
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
  play: { flexDirection: "row", alignItems: "center", gap: 4 },
});
