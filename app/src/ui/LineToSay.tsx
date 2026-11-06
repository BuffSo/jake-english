// The line the learner is about to say. It starts as plain text; 「읽는 법 보기」 opens the three lines (stressed
// syllables, Korean pronunciation, how to read it) in its place, and the same button closes them
// (spec roleplay-practice 8, 2026-11-06: 「처음 보여 주는 문장은 평범하게」).
import { Pressable, StyleSheet, Text, View } from "react-native";

import type { ThreeLine } from "../api/types";
import { notesView } from "./notesView";
import { colors } from "./theme";
import { ThreeLineView } from "./ThreeLine";

type Props = { text: string; three: ThreeLine | "loading" | null; open: boolean; onToggle: () => void };

export function LineToSay({ text, three, open, onToggle }: Props) {
  const view = notesView(three, open);
  return (
    <View style={styles.wrap}>
      {view === "open" && three && three !== "loading" ? (
        <ThreeLineView three={three} />
      ) : (
        <Text style={styles.text}>{text}</Text>
      )}
      {view === "loading" && <Text style={styles.sub}>세 줄을 만들고 있어요…</Text>}
      {view !== "plain" && (
        <Pressable onPress={onToggle} hitSlop={8} style={styles.toggle}>
          <Text style={styles.toggleText}>{view === "closed" ? "읽는 법 보기 ›" : "읽는 법 접기"}</Text>
        </Pressable>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {}, // inside the 「내 차례」 bubble, which has its own padding
  text: { fontSize: 22, color: colors.text, lineHeight: 30 },
  sub: { fontSize: 15, color: colors.sub, marginTop: 4 },
  toggle: { alignSelf: "flex-start", marginTop: 6 },
  toggleText: { fontSize: 15, color: colors.primary, fontWeight: "600" },
});
