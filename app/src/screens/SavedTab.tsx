// 「모아 둔 문장」 tab of 「복습하기」: the saved sentences, newest first; practise one or all of them (spec
// review-practice 6, review-screens 4). ★ takes a sentence out after asking: 「빼기 ✕」 went, and a stray tap on ★
// must not lose one (2026-11-07 user).
import { useEffect, useRef, useState, type Dispatch } from "react";
import { Alert, ScrollView, StyleSheet, Text, View } from "react-native";

import { api } from "../api";
import type { Roleplay, SavedItem } from "../api/types";
import { createGate } from "../flow/gate";
import { dayKo } from "../flow/review";
import type { Action } from "../flow/state";
import { Button } from "../ui/Button";
import { InRowButton } from "../ui/InRowButton";
import { keepWords } from "../ui/keepWords";
import { ListCard } from "../ui/ListCard";
import { colors } from "../ui/theme";
import { useSaved } from "../ui/useSaved";
import { messageOf, styles as common, Waiting } from "./common";

export function SavedTab({ dispatch }: { dispatch: Dispatch<Action> }) {
  const saved = useSaved();
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const gate = useRef(createGate()).current; // one start at a time: a double tap must not start twice
  const asking = useRef(false); // one 「목록에서 뺄까요?」 at a time: a double tap on ★ must not stack two
  const mounted = useRef(true);
  useEffect(
    () => () => {
      mounted.current = false;
    },
    [],
  );
  const items = saved.items();

  // the lines come from their own roleplays, each asked for once (spec review-practice 7)
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

  function askRemove(i: SavedItem) {
    if (asking.current || saved.pending(i.text)) return; // asked already, or on its way out
    asking.current = true;
    const done = () => {
      asking.current = false;
    };
    Alert.alert(
      "목록에서 뺄까요?",
      i.text,
      [
        { text: "취소", style: "cancel", onPress: done },
        {
          text: "빼기",
          style: "destructive",
          onPress: () => {
            done();
            void saved.toggle(i.rp_id, i.idx, i.text);
          },
        },
      ],
      { cancelable: true, onDismiss: done },
    );
  }

  return (
    <View style={styles.wrap}>
      <ScrollView contentContainerStyle={styles.scroll}>
        {items?.length === 0 && (
          <Text style={[common.sub, styles.empty]}>{keepWords("아직 모아 둔 문장이 없어요. 대화나 연습에서 ☆를 누르면 여기에 모여요.")}</Text>
        )}
        {items?.map((i) => (
          <ListCard key={i.key} onPress={() => start([i])} chevron={false}>
            <View style={styles.top}>
              <Text style={[styles.tag, i.speaker === "ryan" ? styles.ryan : styles.mine]}>{i.speaker === "ryan" ? "라이언" : "나"}</Text>
              {/* not disabled while it is on its way: a second tap would open the practice of the row (final review) */}
              <InRowButton label="★" onPress={() => askRemove(i)} dim={saved.pending(i.text)} textStyle={styles.star} />
            </View>
            <Text style={styles.text}>{i.text}</Text>
            <Text style={styles.from}>
              {keepWords(`${i.title_ko} · ${dayKo(i.at)}에 모음`)}
            </Text>
          </ListCard>
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
  wrap: { flex: 1 },
  scroll: { paddingHorizontal: 16, paddingTop: 12, paddingBottom: 16 },
  top: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  tag: { fontSize: 13, color: colors.sub, paddingHorizontal: 6, paddingVertical: 1, borderRadius: 4, overflow: "hidden" },
  ryan: { backgroundColor: colors.ryanTag },
  mine: { backgroundColor: colors.user, color: colors.primary },
  star: { fontSize: 20, color: colors.stress },
  text: { fontSize: 18, color: colors.text, lineHeight: 26, marginTop: 4, marginBottom: 2 },
  from: { fontSize: 13, color: colors.weak },
  empty: { marginTop: 24, textAlign: "center", lineHeight: 22 },
  controls: { padding: 12, borderTopWidth: 1, borderTopColor: "#E9ECEF" },
});
