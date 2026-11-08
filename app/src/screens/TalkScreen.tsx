// 「자유 대화」 (spec free-talk-design 2, 6): Ryan asks a first question, I answer with 「🎤 말하기」, he answers from his
// first sentence on, and 「대화 끝내기」 shows the fixes one at a time (`TalkFixScreen`, spec 7). `talkReduce` decides
// what shows; this opens the talk, plays the sounds, records (`useMic`) and sends.
//
// Cutting Ryan off (spec 2): his sounds play under `talk:<key>`, and the keys whose sound has started are kept, so the
// tap that cuts him says how many of his sentences I heard (`heardCount`). The reducer's `turn` grows with every
// recording and with 「대화 끝내기」, and the stream's events are checked against it through `now` (`isCurrent`): the
// answer to an older turn, its sounds and its 「sounds ended」 are dropped before a sound is queued.
//
// The bubbles are the roleplay's, copied from `RoleplayScreen`, which this PR does not touch: its `styles` (bubble,
// ryan, user, feedback, ryanOpen, userOpen, ryanText, plainText, links, link, hint, micHint, count and the frame) and
// the bubble handlers `playFromBubble`, `toggleThree` (here `toggleNotes`), `toggleKo`, `toggleBubble`, `ryanBubble` and
// `myBubble`. They move into one place with the recording wiring (docs/todo 20261108_44_todo_roleplay_use_usemic.md).
import { useEffect, useReducer, useRef, useState, type ComponentRef } from "react";
import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";

import { api } from "../api";
import type { TalkEvent, ThreeLine, TryRef } from "../api/types";
import type { SoundQueue } from "../audio/player";
import { tapPlay } from "../audio/tapPlay";
import { useMic } from "../audio/useMic";
import { usePlayingTag } from "../audio/usePlayingTag";
import { createGate, tapHold, tapThenHold } from "../flow/gate";
import { koOpensOnTap, koView } from "../flow/interpret";
import { tapRow } from "../flow/review";
import {
  canEnd,
  canSpeak,
  cutOf,
  englishTurns,
  heardCount,
  isCurrent,
  lineSounds,
  mayListenTalk,
  talkInitial,
  talkMessageIsError,
  talkReduce,
  turnNo,
  type TalkAction,
  type TalkBubble,
  type TalkState,
} from "../flow/talk";
import { BackButton, useBackKey } from "../ui/BackButton";
import { Button } from "../ui/Button";
import { InRowButton } from "../ui/InRowButton";
import { KoButton, KoLine } from "../ui/Interpret";
import { keepWords } from "../ui/keepWords";
import { Named } from "../ui/Named";
import { PlayLabel } from "../ui/PlayIcon";
import { SoonEnds, StopButton } from "../ui/StopButton";
import { ThreeLineView } from "../ui/ThreeLine";
import { koTag, useInterpret } from "../ui/useInterpret";
import { colors, top } from "../ui/theme";
import { ErrorText, messageOf, styles as common, Waiting } from "./common";
import { TalkFixScreen } from "./TalkFixScreen";

type Props = { sounds: SoundQueue; onHome: () => void };
type Of<K extends TalkBubble["kind"]> = Extract<TalkBubble, { kind: K }>;

// Ryan's sounds in the talk: the keys whose sound has started are the sentences I heard (spec 2)
const TALK = "talk:";
const talkTag = (key: string) => TALK + key;
// a 🔊 asked for from a bubble (spec play-button-feedback 2): Ryan's line again, his Korean nudge, my recording
const bubbleTag = (idx: number) => `bubble:${idx}`;
const recTag = (r: TryRef) => `rec:${r.rp_id}:${r.idx}:${r.n}`;

export function TalkScreen({ sounds, onHome }: Props) {
  const [s, dispatch] = useReducer(talkReduce, talkInitial);
  // The talk with every action so far, drawn or not: a tap that lands before the redraw (the second tap of a double
  // tap, 「대화 끝내기」 and 「🎤 말하기」 together) reads where the talk is now (REVIEW.md 「앱 화면」).
  const now = useRef<TalkState>(talkInitial);
  function act(a: TalkAction) {
    now.current = talkReduce(now.current, a);
    dispatch(a);
  }
  const rp = s.roleplay;
  // false once I leave (back, or ending a talk with nothing said) and on unmount: what arrives late is dropped
  const mounted = useRef(true);
  // Ryan's sound keys whose sound has started since the last cut (`heardCount`)
  const started = useRef<Set<string>>(new Set());
  // one opening and one end at a time: a double tap on 「대화 끝내기」 asks Claude for the fixes once (spec Review Focus 2)
  const openGate = useRef(createGate()).current;
  const endGate = useRef(createGate()).current;
  const scroll = useRef<ComponentRef<typeof ScrollView>>(null);
  const playingTag = usePlayingTag(sounds);
  const listenOk = mayListenTalk(s);
  // past bubbles show only what was said; one opens its buttons on a tap, by line (spec 2, review-practice 8)
  const [openRow, setOpenRow] = useState<string | null>(null);
  const [threes, setThrees] = useState<Record<number, ThreeLine | "loading">>({});
  const [notesOpen, setNotesOpen] = useState<Record<number, boolean>>({});
  // which Ryan lines show Sohee's line; the ref is set at the tap, before the render, since a sound already made plays
  // at once (as on the roleplay screen)
  const [koOpen, setKoOpen] = useState<Record<number, boolean>>({});
  const koOpenNow = useRef(koOpen);
  // Sohee plays by herself only on my turn with nothing playing; a tap on her line only on my turn (`mayListenTalk`)
  const interp = useInterpret(rp?.id ?? "", sounds, (auto) =>
    mounted.current && mayListenTalk(now.current) && (!auto || !sounds.isPlaying()),
  );

  const mic = useMic({
    canStart: () => mounted.current && canSpeak(now.current),
    // 「🎤 말하기」 while Ryan speaks cuts him off: his sound stops at once and how much I heard goes with the turn
    beforeStart: () => {
      act({ type: "recordStart", heard: cutRyan() });
    },
    onCancelled: () => act({ type: "recordCancel" }),
    onNoSpeech: () => act({ type: "noSpeech" }),
    onFailed: () => act({ type: "micFailed" }),
    onStopped: () => act({ type: "recordStop" }),
    send,
  });

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);

  useEffect(
    () =>
      sounds.subscribeTag(({ tag }) => {
        if (tag?.startsWith(TALK)) started.current.add(tag.slice(TALK.length));
      }),
    [sounds],
  );

  useEffect(() => openTalk(), []); // eslint-disable-line react-hooks/exhaustive-deps

  // Ryan's turn ends when his sounds have played and all of his answer is in (`done`). `done` may come after the last
  // sound ended: `onIdle` then calls at once (the reducer drops an early `ryanDone`). A cut-off answer's call finds a
  // newer turn and does nothing; `sounds.clear()` at the cut drops it too.
  useEffect(() => {
    if (s.phase !== "ryan" || !s.done) return;
    const turn = s.turn;
    sounds.onIdle(() => {
      if (mounted.current && isCurrent(now.current, turn)) act({ type: "ryanDone" });
    });
  }, [s.phase, s.done, s.turn, sounds]); // eslint-disable-line react-hooks/exhaustive-deps

  // what was said, Ryan's text and a message come in at the bottom. Always a moment later: on Android a scroll run
  // with the views that appear in the same commit stops above them (PR #20 review).
  const toEnd = () => setTimeout(() => scroll.current?.scrollToEnd({ animated: true }), 50);
  useEffect(() => {
    toEnd();
  }, [s.bubbles.length, s.phase, s.pending, s.message]);

  // Ryan asks his first question at once: its sound was made on the Mac ahead (spec 2)
  function openTalk() {
    void openGate.run(async () => {
      try {
        const talk = await api.createTalk();
        if (!mounted.current) return;
        const first = talk.lines[0];
        if (!first) throw new Error("a talk without its first question");
        for (const k of lineSounds(first)) sounds.enqueue(api.audioSource(k), talkTag(k));
        act({ type: "opened", roleplay: talk });
      } catch (e) {
        if (mounted.current) act({ type: "openFailed", message: messageOf(e) });
      }
    });
  }

  // Stops Ryan for a recording or the end, saying how many sentences of his answer I heard: only while he says it
  // (spec 2). What starts from here on belongs to his next answer.
  function cutRyan(): number | null {
    const t = now.current;
    const last = t.bubbles[t.bubbles.length - 1];
    const heard = t.phase === "ryan" && last?.kind === "ryan" ? heardCount(last.parts, started.current) : null;
    sounds.clear();
    started.current = new Set();
    return heard;
  }

  // Sends my turn and plays Ryan's answer as it streams in, from his first sentence (spec 2, 4). Only the turn on
  // screen plays: a turn I cut off, ended or left behind (`isCurrent`, `live`, back) is dropped here, before its sound
  // is queued, and by the reducer.
  async function send(uri: string, live: () => boolean) {
    const t = now.current;
    const id = t.roleplay?.id;
    const turn = t.turn; // this recording's: `recordStart` grew it
    const current = () => live() && mounted.current && isCurrent(now.current, turn);
    if (!id || !current()) return;
    const onEvent = (e: TalkEvent) => {
      if (!current()) return;
      if (e.type === "audio") sounds.enqueue(api.audioSource(e.key), talkTag(e.key));
      if (e.type === "error" && e.say?.audio) sounds.enqueue(api.audioSource(e.say.audio));
      act({ type: "event", turn, e });
    };
    try {
      // a cut made before a cancelled recording is still on Ryan's line (`cutOf`)
      await api.talkTurn(id, uri, cutOf(t), onEvent);
    } catch (e) {
      if (current()) act({ type: "failed", turn, message: messageOf(e) });
    }
  }

  // 「대화 끝내기」 (spec 6): Ryan stops for good and the Mac picks the fixes. `endStart` moves past the turn as
  // 「🎤 말하기」 does, so the later sentences of a reply I ended in are dropped in `send` while the fixes are made; how
  // many I heard goes with the end. With no English turn there is nothing to fix, so home at once. Not after 「취소」
  // for a moment: this button is drawn where 「취소」 was, and the second tap of its double tap must not end the talk
  // (spec record-cancel-skip 5).
  const endTalk = () => {
    if (tapHold.on) return;
    void endGate.run(async () => {
      const t = now.current;
      if (!mounted.current || !canEnd(t)) return;
      if (englishTurns(t) === 0) {
        mounted.current = false;
        sounds.clear();
        onHome();
        return;
      }
      act({ type: "endStart", heard: cutRyan() });
      await askEnd();
    });
  };

  // The cut kept on Ryan's last line goes with it, also one made before a cancelled recording (as with a turn)
  async function askEnd() {
    const t = now.current;
    const id = t.roleplay?.id;
    if (!id) return;
    try {
      const end = await api.endTalk(id, cutOf(t));
      if (mounted.current) act({ type: "ended", end });
    } catch (e) {
      if (mounted.current) act({ type: "endFailed", message: messageOf(e) });
    }
  }

  // 「다시 시도」: the opening or the end again. The redraw puts 「🎤 말하기」 there, so taps are held a moment (as in the
  // roleplay); a second tap finds the talk no longer in error.
  const retry = () =>
    tapThenHold(tapHold, () => {
      const t = now.current;
      if (t.phase !== "error") return;
      act({ type: "retry" });
      if (t.errorFrom === "opening") openTalk();
      else if (t.errorFrom === "ending") void endGate.run(askEnd);
    });

  // Back (the button and the phone's key): home without asking and without fixes (spec 2). Ryan stops, a recording in
  // progress is deleted unsent, and what arrives late is dropped (`mounted`, `useMic`).
  async function leave() {
    if (!mounted.current) return;
    mounted.current = false;
    sounds.clear();
    try {
      await mic.leave();
    } finally {
      onHome();
    }
  }
  const goBack = () => void leave();
  useBackKey(goBack);

  // A 🔊 on a bubble: stops what plays and plays it, or stops it while it plays (spec play-button-feedback 3); only on
  // my turn, so never over Ryan or into a recording (`mayListenTalk`)
  function playFromBubble(srcs: ReturnType<typeof api.audioSource>[], tag: string) {
    if (!mounted.current || !mayListenTalk(now.current) || srcs.length === 0) return;
    tapPlay(sounds, tag, () => {
      sounds.clear();
      for (const src of srcs) sounds.enqueue(src, tag);
    });
  }
  // 「🔊 듣기」 plays a cut-off answer whole too (spec 2)
  const playLine = (b: Of<"ryan">) =>
    playFromBubble(lineSounds({ parts: b.parts, audio: null }).map((k) => api.audioSource(k)), bubbleTag(b.idx));
  const playHelp = (b: Of<"help">) => b.audio && playFromBubble([api.audioSource(b.audio)], bubbleTag(b.idx));
  const playRec = (r: TryRef) => playFromBubble([api.recordingSource(r.rp_id, r.idx, r.n)], recTag(r));

  // 「읽는 법 보기」: made on the Mac only when asked; a failure folds it again and the next tap asks again
  async function toggleNotes(idx: number) {
    if (notesOpen[idx]) return setNotesOpen((o) => ({ ...o, [idx]: false }));
    setNotesOpen((o) => ({ ...o, [idx]: true }));
    if (threes[idx] || !rp) return;
    setThrees((t) => ({ ...t, [idx]: "loading" }));
    try {
      const three = await api.getThree(rp.id, idx);
      setThrees((t) => ({ ...t, [idx]: three }));
    } catch {
      setThrees(({ [idx]: _, ...rest }) => rest);
      setNotesOpen((o) => ({ ...o, [idx]: false }));
    }
  }

  const koViewAt = (idx: number) => koView(interp.entry(idx), koOpen[idx] === true);
  function setKo(next: Record<number, boolean>) {
    koOpenNow.current = next;
    setKoOpen(next);
  }
  // 「통역」: made on the Mac only when asked (spec 2); her voice plays only if the line is still open when it comes
  function toggleKo(idx: number) {
    const open = koOpensOnTap(koViewAt(idx));
    setKo({ ...koOpenNow.current, [idx]: open });
    if (open) interp.open(idx, undefined, () => mounted.current && koOpenNow.current[idx] === true);
  }
  const replayKo = (idx: number) => tapPlay(sounds, koTag(idx), () => interp.replay(idx, undefined, () => mounted.current));

  // one past bubble open at a time; the one closing and the one opening start plain (`tapRow`, as in the roleplay)
  function toggleBubble(idx: number) {
    const { open: next, close } = tapRow(openRow, String(idx));
    const shut = Object.fromEntries(close.map((i) => [i, false]));
    setNotesOpen((o) => ({ ...o, ...shut }));
    setKo({ ...koOpenNow.current, ...shut });
    setOpenRow(next);
  }

  // Ryan's English line, the sentences I did not hear when I cut in weak (spec 2). The line he says now has its buttons
  // out; a past one opens them on a tap. The buttons are the roleplay's, in its order.
  function ryanBubble(b: Of<"ryan">, isNow: boolean) {
    const opened = isNow || openRow === String(b.idx);
    const three = threes[b.idx];
    const body = (
      <>
        <Text style={styles.ryanText}>
          {b.parts.length === 0
            ? b.text
            : b.parts.map((p, i) => (
                <Text key={i} style={b.heard !== null && i >= b.heard ? styles.unheard : undefined}>
                  {i > 0 ? " " : ""}
                  {p.text}
                </Text>
              ))}
        </Text>
        {opened && notesOpen[b.idx] && three === "loading" && (
          <Text style={common.sub}>{keepWords("세 줄을 만들고 있어요…")}</Text>
        )}
        {opened && notesOpen[b.idx] && three && three !== "loading" && <ThreeLineView three={three} />}
        {opened && (
          <KoLine
            view={koViewAt(b.idx)}
            entry={interp.entry(b.idx)}
            onReplay={() => replayKo(b.idx)}
            playing={playingTag === koTag(b.idx)}
          />
        )}
        {opened && (
          <View style={styles.links}>
            <InRowButton
              label="듣기"
              playing={playingTag === bubbleTag(b.idx)}
              onPress={() => playLine(b)}
              dim={!listenOk}
              textStyle={styles.link}
            />
            <Pressable onPress={() => toggleNotes(b.idx)} hitSlop={8}>
              <Text style={styles.link}>{notesOpen[b.idx] ? "읽는 법 접기" : "읽는 법 보기 ›"}</Text>
            </Pressable>
            <KoButton view={koViewAt(b.idx)} onPress={() => toggleKo(b.idx)} />
          </View>
        )}
      </>
    );
    return (
      <Named key={b.idx} part="ryan">
        {isNow ? (
          <View style={[styles.bubble, styles.ryan]}>{body}</View>
        ) : (
          <Pressable onPress={() => toggleBubble(b.idx)} style={[styles.bubble, styles.ryan, opened && styles.ryanOpen]}>
            {body}
          </Pressable>
        )}
      </Named>
    );
  }

  // what was heard of my turn; opened, its recording (spec 2, three-line-listen 3)
  function myBubble(b: Of<"me">) {
    const opened = openRow === String(b.idx);
    return (
      <Named key={b.idx} part="mine">
        <Pressable onPress={() => toggleBubble(b.idx)} style={[styles.bubble, styles.user, opened && styles.userOpen]}>
          <Text style={styles.plainText}>{keepWords(b.text)}</Text>
          {opened && (
            <View style={styles.links}>
              <InRowButton
                label="내 녹음"
                playing={playingTag === recTag(b.rec)}
                onPress={() => playRec(b.rec)}
                dim={!listenOk}
                textStyle={styles.link}
              />
            </View>
          )}
        </Pressable>
      </Named>
    );
  }

  // Ryan's fixed Korean nudge after Korean said with 「🎤 말하기」 (spec 3): the yellow box, his voice again on a tap
  function helpBubble(b: Of<"help">) {
    return (
      <Named key={b.idx} part="feedback">
        <Pressable onPress={() => playHelp(b)} style={[styles.bubble, styles.feedback]}>
          <Text style={styles.plainText}>{keepWords(b.text)}</Text>
          {b.audio && <PlayLabel on={playingTag === bubbleTag(b.idx)} label="눌러서 다시 듣기" style={styles.hint} />}
        </Pressable>
      </Named>
    );
  }

  if (s.phase === "fixes" && rp && s.end) return <TalkFixScreen rp={rp} end={s.end} sounds={sounds} onHome={onHome} />;

  const last = s.bubbles[s.bubbles.length - 1];
  const nowIdx = last?.kind === "ryan" ? last.idx : null;

  return (
    <View style={styles.wrap}>
      <View style={styles.header}>
        <BackButton onPress={goBack} />
        <View style={styles.titleRow}>
          <Text style={[common.title, styles.titleText]}>{keepWords("자유 대화")}</Text>
          {rp && <Text style={styles.count}>{keepWords(`${turnNo(s)}번째`)}</Text>}
        </View>
      </View>
      <ScrollView ref={scroll} contentContainerStyle={styles.scroll}>
        {/* who says each bubble, like a messenger: Ryan left in gray, me right in blue (as in the roleplay) */}
        {s.bubbles.map((b) =>
          b.kind === "ryan" ? ryanBubble(b, b.idx === nowIdx) : b.kind === "me" ? myBubble(b) : helpBubble(b),
        )}
        {s.phase === "opening" && <Waiting who="ryan" text={keepWords("준비하고 있어요")} onShow={toEnd} />}
        {s.phase === "waiting" && s.pending === "" && (
          <Waiting who="ryan" text={keepWords("라이언이 듣고 있어요")} onShow={toEnd} />
        )}
        {/* Ryan's answer as it is written, before it is his line: no buttons yet */}
        {s.pending !== "" && (
          <Named part="ryan">
            <View style={[styles.bubble, styles.ryan]}>
              <Text style={styles.ryanText}>{s.pending}</Text>
            </View>
          </Named>
        )}
        {s.phase === "ending" && <Waiting who="ryan" text={keepWords("라이언이 대화를 돌아보고 있어요")} onShow={toEnd} />}
        {s.message &&
          (talkMessageIsError(s) ? <ErrorText text={s.message} /> : <Text style={styles.notice}>{keepWords(s.message)}</Text>)}
      </ScrollView>

      {/* the less important button on the left, the main one filling the rest (spec button-colors 1, record-cancel-skip 4) */}
      <View style={styles.controls}>
        {s.phase === "recording" ? (
          <>
            {/* near the 55 s stop, that recording ends soon (spec record-feedback 2) */}
            <SoonEnds since={mic.liveSince} />
            <View style={styles.pair}>
              <Button label="취소" onPress={mic.cancel} kind="secondary" />
              {/* 「● 말하기 끝」: blue, a blinking red dot and the voice line once the mic is on (spec record-feedback 2) */}
              <StopButton live={mic.liveSince !== null} onLevel={mic.onLevel} onPress={mic.stop} />
            </View>
          </>
        ) : s.phase === "error" ? (
          <Button label="다시 시도" onPress={retry} />
        ) : (
          <>
            {/* my first turn says to tap 🎤 first (spec 2, record-feedback 3) */}
            {!s.micUsed && canSpeak(s) && <Text style={styles.micHint}>{keepWords("🎤를 누르고 말하세요")}</Text>}
            <View style={styles.pair}>
              <Button label="대화 끝내기" onPress={endTalk} kind="secondary" disabled={!canEnd(s)} />
              <Button label="🎤 말하기" onPress={mic.start} disabled={!canSpeak(s)} grow />
            </View>
          </>
        )}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { flex: 1, backgroundColor: colors.bg, paddingTop: top },
  header: { paddingHorizontal: 16, paddingBottom: 8, borderBottomWidth: 1, borderBottomColor: "#E9ECEF" },
  titleRow: { flexDirection: "row", alignItems: "center", gap: 8 },
  titleText: { flexShrink: 1 },
  // 「N번째」 in my blue, where the roleplay has 「내 대사 2/3」 (spec 2)
  count: { fontSize: 14, fontWeight: "700", color: colors.primary, backgroundColor: colors.user, borderRadius: 10, paddingHorizontal: 8, paddingVertical: 2 },
  scroll: { padding: 16, paddingBottom: 32 },
  bubble: { borderRadius: 14, padding: 12, marginVertical: 5, maxWidth: "92%" },
  ryan: { backgroundColor: colors.ryan, alignSelf: "flex-start" },
  user: { backgroundColor: colors.user, alignSelf: "flex-end" },
  feedback: { backgroundColor: colors.feedback, alignSelf: "flex-start" },
  ryanOpen: { backgroundColor: "#E9ECEF" },
  userOpen: { backgroundColor: "#D0EBFF" },
  ryanText: { fontSize: 20, color: colors.text, lineHeight: 28 },
  // the sentences of a cut-off answer I did not hear (spec 2)
  unheard: { color: colors.weak },
  plainText: { fontSize: 17, color: colors.text, lineHeight: 25 },
  hint: { fontSize: 13, color: colors.weak, marginTop: 4 },
  links: { flexDirection: "row", flexWrap: "wrap", alignItems: "center", rowGap: 12, columnGap: 16, marginTop: 8 },
  link: { fontSize: 15, color: colors.primary, fontWeight: "600" },
  notice: { fontSize: 16, color: colors.sub, marginTop: 8 },
  micHint: { textAlign: "center", color: colors.primary, fontSize: 15, fontWeight: "600", marginBottom: 2 },
  controls: { padding: 12, borderTopWidth: 1, borderTopColor: "#E9ECEF" },
  pair: { flexDirection: "row", gap: 8 },
});
