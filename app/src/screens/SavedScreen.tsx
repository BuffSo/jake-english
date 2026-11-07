// 「모아 둔 문장」: the saved sentences, newest first; practise one or all of them (spec review-practice 6)
import { useEffect, useRef, useState, type Dispatch } from "react";
import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";

import { api } from "../api";
import type { Roleplay, SavedItem } from "../api/types";
import { createGate } from "../flow/gate";
import { dayKo } from "../flow/review";
import type { Action } from "../flow/state";
import { BackButton, useBackKey } from "../ui/BackButton";
import { Button } from "../ui/Button";
import { InRowButton } from "../ui/InRowButton";
import { colors, top } from "../ui/theme";
import { useSaved } from "../ui/useSaved";
import { messageOf, styles as common, Waiting } from "./common";

export function SavedScreen({ dispatch }: { dispatch: Dispatch<Action> }) {
  const saved = useSaved();
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const gate = useRef(createGate()).current; // one start at a time: a double tap must not start twice
  const mounted = useRef(true);
  const back = () => dispatch({ type: "back" });
  useBackKey(back);
  useEffect(() => {
    saved.refresh();
    return () => {
      mounted.current = false;
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps
  const items = saved.items();

  // the lines come from their own roleplays, each asked for once (spec 7)
  const start = (chosen: SavedItem[]) =>
    gate.run(async () => {
      setStarting(true);
      setError(null);
      try {
        const ids = [...new Set(chosen.map((i) => i.rp_id))];
        const got = new Map<string, Roleplay>();
        for (const id of ids) got.set(id, await api.getRoleplay(id));
        if (mounted.current) dispatch({ type: "startSaved", runs: chosen.map((i) => got.get(i.rp_id)!), order: chosen.map((i) => i.idx) });
      } catch (e) {
        if (mounted.current) setError(messageOf(e));
      } finally {
        if (mounted.current) setStarting(false);
      }
    });

  return (
    <View style={styles.wrap}>
      <View style={styles.header}>
        <BackButton onPress={back} />
        <Text style={common.title}>모아 둔 문장</Text>
      </View>
      <ScrollView contentContainerStyle={styles.scroll}>
        {items?.length === 0 && (
          <Text style={[common.sub, styles.empty]}>아직 모아 둔 문장이 없어요. 역할극이나 연습에서 ☆를 누르면 여기에 모여요.</Text>
        )}
        {items?.map((i) => (
          <Pressable
            key={i.key}
            accessibilityRole="button"
            style={({ pressed }) => [styles.row, pressed && styles.pressed]}
            onPress={() => start([i])}
          >
            <View style={styles.top}>
              <Text style={[styles.tag, i.speaker === "ryan" ? styles.ryan : styles.mine]}>{i.speaker === "ryan" ? "라이언" : "나"}</Text>
              {/* not disabled while it is on its way: a second tap would open the practice of the row (final review) */}
              <InRowButton
                label="빼기 ✕"
                onPress={() => saved.toggle(i.rp_id, i.idx, i.text)}
                dim={saved.pending(i.text)}
                textStyle={styles.remove}
              />
            </View>
            <Text style={styles.text}>{i.text}</Text>
            <Text style={common.sub}>
              {i.title_ko} · {dayKo(i.at)}에 모음
            </Text>
          </Pressable>
        ))}
        {items === null && saved.lastError() !== null && (
          <>
            <Text style={common.error}>{messageOf(saved.lastError())}</Text>
            <Button label="다시 시도" onPress={() => saved.refresh()} />
          </>
        )}
        {starting && <Waiting text="준비하고 있어요" />}
        {error && <Text style={common.error}>{error}</Text>}
      </ScrollView>
      {!!items?.length && (
        <View style={styles.controls}>
          <Button label={`처음부터 차례로 연습(${items.length})`} onPress={() => start(items)} disabled={starting} />
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { flex: 1, paddingTop: top, backgroundColor: colors.bg },
  header: { paddingHorizontal: 16, paddingBottom: 8, borderBottomWidth: 1, borderBottomColor: "#E9ECEF" },
  scroll: { padding: 16 },
  row: { paddingVertical: 12, borderBottomWidth: 1, borderBottomColor: "#F1F3F5" },
  pressed: { opacity: 0.6 },
  top: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  tag: { fontSize: 13, color: colors.sub, paddingHorizontal: 6, paddingVertical: 1, borderRadius: 4, overflow: "hidden" },
  ryan: { backgroundColor: colors.ryan },
  mine: { backgroundColor: colors.user, color: colors.primary },
  remove: { fontSize: 14, color: colors.weak },
  text: { fontSize: 18, color: colors.text, lineHeight: 26, marginVertical: 4 },
  empty: { marginTop: 24, textAlign: "center", lineHeight: 22 },
  controls: { padding: 12, borderTopWidth: 1, borderTopColor: "#E9ECEF" },
});
