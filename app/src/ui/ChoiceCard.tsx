// A choice on the first screen: a filled rounded card with a small sign on the left, the name and a line on what it
// does, and 「›」 (spec review-screens 1). The names alone did not say what the buttons do (2026-11-07 user). The
// sign has no box behind it (user); an emoji keeps its own colours, a plain sign such as ↻ is drawn white.
import { Pressable, StyleSheet, Text, View } from "react-native";

import { keepWords } from "./keepWords";
import { colors } from "./theme";

// `iconSize`: a plain sign such as ↻ draws smaller than an emoji at the same size, so it may ask for more
type Props = { icon: string; iconSize?: number; title: string; line: string; color: string; onPress: () => void };

export function ChoiceCard({ icon, iconSize = 26, title, line, color, onPress }: Props) {
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={`${title}. ${line}`}
      onPress={onPress}
      style={({ pressed }) => [styles.card, { backgroundColor: color }, pressed && styles.pressed]}
    >
      <Text style={[styles.icon, { fontSize: iconSize }]}>{icon}</Text>
      <View style={styles.body}>
        <Text style={styles.title}>{keepWords(title)}</Text>
        <Text style={styles.line}>{keepWords(line)}</Text>
      </View>
      <Text style={styles.chevron}>›</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  card: { borderRadius: 14, paddingVertical: 14, paddingHorizontal: 14, flexDirection: "row", alignItems: "center" },
  pressed: { opacity: 0.7 },
  icon: { width: 36, textAlign: "center", fontWeight: "700", color: colors.onColor, marginRight: 10 },
  body: { flex: 1 },
  title: { fontSize: 18, fontWeight: "600", color: colors.onColor, lineHeight: 24 },
  line: { fontSize: 14, color: colors.onColorSub, lineHeight: 20, marginTop: 3 },
  chevron: { fontSize: 24, color: colors.onColorSub, marginLeft: 8 },
});
