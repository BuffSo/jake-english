import { File } from "expo-file-system";
import { useEffect, useRef, useState, type ComponentRef, type Dispatch } from "react";
import { Alert, Pressable, ScrollView, StyleSheet, Text, View, type LayoutChangeEvent } from "react-native";

import { api } from "../api";
import { ApiError } from "../api/client";
import type { AttemptEvent, ScriptLine, ThreeLine, TryRef } from "../api/types";
import type { SoundQueue } from "../audio/player";
import { useAnswering } from "../audio/useAnswering";
import { usePlaying } from "../audio/usePlaying";
import { useRecorder } from "../audio/useRecorder";
import { createGate, runThenHold, stopThenSend, tapHold, tapThenHold } from "../flow/gate";
import { koOpensOnTap, koView, mayAutoPlay, mayReplay } from "../flow/interpret";
import { scrollToShow, tapRow } from "../flow/review";
import { askFirst, canReplay, canSkip, leaveAction, leavesScreen, mayListen, modelKey, practiceFor, type Action, type State } from "../flow/state";
import { BackButton, useBackKey } from "../ui/BackButton";
import { Button } from "../ui/Button";
import { InRowButton } from "../ui/InRowButton";
import { KoButton, KoLine } from "../ui/Interpret";
import { LineToSay } from "../ui/LineToSay";
import { keepWords } from "../ui/keepWords";
import { Named } from "../ui/Named";
import { lineNotes, needsNotes } from "../ui/notesView";
import { StarButton, StarMark } from "../ui/Star";
import { ThreeLineView } from "../ui/ThreeLine";
import { useInterpret } from "../ui/useInterpret";
import { useSaved } from "../ui/useSaved";
import { colors, top } from "../ui/theme";
import { codeOf, ErrorText, messageOf, styles as common, Waiting } from "./common";

type Props = { state: State; dispatch: Dispatch<Action>; sounds: SoundQueue };
type Rate = 0.6 | 0.8 | 1;
const RATES: Rate[] = [0.6, 0.8, 1];

export function RoleplayScreen({ state, dispatch, sounds }: Props) {
  const rp = state.roleplay!;
  const [rate, setRate] = useState<Rate>(1);
  const [threes, setThrees] = useState<Record<number, ThreeLine | "loading">>({});
  // lines to say whose notes could not be fetched: shown plain and not asked again (todo line-notes minors 3)
  const [noNotes, setNoNotes] = useState<Record<number, true>>({});
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
  // the state as of the last render, for Sohee's sound, which arrives after the tap (spec korean-translation 2)
  const now = useRef(state);
  now.current = state;
  // which past bubbles show Sohee's line, by line; the line to say keeps it in the state (`interpreting`). The refs
  // are set at the tap, before the render, since a sound already made plays at once.
  const [koOpen, setKoOpen] = useState<Record<number, boolean>>({});
  const koOpenNow = useRef(koOpen);
  const sayOpenNow = useRef(state.interpreting);
  sayOpenNow.current = state.interpreting;
  // past bubbles show only what was said; one opens its buttons at a time (spec review-practice 8). The key is
  // "<place>:<line>", so two bubbles of one line (「다시 해 보기」) open apart.
  const [openRow, setOpenRow] = useState<string | null>(null);
  const view = useRef({ offset: 0, height: 0 }); // the conversation's scroll, to bring an opened bubble into view
  const toShow = useRef<string | null>(null);
  const saved = useSaved();
  // 「이 상황 다시 하기」 from saved-sentence practice (spec review-practice 7)
  const [copying, setCopying] = useState(false);
  const [copyError, setCopyError] = useState<string | null>(null);
  const copyGate = useRef(createGate()).current;
  // Ryan's answer to a recording is playing: a sound asked for from a bubble waits for it (spec three-line-listen 5)
  const { answering, mark: markAnswer } = useAnswering(sounds);
  const answeringNow = useRef(answering);
  answeringNow.current = answering;
  const listenOk = mayListen(state.phase, answering);
  const interp = useInterpret(rp.id, sounds, (auto) =>
    mounted.current &&
    (auto
      ? mayAutoPlay("roleplay", now.current.phase, sounds.isPlaying())
      : mayReplay("roleplay", now.current.phase, answeringNow.current)),
  );

  useEffect(() => {
    mounted.current = true;
    return () => {
      // leaving mid-evaluation: the stream may still answer; its sounds and errors must not reach other screens
      mounted.current = false;
    };
  }, []);

  // load the current line (the server waits until its sound is ready; a learner's notes may come later, fetched below)
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

  // The line to say comes without its notes when they are not made yet: Ryan's in shadow practice are made only when
  // asked (the end screen starts them, spec 5), the learner's are still being made on the Mac (spec
  // dont-wait-for-line-notes 2). Fetched as soon as the line is up, so 「읽는 법 보기」 usually opens at once.
  useEffect(() => {
    const toSay = line && (line.speaker === "user" || shadow);
    if (toSay && state.phase === "ready" && needsNotes(line, threes[line.idx], !!noNotes[line.idx])) fetchThree(line.idx, true);
  }, [shadow, line, state.phase]); // eslint-disable-line react-hooks/exhaustive-deps

  // Always a moment later: on Android the new renderer runs a scroll before it adds the views committed with it, so
  // scrolling at once to a wait that has just appeared (`Waiting` `onShow`) stopped above it (PR #20 review).
  const toEnd = () => setTimeout(() => scroll.current?.scrollToEnd({ animated: true }), 50);
  useEffect(() => {
    toEnd();
  }, [state.history.length, state.phase, state.feedback]);

  function listen(r: Rate = rate) {
    if (!line?.audio) return;
    setRate(r);
    sounds.clear();
    sounds.enqueue(api.audioSource(line.audio, r));
  }

  // Leaving (back): sounds stop, a recording in progress is deleted without being sent, and a
  // stream still answering is dropped by `epoch` (and by `mounted` when the screen goes away). A roleplay cannot
  // be picked up again later yet (이어 하기), so leaving one in progress asks first; a practice has nothing to lose
  // (`askFirst`).
  async function leave() {
    // set before anything is awaited: a stop or start still finishing sees it (PR #13 review)
    epoch.current += 1;
    if (leavesScreen(state)) mounted.current = false;
    sounds.clear();
    await rec.discard();
    dispatch(leaveAction(state));
  }

  function askLeave() {
    if (!askFirst(state)) return void leave();
    Alert.alert(
      "대화를 그만둘까요?",
      "하던 대화는 아직 이어 할 수 없어요.",
      [
        { text: "계속하기", style: "cancel" },
        { text: "그만두기", style: "destructive", onPress: () => void leave() },
      ],
      { cancelable: true },
    );
  }
  useBackKey(askLeave);

  // A sound asked for from a bubble (🔊, or a tap on a bubble that plays): stops what plays and plays it, only while
  // my turn waits and not over Ryan's answer (`mayListen`, spec three-line-listen 5)
  function playFromBubble(src: ReturnType<typeof api.audioSource>) {
    if (!mayListen(now.current.phase, answeringNow.current)) return;
    sounds.clear();
    sounds.enqueue(src);
  }

  const playRec = (r: TryRef) => playFromBubble(api.recordingSource(r.rp_id, r.idx, r.n));

  // 「🔊 듣기」 on a past bubble: Ryan's voice or my line's model, at the rate last picked below (spec three-line-listen 3)
  function listenButton(idx: number) {
    const audio = lineAt(idx)?.audio;
    if (!audio) return null;
    return (
      <InRowButton label="🔊 듣기" onPress={() => playFromBubble(api.audioSource(audio, rate))} dim={!listenOk} textStyle={styles.link} />
    );
  }

  function replayJake() {
    if (state.jake) playFromBubble(api.audioSource(state.jake.audio));
  }

  // `toSay`: the line to say asked for them on its own, and a failure leaves it plain; a tap on a past bubble's
  // 「읽는 법 보기」 asks again whenever it is tapped
  async function fetchThree(idx: number, toSay = false): Promise<boolean> {
    setThrees((t) => ({ ...t, [idx]: "loading" }));
    setNoNotes(({ [idx]: _, ...rest }) => rest);
    try {
      const three = await api.getThree(rp.id, idx);
      setThrees((t) => ({ ...t, [idx]: three }));
      return true;
    } catch {
      setThrees((t) => {
        const { [idx]: _, ...rest } = t;
        return rest;
      });
      if (toSay) setNoNotes((n) => ({ ...n, [idx]: true }));
      return false;
    }
  }

  async function toggleThree(idx: number) {
    if (open[idx]) return setOpen({ ...open, [idx]: false });
    setOpen({ ...open, [idx]: true });
    if (threes[idx]) return;
    if (!(await fetchThree(idx))) setOpen((o) => ({ ...o, [idx]: false }));
  }

  // The line object for a bubble: the one on screen, or one seen before (an old record's reply lines included)
  function lineAt(idx: number): ScriptLine | undefined {
    if (state.line?.idx === idx) return state.line;
    return state.seen[idx];
  }

  // Sohee's sound plays only on the screen it was asked on: a back bumps `epoch`, and a practice mid-roleplay keeps
  // this screen but bumps `practiceNo`, which stays bumped after coming back (final review: a replay asked for
  // before 「따라 말하기 ›」 played on the practice screen)
  function here(): () => boolean {
    const my = epoch.current;
    const no = now.current.practiceNo;
    return () => epoch.current === my && now.current.practiceNo === no;
  }

  // ...and when it opens by itself, only if the line is still open when the sound arrives
  function stillOpen(idx: number, say: boolean): () => boolean {
    const there = here();
    return () =>
      there() && (say ? sayOpenNow.current && now.current.line?.idx === idx : koOpenNow.current[idx] === true);
  }

  const koViewAt = (idx: number) => koView(interp.entry(idx, lineAt(idx)), koOpen[idx] === true);

  function toggleKo(idx: number) {
    const open = koOpensOnTap(koViewAt(idx));
    koOpenNow.current = { ...koOpenNow.current, [idx]: open };
    setKoOpen(koOpenNow.current);
    if (open) interp.open(idx, lineAt(idx), stillOpen(idx, false));
  }

  function toggleSayKo(idx: number) {
    const open = koOpensOnTap(koView(interp.entry(idx, lineAt(idx)), state.interpreting));
    sayOpenNow.current = open;
    dispatch({ type: "interpret", open });
    if (open) interp.open(idx, lineAt(idx), stillOpen(idx, true));
  }

  // one bubble open at a time; closing one closes its notes and Sohee's line too, so the screen is plain again, and
  // the one that opens starts plain (`tapRow`). A folded bubble shows neither (PR #27 review).
  function toggleBubble(key: string) {
    const { open: next, close } = tapRow(openRow, key);
    const shut = Object.fromEntries(close.map((i) => [i, false]));
    setOpen((o) => ({ ...o, ...shut }));
    koOpenNow.current = { ...koOpenNow.current, ...shut };
    setKoOpen(koOpenNow.current);
    setOpenRow(next);
    toShow.current = next;
  }

  // an opened bubble has drawn its buttons: bring them on screen if they are below it (spec review-practice 8)
  function laidOut(key: string, e: LayoutChangeEvent) {
    if (toShow.current !== key) return;
    toShow.current = null;
    const y = scrollToShow(e.nativeEvent.layout, view.current);
    if (y !== null) scroll.current?.scrollTo({ y, animated: true });
  }

  // 「☆ 모아 두기」 for a line this screen holds (spec review-practice 5)
  function starAt(idx: number) {
    const l = lineAt(idx);
    if (!l) return null;
    return { saved: saved.has(l.text), busy: saved.pending(l.text), onPress: () => saved.toggle(rp.id, idx, l.text) };
  }

  function replaySituation() {
    copyGate.run(async () => {
      if (!canReplay(now.current.phase) || sounds.isPlaying()) return;
      setCopying(true);
      setCopyError(null);
      sounds.clear();
      try {
        const copy = await api.copyRoleplay(rp.id);
        if (mounted.current) dispatch({ type: "restarted", roleplay: copy });
      } catch (e) {
        if (mounted.current) setCopyError(messageOf(e));
      } finally {
        if (mounted.current) setCopying(false);
      }
    });
  }

  // Sohee's line for a past bubble. The bubbles below are plain functions, not components made inside this one: a
  // component defined in a render is a new type each time, so React threw the bubble away and made it again on every
  // render (todo 20261106_10 3).
  function koLine(idx: number) {
    const line = lineAt(idx);
    return <KoLine view={koViewAt(idx)} entry={interp.entry(idx, line)} onReplay={() => interp.replay(idx, line, here())} />;
  }

  // the Ryan line before a practised line of mine, to know what it answers (spec 4)
  function playBefore(audio: string | null) {
    if (audio) playFromBubble(api.audioSource(audio));
  }

  // a start right after 「취소」 or 「건너뛰기」 is the second tap of a double tap, on the button the redraw put there
  const startRecording = () => (tapHold.on ? undefined : gate.run(doStart));
  const stopRecording = () => stopThenSend(gate, stopRec, sendRec);
  // 「취소」 and 「건너뛰기」 go through the same gate and then hold taps a moment, on this screen and the next one
  // (spec record-cancel-skip 5)
  const cancelRecording = () => runThenHold(gate, tapHold, doCancel);
  const skipLine = () => runThenHold(gate, tapHold, doSkip);

  // 「취소」: the recording is stopped and deleted on the phone, never sent; back to before speaking, in the same mode
  // (spec record-cancel-skip 1). Nothing to cancel when a stop or the auto-stop got there first.
  async function doCancel(): Promise<boolean> {
    if (!rec.isRecording()) return false;
    await rec.discard();
    dispatch({ type: "recordCancel" });
    return true;
  }

  // 「다시 해 보기」 redraws the bar with 「건너뛰기」 where it was: its double tap must not skip the line (PR #45 review)
  const again = () => tapThenHold(tapHold, () => dispatch({ type: "again" }));

  // 「건너뛰기」: where 「다음」 goes, without a recording (spec record-cancel-skip 2)
  async function doSkip(): Promise<boolean> {
    if (!canSkip(state)) return false;
    dispatch({ type: "skip" });
    return true;
  }

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
      if (e.type === "audio") {
        sounds.enqueue(api.audioSource(e.key));
        markAnswer();
      }
      if (e.type === "error" && e.say?.audio) {
        sounds.enqueue(api.audioSource(e.say.audio));
        markAnswer();
      }
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
  // since leaving would cut Ryan's feedback, teacher Ryan's answer or the model off.
  const canPractise = !state.practice && canReplay(state.phase) && !playing;
  function practise(kind: "mine" | "shadow", idx: number) {
    if (canPractise) dispatch({ type: "practiseLine", kind, idx });
  }

  // `follow`: the bubble is a past Ryan line that can be practised (`practiceFor`). `row`: a past bubble, which
  // shows only the line until tapped and then its buttons (spec review-practice 8); without it (the line Ryan is
  // saying now) the buttons show as before and there is no 「모아 두기」.
  type RyanProps = { idx?: number; text: string; follow?: boolean; row?: string };
  function ryanBubble({ idx, text, follow, row }: RyanProps, key?: number) {
    const three = idx !== undefined ? threes[idx] : undefined;
    const folds = row !== undefined && idx !== undefined;
    const opened = folds && openRow === row;
    const star = folds ? starAt(idx) : null;
    const body = (
      <>
        <Text style={styles.ryanText}>
          {text}
          {star?.saved && !opened && <Text> </Text>}
          {star?.saved && !opened && <StarMark />}
        </Text>
        {idx !== undefined && (!folds || opened) && open[idx] && three === "loading" && (
          <Text style={common.sub}>세 줄을 만들고 있어요…</Text>
        )}
        {idx !== undefined && (!folds || opened) && open[idx] && three && three !== "loading" && <ThreeLineView three={three} />}
        {idx !== undefined && (!folds || opened) && koLine(idx)}
        {idx !== undefined && (!folds || opened) && (
          // one flow of buttons, 「따라 말하기 ›」 pushed right on whichever row it lands: with 「🔊 듣기」 in front, a
          // nested group took a whole row on a 360dp phone and left it alone on a third (spec three-line-listen 2A)
          <View style={styles.links}>
            {folds && listenButton(idx)}
            <Pressable onPress={() => toggleThree(idx)} hitSlop={8}>
              <Text style={styles.link}>{open[idx] ? "읽는 법 접기" : "읽는 법 보기 ›"}</Text>
            </Pressable>
            <KoButton view={koViewAt(idx)} onPress={() => toggleKo(idx)} />
            {star && <StarButton saved={star.saved} onPress={star.onPress} busy={star.busy} />}
            {follow && (
              <View style={styles.right}>
                <PractiseLink label="따라 말하기 ›" disabled={!canPractise} onPress={() => practise("shadow", idx)} inRow />
              </View>
            )}
          </View>
        )}
      </>
    );
    return (
      <Named key={key} part="ryan" onLayout={row ? (e) => laidOut(row, e) : undefined}>
        {folds ? (
          <Pressable onPress={() => toggleBubble(row)} style={[styles.bubble, styles.ryan, opened && styles.ryanOpen]}>
            {body}
          </Pressable>
        ) : (
          <View style={[styles.bubble, styles.ryan]}>{body}</View>
        )}
      </Named>
    );
  }

  // A past bubble of mine: the script line, what was heard under it, and its buttons once tapped (review-practice 8)
  function myBubble(at: number, b: (typeof state.history)[number]) {
    const idx = b.idx;
    const row = idx !== undefined ? `${at}:${idx}` : undefined;
    const opened = row !== undefined && openRow === row;
    const star = idx !== undefined ? starAt(idx) : null;
    return (
      <Named key={at} part="mine" onLayout={row ? (e) => laidOut(row, e) : undefined}>
        <Pressable onPress={() => row && toggleBubble(row)} style={[styles.bubble, styles.user, opened && styles.userOpen]}>
          <Text style={styles.plainText}>
            {b.script}
            {star?.saved && !opened && <Text> </Text>}
            {star?.saved && !opened && <StarMark />}
          </Text>
          {/* a line skipped without a recording has its script only (spec record-cancel-skip 3) */}
          {!b.skipped && (
            <View style={styles.heardRow}>
              <Text style={[styles.heardLine, styles.shrink]}>{keepWords(`들린 말: ${b.text}`)}</Text>
              {opened && b.rec && (
                <InRowButton label="🔊 내 녹음" onPress={() => b.rec && playRec(b.rec)} dim={!listenOk} textStyle={styles.link} />
              )}
            </View>
          )}
          {opened && idx !== undefined && koLine(idx)}
          {opened && idx !== undefined && (
            <View style={[styles.linkGroup, styles.gap]}>
              {listenButton(idx)}
              <KoButton view={koViewAt(idx)} onPress={() => toggleKo(idx)} />
              {practiceFor(state, b) === "mine" && (
                <PractiseLink label="이 줄 다시 ›" disabled={!canPractise} onPress={() => practise("mine", idx)} inRow />
              )}
              {star && <StarButton saved={star.saved} onPress={star.onPress} busy={star.busy} />}
            </View>
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
  const fromSaved = practice?.from === "saved"; // saved sentences, maybe from several roleplays (spec review-practice 7)
  const title = practice
    ? fromSaved
      ? "모아 둔 문장"
      : midway
        ? practice.kind === "mine"
          ? "이 줄 다시"
          : "따라 말하기"
        : practice.kind === "mine"
          ? "내 대사 다시 연습"
          : "라이언 대사 따라 말하기"
    : rp.frame.title_ko;
  const count = practice
    ? midway || (fromSaved && practice.order.length === 1)
      ? null
      : `${practice.at + 1}/${practice.order.length}`
    : state.progress && state.progress.total > 0
      ? `내 대사 ${state.progress.no}/${state.progress.total}`
      : null;
  const before = practice?.kind === "mine" && line && !fromSaved ? state.seen[line.idx - 1] : undefined;
  // in saved practice the line before is hidden until asked (「앞 대화 보기」), whoever said it
  const savedBefore = fromSaved && line ? rp.lines[line.idx - 1] : undefined;
  const canCopy = fromSaved && canReplay(state.phase) && !playing && !copying;

  return (
    <View style={styles.wrap}>
      <View style={styles.header}>
        <BackButton onPress={askLeave} />
        <View style={styles.titleRow}>
          <Text style={[common.title, styles.titleText]}>{keepWords(title)}</Text>
          {count && <Text style={styles.count}>{count}</Text>}
        </View>
        <Text style={common.sub}>
          {keepWords(
            practice ? rp.frame.title_ko : `나: ${rp.frame.user_role_ko} · 라이언: ${rp.frame.ryan_role_ko} · ${rp.frame.place_ko}`,
          )}
        </Text>
        {fromSaved && (
          <Pressable onPress={replaySituation} hitSlop={8} style={styles.replay}>
            <Text style={[styles.link, !canCopy && styles.off]}>{copying ? "준비하고 있어요" : "이 상황 다시 하기 ›"}</Text>
          </Pressable>
        )}
        {copyError && <ErrorText text={copyError} />}
      </View>
      <ScrollView
        ref={scroll}
        contentContainerStyle={styles.scroll}
        onLayout={(e) => (view.current.height = e.nativeEvent.layout.height)}
        onScroll={(e) => (view.current.offset = e.nativeEvent.contentOffset.y)}
        scrollEventThrottle={32}
      >
        {/* who says each bubble, like a messenger: others left in gray, me right in blue (2026-11-06 user) */}
        {state.jake && !practice && (
          <Named part="jake">
            <Pressable onPress={replayJake} style={[styles.bubble, styles.ryan]}>
              <Text style={styles.plainText}>{keepWords(state.jake.text)}</Text>
              <Text style={styles.hint}>🔊 눌러서 다시 듣기</Text>
            </Pressable>
          </Named>
        )}
        {state.history.map((b, i) =>
          b.kind === "ryan" ? (
            ryanBubble(
              { idx: b.idx, text: b.text, follow: practiceFor(state, b) === "shadow", row: b.idx !== undefined ? `${i}:${b.idx}` : undefined },
              i,
            )
          ) : b.kind === "user" && b.script ? (
            myBubble(i, b)
          ) : (
            <Named key={i} part={b.kind === "user" ? "mine" : "feedback"}>
              <View style={[styles.bubble, b.kind === "user" ? styles.user : styles.feedback]}>
                <Text style={styles.plainText}>{keepWords(b.text)}</Text>
              </View>
            </Named>
          ),
        )}
        {state.phase === "loading" && (
          <Waiting who="ryan" text={practice ? "대사를 준비하고 있어요" : "다음 대사를 준비하고 있어요"} onShow={toEnd} />
        )}
        {state.phase === "ryan" && line && ryanBubble({ idx: line.idx, text: line.text })}
        {myTurn && before?.speaker === "ryan" && (
          <Named part="ryan">
            <Pressable onPress={() => playBefore(before.audio)} style={[styles.bubble, styles.ryan]}>
              <Text style={styles.beforeText}>{before.text}</Text>
              {koLine(before.idx)}
              <View style={styles.linkGroup}>
                <Text style={styles.hint}>🔊 눌러서 듣기</Text>
                <View style={styles.linkRow}>
                  <KoButton view={koViewAt(before.idx)} onPress={() => toggleKo(before.idx)} />
                </View>
              </View>
            </Pressable>
          </Named>
        )}
        {savedBefore && (
          <Pressable onPress={() => dispatch({ type: "toggleBefore" })} hitSlop={8} style={styles.beforeToggle}>
            <Text style={styles.link}>{state.beforeOpen ? "앞 대화 접기" : "앞 대화 보기 ›"}</Text>
          </Pressable>
        )}
        {myTurn && savedBefore && state.beforeOpen && (
          <Named part={savedBefore.speaker === "ryan" ? "ryan" : "mine"}>
            <Pressable
              onPress={() => playBefore(savedBefore.audio)}
              style={[styles.bubble, savedBefore.speaker === "ryan" ? styles.ryan : styles.user]}
            >
              <Text style={styles.beforeText}>{savedBefore.text}</Text>
              <Text style={styles.hint}>🔊 눌러서 듣기</Text>
            </Pressable>
          </Named>
        )}
        {/* the line to say, Ryan's own in shadow practice: the learner says it, so it is on their side */}
        {myTurn && line && (
          <Named part="now">
            <View style={[styles.bubble, styles.now]}>
              <LineToSay
                text={line.text}
                three={lineNotes(line, threes[line.idx], !!noNotes[line.idx])}
                open={state.reading}
                onToggle={() => dispatch({ type: "toggleReading" })}
                ko={{
                  view: koView(interp.entry(line.idx, line), state.interpreting),
                  entry: interp.entry(line.idx, line),
                  onToggle: () => toggleSayKo(line.idx),
                  onReplay: () => interp.replay(line.idx, line, here()),
                }}
                star={{ saved: saved.has(line.text), busy: saved.pending(line.text), onPress: () => saved.toggle(rp.id, line.idx, line.text) }}
              />
            </View>
          </Named>
        )}
        {/* what was heard, and the recording just sent next to it (spec three-line-listen 4) */}
        {state.heard && (
          <View style={styles.heardNow}>
            <Text style={[styles.heard, styles.shrink]}>{keepWords(`들린 말: ${state.heard}`)}</Text>
            {state.heardRec && (
              <InRowButton
                label="🔊 내 녹음"
                onPress={() => state.heardRec && playRec(state.heardRec)}
                dim={!listenOk}
                textStyle={styles.link}
              />
            )}
          </View>
        )}
        {state.feedback !== "" && (
          <Named part="feedback">
            <View style={[styles.bubble, styles.feedback]}>
              <Text style={styles.plainText}>{keepWords(state.feedback)}</Text>
            </View>
          </Named>
        )}
        {busy && !state.feedback && <Waiting who="ryan" text="라이언이 듣고 있어요" onShow={toEnd} />}
        {state.message &&
          (state.phase === "error" ? <ErrorText text={state.message} /> : <Text style={styles.notice}>{keepWords(state.message)}</Text>)}
      </ScrollView>

      {/* No 「처음으로」 at the bottom: back does nearly the same, one screen at a time (2026-11-06 user). Without it
          the bar is empty while Ryan speaks or the next line loads, so it shows only when it has buttons. */}
      {(myTurn || state.phase === "error") && (
        <View style={styles.controls}>
          {myTurn && state.phase !== "error" && (
            <>
              <View style={styles.row}>
                <Button label="🔊 다시 듣기" onPress={() => listen()} kind="plain" small disabled={busy || state.phase === "recording"} />
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
              {/* gray on the left, blue filling the rest, like 「다시 해 보기 | 다음」 (spec record-cancel-skip 4) */}
              {state.phase !== "evaluated" && (
                <View style={styles.pair}>
                  {canSkip(state) && <Button label="건너뛰기" onPress={skipLine} kind="plain" />}
                  {state.phase === "recording" && <Button label="취소" onPress={cancelRecording} kind="plain" />}
                  <Button
                    label={state.phase === "recording" ? "■ 말하기 끝" : busy ? "평가하고 있어요" : shadow ? "🎤 따라 말하기" : "🎤 말하기"}
                    onPress={state.phase === "recording" ? stopRecording : startRecording}
                    disabled={busy}
                    grow
                  />
                </View>
              )}
              {/* after teacher Ryan's answer the same line again, or past it without a recording (spec offscript-aside 5,
                  record-cancel-skip 2) */}
              {state.phase === "evaluated" && state.aside && (
                <View style={styles.pair}>
                  <Button label="건너뛰기" onPress={skipLine} kind="plain" />
                  <Button label="다시 해 보기" onPress={again} grow />
                </View>
              )}
              {state.phase === "evaluated" && !state.aside && (
                <View style={styles.row}>
                  <Button label="다시 해 보기" onPress={again} kind="plain" />
                  <Button label={midway ? "대화로 돌아가기" : "다음"} onPress={() => dispatch({ type: "next" })} />
                </View>
              )}
            </>
          )}
          {state.phase === "error" && <Button label="다시 시도" onPress={() => tapThenHold(tapHold, () => dispatch({ type: "retry" }))} />}
        </View>
      )}
    </View>
  );
}

// A small link under a past bubble: practise that line on its own (spec 9). Dimmed while it cannot be used, but
// still taking the tap (`practise` ignores it then): a disabled Pressable passes the tap to the bubble around it,
// which would fold the bubble instead (final review; then the Ryan bubble opened the notes).
function PractiseLink(props: { label: string; disabled: boolean; onPress: () => void; inRow?: boolean }) {
  const { label, disabled, onPress, inRow } = props;
  return (
    <Pressable onPress={onPress} hitSlop={8} style={inRow ? undefined : styles.practise}>
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
  gap: { marginTop: 8 },
  heardLine: { fontSize: 14, color: colors.sub },
  heardRow: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: 8, marginTop: 4 },
  heardNow: { flexDirection: "row", alignItems: "center", alignSelf: "flex-end", gap: 12, marginTop: 4, maxWidth: "100%" },
  shrink: { flexShrink: 1 },
  ryanOpen: { backgroundColor: "#E9ECEF" },
  userOpen: { backgroundColor: "#D0EBFF" },
  beforeToggle: { alignSelf: "flex-end", marginTop: 4 },
  replay: { alignSelf: "flex-start", marginTop: 6 },
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
  links: { flexDirection: "row", flexWrap: "wrap", alignItems: "center", rowGap: 12, columnGap: 16, marginTop: 8 },
  right: { marginLeft: "auto" },
  linkGroup: { flexDirection: "row", flexWrap: "wrap", alignItems: "center", gap: 16 },
  linkRow: { marginTop: 4 },
  link: { fontSize: 15, color: colors.primary, fontWeight: "600" },
  practiseText: { fontSize: 14, color: colors.primary, fontWeight: "600" },
  off: { opacity: 0.4 },
  heard: { fontSize: 14, color: colors.sub },
  notice: { fontSize: 16, color: colors.sub, marginTop: 8 },
  controls: { padding: 12, borderTopWidth: 1, borderTopColor: "#E9ECEF" },
  row: { flexDirection: "row", flexWrap: "wrap", gap: 6, justifyContent: "center" },
  pair: { flexDirection: "row", gap: 8 },
});
