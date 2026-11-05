// The end of a roleplay: the whole conversation to read and hear again, and three practices (spec
// docs/superpowers/specs/2026-11-05-roleplay-practice-design.md 3, 6).
import { useEffect, useRef, useState, type Dispatch } from "react";
import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";

import { api } from "../api";
import type { Summary, TranscriptLine, Try } from "../api/types";
import type { SoundQueue } from "../audio/player";
import { createGate } from "../flow/gate";
import type { Action, State } from "../flow/state";
import { BackButton, useBackKey } from "../ui/BackButton";
import { Button } from "../ui/Button";
import { colors, top } from "../ui/theme";
import { messageOf, styles as common, Waiting } from "./common";

type Props = { state: State; dispatch: Dispatch<Action>; sounds: SoundQueue };
type Source = ReturnType<typeof api.audioSource>;

export function EndScreen({ state, dispatch, sounds }: Props) {
  const [summary, setSummary] = useState<Summary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [copying, setCopying] = useState(false);
  const rp = state.roleplay!;
  const id = rp.id;
  const said = useRef(state.closingPlayed); // the closing words are said once, not again after each practice
  const mounted = useRef(true);
  // one copy at a time: `copying` is the render's value, so two taps before the next render would both pass it
  // (PR #15 review); the gate is checked at the tap itself, like the recording buttons (PR #13)
  const gate = useRef(createGate()).current;

  useEffect(() => {
    mounted.current = true;
    let alive = true; // a summary that comes back after leaving must not speak on the next screen
    api
      .summary(id)
      .then((s) => {
        if (!alive) return;
        setSummary(s);
        if (!said.current) {
          said.current = true;
          dispatch({ type: "closingPlayed" });
          sounds.onIdle(() => alive && sounds.enqueue(api.audioSource(s.say.audio)));
        }
        // Ryan's three-line notes are made only when asked; start them now for 「따라 말하기」 (spec 5)
        for (const { line } of s.lines) {
          if (line.speaker === "ryan" && !line.three) api.getThree(id, line.idx).catch(() => {});
        }
      })
      .catch((e) => alive && setError(messageOf(e)));
    return () => {
      alive = false;
      mounted.current = false;
    };
  }, [id, sounds, dispatch]);

  // back: a new situation (the roleplay is over, so nothing is lost)
  function back() {
    sounds.clear();
    dispatch({ type: "back" });
  }
  useBackKey(back);

  // 「처음으로」 stops what is playing too, like every other button here (PR #15 review)
  function home() {
    sounds.clear();
    dispatch({ type: "home" });
  }

  function play(src: Source) {
    sounds.clear();
    sounds.enqueue(src);
  }

  function practise(kind: "mine" | "shadow", order: number[]) {
    sounds.clear();
    dispatch({ type: "startPractice", kind, order });
  }

  const restart = () => gate.run(doRestart);

  async function doRestart() {
    setCopying(true);
    setError(null);
    sounds.clear();
    try {
      const copy = await api.copyRoleplay(id);
      if (mounted.current) dispatch({ type: "restarted", roleplay: copy });
    } catch (e) {
      if (mounted.current) setError(messageOf(e));
    } finally {
      if (mounted.current) setCopying(false);
    }
  }

  const mine = summary?.lines.filter((l) => l.line.speaker === "user").map((l) => l.line.idx) ?? [];
  const ryans = summary?.lines.filter((l) => l.line.speaker === "ryan").map((l) => l.line.idx) ?? [];

  return (
    <View style={styles.wrap}>
      <View style={styles.header}>
        <BackButton onPress={back} />
        <Text style={common.title}>{rp.frame.title_ko}</Text>
        {summary && <Text style={[common.body, styles.say]}>{summary.say.text}</Text>}
      </View>
      <ScrollView contentContainerStyle={styles.scroll}>
        {!summary && !error && <Waiting text="마무리하고 있어요" />}
        {summary && <Text style={styles.section}>주고받은 말</Text>}
        {summary?.lines.map((l) =>
          l.line.speaker === "ryan" ? (
            <RyanLine key={l.line.idx} l={l} onPlay={play} />
          ) : (
            <MyLine key={l.line.idx} id={id} l={l} onPlay={play} onAgain={() => practise("mine", [l.line.idx])} />
          ),
        )}
        {error && <Text style={common.error}>{error}</Text>}
      </ScrollView>
      <View style={styles.controls}>
        {summary && (
          <>
            <Button label={`내 대사 다시 연습(${mine.length}줄)`} onPress={() => practise("mine", mine)} />
            <Button label={`라이언 대사 따라 말하기(${ryans.length}줄)`} onPress={() => practise("shadow", ryans)} kind="plain" />
            <Button label={copying ? "준비하고 있어요" : "같은 대본으로 처음부터"} onPress={restart} kind="plain" disabled={copying} />
          </>
        )}
        <Button label="처음으로" onPress={home} kind="plain" small />
      </View>
    </View>
  );
}

function RyanLine({ l, onPlay }: { l: TranscriptLine; onPlay: (src: Source) => void }) {
  const audio = l.line.audio;
  return (
    <View style={styles.line}>
      <View style={styles.who}>
        <Text style={styles.whoText}>라이언</Text>
        {audio && (
          <Pressable onPress={() => onPlay(api.audioSource(audio))} hitSlop={8}>
            <Text style={styles.play}>▶ 듣기</Text>
          </Pressable>
        )}
      </View>
      <Text style={styles.text}>{l.line.text}</Text>
    </View>
  );
}

function MyLine(props: { id: string; l: TranscriptLine; onPlay: (src: Source) => void; onAgain: () => void }) {
  const { id, l, onPlay, onAgain } = props;
  return (
    <View style={styles.line}>
      <View style={styles.who}>
        <Text style={styles.whoText}>나</Text>
        <Pressable onPress={onAgain} hitSlop={8}>
          <Text style={styles.again}>이 줄 다시 ›</Text>
        </Pressable>
      </View>
      <Text style={styles.text}>{l.line.text}</Text>
      {l.tries.map((t) => (
        <TryView key={t.n} t={t} onPlay={() => onPlay(api.recordingSource(id, l.line.idx, t.n))} />
      ))}
    </View>
  );
}

// One try inside the roleplay: what was heard, the recording, and what Ryan pointed out (only that, so the
// screen never says more than he did)
function TryView({ t, onPlay }: { t: Try; onPlay: () => void }) {
  const points = [...t.issues.map((i) => `「${i.target}」 → 「${i.heard}」처럼 들렸어요`), ...(t.point_ko ? [t.point_ko] : [])];
  return (
    <View style={styles.try}>
      <View style={styles.who}>
        <Text style={styles.heard}>들린 말: {t.heard}</Text>
        <Pressable onPress={onPlay} hitSlop={8}>
          <Text style={styles.play}>▶ 내 녹음</Text>
        </Pressable>
      </View>
      {points.map((p, i) => (
        <Text key={i} style={styles.point}>
          {p}
        </Text>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { flex: 1, backgroundColor: colors.bg, paddingTop: top },
  header: { paddingHorizontal: 16, paddingBottom: 8, borderBottomWidth: 1, borderBottomColor: "#E9ECEF" },
  say: { marginTop: 6 },
  scroll: { padding: 16, paddingBottom: 24 },
  section: { fontSize: 14, fontWeight: "700", color: colors.sub, marginBottom: 6 },
  line: { paddingVertical: 10, borderBottomWidth: 1, borderBottomColor: "#F1F3F5" },
  who: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: 8 },
  whoText: { fontSize: 13, color: colors.weak },
  text: { fontSize: 17, color: colors.text, lineHeight: 25, marginTop: 2 },
  try: { marginTop: 6 },
  heard: { fontSize: 15, color: colors.sub, flexShrink: 1 },
  play: { fontSize: 15, color: colors.primary, fontWeight: "600" },
  again: { fontSize: 14, color: colors.primary },
  point: { fontSize: 15, color: colors.sub, marginTop: 2 },
  controls: { padding: 12, gap: 6, borderTopWidth: 1, borderTopColor: "#E9ECEF" },
});
