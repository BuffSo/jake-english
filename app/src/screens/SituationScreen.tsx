import { File } from "expo-file-system";
import { useEffect, useRef, useState } from "react";
import { ScrollView, StyleSheet, Text, TextInput, View } from "react-native";

import { api } from "../api";
import type { Home, Resume, Roleplay, Said, Topic } from "../api/types";
import type { SoundQueue } from "../audio/player";
import { useRecorder } from "../audio/useRecorder";
import { createGate, createLatch } from "../flow/gate";
import { pending, RESUME_WAIT_MS } from "../flow/pending";
import { resumeLabel } from "../flow/resume";
import {
  backFrom,
  canStart,
  clearsTurnedDown,
  HOW_LABEL,
  howChoices,
  lineFor,
  OTHER_TOPIC,
  resumeFrom,
  startStep,
  topicsOf,
  type HowChoice,
  type Origin,
  type SituationStart,
  type SituationStep,
} from "../flow/situation";
import { turnDown } from "../flow/turnedDown";
import { whenSilent } from "../flow/whenSilent";
import { BackButton, useBackKey } from "../ui/BackButton";
import { Button } from "../ui/Button";
import { circleFace, type Face } from "../ui/faces";
import { Named } from "../ui/Named";
import { keepWords } from "../ui/keepWords";
import { ListCard } from "../ui/ListCard";
import { ResumeRow } from "../ui/ResumeRow";
import { FaceCircle } from "../ui/RyanFace";
import { ThinkingFace } from "../ui/ThinkingFace";
import { colors, top } from "../ui/theme";
import { waiterOf } from "../ui/thinking";
import { ErrorText, messageOf, styles as common, Waiting } from "./common";

type Props = {
  sounds: SoundQueue;
  home: Home;
  // where back from the roleplay comes to: the topic and the step its situation was picked from (null: the topics)
  start: SituationStart | null;
  onCreated: (rp: Roleplay, jake: Said | null, from: SituationStart) => void;
  // the row on the topic step: resume the newest conversation (spec resume-roleplay 4)
  onResume: (r: Resume) => void;
  onBack: () => void;
};
type Choice = { situation: string } | { pick: string };

const WANTS_RECOMMEND = /모르겠|추천/;

// The situation screen: the topic first, then how to pick the situation (spec situation-topics 2). The steps and
// what back does are in flow/situation.ts.
export function SituationScreen({ sounds, home, start, onCreated, onResume, onBack }: Props) {
  const topics = topicsOf(home);
  const known = resumeFrom(start, topics);
  const [topicId, setTopicId] = useState<string | null>(known?.topic ?? null);
  const [step, setStep] = useState<SituationStep>(startStep(known));
  const now = useRef<SituationStep>(startStep(known)); // the step as of the last tap, before React re-renders
  const [text, setText] = useState("");
  const [status, setStatus] = useState("");
  const [jake, setJake] = useState<Said | null>(null);
  const [error, setError] = useState<string | null>(null);
  const rec = useRecorder();
  const gate = useRef(createGate()).current; // a double tap or the auto-stop must not send the recording twice
  const gen = useRef(0); // bumped by going back (or leaving): an answer to an earlier request is dropped
  const turnedDown = useRef<string[]>([]); // Jake's suggestions turned down in this topic, not suggested again
  const choice = useRef(createLatch()).current; // one answer per suggestion: a double tap must not ask twice
  const origin = useRef<Origin>(known?.step ?? "how"); // the step the situation is being picked from
  const [jakeFailed, setJakeFailed] = useState(false); // Jake's picture did not load: Ryan's face instead
  const shown = useRef<Face>("listening"); // the circle's face before a wait, kept until the thinking face comes
  const topic: Topic | null = topics.find((t) => t.id === topicId) ?? null;
  // the newest conversation to resume, asked once when the screen opens (spec resume-roleplay 4)
  const [resume, setResume] = useState<Resume | null>(null);

  // after what the roleplay screen left running: an evaluation moves the place only when it has finished (`pending`).
  // A failure leaves the screen as it was, without the row.
  useEffect(() => {
    let alive = true;
    pending
      .settled(RESUME_WAIT_MS)
      .then(() => api.resume())
      .then((r) => alive && setResume(r))
      .catch(() => {});
    return () => {
      alive = false;
    };
  }, []);

  useEffect(
    () => () => {
      gen.current += 1;
    },
    [],
  );

  // Ryan's line for the first step, once
  useEffect(() => {
    say(startStep(known));
  }, [sounds, home]); // eslint-disable-line react-hooks/exhaustive-deps

  function toStep(s: SituationStep) {
    now.current = s;
    setStep(s);
  }

  function say(s: SituationStep) {
    const key = lineFor(s);
    const line = key ? home.lines[key] : undefined;
    sounds.clear();
    if (line) sounds.enqueue(api.audioSource(line.audio));
  }

  // a step the learner moves on to: Ryan says its line (going back says nothing again)
  function go(s: SituationStep) {
    toStep(s);
    say(s);
  }

  // Back: the step before on this screen, or the home screen from the topics. Sounds stop, a recording in progress
  // is deleted without being sent, and a script or suggestion still on its way is dropped.
  function back() {
    gen.current += 1;
    sounds.clear();
    setError(null);
    const prev = backFrom(step, origin.current);
    if (prev === null) {
      rec.discard().finally(onBack);
      return;
    }
    if (step === "describe") rec.discard();
    if (clearsTurnedDown(prev)) turnedDown.current = [];
    setJake(null);
    toStep(prev);
  }
  useBackKey(back);

  function chooseTopic(t: Topic) {
    setTopicId(t.id);
    turnedDown.current = [];
    go("how");
  }

  function chooseHow(c: HowChoice) {
    setError(null);
    if (c === "list") {
      origin.current = "list";
      go("list");
    } else if (c === "jake") {
      origin.current = "how";
      recommend(); // the button already asked for it: no 「추천받아 볼까요?」 first (spec 2)
    } else {
      origin.current = "describe";
      setText("");
      go("describe");
    }
  }

  async function create(c: Choice, jakeSaid: Said | null = null) {
    if (!topic || !canStart(now.current)) return;
    const my = gen.current;
    const from = { topic: topic.id, step: origin.current };
    toStep("working");
    setStatus("라이언이 대본을 만들고 있어요");
    setError(null);
    try {
      // the script is made while Jake (or Ryan) is still talking; the roleplay screen opens after they finish
      const rp = await whenSilent(sounds, api.createRoleplay(c, topic.id));
      if (my === gen.current) onCreated(rp, jakeSaid, from);
    } catch (e) {
      if (my !== gen.current) return;
      setError(messageOf(e));
      toStep(from.step);
    }
  }

  // Jake suggests a situation in the topic and the learner picks it or asks for another. The script is not made
  // until they pick it: one made while they choose would be thrown away on 「다른 걸로요」 (2026-11-06, user).
  async function recommend() {
    if (!topic || !canStart(now.current)) return;
    const my = gen.current;
    toStep("working");
    setStatus("제이크가 상황을 고르고 있어요");
    setJake(null);
    setError(null);
    try {
      const said = await api.recommend(turnedDown.current, topic.id);
      if (my !== gen.current) return;
      setJake(said);
      sounds.clear();
      sounds.enqueue(api.audioSource(said.audio));
      choice.open();
      toStep("confirm");
    } catch (e) {
      if (my !== gen.current) return;
      setError(messageOf(e));
      toStep(origin.current);
    }
  }

  function pick() {
    if (!jake || !choice.take()) return;
    create({ situation: jake.text }, jake);
  }

  function another() {
    if (!jake || !choice.take()) return;
    turnedDown.current = turnDown(turnedDown.current, jake.text);
    sounds.clear(); // Jake stops; the next suggestion is on its way
    recommend();
  }

  function startDescribed() {
    const t = text.trim();
    if (!t || WANTS_RECOMMEND.test(t)) go("askRecommend");
    else create({ situation: t });
  }

  const startMic = () => gate.run(doStartMic);
  const stopMic = () => gate.run(doStopMic);

  async function doStartMic() {
    const my = gen.current;
    setError(null);
    sounds.clear();
    try {
      await rec.start(stopMic);
      if (my !== gen.current) await rec.discard(); // went back while the mic was starting (permission prompt)
    } catch {
      if (my !== gen.current) return;
      setError("마이크를 쓸 수 없어요. 앱의 마이크 권한을 확인해 주세요.");
    }
  }

  async function doStopMic() {
    if (!rec.isRecording()) return; // already stopped (auto-stop and a tap)
    const my = gen.current;
    let uri: string | null = null;
    try {
      uri = await rec.stop();
      if (my !== gen.current) return; // went back while the recorder was stopping; `finally` deletes it unsent
      toStep("working");
      setStatus("받아쓰고 있어요");
      const said = await api.transcribe(uri);
      if (my !== gen.current) return;
      setText(said);
      if (WANTS_RECOMMEND.test(said)) go("askRecommend");
      else toStep("describe");
    } catch (e) {
      if (my !== gen.current) return;
      setError(messageOf(e));
      toStep("describe");
    } finally {
      if (uri) {
        try {
          new File(uri).delete(); // the recording is not kept on the phone
        } catch {
          // already gone
        }
      }
    }
  }

  const jakePicture = !jakeFailed ? home.images.jake : undefined;
  const face = circleFace(step, shown.current, !!jakePicture);
  shown.current = face;
  const circle =
    face === "jake" && jakePicture ? (
      <FaceCircle source={api.imageSource(jakePicture)} size={160} face="jake" onError={() => setJakeFailed(true)} />
    ) : (
      <FaceCircle source={api.imageSource(home.images.listening)} size={160} face="listening" />
    );
  const key = lineFor(step);
  const ryanSays = key ? home.lines[key]?.text : undefined;

  if (step === "list" && topic) {
    // no face here, so more of the list shows; it scrolls as the list grows (spec 2)
    return (
      <View style={styles.wrap}>
        <BackButton onPress={back} floating />
        <Text style={[common.sub, styles.topic]}>{topic.name_ko}</Text>
        {ryanSays && <Text style={[common.body, styles.say]}>{keepWords(ryanSays)}</Text>}
        <ScrollView contentContainerStyle={styles.list}>
          {topic.picks.map((p) => (
            <ListCard key={p.id} onPress={() => create({ pick: p.id })}>
              <Text style={common.body}>{keepWords(p.title_ko)}</Text>
            </ListCard>
          ))}
        </ScrollView>
        {error && <ErrorText text={error} />}
      </View>
    );
  }

  return (
    <View style={styles.wrap}>
      <BackButton onPress={back} floating />
      <View style={styles.face}>
        {/* while working, this circle thinks in place, so the screen never shows two faces (2026-11-06) */}
        {step === "working" ? <ThinkingFace who={waiterOf(status)} size={160} fallback={circle} /> : circle}
      </View>
      {topic && step !== "topic" && <Text style={[common.sub, styles.topic]}>{topic.name_ko}</Text>}
      {ryanSays && <Text style={[common.body, styles.say]}>{keepWords(ryanSays)}</Text>}
      {step === "topic" &&
        topics.map((t) => (
          <Button key={t.id} label={t.name_ko} onPress={() => chooseTopic(t)} kind={t.id === OTHER_TOPIC ? "secondary" : "primary"} />
        ))}
      {/* at the very bottom, apart from the topics: not a topic, and showing up late it pushes nothing (the user
          chose it from the drafts) */}
      {step === "topic" && resume && (
        <>
          <View style={styles.push} />
          <ResumeRow
            line={resumeLabel(resume)}
            onPress={() => {
              sounds.clear();
              onResume(resume);
            }}
          />
        </>
      )}
      {step === "how" &&
        topic &&
        howChoices(topic).map((c, i) => (
          <Button key={c} label={HOW_LABEL[c]} onPress={() => chooseHow(c)} kind={i === 0 ? "primary" : "secondary"} />
        ))}
      {step === "describe" && (
        <>
          <TextInput
            style={styles.input}
            value={text}
            onChangeText={setText}
            placeholder={topic?.placeholder_ko}
            multiline
            maxLength={300}
          />
          <Button label={rec.recording ? "■ 말하기 끝" : "🎤 말로 하기"} onPress={rec.recording ? stopMic : startMic} kind="secondary" />
          <Button label="시작" onPress={startDescribed} disabled={rec.recording} />
        </>
      )}
      {step === "askRecommend" && (
        <>
          <Button label="좋아요" onPress={recommend} />
          <Button label="아니요" onPress={() => toStep("describe")} kind="secondary" />
        </>
      )}
      {step === "confirm" && jake && (
        <>
          <JakeSays text={jake.text} />
          <Button label="이걸로 할게요" onPress={pick} />
          <Button label="다른 걸로요" onPress={another} kind="secondary" />
        </>
      )}
      {step === "working" && (
        <>
          {jake && <JakeSays text={jake.text} />}
          <Waiting text={status} />
        </>
      )}
      {error && <ErrorText text={error} />}
    </View>
  );
}

// Jake's suggestion, on the left in gray with his name like on the roleplay screen: it was blue like the learner's
// own lines there (2026-11-06 user)
function JakeSays({ text }: { text: string }) {
  return (
    <Named part="jake">
      <Text style={[common.body, styles.jake]}>{text}</Text>
    </Named>
  );
}

const styles = StyleSheet.create({
  // from just below the floating back button: centring left a wide gap above the picture (2026-11-05, user)
  wrap: { flex: 1, paddingTop: top + 44, paddingHorizontal: 20, paddingBottom: 20, backgroundColor: colors.bg },
  face: { marginBottom: 12 },
  topic: { marginBottom: 4 },
  say: { marginBottom: 10 },
  jake: { backgroundColor: colors.ryan, borderRadius: 12, padding: 12, marginTop: 2, marginBottom: 8, maxWidth: "92%" },
  input: {
    borderWidth: 1,
    borderColor: "#CED4DA",
    borderRadius: 12,
    padding: 12,
    fontSize: 17,
    minHeight: 80,
    textAlignVertical: "top",
    marginBottom: 8,
  },
  // the gray rounded cards, the same as the lists of 「복습하기」 (spec review-screens 5)
  list: { paddingBottom: 12 },
  push: { flex: 1 },
});
