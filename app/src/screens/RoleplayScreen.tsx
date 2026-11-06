import { File } from "expo-file-system";
import { useEffect, useRef, useState, type ComponentRef, type Dispatch } from "react";
import { Alert, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";

import { api } from "../api";
import { ApiError } from "../api/client";
import type { AttemptEvent, ThreeLine } from "../api/types";
import type { SoundQueue } from "../audio/player";
import { usePlaying } from "../audio/usePlaying";
import { useRecorder } from "../audio/useRecorder";
import { createGate, stopThenSend } from "../flow/gate";
import { askFirst, canReplay, leavesScreen, modelKey, practiceFor, type Action, type State } from "../flow/state";
import { BackButton, useBackKey } from "../ui/BackButton";
import { Button } from "../ui/Button";
import { LineToSay } from "../ui/LineToSay";
import { Named } from "../ui/Named";
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
  const shadow = state.mode === "shadow";
  // one start or stop at a time; the recording is sent and the answer read outside it (`stopThenSend`)
  const gate = useRef(createGate()).current;
  // false once this screen goes away: set by leave() at once when it leaves the screen (`leavesScreen`), and on
  // unmount. Back from a line practised mid-roleplay keeps the screen, so it stays true there; `epoch` covers that.
  const mounted = useRef(true);
  // Bumped by every leave(). Back from a line practised mid-roleplay stays on this screen, so `mounted` stays true;
  // a start, stop or stream that began before the leave sees the number change and drops itself (spec 9).
  const epoch = useRef(0);
  const playing = usePlaying(sounds);

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
      .then((l) => alive && dispatch({ type: "lineLoaded", line: l, progress: l.progress }))
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
    // the roleplay line keeps its key across a practice (not played again on return); each practice has its own
    const key = modelKey(state);
    if (key && state.phase === "ready" && (line.speaker === "user" || shadow) && line.audio && !played.current.has(key)) {
      played.current.add(key);
      sounds.clear();
      sounds.enqueue(api.audioSource(line.audio, rate));
    }
  }, [line, state.phase, state.mode, sounds, dispatch]); // eslint-disable-line react-hooks/exhaustive-deps

  // Ryan's lines get their three-line notes only when asked; the end screen starts making them (spec 5)
  useEffect(() => {
    if (shadow && line && !line.three && state.phase === "ready" && !threes[line.idx]) fetchThree(line.idx);
  }, [shadow, line, state.phase]); // eslint-disable-line react-hooks/exhaustive-deps

  const toEnd = () => scroll.current?.scrollToEnd({ animated: true });
  useEffect(() => {
    setTimeout(toEnd, 50);
  }, [state.history.length, state.phase, state.feedback]);

  function listen(r: Rate = rate) {
    if (!line?.audio) return;
    setRate(r);
    sounds.clear();
    sounds.enqueue(api.audioSource(line.audio, r));
  }

  // Leaving (back or 「처음으로」): sounds stop, a recording in progress is deleted without being sent, and a
  // stream still answering is dropped by `epoch` (and by `mounted` when the screen goes away). A roleplay cannot
  // be picked up again later yet (이어 하기), so leaving one in progress asks first; a practice has nothing to lose
  // (`askFirst`).
  async function leave(a: "back" | "home") {
    // set before anything is awaited: a stop or start still finishing sees it (PR #13 review)
    epoch.current += 1;
    if (leavesScreen(state, a)) mounted.current = false;
    sounds.clear();
    await rec.discard();
    dispatch({ type: a });
  }

  function askLeave(a: "back" | "home") {
    if (!askFirst(state, a)) return void leave(a);
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

  async function fetchThree(idx: number): Promise<boolean> {
    setThrees((t) => ({ ...t, [idx]: "loading" }));
    try {
      const three = await api.getThree(rp.id, idx);
      setThrees((t) => ({ ...t, [idx]: three }));
      return true;
    } catch {
      setThrees((t) => {
        const { [idx]: _, ...rest } = t;
        return rest;
      });
      return false;
    }
  }

  async function toggleThree(idx: number) {
    if (open[idx]) return setOpen({ ...open, [idx]: false });
    setOpen({ ...open, [idx]: true });
    if (threes[idx]) return;
    if (!(await fetchThree(idx))) setOpen((o) => ({ ...o, [idx]: false }));
  }

  // the Ryan line before a practised line of mine, to know what it answers (spec 4)
  function playBefore(audio: string | null) {
    if (!audio || !canReplay(state.phase)) return;
    sounds.clear();
    sounds.enqueue(api.audioSource(audio));
  }

  const startRecording = () => gate.run(doStart);
  const stopRecording = () => stopThenSend(gate, stopRec, sendRec);

  async function doStart() {
    if (state.phase !== "ready" && state.phase !== "evaluated") return;
    const my = epoch.current;
    sounds.clear();
    dispatch({ type: "recordStart" });
    try {
      await rec.start(stopRecording);
      // left while the mic was starting (permission prompt)
      if (!mounted.current || epoch.current !== my) await rec.discard();
    } catch {
      dispatch({ type: "recordCancel" });
    }
  }

  // Stops the recorder, inside the gate. Gives the recording and the leave count it was made under, when it is to
  // be sent; the sending happens outside the gate (`stopThenSend`).
  async function stopRec(): Promise<{ uri: string; my: number } | undefined> {
    if (!rec.isRecording()) return undefined; // already stopped (auto-stop and a tap)
    const my = epoch.current;
    let uri: string;
    try {
      uri = await rec.stop();
    } catch {
      dispatch({ type: "recordCancel" });
      return undefined;
    }
    if (!mounted.current || epoch.current !== my) {
      // left while the recorder was stopping: `discard()` found it already stopped, so delete it here unsent
      try {
        new File(uri).delete();
      } catch {
        // already gone
      }
      return undefined;
    }
    dispatch({ type: "recordStop" });
    return { uri, my };
  }

  // Sends the recording and plays Ryan's answer as it streams in. An answer to something the learner has left
  // (another screen, or back from a practice to the roleplay) is dropped by `live`.
  async function sendRec({ uri, my }: { uri: string; my: number }) {
    const live = () => mounted.current && epoch.current === my;
    const onEvent = (e: AttemptEvent) => {
      if (!live()) return;
      if (e.type === "audio") sounds.enqueue(api.audioSource(e.key));
      if (e.type === "reply" && e.line.audio) sounds.enqueue(api.audioSource(e.line.audio));
      if (e.type === "error" && e.say?.audio) sounds.enqueue(api.audioSource(e.say.audio));
      dispatch({ type: "event", e });
    };
    try {
      await api.attempt(rp.id, state.idx, uri, state.mode, onEvent);
    } catch (e) {
      if (live()) dispatch({ type: "failed", code: codeOf(e), say: e instanceof ApiError ? e.say : undefined });
    } finally {
      try {
        new File(uri).delete(); // sent to the Mac; nothing stays on the phone
      } catch {
        // already gone
      }
    }
  }

  // A past line to practise on its own and come back (spec 9): only while my turn waits and nothing is playing,
  // since leaving would cut Ryan's feedback, his reply or the model off.
  const canPractise = !state.practice && canReplay(state.phase) && !playing;
  function practise(kind: "mine" | "shadow", idx: number) {
    if (canPractise) dispatch({ type: "practiseLine", kind, idx });
  }

  // `follow`: the bubble is a past Ryan line that can be practised (`practiceFor`)
  function RyanBubble({ idx, text, follow }: { idx?: number; text: string; follow?: boolean }) {
    const three = idx !== undefined ? threes[idx] : undefined;
    return (
      <Named part="ryan">
        <Pressable onPress={() => idx !== undefined && toggleThree(idx)} style={[styles.bubble, styles.ryan]}>
          <Text style={styles.ryanText}>{text}</Text>
          {idx !== undefined && open[idx] && three === "loading" && <Text style={common.sub}>세 줄을 만들고 있어요…</Text>}
          {idx !== undefined && open[idx] && three && three !== "loading" && <ThreeLineView three={three} />}
          {idx !== undefined && !open[idx] && <Text style={styles.hint}>눌러서 읽는 법 보기</Text>}
          {follow && idx !== undefined && (
            <PractiseLink label="따라 말하기 ›" disabled={!canPractise} onPress={() => practise("shadow", idx)} />
          )}
        </Pressable>
      </Named>
    );
  }

  const busy = state.phase === "evaluating";
  // the learner's turn: a line of mine, or Ryan's line to follow in shadow practice
  const myTurn =
    (line?.speaker === "user" || shadow) && ["ready", "recording", "evaluating", "evaluated", "error"].includes(state.phase);
  const practice = state.practice;
  const midway = practice?.from === "roleplay"; // one past line, back to the roleplay after it
  const title = practice
    ? midway
      ? practice.kind === "mine"
        ? "이 줄 다시"
        : "따라 말하기"
      : practice.kind === "mine"
        ? "내 대사 다시 연습"
        : "라이언 대사 따라 말하기"
    : rp.frame.title_ko;
  const count = practice
    ? midway
      ? null
      : `${practice.at + 1}/${practice.order.length}`
    : state.progress && state.progress.total > 0
      ? `내 대사 ${state.progress.no}/${state.progress.total}`
      : null;
  const before = practice?.kind === "mine" && line ? state.seen[line.idx - 1] : undefined;

  return (
    <View style={styles.wrap}>
      <View style={styles.header}>
        <BackButton onPress={() => askLeave("back")} />
        <View style={styles.titleRow}>
          <Text style={[common.title, styles.titleText]}>{title}</Text>
          {count && <Text style={styles.count}>{count}</Text>}
        </View>
        <Text style={common.sub}>
          {practice
            ? rp.frame.title_ko
            : `나: ${rp.frame.user_role_ko} · 라이언: ${rp.frame.ryan_role_ko} · ${rp.frame.place_ko}`}
        </Text>
      </View>
      <ScrollView ref={scroll} contentContainerStyle={styles.scroll}>
        {/* who says each bubble, like a messenger: others left in gray, me right in blue (2026-11-06 user) */}
        {state.jake && !practice && (
          <Named part="jake">
            <Pressable onPress={replayJake} style={[styles.bubble, styles.ryan]}>
              <Text style={styles.plainText}>{state.jake.text}</Text>
              <Text style={styles.hint}>눌러서 다시 듣기</Text>
            </Pressable>
          </Named>
        )}
        {state.history.map((b, i) =>
          b.kind === "ryan" ? (
            <RyanBubble key={i} idx={b.idx} text={b.text} follow={practiceFor(state, b) === "shadow"} />
          ) : b.kind === "user" && b.script ? (
            <Named key={i} part="mine">
              <View style={[styles.bubble, styles.user]}>
                <Text style={styles.label}>대본</Text>
                <Text style={styles.plainText}>{b.script}</Text>
                <Text style={[styles.label, styles.gap]}>들린 말</Text>
                <Text style={styles.plainText}>{b.text}</Text>
                {practiceFor(state, b) === "mine" && b.idx !== undefined && (
                  <PractiseLink label="이 줄 다시 ›" disabled={!canPractise} onPress={() => practise("mine", b.idx!)} />
                )}
              </View>
            </Named>
          ) : (
            <Named key={i} part={b.kind === "user" ? "mine" : "feedback"}>
              <View style={[styles.bubble, b.kind === "user" ? styles.user : styles.feedback]}>
                <Text style={styles.plainText}>{b.text}</Text>
              </View>
            </Named>
          ),
        )}
        {state.phase === "loading" && (
          <Waiting who="ryan" text={practice ? "대사를 준비하고 있어요" : "다음 대사를 준비하고 있어요"} onShow={toEnd} />
        )}
        {state.phase === "ryan" && line && <RyanBubble idx={line.idx} text={line.text} />}
        {myTurn && before?.speaker === "ryan" && (
          <Named part="ryan">
            <Pressable onPress={() => playBefore(before.audio)} style={[styles.bubble, styles.ryan]}>
              <Text style={styles.beforeText}>{before.text}</Text>
              <Text style={styles.hint}>눌러서 듣기</Text>
            </Pressable>
          </Named>
        )}
        {/* the line to say, Ryan's own in shadow practice: the learner says it, so it is on their side */}
        {myTurn && line && (
          <Named part="now">
            <View style={[styles.bubble, styles.now]}>
              <LineToSay
                text={line.text}
                three={shadow ? (line.three ?? threes[line.idx] ?? null) : line.three}
                open={state.reading}
                onToggle={() => dispatch({ type: "toggleReading" })}
              />
            </View>
          </Named>
        )}
        {state.heard && <Text style={styles.heard}>들린 말: {state.heard}</Text>}
        {state.feedback !== "" && (
          <Named part="feedback">
            <View style={[styles.bubble, styles.feedback]}>
              <Text style={styles.plainText}>{state.feedback}</Text>
            </View>
          </Named>
        )}
        {state.reply && (
          <RyanBubble
            idx={state.reply.idx}
            text={state.reply.text}
            follow={practiceFor(state, { kind: "ryan", idx: state.reply.idx }) === "shadow"}
          />
        )}
        {busy && !state.feedback && <Waiting who="ryan" text="라이언이 듣고 있어요" onShow={toEnd} />}
        {state.message && <Text style={state.phase === "error" ? common.error : styles.notice}>{state.message}</Text>}
      </ScrollView>

      <View style={styles.controls}>
        {myTurn && state.phase !== "error" && (
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
                label={state.phase === "recording" ? "■ 말하기 끝" : busy ? "평가하고 있어요" : shadow ? "🎤 따라 말하기" : "🎤 말하기"}
                onPress={state.phase === "recording" ? stopRecording : startRecording}
                disabled={busy}
              />
            )}
            {state.phase === "evaluated" && (
              <View style={styles.row}>
                <Button label="다시 해 보기" onPress={() => dispatch({ type: "again" })} kind="plain" />
                <Button label={midway ? "역할극으로" : "다음"} onPress={() => dispatch({ type: "next" })} />
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

// A small link under a past bubble: practise that line on its own (spec 9). Dimmed while it cannot be used, but
// still taking the tap (`practise` ignores it then): a disabled Pressable passes the tap to the Ryan bubble around
// it, which opened the notes instead (final review).
function PractiseLink({ label, disabled, onPress }: { label: string; disabled: boolean; onPress: () => void }) {
  return (
    <Pressable onPress={onPress} hitSlop={8} style={styles.practise}>
      <Text style={[styles.practiseText, disabled && styles.off]}>{label}</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  wrap: { flex: 1, backgroundColor: colors.bg, paddingTop: top },
  header: { paddingHorizontal: 16, paddingBottom: 8, borderBottomWidth: 1, borderBottomColor: "#E9ECEF" },
  titleRow: { flexDirection: "row", alignItems: "center", gap: 8 },
  titleText: { flexShrink: 1 },
  // in my blue, like my bubbles (2026-11-06 user); it was yellow, which is Ryan's feedback
  count: { fontSize: 14, fontWeight: "700", color: colors.primary, backgroundColor: colors.user, borderRadius: 10, paddingHorizontal: 8, paddingVertical: 2 },
  label: { fontSize: 12, color: colors.sub },
  gap: { marginTop: 6 },
  beforeText: { fontSize: 15, color: colors.sub, lineHeight: 22 },
  scroll: { padding: 16, paddingBottom: 32 },
  bubble: { borderRadius: 14, padding: 12, marginVertical: 5, maxWidth: "92%" },
  ryan: { backgroundColor: colors.ryan, alignSelf: "flex-start" },
  user: { backgroundColor: colors.user, alignSelf: "flex-end" },
  now: { backgroundColor: colors.user, alignSelf: "flex-end", borderWidth: 2, borderColor: colors.primary },
  feedback: { backgroundColor: colors.feedback, alignSelf: "flex-start" },
  ryanText: { fontSize: 20, color: colors.text, lineHeight: 28 },
  plainText: { fontSize: 17, color: colors.text, lineHeight: 25 },
  hint: { fontSize: 13, color: colors.weak, marginTop: 4 },
  practise: { alignSelf: "flex-end", marginTop: 6 },
  practiseText: { fontSize: 14, color: colors.primary, fontWeight: "600" },
  off: { opacity: 0.4 },
  heard: { fontSize: 14, color: colors.sub, marginTop: 4, alignSelf: "flex-end" },
  notice: { fontSize: 16, color: colors.sub, marginTop: 8 },
  controls: { padding: 12, borderTopWidth: 1, borderTopColor: "#E9ECEF" },
  row: { flexDirection: "row", flexWrap: "wrap", gap: 6, justifyContent: "center" },
});
