// Sohee's interpretation under a script line: the 「통역」 button and her line, a 「통역」 tag with the Korean. The tag
// has the 「발음」 tag's shape in her green, so the two Korean lines are told apart at a glance; it said 「소희」
// until the user found the name out of place on a subtitle (spec three-line-listen 2). A tap on her line replays her
// voice.
import { Pressable, StyleSheet, Text } from "react-native";

import type { KoEntry, KoView } from "../flow/interpret";
import { keepWords } from "./keepWords";
import { PlayIcon } from "./PlayIcon";
import { Tag } from "./Tag";
import { colors } from "./theme";

// What a line hands to its 「통역」 button and Sohee's line
// playing: her voice plays now, so her 🔊 bounces (spec play-button-feedback 2)
export type KoProps = { view: KoView; entry: KoEntry | undefined; onToggle: () => void; onReplay: () => void; playing?: boolean };

export function KoButton({ view, onPress }: { view: KoView; onPress: () => void }) {
  const open = view === "open" || view === "loading";
  return (
    <Pressable onPress={onPress} hitSlop={8}>
      <Text style={styles.button}>{open ? "통역 접기" : "통역 ›"}</Text>
    </Pressable>
  );
}

export function KoLine(props: { view: KoView; entry: KoEntry | undefined; onReplay: () => void; playing?: boolean }) {
  const { view, entry, onReplay, playing } = props;
  if (view === "closed") return null;
  if (view === "loading") return <Text style={styles.note}>{keepWords("통역하고 있어요…")}</Text>;
  if (view === "failed" || typeof entry !== "object") return <Text style={styles.note}>지금은 통역할 수 없어요</Text>;
  return (
    <Pressable onPress={onReplay} style={styles.line}>
      <Tag label="통역" color={colors.sohee} />
      <Text style={styles.text}>{keepWords(entry.text)}</Text>
      {/* drawn beside the words, at their last line, so it can bounce: Android cannot move a glyph inside a Text. It
          used to sit in the text after a no-break space, so it never stood alone on a line (spec play-button-feedback 2) */}
      <PlayIcon on={!!playing} style={styles.play} />
    </Pressable>
  );
}

const styles = StyleSheet.create({
  button: { fontSize: 15, color: colors.primary, fontWeight: "600" },
  note: { fontSize: 15, color: colors.sub, marginTop: 6 },
  line: { flexDirection: "row", alignItems: "flex-start", gap: 6, marginTop: 6 },
  // her own color too, not the pronunciation line's (spec korean-translation 2, final review)
  text: { flexShrink: 1, fontSize: 16, color: colors.soheeText, lineHeight: 23 },
  play: { fontSize: 13, color: colors.sohee, alignSelf: "flex-end", marginBottom: 3 },
});
