// 「복습하기」: the past situations and the saved sentences as two tabs (spec
// docs/superpowers/specs/2026-11-07-review-screens-design.md 2). It replaced a menu of two buttons that looked empty
// (2026-11-07 user). No Ryan here: he asked on the first screen. The tab is the app state's screen, `past` or
// `saved`, so coming back from a past view or a saved practice lands on the tab it was opened from.
import { useCallback, useEffect, useState, type Dispatch } from "react";
import { StyleSheet, Text, View } from "react-native";

import { api } from "../api";
import type { PastItem } from "../api/types";
import type { Action } from "../flow/state";
import { BackButton, useBackKey } from "../ui/BackButton";
import { Tabs } from "../ui/Tabs";
import { colors, top } from "../ui/theme";
import { useSaved } from "../ui/useSaved";
import { messageOf, styles as common } from "./common";
import { PastTab } from "./PastTab";
import { SavedTab } from "./SavedTab";

type Tab = "past" | "saved";

export function ReviewScreen({ tab, dispatch }: { tab: Tab; dispatch: Dispatch<Action> }) {
  const saved = useSaved();
  const back = () => dispatch({ type: "back" });
  useBackKey(back);
  // Both lists (and the count on the tab) are asked for each time 「복습하기」 opens. Switching tabs keeps this screen,
  // so they are not asked again then; the past list lives here, not in its tab, which is drawn anew (todo 12-4).
  const [past, setPast] = useState<PastItem[] | null>(null);
  const [pastError, setPastError] = useState<string | null>(null);
  const loadPast = useCallback(async () => {
    setPastError(null);
    try {
      setPast(await api.past());
    } catch (e) {
      setPastError(messageOf(e));
    }
  }, []);
  useEffect(() => {
    saved.refresh();
    loadPast();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps
  const n = saved.items()?.length;

  return (
    <View style={styles.wrap}>
      <View style={styles.header}>
        <BackButton onPress={back} />
        <Text style={[common.title, styles.title]}>복습하기</Text>
        <Tabs<Tab>
          tabs={[
            { key: "past", label: "지난 상황" },
            { key: "saved", label: n === undefined ? "모아 둔 문장" : `모아 둔 문장 ${n}` },
          ]}
          current={tab}
          onChange={(k) => dispatch({ type: k === "past" ? "openPast" : "openSaved" })}
        />
      </View>
      <View style={styles.body}>
        {tab === "past" ? (
          <PastTab items={past} error={pastError} onRetry={loadPast} dispatch={dispatch} />
        ) : (
          <SavedTab dispatch={dispatch} />
        )}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { flex: 1, paddingTop: top, backgroundColor: colors.bg },
  header: { paddingHorizontal: 16, paddingBottom: 4 },
  title: { marginTop: 8, marginBottom: 14 },
  body: { flex: 1 },
});
