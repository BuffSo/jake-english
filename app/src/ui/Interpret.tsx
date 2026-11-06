// Sohee's interpretation under a script line: the 「통역」 button and her line, a 「소희」 tag with the Korean, which
// is told apart from the Korean pronunciation line by the tag (spec korean-translation 2). A tap on her line replays
// her voice.
import { Pressable, StyleSheet, Text, View } from "react-native";

import type { KoEntry, KoView } from "../flow/interpret";
import { colors } from "./theme";

export function KoButton({ view, onPress }: { view: KoView; onPress: () => void }) {
  const open = view === "open" || view === "loading";
  return (
    <Pressable onPress={onPress} hitSlop={8}>
      <Text style={styles.button}>{open ? "통역 접기" : "통역 ›"}</Text>
    </Pressable>
  );
}

export function KoLine({ view, entry, onReplay }: { view: KoView; entry: KoEntry | undefined; onReplay: () => void }) {
  if (view === "closed") return null;
  if (view === "loading") return <Text style={styles.note}>소희가 통역하고 있어요…</Text>;
  if (view === "failed" || typeof entry !== "object") return <Text style={styles.note}>지금은 통역할 수 없어요</Text>;
  return (
    <Pressable onPress={onReplay} style={styles.line}>
      <View style={styles.tag}>
        <Text style={styles.tagText}>소희</Text>
      </View>
      <Text style={styles.text}>
        {entry.text}
        <Text style={styles.play}> ▶</Text>
      </Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  button: { fontSize: 15, color: colors.primary, fontWeight: "600" },
  note: { fontSize: 15, color: colors.sub, marginTop: 6 },
  line: { flexDirection: "row", alignItems: "flex-start", gap: 6, marginTop: 6 },
  tag: { backgroundColor: colors.sohee, borderRadius: 8, paddingHorizontal: 6, paddingVertical: 1, marginTop: 2 },
  tagText: { fontSize: 12, fontWeight: "700", color: "#FFFFFF" },
  text: { flexShrink: 1, fontSize: 16, color: colors.text, lineHeight: 23 },
  play: { fontSize: 13, color: colors.sohee },
});
