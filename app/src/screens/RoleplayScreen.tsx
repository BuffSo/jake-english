import { File } from "expo-file-system";
import { useEffect, useRef, useState, type ComponentRef, type Dispatch } from "react";
import { Alert, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";

import { api } from "../api";
import { ApiError } from "../api/client";
import type { AttemptEvent, ThreeLine } from "../api/types";
import type { SoundQueue } from "../audio/player";
import { useRecorder } from "../audio/useRecorder";
import { createGate } from "../flow/gate";
import { canReplay, type Action, type State } from "../flow/state";
import { BackButton, useBackKey } from "../ui/BackButton";
import { Button } from "../ui/Button";
import { ThreeLineView } from "../ui/ThreeLine";
import { colors, top } from "../ui/theme";
import { codeOf, styles as common, Waiting } from "./common";

type Props = { state: State; dispatch: Dispatch<Action>; sounds: SoundQueue };
type Rate = 0.6 | 0.8 | 1;
const RATES: Rate[] = [0.6, 0.8, 1];

export function RoleplayScreen({ state, dispatch, sounds }: Props) {
  const rp = state.roleplay!;
  const [rate, setRate] = useState<Rate>(1);
  const [threes, setThrees] = useState<Record<number, ThreeLine | "loading">>({});
  const [open, setOpen] = useState<Record<number, boolean>>({});
  const played = useRef<Set<string>>(new Set());
  const scroll = useRef<ComponentRef<typeof ScrollView>>(null);
  const rec = useRecorder();
  const line = state.line;
  const gate = useRef(createGate()).current; // one start or stop (and its upload) at a time
  const mounted = useRef(true); // false once the learner leaves: set by leave() at once, and on unmount

  useEffect(() => {
    mounted.current = true;
    return () => {
      // leaving mid-evaluation: the stream may still answer; its sounds and errors must not reach other screens
      mounted.current = false;
    };
  }, []);

  // load the current line (the server waits until its notes and sound are ready)
  useEffect(() => {
    if (state.phase !== "loading") return;
    let alive = true;
    api
      .getLine(rp.id, state.idx)
      .then((l) => alive && dispatch({ type: "lineLoaded", line: l }))
      .catch((e) => {
        if (!alive) return;
        if (e instanceof ApiError && e.code === "not_found") dispatch({ type: "lineMissing" });
        else dispatch({ type: "failed", code: codeOf(e), say: e instanceof ApiError ? e.say : undefined });
      });
    return () => {
      alive = false;
    };
  }, [state.phase, state.idx, rp.id, dispatch]);

  // Ryan says his line, then the next line comes; the learner's model is played once
  useEffect(() => {
    if (!line) return;
    if (state.phase === "ryan") {
      sounds.clear();
      if (line.audio) {
        sounds.enqueue(api.audioSource(line.audio));
        sounds.onIdle(() => dispatch({ type: "ryanDone" }));
      } else {
        const t = setTimeout(() => dispatch({ type: "ryanDone" }), 2500);
        return () => clearTimeout(t);
      }
    }
    const key = `${line.idx}:${state.mode}`;
    if (state.phase === "ready" && line.speaker === "user" && line.audio && !played.current.has(key)) {
      played.current.add(key);
      sounds.clear();
      sounds.enqueue(api.audioSource(line.audio, rate));
    }
  }, [line, state.phase, state.mode, sounds, dispatch]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    setTimeout(() => scroll.current?.scrollToEnd({ animated: true }), 50);
  }, [state.history.length, state.phase, state.feedback]);

  function listen(r: Rate = rate) {
    if (!line?.audio) return;
    setRate(r);
    sounds.clear();
    sounds.enqueue(api.audioSource(line.audio, r));
  }

  // Leaving (back or 「처음으로」): sounds stop, a recording in progress is deleted without being sent, and a
  // stream still answering is dropped by `mounted`. There is no resume yet, so a roleplay in progress asks
  // first; a line retried from the end screen has nothing to lose.
  async function leave(a: "back" | "home") {
    // set before anything is awaited: a stop or start still finishing sees it (PR #13 review)
    mounted.current = false;
    sounds.clear();
    await rec.discard();
    dispatch({ type: a });
  }

  function askLeave(a: "back" | "home") {
    if (state.practice) return void leave(a);
    Alert.alert(
      "역할극을 그만둘까요?",
      "하던 역할극은 아직 이어 할 수 없어요.",
      [
        { text: "계속하기", style: "cancel" },
        { text: "그만두기", style: "destructive", onPress: () => void leave(a) },
      ],
      { cancelable: true },
    );
  }
  useBackKey(() => askLeave("back"));

  function replayJake() {
    if (!state.jake || !canReplay(state.phase)) return;
    sounds.clear();
    sounds.enqueue(api.audioSource(state.jake.audio));
  }

  async function toggleThree(idx: number) {
    if (open[idx]) return setOpen({ ...open, [idx]: false });
    setOpen({ ...open, [idx]: true });
    if (threes[idx]) return;
    setThrees((t) => ({ ...t, [idx]: "loading" }));
    try {
      const three = await api.getThree(rp.id, idx);
      setThrees((t) => ({ ...t, [idx]: three }));
    } catch {
      setThrees((t) => {
        const { [idx]: _, ...rest } = t;
        return rest;
      });
      setOpen((o) => ({ ...o, [idx]: false }));
    }
  }

  const startRecording = () => gate.run(doStart);
  const stopRecording = () => gate.run(doStop);

  async function doStart() {
    if (state.phase !== "ready" && state.phase !== "evaluated") return;
    sounds.clear();
    dispatch({ type: "recordStart" });
    try {
      await rec.start(stopRecording);
      if (!mounted.current) await rec.discard(); // left while the mic was starting (permission prompt)
    } catch {
      dispatch({ type: "recordCancel" });
    }
  }

  async function doStop() {
    if (!rec.isRecording()) return; // already stopped (auto-stop and a tap)
    let uri: string;
    try {
      uri = await rec.stop();
    } catch {
      dispatch({ type: "recordCancel" });
      return;
    }
    if (!mounted.current) {
      // left while the recorder was stopping: `discard()` found it already stopped, so delete it here unsent
      try {
        new File(uri).delete();
      } catch {
        // already gone
      }
      return;
    }
    dispatch({ type: "recordStop" });
    const onEvent = (e: AttemptEvent) => {
      if (!mounted.current) return;
      if (e.type === "audio") sounds.enqueue(api.audioSource(e.key));
      if (e.type === "reply" && e.line.audio) sounds.enqueue(api.audioSource(e.line.audio));
      if (e.type === "error" && e.say?.audio) sounds.enqueue(api.audioSource(e.say.audio));
      dispatch({ type: "event", e });
    };
    try {
      await api.attempt(rp.id, state.idx, uri, state.mode, onEvent);
    } catch (e) {
      if (mounted.current) dispatch({ type: "failed", code: codeOf(e), say: e instanceof ApiError ? e.say : undefined });
    } finally {
      try {
        new File(uri).delete(); // sent to the Mac; nothing stays on the phone
      } catch {
        // already gone
      }
    }
  }

  function RyanBubble({ idx, text }: { idx?: number; text: string }) {
    const three = idx !== undefined ? threes[idx] : undefined;
    return (
      <Pressable onPress={() => idx !== undefined && toggleThree(idx)} style={[styles.bubble, styles.ryan]}>
        <Text style={styles.ryanText}>{text}</Text>
        {idx !== undefined && open[idx] && three === "loading" && <Text style={common.sub}>세 줄을 만들고 있어요…</Text>}
        {idx !== undefined && open[idx] && three && three !== "loading" && <ThreeLineView three={three} />}
        {idx !== undefined && !open[idx] && <Text style={styles.hint}>눌러서 읽는 법 보기</Text>}
      </Pressable>
    );
  }

  const busy = state.phase === "evaluating";
  const userTurn = line?.speaker === "user" && ["ready", "recording", "evaluating", "evaluated", "error"].includes(state.phase);

  return (
    <View style={styles.wrap}>
      <View style={styles.header}>
        <BackButton onPress={() => askLeave("back")} />
        <Text style={common.title}>{rp.frame.title_ko}</Text>
        <Text style={common.sub}>
          나: {rp.frame.user_role_ko} · 라이언: {rp.frame.ryan_role_ko} · {rp.frame.place_ko}
        </Text>
      </View>
      <ScrollView ref={scroll} contentContainerStyle={styles.scroll}>
        {state.jake && (
          <Pressable onPress={replayJake} style={[styles.bubble, styles.user]}>
            <Text style={styles.plainText}>제이크: {state.jake.text}</Text>
            <Text style={styles.hint}>눌러서 다시 듣기</Text>
          </Pressable>
        )}
        {state.history.map((b, i) =>
          b.kind === "ryan" ? (
            <RyanBubble key={i} idx={b.idx} text={b.text} />
          ) : (
            <View key={i} style={[styles.bubble, b.kind === "user" ? styles.user : styles.feedback]}>
              <Text style={styles.plainText}>{b.text}</Text>
            </View>
          ),
        )}
        {state.phase === "loading" && <Waiting text="다음 대사를 준비하고 있어요" />}
        {state.phase === "ryan" && line && <RyanBubble idx={line.idx} text={line.text} />}
        {userTurn && line?.three && <ThreeLineView three={line.three} />}
        {state.heard && <Text style={styles.heard}>들린 말: {state.heard}</Text>}
        {state.feedback !== "" && (
          <View style={[styles.bubble, styles.feedback]}>
            <Text style={styles.plainText}>{state.feedback}</Text>
          </View>
        )}
        {state.reply && <RyanBubble idx={state.reply.idx} text={state.reply.text} />}
        {busy && !state.feedback && <Waiting text="라이언이 듣고 있어요" />}
        {state.message && <Text style={state.phase === "error" ? common.error : styles.notice}>{state.message}</Text>}
      </ScrollView>

      <View style={styles.controls}>
        {userTurn && state.phase !== "error" && (
          <>
            <View style={styles.row}>
              <Button label="다시 듣기" onPress={() => listen()} kind="plain" small disabled={busy || state.phase === "recording"} />
              {RATES.map((r) => (
                <Button
                  key={r}
                  label={`${r}배${r === rate ? " ✓" : ""}`}
                  onPress={() => listen(r)}
                  kind="plain"
                  small
                  disabled={busy || state.phase === "recording"}
                />
              ))}
            </View>
            {state.phase !== "evaluated" && (
              <Button
                label={state.phase === "recording" ? "■ 말하기 끝" : busy ? "평가하고 있어요" : "🎤 말하기"}
                onPress={state.phase === "recording" ? stopRecording : startRecording}
                disabled={busy}
              />
            )}
            {state.phase === "evaluated" && (
              <View style={styles.row}>
                <Button label="다시 해 보기" onPress={() => dispatch({ type: "again" })} kind="plain" />
                <Button label="다음" onPress={() => dispatch({ type: "next" })} />
              </View>
            )}
          </>
        )}
        {state.phase === "error" && <Button label="다시 시도" onPress={() => dispatch({ type: "retry" })} />}
        <Button label="처음으로" onPress={() => askLeave("home")} kind="plain" small />
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { flex: 1, backgroundColor: colors.bg, paddingTop: top },
  header: { paddingHorizontal: 16, paddingBottom: 8, borderBottomWidth: 1, borderBottomColor: "#E9ECEF" },
  scroll: { padding: 16, paddingBottom: 32 },
  bubble: { borderRadius: 14, padding: 12, marginVertical: 5, maxWidth: "92%" },
  ryan: { backgroundColor: colors.ryan, alignSelf: "flex-start" },
  user: { backgroundColor: colors.user, alignSelf: "flex-end" },
  feedback: { backgroundColor: colors.feedback, alignSelf: "flex-start" },
  ryanText: { fontSize: 20, color: colors.text, lineHeight: 28 },
  plainText: { fontSize: 17, color: colors.text, lineHeight: 25 },
  hint: { fontSize: 13, color: colors.weak, marginTop: 4 },
  heard: { fontSize: 14, color: colors.sub, marginTop: 4, alignSelf: "flex-end" },
  notice: { fontSize: 16, color: colors.sub, marginTop: 8 },
  controls: { padding: 12, borderTopWidth: 1, borderTopColor: "#E9ECEF" },
  row: { flexDirection: "row", flexWrap: "wrap", gap: 6, justifyContent: "center" },
});
