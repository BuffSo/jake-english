// Three lines: English, Korean pronunciation, how to read it. Bold dark orange = strong, small gray = weak.
// Strong used to be a yellow fill; on the light blue card it looked blocky, so the user chose colored bold text
// (2026-11-06). The Korean line is smaller, blue-gray and tagged 「발음」, and the Korean sounds in the reading line
// share its color: the two big lines read as one block before (spec three-line-listen 1, 2026-11-08 user).
import { StyleSheet, Text, View } from "react-native";

import type { ThreeLine } from "../api/types";
import { keepPieces } from "./keepWords";
import { Tag } from "./Tag";
import { colors } from "./theme";
import { englishSegments, koreanSegments, readingSegments, type Seg } from "./threeLineSegments";

// A group is one word in pieces (the stressed letter is its own `Text`), kept whole across them (`keepPieces`)
function Pieces({ groups, size }: { groups: Seg[][]; size: number }) {
  return (
    <>
      {groups.map((g, i) => {
        const texts = keepPieces(g.map((s) => s.text));
        return (
          <Text key={i}>
            {i > 0 ? " " : ""}
            {g.map((s, j) => (
              <Text
                key={j}
                style={
                  s.style === "strong"
                    ? { color: colors.stress, fontWeight: "800" }
                    : s.style === "weak"
                      ? { fontSize: size * 0.78, color: colors.weak }
                      : undefined
                }
              >
                {texts[j]}
              </Text>
            ))}
          </Text>
        );
      })}
    </>
  );
}

// `bare`: no card of its own, inside the 「내 차례」 bubble, which is the same blue (a card there doubled the padding)
export function ThreeLineView({ three, bare = false }: { three: ThreeLine; bare?: boolean }) {
  const korean = koreanSegments(three);
  const reading = readingSegments(three.reading);
  return (
    <View style={bare ? styles.bare : styles.card}>
      <Text style={styles.en}>
        <Pieces groups={englishSegments(three)} size={24} />
      </Text>
      {korean.length > 0 && (
        <View style={styles.koRow}>
          <Tag label="발음" color={colors.pron} style={styles.koTag} />
          <Text style={styles.ko}>
            <Pieces groups={korean} size={17} />
          </Text>
        </View>
      )}
      {reading.length > 0 && (
        <Text style={styles.reading}>
          {keepPieces(reading.map((s) => s.text)).map((t, i) => (
            <Text key={i} style={reading[i].style === "sound" ? styles.sound : undefined}>
              {t}
            </Text>
          ))}
        </Text>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  card: { backgroundColor: colors.user, borderRadius: 14, padding: 14, marginVertical: 6 },
  bare: { marginVertical: 2 },
  en: { fontSize: 24, color: colors.text, lineHeight: 34 },
  koRow: { flexDirection: "row", alignItems: "flex-start", gap: 6, marginTop: 6 },
  koTag: { marginTop: 4 },
  ko: { flexShrink: 1, fontSize: 17, color: colors.pron, lineHeight: 26 },
  reading: { fontSize: 16, color: colors.sub, marginTop: 8, lineHeight: 23 },
  sound: { color: colors.pron, fontWeight: "700" },
});
