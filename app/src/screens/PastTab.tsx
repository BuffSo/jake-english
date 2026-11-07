// 「지난 상황」 tab of 「복습하기」: one card per script spoken in, newest first, with the last day it was done (spec
// review-practice 2, review-screens 3). The rows showed the first day before; with the newest first the days came out
// of order, so they show the last day, labelled once above the list. The list is loaded by `ReviewScreen`, once while
// 「복습하기」 is open: this tab is drawn anew at each switch, and loading here showed an empty tab each time (todo 12-4).
import type { Dispatch } from "react";
import { ScrollView, StyleSheet, Text, View } from "react-native";

import type { PastItem } from "../api/types";
import { dayKo } from "../flow/review";
import type { Action } from "../flow/state";
import { Button } from "../ui/Button";
import { keepWords } from "../ui/keepWords";
import { ListCard } from "../ui/ListCard";
import { colors } from "../ui/theme";
import { ErrorText, styles as common } from "./common";

type Props = { items: PastItem[] | null; error: string | null; onRetry: () => void; dispatch: Dispatch<Action> };

export function PastTab({ items, error, onRetry, dispatch }: Props) {
  return (
    <ScrollView contentContainerStyle={styles.scroll}>
      {items?.length === 0 && <Text style={[common.sub, styles.empty]}>아직 해 본 상황이 없어요</Text>}
      {!!items?.length && <Text style={styles.note}>마지막으로 한 날</Text>}
      {items?.map((i) => (
        <ListCard key={i.group} onPress={() => dispatch({ type: "openPastRun", group: i.group, title: i.title_ko })}>
          <View style={styles.row}>
            <Text style={styles.title}>{keepWords(i.title_ko)}</Text>
            <Text style={styles.day}>{dayKo(i.latest)}</Text>
          </View>
        </ListCard>
      ))}
      {error && (
        <>
          <ErrorText text={error} />
          <Button label="다시 시도" onPress={onRetry} />
        </>
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  scroll: { paddingHorizontal: 16, paddingTop: 12, paddingBottom: 16 },
  note: { fontSize: 13, color: colors.weak, marginBottom: 6 },
  row: { flexDirection: "row", alignItems: "center" },
  title: { flex: 1, fontSize: 17, fontWeight: "600", color: colors.text, lineHeight: 24 },
  day: { fontSize: 13, color: colors.weak, marginLeft: 10 },
  empty: { marginTop: 24, textAlign: "center" },
});
