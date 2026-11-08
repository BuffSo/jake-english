// Sohee's bubble under Ryan's line in the free talk (spec free-talk-design 9 「소희 말풍선」, 「2단계」): it pops up from
// below when 「소희 찬스」 is tapped and stays in the talk, also while I record. While she thinks, her two thinking
// faces and 「소희가 생각하고 있어요」; then her whisper face with the meaning in Korean, 「이렇게 시작해 보세요.」 and the
// English openers, whose 🔊 is Ryan's English voice (her Korean voice would make an accent the model). Step 2 adds the
// full sentence, its 🔊 and its reading notes. A tap on her Korean plays her voice again.
//
// Once Ryan has a newer reply, the bubble folds to 「🤫 소희 찬스」 (「· 전체 문장 봄」 after step 2) and opens on a tap.
// Without pictures (a server from before the Sohee chance, or one that failed to load) the words alone.
import { useEffect, useRef } from "react";
import { Animated, Image, Pressable, StyleSheet, Text, View } from "react-native";

import { api } from "../api";
import type { ThreeLine } from "../api/types";
import { HINT_FAILED, hintSoundTag, soheeFullTag, soheeTag, type Chance } from "../flow/soheeChance";
import { InRowButton } from "./InRowButton";
import { keepWords } from "./keepWords";
import { usePicture } from "./picture";
import { PlayIcon } from "./PlayIcon";
import { colors } from "./theme";
import { Dots, ThinkingFace } from "./ThinkingFace";
import { ThreeLineView } from "./ThreeLine";

const FACE = 48;
const FOLDED_FACE = 32;

type Props = {
  chance: Chance;
  open: boolean; // its line is Ryan's latest reply, or a tap opened it
  latest: boolean; // its line is Ryan's latest reply: step 2 is offered and it does not fold
  faces?: { face: string; whisper: string };
  canFull: boolean; // 「전체 문장 보기」 can be pressed now
  listenOk: boolean; // a 🔊 may play now (my turn); the buttons only dim otherwise
  playingTag: string | null;
  three: ThreeLine | "loading" | undefined; // the full sentence's reading notes
  notesOpen: boolean;
  onToggle: () => void; // folds or opens an older one
  onReplay: (which: "hint" | "full") => void;
  onSound: (n: number) => void; // Ryan's model of opener `n`, or of the full sentence (`n` = the openers' count)
  onFull: () => void;
  onNotes: () => void;
};

export function SoheeHint(p: Props) {
  const { chance: c, faces } = p;
  // from below, with a little bounce (spec 9, AI judgment); once, when the bubble first shows
  const rise = useRef(new Animated.Value(0)).current;
  useEffect(() => {
    Animated.spring(rise, { toValue: 1, friction: 6, tension: 80, useNativeDriver: true }).start();
  }, [rise]);
  const motion = {
    opacity: rise.interpolate({ inputRange: [0, 1], outputRange: [0, 1], extrapolate: "clamp" }),
    transform: [{ translateY: rise.interpolate({ inputRange: [0, 1], outputRange: [24, 0] }) }],
  };

  if (!p.open) {
    return (
      <Animated.View style={[styles.wrap, motion]}>
        <Pressable onPress={p.onToggle} style={styles.row} accessibilityRole="button">
          <Face path={faces?.face} size={FOLDED_FACE} />
          <View style={[styles.body, styles.folded]}>
            <Text style={styles.foldedText}>{keepWords(c.step === "full" ? "🤫 소희 찬스 · 전체 문장 봄" : "🤫 소희 찬스")}</Text>
          </View>
        </Pressable>
      </Animated.View>
    );
  }

  if (c.step === "thinking") {
    return (
      <Animated.View style={[styles.wrap, styles.row, motion]}>
        {/* her two thinking faces cross-fade, at once: the bubble itself shows at the tap */}
        <ThinkingFace who="sohee" size={FACE} after={0} fallback={<Face path={faces?.face} size={FACE} />} />
        <View style={[styles.body, styles.thinking]}>
          <Text style={styles.thinkingText}>{keepWords("소희가 생각하고 있어요")}</Text>
          <Dots />
        </View>
      </Animated.View>
    );
  }

  if (c.step === "failed") {
    return (
      <Animated.View style={[styles.wrap, styles.row, motion]}>
        <Face path={faces?.face} size={FACE} />
        <View style={styles.body}>
          <Text style={styles.note}>{keepWords(HINT_FAILED)}</Text>
        </View>
      </Animated.View>
    );
  }

  const { hint } = c;
  const n = hint.starters.length; // the full sentence's sound comes after the openers'
  return (
    <Animated.View style={[styles.wrap, styles.row, motion]}>
      <Face path={faces?.whisper} size={FACE} />
      <View style={styles.body}>
        {/* an older one folds again from its head */}
        <Pressable onPress={p.latest ? undefined : p.onToggle} disabled={p.latest} hitSlop={8}>
          <Text style={styles.head}>{keepWords("🤫 소희 찬스")}</Text>
        </Pressable>
        <Pressable onPress={() => p.onReplay("hint")} style={styles.said}>
          <PlayIcon on={p.playingTag === soheeTag(c.idx)} style={styles.play} />
          <View style={styles.saidText}>
            <Text style={styles.meaning}>{keepWords(hint.meaning_ko)}</Text>
            <Text style={styles.meaning}>{keepWords("이렇게 시작해 보세요.")}</Text>
          </View>
        </Pressable>
        <View style={styles.chips}>
          {hint.starters.map((s, i) => (
            <Pressable key={i} onPress={() => p.onSound(i)} style={[styles.chip, !p.listenOk && styles.dim]} hitSlop={4}>
              <PlayIcon on={p.playingTag === hintSoundTag(c.idx, i)} style={styles.chipPlay} />
              <Text style={styles.chipText}>{s}</Text>
            </Pressable>
          ))}
        </View>
        {c.step === "hint" && c.fullFailed && <Text style={styles.note}>{keepWords(HINT_FAILED)}</Text>}
        {/* step 2 is for the line Ryan waits an answer to; an older one keeps only what it showed */}
        {p.latest && (c.step === "hint" || c.step === "fullLoading") && (
          <InRowButton
            label={keepWords("그래도 어려우면 전체 문장 보기 ›")}
            onPress={p.onFull}
            dim={!p.canFull}
            textStyle={styles.fullLink}
          />
        )}
        {c.step === "full" && (
          <>
            <Pressable onPress={() => p.onReplay("full")} style={styles.said}>
              <PlayIcon on={p.playingTag === soheeFullTag(c.idx)} style={styles.play} />
              <Text style={[styles.meaning, styles.saidText]}>{keepWords("이렇게 말해 봐요. 낱말을 바꿔 말해도 돼요.")}</Text>
            </Pressable>
            <View style={styles.full}>
              <Text style={styles.fullText}>{c.full.text}</Text>
              <View style={styles.links}>
                <InRowButton
                  label="듣기"
                  playing={p.playingTag === hintSoundTag(c.idx, n)}
                  onPress={() => p.onSound(n)}
                  dim={!p.listenOk}
                  textStyle={styles.link}
                />
                <Pressable onPress={p.onNotes} hitSlop={8}>
                  <Text style={styles.link}>{p.notesOpen ? "읽는 법 접기" : "읽는 법 보기 ›"}</Text>
                </Pressable>
              </View>
              {p.notesOpen && p.three === "loading" && <Text style={styles.note}>{keepWords("세 줄을 만들고 있어요…")}</Text>}
              {p.notesOpen && p.three && p.three !== "loading" && <ThreeLineView three={p.three} bare />}
            </View>
          </>
        )}
      </View>
    </Animated.View>
  );
}

// her face in a green ring; nothing without a picture, or once it failed to load (spec 9 「그림」: the words alone)
function Face({ path, size }: { path?: string; size: number }) {
  const [shown, onError] = usePicture(path);
  if (!shown) return null;
  return (
    <Image
      source={api.imageSource(shown)}
      onError={onError}
      style={[styles.face, { width: size, height: size, borderRadius: size / 2 }]}
    />
  );
}

const styles = StyleSheet.create({
  wrap: { alignSelf: "flex-start", maxWidth: "96%", marginVertical: 5 },
  row: { flexDirection: "row", alignItems: "flex-start", gap: 8 },
  face: { borderWidth: 2, borderColor: colors.sohee, backgroundColor: colors.ryan },
  body: { flexShrink: 1, backgroundColor: colors.soheeBg, borderRadius: 14, paddingVertical: 10, paddingHorizontal: 12 },
  thinking: { backgroundColor: colors.ryan },
  thinkingText: { fontSize: 16, color: colors.sub },
  folded: { paddingVertical: 6 },
  foldedText: { fontSize: 14, fontWeight: "700", color: colors.soheeText },
  head: { fontSize: 13, fontWeight: "700", color: colors.sohee },
  said: { flexDirection: "row", alignItems: "flex-start", gap: 6, marginTop: 4 },
  saidText: { flexShrink: 1 },
  play: { fontSize: 13, color: colors.sohee, marginTop: 4 },
  meaning: { fontSize: 16, color: colors.soheeText, lineHeight: 24 },
  chips: { flexDirection: "row", flexWrap: "wrap", gap: 6, marginTop: 8 },
  chip: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
    backgroundColor: colors.bg,
    borderWidth: 1,
    borderColor: colors.soheeLine,
    borderRadius: 10,
    paddingVertical: 4,
    paddingHorizontal: 9,
  },
  chipPlay: { fontSize: 13, color: colors.primary },
  chipText: { fontSize: 16, color: colors.text },
  dim: { opacity: 0.4 },
  fullLink: { fontSize: 15, fontWeight: "700", color: colors.sohee, marginTop: 10 },
  full: { backgroundColor: colors.bg, borderWidth: 1, borderColor: colors.soheeLine, borderRadius: 11, padding: 10, marginTop: 6 },
  fullText: { fontSize: 20, color: colors.text, lineHeight: 27 },
  links: { flexDirection: "row", flexWrap: "wrap", alignItems: "center", columnGap: 16, rowGap: 12, marginTop: 6 },
  link: { fontSize: 15, color: colors.primary, fontWeight: "600" },
  note: { fontSize: 15, color: colors.sub, marginTop: 6 },
});
