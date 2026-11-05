import { useEffect, useState, type Dispatch } from "react";
import { StyleSheet, Text, View } from "react-native";

import { api } from "../api";
import type { Summary } from "../api/types";
import type { SoundQueue } from "../audio/player";
import type { Action, State } from "../flow/state";
import { BackButton, useBackKey } from "../ui/BackButton";
import { Button } from "../ui/Button";
import { colors } from "../ui/theme";
import { messageOf, styles as common, Waiting } from "./common";

type Props = { state: State; dispatch: Dispatch<Action>; sounds: SoundQueue };

export function EndScreen({ state, dispatch, sounds }: Props) {
  const [summary, setSummary] = useState<Summary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const id = state.roleplay!.id;

  useEffect(() => {
    let alive = true; // a summary that comes back after leaving must not speak on the next screen
    api
      .summary(id)
      .then((s) => {
        if (!alive) return;
        setSummary(s);
        sounds.onIdle(() => sounds.enqueue(api.audioSource(s.say.audio)));
      })
      .catch((e) => alive && setError(messageOf(e)));
    return () => {
      alive = false;
    };
  }, [id, sounds]);

  // back: a new situation (the roleplay is over, so nothing is lost)
  function back() {
    sounds.clear();
    dispatch({ type: "back" });
  }
  useBackKey(back);

  return (
    <View style={styles.wrap}>
      <BackButton onPress={back} floating />
      {!summary && !error && <Waiting text="마무리하고 있어요" />}
      {summary && (
        <>
          <Text style={[common.body, styles.say]}>{summary.say.text}</Text>
          {summary.retry.map((idx) => (
            <Button
              key={idx}
              label={state.seen[idx]?.text ?? `${idx}번 대사`}
              onPress={() => dispatch({ type: "retryFromEnd", idx })}
              kind="plain"
            />
          ))}
        </>
      )}
      {error && <Text style={common.error}>{error}</Text>}
      <Button label="처음으로" onPress={() => dispatch({ type: "home" })} />
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { flex: 1, padding: 20, justifyContent: "center", backgroundColor: colors.bg },
  say: { marginBottom: 12 },
});
