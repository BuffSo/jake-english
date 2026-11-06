// The line the learner is about to say. It starts as plain text; 「읽는 법 보기」 opens the three lines (stressed
// syllables, Korean pronunciation, how to read it) in its place, and the same button closes them
// (spec roleplay-practice 8, 2026-11-06: 「처음 보여 주는 문장은 평범하게」). 「통역」 opens Sohee's Korean under them
// (spec korean-translation 2).
import { Pressable, StyleSheet, Text, View } from "react-native";

import type { ThreeLine } from "../api/types";
import type { KoEntry, KoView } from "../flow/interpret";
import { KoButton, KoLine } from "./Interpret";
import { notesView } from "./notesView";
import { colors } from "./theme";
import { ThreeLineView } from "./ThreeLine";

type Ko = { view: KoView; entry: KoEntry | undefined; onToggle: () => void; onReplay: () => void };
type Props = { text: string; three: ThreeLine | "loading" | null; open: boolean; onToggle: () => void; ko: Ko };

export function LineToSay({ text, three, open, onToggle, ko }: Props) {
  const view = notesView(three, open);
  return (
    <View style={styles.wrap}>
      {view === "open" && three && three !== "loading" ? (
        <ThreeLineView three={three} bare />
      ) : (
        <Text style={styles.text}>{text}</Text>
      )}
      {view === "loading" && <Text style={styles.sub}>세 줄을 만들고 있어요…</Text>}
      <KoLine view={ko.view} entry={ko.entry} onReplay={ko.onReplay} />
      <View style={styles.toggles}>
        {view !== "plain" && (
          <Pressable onPress={onToggle} hitSlop={8}>
            <Text style={styles.toggleText}>{view === "closed" ? "읽는 법 보기 ›" : "읽는 법 접기"}</Text>
          </Pressable>
        )}
        <KoButton view={ko.view} onPress={ko.onToggle} />
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {}, // inside the 「내 차례」 bubble, which has its own padding
  text: { fontSize: 22, color: colors.text, lineHeight: 30 },
  sub: { fontSize: 15, color: colors.sub, marginTop: 4 },
  toggles: { flexDirection: "row", flexWrap: "wrap", gap: 16, marginTop: 6 },
  toggleText: { fontSize: 15, color: colors.primary, fontWeight: "600" },
});
