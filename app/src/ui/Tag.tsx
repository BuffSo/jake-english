// A small label in front of a line that says what the line is: 「발음」 on the Korean pronunciation line, 「통역」 on
// Sohee's interpretation (spec three-line-listen 1, 2). One shape for both, so the two read as a pair; only the color
// differs.
import { StyleSheet, Text, View, type StyleProp, type ViewStyle } from "react-native";

import { colors } from "./theme";

export function Tag({ label, color, style }: { label: string; color: string; style?: StyleProp<ViewStyle> }) {
  return (
    <View style={[styles.tag, { backgroundColor: color }, style]}>
      <Text style={styles.text}>{label}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  tag: { borderRadius: 8, paddingHorizontal: 6, paddingVertical: 1, marginTop: 3 },
  text: { fontSize: 12, fontWeight: "700", color: colors.onColor },
});
