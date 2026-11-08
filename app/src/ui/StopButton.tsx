// 「● 말하기 끝」 while recording (spec record-feedback 2): the app's blue button, a slowly blinking red dot in front
// of the words and a thin voice line under them that follows the mic level. Both come only once the mic is on, with
// the start cue, so a red dot means recording. This component redraws every 0.1 s for the line; the roleplay screen
// does not.
import { useEffect, useRef, useState } from "react";
import { Animated, Pressable, StyleSheet, Text, View } from "react-native";

import { SOON_ENDS_MS } from "../config";
import { BUTTON_BORDER, buttonLook } from "./buttonLook";
import { colors } from "./theme";
import { LINE_MIN, voiceShare } from "./voiceLevel";

type Props = {
  live: boolean; // the mic is on
  onLevel: (cb: (db: number | undefined) => void) => () => void;
  onPress: () => void;
};

const BLINK_MS = 700; // half of a slow blink
const LINE = 3; // the voice line's height
const LINE_GAP = 4; // between the words and the line

export function StopButton({ live, onLevel, onPress }: Props) {
  const [share, setShare] = useState(LINE_MIN);
  const blink = useRef(new Animated.Value(1)).current;

  useEffect(() => {
    if (!live) return setShare(LINE_MIN);
    return onLevel((db) => setShare(voiceShare(db)));
  }, [live, onLevel]);

  useEffect(() => {
    if (!live) return;
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(blink, { toValue: 0.3, duration: BLINK_MS, useNativeDriver: true }),
        Animated.timing(blink, { toValue: 1, duration: BLINK_MS, useNativeDriver: true }),
      ]),
    );
    loop.start();
    return () => {
      loop.stop();
      blink.setValue(1);
    };
  }, [live, blink]);

  const look = buttonLook("primary", {});
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel="말하기 끝"
      onPress={onPress}
      style={({ pressed }) => [
        styles.base,
        { backgroundColor: look.background, borderColor: look.border, opacity: buttonLook("primary", { pressed }).opacity },
      ]}
    >
      <View style={styles.words}>
        {/* the red fades to pale pink on a white disc, not to the blue under it, which read as gray-purple on the phone */}
        {live && (
          <View style={styles.dot}>
            <Animated.View style={[styles.dotFill, { opacity: blink }]} />
          </View>
        )}
        <Text style={[styles.label, { color: look.text }]}>말하기 끝</Text>
      </View>
      {/* the line's place is kept while the mic is not on yet, so the button does not change height */}
      <View style={styles.track}>
        {live && <View style={[styles.line, { width: `${Math.round(share * 100)}%` }]} />}
      </View>
    </Pressable>
  );
}

// 「녹음이 곧 끝나요」 above the buttons from 50 s after the mic came on until it stops at 55 s (spec
// record-feedback 2). Redraws once, by itself.
export function SoonEnds({ since }: { since: number | null }) {
  const [soon, setSoon] = useState(false);
  useEffect(() => {
    setSoon(false);
    if (since === null) return;
    const t = setTimeout(() => setSoon(true), Math.max(0, since + SOON_ENDS_MS - Date.now()));
    return () => clearTimeout(t);
  }, [since]);
  return soon ? <Text style={styles.soon}>녹음이 곧 끝나요</Text> : null;
}

// the size of a large `Button` next to it: its padding less the line and its gap, so 「취소」 and this match
const PAD = 14 - BUTTON_BORDER;
const styles = StyleSheet.create({
  base: {
    paddingTop: PAD - (LINE + LINE_GAP) / 2,
    paddingBottom: PAD - (LINE + LINE_GAP) / 2,
    paddingHorizontal: 18 - BUTTON_BORDER,
    borderWidth: BUTTON_BORDER,
    borderRadius: 12,
    alignItems: "center",
    marginVertical: 4,
    flexGrow: 1,
    flexBasis: 0,
  },
  words: { flexDirection: "row", alignItems: "center", gap: 8 },
  label: { fontSize: 18, fontWeight: "600" },
  dot: { width: 14, height: 14, borderRadius: 7, backgroundColor: colors.onColor, alignItems: "center", justifyContent: "center" },
  dotFill: { width: 10, height: 10, borderRadius: 5, backgroundColor: colors.recDot },
  track: { width: "55%", height: LINE, marginTop: LINE_GAP, alignItems: "center" },
  line: { height: LINE, borderRadius: LINE / 2, backgroundColor: colors.voiceLine },
  soon: { textAlign: "center", color: colors.sub, fontSize: 15, marginBottom: 2 },
});
