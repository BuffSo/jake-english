// 「지난 상황」: one row per script spoken in, newest first, with the first day it was done (spec review-practice 2)
import { useCallback, useEffect, useState, type Dispatch } from "react";
import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";

import { api } from "../api";
import type { PastItem } from "../api/types";
import { dayKo } from "../flow/review";
import type { Action } from "../flow/state";
import { BackButton, useBackKey } from "../ui/BackButton";
import { Button } from "../ui/Button";
import { colors, top } from "../ui/theme";
import { messageOf, styles as common } from "./common";

export function PastScreen({ dispatch }: { dispatch: Dispatch<Action> }) {
  const [items, setItems] = useState<PastItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const back = () => dispatch({ type: "back" });
  useBackKey(back);

  const load = useCallback(async () => {
    setError(null);
    try {
      setItems(await api.past());
    } catch (e) {
      setError(messageOf(e));
    }
  }, []);
  useEffect(() => {
    load();
  }, [load]);

  return (
    <View style={styles.wrap}>
      <View style={styles.header}>
        <BackButton onPress={back} />
        <Text style={common.title}>지난 상황</Text>
      </View>
      <ScrollView contentContainerStyle={styles.scroll}>
        {items?.length === 0 && <Text style={[common.sub, styles.empty]}>아직 해 본 상황이 없어요</Text>}
        {items?.map((i) => (
          <Pressable
            key={i.group}
            accessibilityRole="button"
            style={({ pressed }) => [styles.row, pressed && styles.pressed]}
            onPress={() => dispatch({ type: "openPastRun", group: i.group, title: i.title_ko })}
          >
            <Text style={styles.title}>{i.title_ko}</Text>
            <Text style={common.sub}>처음 한 날 {dayKo(i.first)}</Text>
          </Pressable>
        ))}
        {error && (
          <>
            <Text style={common.error}>{error}</Text>
            <Button label="다시 시도" onPress={load} />
          </>
        )}
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { flex: 1, paddingTop: top, backgroundColor: colors.bg },
  header: { paddingHorizontal: 16, paddingBottom: 8, borderBottomWidth: 1, borderBottomColor: "#E9ECEF" },
  scroll: { padding: 16 },
  row: { paddingVertical: 14, borderBottomWidth: 1, borderBottomColor: "#F1F3F5" },
  pressed: { opacity: 0.6 },
  title: { fontSize: 18, fontWeight: "600", color: colors.text, marginBottom: 2 },
  empty: { marginTop: 24, textAlign: "center" },
});
