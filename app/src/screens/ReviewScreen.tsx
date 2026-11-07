// 「다시 연습」: two ways to practise again (spec docs/superpowers/specs/2026-11-07-review-practice-design.md 1).
// Only the two buttons and a line under each; Ryan already asked on the first screen.
import { useEffect, type Dispatch } from "react";
import { StyleSheet, Text, View } from "react-native";

import type { Action } from "../flow/state";
import { BackButton, useBackKey } from "../ui/BackButton";
import { Button } from "../ui/Button";
import { colors, top } from "../ui/theme";
import { useSaved } from "../ui/useSaved";
import { styles as common } from "./common";

export function ReviewScreen({ dispatch }: { dispatch: Dispatch<Action> }) {
  const saved = useSaved();
  const back = () => dispatch({ type: "back" });
  useBackKey(back);
  useEffect(() => {
    saved.refresh();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps
  const n = saved.items()?.length;

  return (
    <View style={styles.wrap}>
      <BackButton onPress={back} />
      <Text style={[common.title, styles.title]}>다시 연습</Text>
      <Button label="지난 상황" onPress={() => dispatch({ type: "openPast" })} />
      <Text style={[common.sub, styles.note]}>했던 상황을 같은 대본으로 다시</Text>
      <Button label={n === undefined ? "모아 둔 문장" : `모아 둔 문장 (${n})`} onPress={() => dispatch({ type: "openSaved" })} />
      <Text style={[common.sub, styles.note]}>모아 둔 문장만 집중해서</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { flex: 1, paddingTop: top, paddingHorizontal: 20, backgroundColor: colors.bg },
  title: { marginTop: 8, marginBottom: 16 },
  note: { marginTop: 4, marginBottom: 20, textAlign: "center" },
});
