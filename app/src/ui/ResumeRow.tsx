// The row on the topic step that resumes the newest conversation (spec
// docs/superpowers/specs/2026-11-08-resume-roleplay-design.md 4): the look of a secondary button, white with a blue
// border (button guide), in two lines. The first screen has no such card: 「메인이 복잡해진다」 (2026-11-08 user).
import { Pressable, StyleSheet, Text, View } from "react-native";

import { BUTTON_BORDER } from "./buttonLook";
import { keepWords } from "./keepWords";
import { colors } from "./theme";

const TITLE = "하던 대화 이어 하기";
// ▶ with the text selector: without it Android may draw a coloured emoji box
const PLAY = "\u25B6\uFE0E";

type Props = { line: string; onPress: () => void };

export function ResumeRow({ line, onPress }: Props) {
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={`${TITLE}. ${line}`}
      onPress={onPress}
      style={({ pressed }) => [styles.row, pressed && styles.pressed]}
    >
      <Text style={styles.play}>{PLAY}</Text>
      <View style={styles.body}>
        <Text style={styles.title}>{TITLE}</Text>
        <Text style={styles.line}>{keepWords(line)}</Text>
      </View>
      <Text style={styles.chevron}>›</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: colors.bg,
    borderColor: colors.primary,
    borderWidth: BUTTON_BORDER,
    borderRadius: 12,
    paddingVertical: 10 - BUTTON_BORDER,
    paddingHorizontal: 14 - BUTTON_BORDER,
  },
  // pressed: a little dim, like the buttons (button guide)
  pressed: { opacity: 0.7 },
  play: { width: 24, textAlign: "center", fontSize: 16, color: colors.primary, marginRight: 6 },
  body: { flex: 1 },
  title: { fontSize: 16, fontWeight: "600", color: colors.primary, lineHeight: 22 },
  line: { fontSize: 14, color: colors.sub, lineHeight: 20 },
  chevron: { fontSize: 22, color: colors.primary, marginLeft: 8 },
});
