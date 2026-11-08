// 「소희 찬스」 (spec free-talk-design 9 「버튼」): above the 「🎤 말하기」 row, on the left. Sohee's face and the words
// in her green border on white, outside the three looks of `buttonLook` since it is hers alone. While it cannot be
// pressed it takes the fixed gray every button takes then (spec button-colors 1), her face faded. With no face (a
// server from before the Sohee chance, or a picture that failed to load) the words alone.
import { Image, Pressable, StyleSheet, Text } from "react-native";

import { api } from "../api";
import { BUTTON_BORDER } from "./buttonLook";
import { usePicture } from "./picture";
import { colors } from "./theme";

type Props = { face?: string; on: boolean; onPress: () => void };

export function SoheeChanceButton({ face, on, onPress }: Props) {
  const [shown, onError] = usePicture(face);
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityState={{ disabled: !on }}
      onPress={onPress}
      disabled={!on}
      style={({ pressed }) => [styles.button, on ? styles.on : styles.off, !shown && styles.noFace, pressed && styles.pressed]}
    >
      {shown && <Image source={api.imageSource(shown)} onError={onError} style={[styles.face, !on && styles.faded]} />}
      <Text style={[styles.label, { color: on ? colors.soheeText : colors.offText }]}>소희 찬스</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  button: {
    flexDirection: "row",
    alignItems: "center",
    alignSelf: "flex-start",
    gap: 6,
    borderWidth: BUTTON_BORDER,
    borderRadius: 32,
    paddingVertical: 4,
    paddingLeft: 4,
    paddingRight: 13,
    marginBottom: 8,
  },
  on: { backgroundColor: colors.bg, borderColor: colors.sohee },
  off: { backgroundColor: colors.off, borderColor: colors.off },
  noFace: { paddingVertical: 8, paddingLeft: 13 },
  pressed: { opacity: 0.7 },
  face: { width: 32, height: 32, borderRadius: 16, backgroundColor: colors.ryan },
  faded: { opacity: 0.5 },
  label: { fontSize: 15, fontWeight: "700" },
});
