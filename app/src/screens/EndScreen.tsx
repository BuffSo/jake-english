// The end of a roleplay: the whole conversation to read and hear again, and three practices (spec
// docs/superpowers/specs/2026-11-05-roleplay-practice-design.md 3, 6). The same screen shows a past situation's
// last conversation when `state.past` is set (spec docs/superpowers/specs/2026-11-07-review-practice-design.md 3).
// Lines show only what was said; tapping one opens its buttons, one line at a time (review-practice 8).
import { useEffect, useRef, useState, type ComponentRef, type Dispatch } from "react";
import { Pressable, ScrollView, StyleSheet, Text, View, type LayoutChangeEvent } from "react-native";

import { api } from "../api";
import type { ScriptLine, Summary, TranscriptLine, Try, TryRef } from "../api/types";
import type { SoundQueue } from "../audio/player";
import { createGate } from "../flow/gate";
import { koOpensOnTap, koView } from "../flow/interpret";
import { comparePair, dayKo, scrollToShow, tapRow } from "../flow/review";
import type { Action, State } from "../flow/state";
import { BackButton, useBackKey } from "../ui/BackButton";
import { Button } from "../ui/Button";
import { KoButton, KoLine, type KoProps } from "../ui/Interpret";
import { keepWords } from "../ui/keepWords";
import { StarButton, StarMark } from "../ui/Star";
import { colors, top } from "../ui/theme";
import { useInterpret } from "../ui/useInterpret";
import { useSaved } from "../ui/useSaved";
import { ErrorText, messageOf, styles as common, Waiting } from "./common";

type Props = { state: State; dispatch: Dispatch<Action>; sounds: SoundQueue };
type Source = ReturnType<typeof api.audioSource>;
const PAIR_GAP_MS = 600; // between the first and this run's recording

type Star = { saved: boolean; busy: boolean; onPress: () => void };

export function EndScreen({ state, dispatch, sounds }: Props) {
  const [summary, setSummary] = useState<Summary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [copying, setCopying] = useState(false);
  const past = state.past;
  const rp = state.roleplay; // in a past view it comes with `pastLoaded`
  const id = rp?.id ?? "";
  const saved = useSaved();
  const said = useRef(state.closingPlayed); // the closing words are said once, not again after each practice
  const mounted = useRef(true);
  // one copy at a time: `copying` is the render's value, so two taps before the next render would both pass it
  // (PR #15 review); the gate is checked at the tap itself, like the recording buttons (PR #13)
  const gate = useRef(createGate()).current;
  // no turn here: Sohee plays whenever asked and stops what played, like 🔊 (spec korean-translation 2)
  const interp = useInterpret(id, sounds, () => mounted.current);
  const [koOpen, setKoOpen] = useState<Record<number, boolean>>({});
  const koOpenNow = useRef(koOpen); // set at the tap: a sound made before plays at once
  const [openRow, setOpenRow] = useState<string | null>(null);
  // an opened line is scrolled into view once its buttons are laid out (spec review-practice 8)
  const scroll = useRef<ComponentRef<typeof ScrollView>>(null);
  const view = useRef({ offset: 0, height: 0 });
  const toShow = useRef<string | null>(null);
  // what to load: the newest run of a past situation, or this roleplay
  const source = past ? `group:${past.group}` : `roleplay:${id}`;

  useEffect(() => {
    mounted.current = true;
    let alive = true; // a summary that comes back after leaving must not speak on the next screen
    const got = past
      ? api.pastRun(past.group).then((r) => {
          if (alive) dispatch({ type: "pastLoaded", roleplay: r.roleplay });
          return r.summary;
        })
      : api.summary(id);
    got
      .then((s) => {
        if (!alive) return;
        setSummary(s);
        if (!said.current) {
          said.current = true;
          dispatch({ type: "closingPlayed" });
          sounds.onIdle(() => alive && sounds.enqueue(api.audioSource(s.say.audio)));
        }
        // Ryan's three-line notes are made only when asked; start them now for 「따라 말하기」 (spec 5). A past view
        // does not: opening it only to look must not call Claude (review-practice 3).
        if (!past) {
          for (const { line } of s.lines) {
            if (line.speaker === "ryan" && !line.three) api.getThree(id, line.idx).catch(() => {});
          }
        }
      })
      .catch((e) => alive && setError(messageOf(e)));
    return () => {
      alive = false;
      mounted.current = false;
    };
  }, [source, sounds, dispatch]); // eslint-disable-line react-hooks/exhaustive-deps

  // back: a new situation, the past list, or where 「이 상황 다시 하기」 was pressed (nothing is lost)
  function back() {
    sounds.clear();
    dispatch({ type: "back" });
  }
  useBackKey(back);

  function play(src: Source) {
    sounds.clear();
    sounds.enqueue(src);
  }

  // 「🔊 처음 녹음」: the first recording, a short pause, then this run's (review-practice 4). Many recordings end right
  // on the last word, so back to back the two ran together (todo 01).
  function playPair(pair: { first: TryRef; then: TryRef | null }) {
    sounds.clear();
    sounds.enqueue(api.recordingSource(pair.first.rp_id, pair.first.idx, pair.first.n));
    if (!pair.then) return;
    sounds.enqueuePause(PAIR_GAP_MS);
    sounds.enqueue(api.recordingSource(pair.then.rp_id, pair.then.idx, pair.then.n));
  }

  function practise(kind: "mine" | "shadow", order: number[]) {
    sounds.clear();
    dispatch({ type: "startPractice", kind, order });
  }

  const restart = () => gate.run(doRestart);

  async function doRestart() {
    if (!rp) return;
    setCopying(true);
    setError(null);
    sounds.clear();
    try {
      const copy = await api.copyRoleplay(rp.id);
      if (mounted.current) dispatch({ type: "restarted", roleplay: copy });
    } catch (e) {
      if (mounted.current) setError(messageOf(e));
    } finally {
      if (mounted.current) setCopying(false);
    }
  }

  // Sohee's interpretation of one line (spec korean-translation 2): not made ahead when this screen opens
  function ko(line: ScriptLine): KoProps {
    const idx = line.idx;
    const view = koView(interp.entry(idx, line), koOpen[idx] === true);
    return {
      view,
      entry: interp.entry(idx, line),
      onToggle: () => {
        const open = koOpensOnTap(view);
        koOpenNow.current = { ...koOpenNow.current, [idx]: open };
        setKoOpen(koOpenNow.current);
        if (open) interp.open(idx, line, () => koOpenNow.current[idx] === true);
      },
      onReplay: () => interp.replay(idx, line, () => true), // the hook drops it once this screen goes away
    };
  }

  // one line open at a time; closing a line closes Sohee's line in it too, so the screen is plain again (8)
  function toggle(idx: number) {
    const { open, close } = tapRow(openRow, String(idx));
    koOpenNow.current = { ...koOpenNow.current, ...Object.fromEntries(close.map((i) => [i, false])) };
    setKoOpen(koOpenNow.current);
    setOpenRow(open);
    toShow.current = open;
  }

  // the opened line has drawn its buttons: bring them on screen if they are below it
  function laidOut(key: string, e: LayoutChangeEvent) {
    if (toShow.current !== key) return;
    toShow.current = null;
    const y = scrollToShow(e.nativeEvent.layout, view.current);
    if (y !== null) scroll.current?.scrollTo({ y, animated: true });
  }

  function star(line: ScriptLine): Star {
    return { saved: saved.has(line.text), busy: saved.pending(line.text), onPress: () => saved.toggle(id, line.idx, line.text) };
  }

  const mine = summary?.lines.filter((l) => l.line.speaker === "user").map((l) => l.line.idx) ?? [];
  const ryans = summary?.lines.filter((l) => l.line.speaker === "ryan").map((l) => l.line.idx) ?? [];
  const again = copying ? "준비하고 있어요" : "이 상황 다시 하기";

  return (
    <View style={styles.wrap}>
      <View style={styles.header}>
        <BackButton onPress={back} />
        <Text style={common.title}>{keepWords((past ? past.title : rp?.frame.title_ko) ?? "")}</Text>
        {past
          ? rp && <Text style={[common.sub, styles.say]}>{dayKo(rp.created)}</Text>
          : summary && <Text style={[common.body, styles.say]}>{keepWords(summary.say.text)}</Text>}
      </View>
      <ScrollView
        ref={scroll}
        contentContainerStyle={styles.scroll}
        onLayout={(e) => (view.current.height = e.nativeEvent.layout.height)}
        onScroll={(e) => (view.current.offset = e.nativeEvent.contentOffset.y)}
        scrollEventThrottle={32}
      >
        {!summary && !error && <Waiting who="ryan" text={past ? "지난번 대화를 찾고 있어요" : "마무리하고 있어요"} />}
        {summary && <Text style={styles.section}>주고받은 말</Text>}
        {summary?.lines.map((l) => {
          const open = openRow === String(l.line.idx);
          return l.line.speaker === "ryan" ? (
            <RyanLine
              key={l.line.idx}
              l={l}
              open={open}
              onToggle={() => toggle(l.line.idx)}
              onLayout={(e) => laidOut(String(l.line.idx), e)}
              ko={ko(l.line)}
              star={star(l.line)}
              onPlay={play}
              onFollow={() => practise("shadow", [l.line.idx])}
            />
          ) : (
            <MyLine
              key={l.line.idx}
              id={id}
              l={l}
              open={open}
              onToggle={() => toggle(l.line.idx)}
              onLayout={(e) => laidOut(String(l.line.idx), e)}
              ko={ko(l.line)}
              star={star(l.line)}
              onPlay={play}
              onPair={playPair}
              onAgain={() => practise("mine", [l.line.idx])}
            />
          );
        })}
        {error && <ErrorText text={error} />}
      </ScrollView>
      {/* no 「처음으로」: back goes to a new situation, one more back to the first screen (2026-11-06 user) */}
      {summary && rp && (
        <View style={styles.controls}>
          {past ? (
            <>
              {/* a past view is opened to do it again, so that comes first (review-practice 3) */}
              <Button label={again} onPress={restart} disabled={copying} />
              <Button label={`내 대사 다시 연습(${mine.length}줄)`} onPress={() => practise("mine", mine)} kind="secondary" />
              <Button label={`라이언 대사 따라 말하기(${ryans.length}줄)`} onPress={() => practise("shadow", ryans)} kind="secondary" />
            </>
          ) : (
            <>
              <Button label={`내 대사 다시 연습(${mine.length}줄)`} onPress={() => practise("mine", mine)} />
              <Button label={`라이언 대사 따라 말하기(${ryans.length}줄)`} onPress={() => practise("shadow", ryans)} kind="secondary" />
              <Button label={again} onPress={restart} kind="secondary" disabled={copying} />
            </>
          )}
        </View>
      )}
    </View>
  );
}

type LineProps = {
  l: TranscriptLine;
  open: boolean;
  onToggle: () => void;
  onLayout: (e: LayoutChangeEvent) => void;
  ko: KoProps;
  star: Star;
  onPlay: (src: Source) => void;
};

// 「따라 말하기 ›」 follows this one line and comes back here, like 「이 줄 다시」 on my lines (spec 3, 2026-11-06)
function RyanLine(props: LineProps & { onFollow: () => void }) {
  const { l, open, onToggle, onLayout, ko, star, onPlay, onFollow } = props;
  const audio = l.line.audio;
  return (
    <Pressable onPress={onToggle} onLayout={onLayout} style={[styles.line, open && styles.open]}>
      <View style={styles.who}>
        <Text style={styles.whoText}>라이언</Text>
        {star.saved && !open && <StarMark />}
      </View>
      <Text style={styles.text}>{l.line.text}</Text>
      <KoLine view={ko.view} entry={ko.entry} onReplay={ko.onReplay} />
      {open && (
        <View style={styles.actions}>
          {audio && (
            <Pressable onPress={() => onPlay(api.audioSource(audio))} hitSlop={8}>
              <Text style={styles.play}>🔊 듣기</Text>
            </Pressable>
          )}
          <KoButton view={ko.view} onPress={ko.onToggle} />
          <Pressable onPress={onFollow} hitSlop={8}>
            <Text style={styles.again}>따라 말하기 ›</Text>
          </Pressable>
          <StarButton saved={star.saved} onPress={star.onPress} busy={star.busy} />
        </View>
      )}
    </Pressable>
  );
}

// 「🔊 듣기」 plays my line's model here too, like Ryan's lines (spec three-line-listen 6); no rate on this screen
function MyLine(props: LineProps & { id: string; onPair: (p: { first: TryRef; then: TryRef | null }) => void; onAgain: () => void }) {
  const { id, l, open, onToggle, onLayout, ko, star, onPlay, onPair, onAgain } = props;
  const pair = comparePair(id, l);
  const audio = l.line.audio;
  return (
    <Pressable onPress={onToggle} onLayout={onLayout} style={[styles.line, open && styles.open]}>
      <View style={styles.who}>
        <Text style={styles.whoText}>나</Text>
        {star.saved && !open && <StarMark />}
      </View>
      <Text style={styles.text}>{l.line.text}</Text>
      <KoLine view={ko.view} entry={ko.entry} onReplay={ko.onReplay} />
      {l.tries.map((t) => (
        <TryView key={t.n} t={t} open={open} onPlay={() => onPlay(api.recordingSource(id, l.line.idx, t.n))} />
      ))}
      {open && (
        <View style={styles.actions}>
          {audio && (
            <Pressable onPress={() => onPlay(api.audioSource(audio))} hitSlop={8}>
              <Text style={styles.play}>🔊 듣기</Text>
            </Pressable>
          )}
          {pair && (
            <Pressable onPress={() => onPair(pair)} hitSlop={8}>
              <Text style={styles.play}>🔊 처음 녹음</Text>
            </Pressable>
          )}
          <KoButton view={ko.view} onPress={ko.onToggle} />
          <Pressable onPress={onAgain} hitSlop={8}>
            <Text style={styles.again}>이 줄 다시 ›</Text>
          </Pressable>
          <StarButton saved={star.saved} onPress={star.onPress} busy={star.busy} />
        </View>
      )}
    </Pressable>
  );
}

// One try inside the roleplay: what was heard, the recording, and what Ryan pointed out (only that, so the
// screen never says more than he did). The recording's button shows on an open line only.
function TryView({ t, open, onPlay }: { t: Try; open: boolean; onPlay: () => void }) {
  const points = [...t.issues.map((i) => i.say_ko), ...(t.point_ko ? [t.point_ko] : [])];
  return (
    <View style={styles.try}>
      <View style={styles.who}>
        <Text style={styles.heard}>{keepWords(`들린 말: ${t.heard}`)}</Text>
        {open && (
          <Pressable onPress={onPlay} hitSlop={8}>
            <Text style={styles.play}>🔊 내 녹음</Text>
          </Pressable>
        )}
      </View>
      {points.map((p, i) => (
        <Text key={i} style={styles.point}>
          {keepWords(p)}
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
  line: { paddingVertical: 10, paddingHorizontal: 8, borderBottomWidth: 1, borderBottomColor: "#F1F3F5", borderRadius: 8 },
  open: { backgroundColor: "#F8F9FA" },
  who: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: 8 },
  actions: { flexDirection: "row", flexWrap: "wrap", alignItems: "center", gap: 16, marginTop: 10 },
  whoText: { fontSize: 13, color: colors.weak },
  text: { fontSize: 17, color: colors.text, lineHeight: 25, marginTop: 2 },
  try: { marginTop: 6 },
  heard: { fontSize: 15, color: colors.sub, flexShrink: 1 },
  play: { fontSize: 15, color: colors.primary, fontWeight: "600" },
  again: { fontSize: 14, color: colors.primary },
  point: { fontSize: 15, color: colors.sub, marginTop: 2 },
  controls: { padding: 12, gap: 6, borderTopWidth: 1, borderTopColor: "#E9ECEF" },
});
