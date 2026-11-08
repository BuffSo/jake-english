// 「대화 돌아보기」 after a free talk (spec free-talk-design 7): one fix at a time. Ryan's explanation in the yellow box,
// said once when the fix opens; 「내가 한 말」 with my recording only on a tap; 「이렇게 말해 보세요」 with the model, the
// three lines and ☆; 「🎤 따라 말하기」 tried as the end screen's 「내 대사 다시 연습」, the result below. No interpretation
// here. `fixReduce` decides what shows; this loads the line, plays the sounds and records (`useMic`).
//
// The bubble styles are copied from `RoleplayScreen` (its `styles`), which this PR does not touch; they move into one
// place with the recording wiring (docs/todo 20261108_44_todo_roleplay_use_usemic.md).
import { useEffect, useReducer, useRef, useState, type ComponentRef } from "react";
import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";

import { api } from "../api";
import type { AttemptEvent, Roleplay, TalkEnd, ThreeLine, TryRef } from "../api/types";
import type { SoundQueue } from "../audio/player";
import { tapPlay } from "../audio/tapPlay";
import { useAnswering } from "../audio/useAnswering";
import { useMic } from "../audio/useMic";
import { usePlayingTag } from "../audio/usePlayingTag";
import { tapHold, tapThenHold } from "../flow/gate";
import { toggleRow } from "../flow/review";
import { mayListen } from "../flow/state";
import { canTry, fixCount, fixInitial, fixMessageIsError, fixReduce, isLastFix, nextLabel } from "../flow/talkFix";
import { BackButton, useBackKey } from "../ui/BackButton";
import { Button } from "../ui/Button";
import { HeardLine } from "../ui/HeardLine";
import { heardKey } from "../ui/heardView";
import { InRowButton } from "../ui/InRowButton";
import { keepWords } from "../ui/keepWords";
import { Named } from "../ui/Named";
import { lineNotes, needsNotes, notesView } from "../ui/notesView";
import { StarButton } from "../ui/Star";
import { SoonEnds, StopButton } from "../ui/StopButton";
import { ThreeLineView } from "../ui/ThreeLine";
import { useSaved } from "../ui/useSaved";
import { colors, top } from "../ui/theme";
import { ErrorText, messageOf, styles as common, Waiting } from "./common";

type Props = { rp: Roleplay; end: TalkEnd; sounds: SoundQueue; onHome: () => void };

// 「🔊 듣기」 under the corrected sentence plays its model under this tag (spec play-button-feedback 2)
const LISTEN_TAG = "listen";
const recTag = (r: TryRef) => `rec:${r.rp_id}:${r.idx}:${r.n}`;

export function TalkFixScreen({ rp, end, sounds, onHome }: Props) {
  const [s, dispatch] = useReducer(fixReduce, end, (e: TalkEnd) => fixInitial(rp.id, e));
  // the state as of the last render, for what arrives after a tap (the line, the practice answer)
  const now = useRef(s);
  now.current = s;
  const item = s.items[s.at];
  const line = s.line;
  const fix = line?.fix ?? null;
  const [threes, setThrees] = useState<Record<number, ThreeLine | "loading">>({});
  // fixes whose notes could not be fetched: shown plain and not asked again (as on the roleplay screen)
  const [noNotes, setNoNotes] = useState<Record<number, true>>({});
  // what was just heard, opened by a tap on it; kept by its try, so the next try comes folded (spec heard-line-collapsed 2)
  const [heardOpen, setHeardOpen] = useState<string | null>(null);
  // the fixes whose explanation has been said, by number: each says it once, when it first opens
  const played = useRef<Set<number>>(new Set());
  // set by leave(): a line or a mic start arriving between the tap and the home screen does nothing
  const gone = useRef(false);
  const scroll = useRef<ComponentRef<typeof ScrollView>>(null);
  const playingTag = usePlayingTag(sounds);
  // Ryan's answer to a try is playing: a 🔊 waits for it (spec three-line-listen 5)
  const { answering, mark: markAnswer } = useAnswering(sounds);
  const listenOk = mayListen(s.phase, answering);
  const saved = useSaved();

  const mic = useMic({
    canStart: () => !gone.current && canTry(now.current),
    beforeStart: () => {
      sounds.clear();
      dispatch({ type: "recordStart" });
    },
    onCancelled: () => dispatch({ type: "recordCancel" }),
    onNoSpeech: () => dispatch({ type: "noSpeech" }),
    onFailed: () => dispatch({ type: "micFailed" }),
    onStopped: () => dispatch({ type: "recordStop" }),
    send,
  });

  // Load the fix on screen. The Mac answers once the model and the explanation's sound are made (spec 7). The
  // request keeps the fix it was for: 「다음 ›」 works while it loads, and a slow answer must not land on the next fix.
  useEffect(() => {
    if (s.phase !== "loading" || !item) return;
    const at = s.at;
    let alive = true;
    const forHere = () => alive && !gone.current && now.current.at === at;
    api
      .getLine(rp.id, item.line.idx)
      .then((l) => forHere() && dispatch({ type: "lineLoaded", line: l }))
      .catch((e) => forHere() && dispatch({ type: "lineFailed", message: messageOf(e) }));
    return () => {
      alive = false;
    };
  }, [s.phase, s.at]); // eslint-disable-line react-hooks/exhaustive-deps

  // Ryan says the explanation once, when the fix first opens
  useEffect(() => {
    if (s.phase !== "ready" || !line || played.current.has(s.at)) return;
    played.current.add(s.at);
    const audio = line.fix?.why_audio;
    if (!audio || gone.current) return;
    sounds.clear();
    sounds.enqueue(api.audioSource(audio));
  }, [s.phase, line, s.at, sounds]);

  // nothing to fix: Ryan says so once, when the screen opens
  useEffect(() => {
    const audio = end.say?.audio;
    if (s.items.length > 0 || !audio) return;
    sounds.clear();
    sounds.enqueue(api.audioSource(audio));
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // the corrected sentence's notes, when it came without them (made on the Mac after its sounds, spec 7)
  useEffect(() => {
    if (line && s.phase === "ready" && needsNotes(line, threes[line.idx], !!noNotes[line.idx])) void fetchThree(line.idx);
  }, [line, s.phase]); // eslint-disable-line react-hooks/exhaustive-deps

  // a new fix starts at the top; what was heard, the answer and a message come in at the bottom. Always a moment
  // later: on Android a scroll run with the views that appear in the same commit stops above them (PR #20 review).
  useEffect(() => {
    scroll.current?.scrollTo({ y: 0, animated: false });
  }, [s.at]);
  const toEnd = () => setTimeout(() => scroll.current?.scrollToEnd({ animated: true }), 50);
  useEffect(() => {
    if (s.heard || s.feedback || s.message) toEnd();
  }, [s.heard, s.feedback, s.message]);

  async function fetchThree(idx: number) {
    setThrees((t) => ({ ...t, [idx]: "loading" }));
    try {
      const three = await api.getThree(rp.id, idx);
      setThrees((t) => ({ ...t, [idx]: three }));
    } catch {
      setThrees(({ [idx]: _, ...rest }) => rest);
      setNoNotes((n) => ({ ...n, [idx]: true }));
    }
  }

  // Sends the try at the corrected sentence (as 「내 대사 다시 연습」, mode practice) and plays Ryan's answer as it
  // streams in. Only the try on screen plays: the reducer drops another try's events by `tries`, and a fix left by
  // 「다음 ›」 or the screen left (`live`) plays nothing.
  async function send(uri: string, live: () => boolean) {
    const { at, tries, line: l } = now.current;
    if (!l) return;
    const current = () => live() && now.current.at === at && now.current.tries === tries;
    const onEvent = (e: AttemptEvent) => {
      if (!current()) return;
      if (e.type === "audio") {
        sounds.enqueue(api.audioSource(e.key));
        markAnswer();
      }
      if (e.type === "error" && e.say?.audio) {
        sounds.enqueue(api.audioSource(e.say.audio));
        markAnswer();
      }
      dispatch({ type: "event", tries, e });
    };
    try {
      await api.attempt(rp.id, l.idx, uri, "practice", onEvent);
    } catch (e) {
      if (current()) dispatch({ type: "failed", tries, message: messageOf(e) });
    }
  }

  // a 🔊 on this screen: stops what plays and plays it, or stops it while it plays (spec play-button-feedback 3);
  // not while recording or over Ryan's answer (`mayListen`)
  function play(src: ReturnType<typeof api.audioSource>, tag: string) {
    if (!listenOk) return;
    tapPlay(sounds, tag, () => {
      sounds.clear();
      sounds.enqueue(src, tag);
    });
  }
  const playRec = (r: TryRef) => play(api.recordingSource(r.rp_id, r.idx, r.n), recTag(r));

  // Back and 「끝」 go to the first screen (the talk is over, spec 7): the sounds stop and a recording in progress is
  // deleted unsent; an answer still on its way drops itself (`useMic`).
  async function leave() {
    if (gone.current) return;
    gone.current = true;
    sounds.clear();
    await mic.leave();
    onHome();
  }
  const goBack = () => void leave();
  useBackKey(goBack);

  // 「다음 ›」 puts the next fix's 「다음 ›」, or the last one's 「끝」, where it was: the second tap of a double tap must
  // neither skip a fix nor leave the screen, so taps are held a moment after it (as after 「취소」)
  const goNext = () => {
    if (tapHold.on) return;
    tapThenHold(tapHold, () => {
      sounds.clear();
      dispatch({ type: "next" });
    });
  };
  const finish = () => {
    if (!tapHold.on) void leave();
  };
  const nextOrEnd = isLastFix(s) ? finish : goNext;
  // 「다시 해 보기」 and 「다시 시도」 put 「🎤 따라 말하기」 where they were; `useMic` turns away a start while taps are held
  const again = () => tapThenHold(tapHold, () => dispatch({ type: "again" }));
  const retry = () => tapThenHold(tapHold, () => dispatch({ type: "retry" }));

  const count = fixCount(s);
  const busy = s.phase === "evaluating";
  const three = line ? lineNotes(line, threes[line.idx], !!noNotes[line.idx]) : null;
  const view = notesView(three, s.reading);

  return (
    <View style={styles.wrap}>
      <View style={styles.header}>
        <BackButton onPress={goBack} />
        <View style={styles.titleRow}>
          <Text style={[common.title, styles.titleText]}>{keepWords("대화 돌아보기")}</Text>
          {count && <Text style={styles.count}>{count}</Text>}
        </View>
      </View>
      <ScrollView ref={scroll} contentContainerStyle={styles.scroll}>
        {s.items.length === 0 && end.say && (
          <Named part="feedback">
            <View style={[styles.bubble, styles.feedback]}>
              <Text style={styles.plainText}>{keepWords(end.say.text)}</Text>
            </View>
          </Named>
        )}
        {s.items.length > 0 && s.phase === "loading" && <Waiting who="ryan" text="준비하고 있어요" />}
        {line && (
          <>
            {fix && (
              <Named part="feedback">
                <View style={[styles.bubble, styles.feedback]}>
                  <Text style={styles.plainText}>{keepWords(fix.why_ko)}</Text>
                </View>
              </Named>
            )}
            <Text style={styles.label}>{keepWords("내가 한 말")}</Text>
            <View style={[styles.box, styles.said]}>
              <Text style={styles.plainText}>{fix?.said}</Text>
              {item?.rec && (
                <View style={styles.links}>
                  <InRowButton
                    label="내 녹음 들어 보기"
                    playing={playingTag === recTag(item.rec)}
                    onPress={() => item.rec && playRec(item.rec)}
                    dim={!listenOk}
                    textStyle={styles.link}
                  />
                </View>
              )}
            </View>
            <Text style={styles.label}>{keepWords("이렇게 말해 보세요")}</Text>
            <View style={[styles.box, styles.now]}>
              {view === "open" && three && three !== "loading" ? (
                <ThreeLineView three={three} bare />
              ) : (
                <Text style={styles.lineText}>{line.text}</Text>
              )}
              {view === "loading" && <Text style={styles.making}>{keepWords("세 줄을 만들고 있어요…")}</Text>}
              <View style={styles.links}>
                {line.audio && (
                  <InRowButton
                    label="듣기"
                    playing={playingTag === LISTEN_TAG}
                    onPress={() => line.audio && play(api.audioSource(line.audio), LISTEN_TAG)}
                    dim={!listenOk}
                    textStyle={styles.link}
                  />
                )}
                {view !== "plain" && (
                  <Pressable onPress={() => dispatch({ type: "toggleReading" })} hitSlop={8}>
                    <Text style={styles.link}>{view === "closed" ? "읽는 법 보기 ›" : "읽는 법 접기"}</Text>
                  </Pressable>
                )}
                <StarButton
                  saved={saved.has(line.text)}
                  busy={saved.pending(line.text)}
                  onPress={() => saved.toggle(rp.id, line.idx, line.text)}
                />
              </View>
            </View>
            {/* what was heard of the try, and its recording (spec three-line-listen 4); one line until tapped */}
            {s.heard && (
              <View style={styles.heardNow}>
                <HeardLine
                  text={s.heard}
                  open={heardOpen === heardKey(s.heard, s.heardRec)}
                  onPress={() => {
                    const key = s.heard ? heardKey(s.heard, s.heardRec) : null;
                    if (key) setHeardOpen((o) => toggleRow(o, key));
                  }}
                  style={styles.heard}
                  wrapStyle={styles.shrink}
                />
                {s.heardRec && (
                  <InRowButton
                    label="내 녹음"
                    playing={playingTag === recTag(s.heardRec)}
                    onPress={() => s.heardRec && playRec(s.heardRec)}
                    dim={!listenOk}
                    textStyle={styles.link}
                  />
                )}
              </View>
            )}
            {s.feedback !== "" && (
              <Named part="feedback">
                <View style={[styles.bubble, styles.feedback]}>
                  <Text style={styles.plainText}>{keepWords(s.feedback)}</Text>
                </View>
              </Named>
            )}
            {busy && !s.feedback && <Waiting who="ryan" text="라이언이 듣고 있어요" onShow={toEnd} />}
          </>
        )}
        {s.message &&
          (fixMessageIsError(s) ? <ErrorText text={s.message} /> : <Text style={styles.notice}>{keepWords(s.message)}</Text>)}
      </ScrollView>

      {/* the less important button on the left, the main one filling the rest (spec button-colors 1, record-cancel-skip 4) */}
      <View style={styles.controls}>
        {s.phase === "recording" && <SoonEnds since={mic.liveSince} />}
        {s.items.length === 0 ? (
          <Button label="끝" onPress={finish} />
        ) : s.phase === "recording" ? (
          <View style={styles.pair}>
            <Button label="취소" onPress={mic.cancel} kind="secondary" />
            {/* 「● 말하기 끝」: blue, a blinking red dot and the voice line once the mic is on (spec record-feedback 2) */}
            <StopButton live={mic.liveSince !== null} onLevel={mic.onLevel} onPress={mic.stop} />
          </View>
        ) : s.phase === "evaluated" ? (
          <View style={styles.pair}>
            <Button label={nextLabel(s)} onPress={nextOrEnd} kind="secondary" />
            <Button label="다시 해 보기" onPress={again} grow />
          </View>
        ) : (
          <View style={styles.pair}>
            <Button label={nextLabel(s)} onPress={nextOrEnd} kind="secondary" disabled={busy} />
            {s.phase === "error" ? (
              <Button label="다시 시도" onPress={retry} grow />
            ) : (
              <Button
                label={busy ? "평가하고 있어요" : "🎤 따라 말하기"}
                onPress={mic.start}
                disabled={s.phase !== "ready"}
                grow
              />
            )}
          </View>
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
  // in my blue, like the roleplay's 「내 대사 1/3」
  count: { fontSize: 14, fontWeight: "700", color: colors.primary, backgroundColor: colors.user, borderRadius: 10, paddingHorizontal: 8, paddingVertical: 2 },
  scroll: { padding: 16, paddingBottom: 32 },
  // Ryan's explanation and his answer to a try: the roleplay's yellow feedback bubble
  bubble: { borderRadius: 14, padding: 12, marginVertical: 5, maxWidth: "92%" },
  feedback: { backgroundColor: colors.feedback, alignSelf: "flex-start" },
  plainText: { fontSize: 17, color: colors.text, lineHeight: 25 },
  label: { fontSize: 14, color: colors.sub, fontWeight: "600", marginTop: 14, marginBottom: 2, marginHorizontal: 4 },
  // 「내가 한 말」 in Ryan's gray; the sentence to say in the roleplay's 「내 차례」 blue with its border
  box: { borderRadius: 14, padding: 12, marginVertical: 4 },
  said: { backgroundColor: colors.ryan },
  now: { backgroundColor: colors.user, borderWidth: 2, borderColor: colors.primary },
  lineText: { fontSize: 22, color: colors.text, lineHeight: 30 },
  making: { fontSize: 15, color: colors.sub, marginTop: 4 },
  links: { flexDirection: "row", flexWrap: "wrap", alignItems: "center", rowGap: 12, columnGap: 16, marginTop: 8 },
  link: { fontSize: 15, color: colors.primary, fontWeight: "600" },
  heardNow: { flexDirection: "row", alignItems: "center", alignSelf: "flex-end", gap: 12, marginTop: 4, maxWidth: "100%" },
  heard: { fontSize: 14, color: colors.sub },
  shrink: { flexShrink: 1 },
  notice: { fontSize: 16, color: colors.sub, marginTop: 8 },
  controls: { padding: 12, borderTopWidth: 1, borderTopColor: "#E9ECEF" },
  pair: { flexDirection: "row", gap: 8 },
});
