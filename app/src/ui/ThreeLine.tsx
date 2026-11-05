// Three lines: English, Korean pronunciation, how to read it. Yellow = strong, small gray = weak.
import { StyleSheet, Text, View } from "react-native";

import type { ThreeLine } from "../api/types";
import { colors } from "./theme";
import { englishSegments, koreanSegments, readingSegments, type Seg } from "./threeLineSegments";

function Pieces({ groups, size }: { groups: Seg[][]; size: number }) {
  return (
    <>
      {groups.map((g, i) => (
        <Text key={i}>
          {i > 0 ? " " : ""}
          {g.map((s, j) => (
            <Text
              key={j}
              style={
                s.style === "strong"
                  ? { backgroundColor: colors.strong }
                  : s.style === "weak"
                    ? { fontSize: size * 0.78, color: colors.weak }
                    : undefined
              }
            >
              {s.text}
            </Text>
          ))}
        </Text>
      ))}
    </>
  );
}

export function ThreeLineView({ three }: { three: ThreeLine }) {
  const korean = koreanSegments(three);
  const reading = readingSegments(three.reading);
  return (
    <View style={styles.card}>
      <Text style={styles.en}>
        <Pieces groups={englishSegments(three)} size={24} />
      </Text>
      {korean.length > 0 && (
        <Text style={styles.ko}>
          <Pieces groups={korean} size={20} />
        </Text>
      )}
      {reading.length > 0 && <Text style={styles.reading}>{reading[0].text}</Text>}
    </View>
  );
}

const styles = StyleSheet.create({
  card: { backgroundColor: colors.user, borderRadius: 14, padding: 14, marginVertical: 6 },
  en: { fontSize: 24, color: colors.text, lineHeight: 34 },
  ko: { fontSize: 20, color: colors.text, marginTop: 6, lineHeight: 30 },
  reading: { fontSize: 16, color: colors.sub, marginTop: 8, lineHeight: 23 },
});
