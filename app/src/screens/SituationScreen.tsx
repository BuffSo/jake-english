import { File } from "expo-file-system";
import { useEffect, useRef, useState } from "react";
import { StyleSheet, Text, TextInput, View } from "react-native";

import { api } from "../api";
import type { Home, Roleplay, Said } from "../api/types";
import type { SoundQueue } from "../audio/player";
import { useRecorder } from "../audio/useRecorder";
import { createGate, createLatch } from "../flow/gate";
import { turnDown } from "../flow/turnedDown";
import { whenSilent } from "../flow/whenSilent";
import { BackButton, useBackKey } from "../ui/BackButton";
import { Button } from "../ui/Button";
import { circleFace, type Face, type Step } from "../ui/faces";
import { Named } from "../ui/Named";
import { FaceCircle } from "../ui/RyanFace";
import { ThinkingFace } from "../ui/ThinkingFace";
import { colors, top } from "../ui/theme";
import { waiterOf } from "../ui/thinking";
import { messageOf, styles as common, Waiting } from "./common";

type Props = { sounds: SoundQueue; home: Home; onCreated: (rp: Roleplay, jake: Said | null) => void; onBack: () => void };

const WANTS_RECOMMEND = /모르겠|추천/;

export function SituationScreen({ sounds, home, onCreated, onBack }: Props) {
  const [text, setText] = useState("");
  const [step, setStep] = useState<Step>("input");
  const [status, setStatus] = useState("");
  const [jake, setJake] = useState<Said | null>(null);
  const [error, setError] = useState<string | null>(null);
  const rec = useRecorder();
  const gate = useRef(createGate()).current; // a double tap or the auto-stop must not send the recording twice
  const gen = useRef(0); // bumped by going back (or leaving): an answer to an earlier request is dropped
  const turnedDown = useRef<string[]>([]); // Jake's suggestions turned down on this screen, not suggested again
  const choice = useRef(createLatch()).current; // one answer per suggestion: a double tap must not ask twice
  const [jakeFailed, setJakeFailed] = useState(false); // Jake's picture did not load: Ryan's face instead
  const shown = useRef<Face>("listening"); // the circle's face before a wait, kept until the thinking face comes

  useEffect(
    () => () => {
      gen.current += 1;
    },
    [],
  );

  useEffect(() => {
    sounds.clear();
    sounds.enqueue(api.audioSource(home.lines.ask_situation.audio));
  }, [sounds, home]);

  // Back: the step before on this screen, or the home screen from the first step. Sounds stop, a recording
  // in progress is deleted without being sent, and a script or transcript still on its way is dropped.
  function back() {
    gen.current += 1;
    sounds.clear();
    setError(null);
    if (step === "input") {
      rec.discard().finally(onBack);
      return;
    }
    setJake(null);
    setStep("input");
  }
  useBackKey(back);

  async function create(situation: string, jakeSaid: Said | null = null) {
    const my = gen.current;
    setStep("working");
    setStatus("라이언이 대본을 만들고 있어요");
    setError(null);
    try {
      // the script is made while Jake (or Ryan) is still talking; the roleplay screen opens after they finish
      const rp = await whenSilent(sounds, api.createRoleplay(situation));
      if (my === gen.current) onCreated(rp, jakeSaid);
    } catch (e) {
      if (my !== gen.current) return;
      setError(messageOf(e));
      setStep("input");
    }
  }

  function askRecommend() {
    setStep("askRecommend");
    sounds.clear();
    sounds.enqueue(api.audioSource(home.lines.ask_recommend.audio));
  }

  // Jake suggests a situation and the learner picks it or asks for another. The script is not made until they
  // pick it: one made while they choose would be thrown away on 「다른 걸로요」 (2026-11-06, user).
  async function recommend() {
    const my = gen.current;
    setStep("working");
    setStatus("제이크가 상황을 고르고 있어요");
    setJake(null);
    setError(null);
    try {
      const said = await api.recommend(turnedDown.current);
      if (my !== gen.current) return;
      setJake(said);
      sounds.clear();
      sounds.enqueue(api.audioSource(said.audio));
      choice.open();
      setStep("confirm");
    } catch (e) {
      if (my !== gen.current) return;
      setError(messageOf(e));
      setStep("input");
    }
  }

  function pick() {
    if (!jake || !choice.take()) return;
    create(jake.text, jake);
  }

  function another() {
    if (!jake || !choice.take()) return;
    turnedDown.current = turnDown(turnedDown.current, jake.text);
    sounds.clear(); // Jake stops; the next suggestion is on its way
    recommend();
  }

  function start() {
    const t = text.trim();
    if (!t || WANTS_RECOMMEND.test(t)) askRecommend();
    else create(t);
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
      setStep("working");
      setStatus("받아쓰고 있어요");
      const said = await api.transcribe(uri);
      if (my !== gen.current) return;
      setText(said);
      if (WANTS_RECOMMEND.test(said)) askRecommend();
      else setStep("input");
    } catch (e) {
      if (my !== gen.current) return;
      setError(messageOf(e));
      setStep("input");
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
  return (
    <View style={styles.wrap}>
      <BackButton onPress={back} floating />
      <View style={styles.face}>
        {/* while working, this circle thinks in place, so the screen never shows two faces (2026-11-06) */}
        {step === "working" ? <ThinkingFace who={waiterOf(status)} size={160} fallback={circle} /> : circle}
      </View>
      <Text style={[common.body, styles.say]}>{home.lines.ask_situation.text}</Text>
      {step === "input" && (
        <>
          <TextInput
            style={styles.input}
            value={text}
            onChangeText={setText}
            placeholder="예: 길에서 외국인이 지하철역을 물어보는 상황"
            multiline
            maxLength={300}
          />
          <Button label={rec.recording ? "■ 말하기 끝" : "🎤 말로 하기"} onPress={rec.recording ? stopMic : startMic} kind="plain" />
          <Button label="시작" onPress={start} disabled={rec.recording} />
          <Button label="추천해 줘" onPress={askRecommend} kind="plain" disabled={rec.recording} />
        </>
      )}
      {step === "askRecommend" && (
        <>
          <Text style={[common.body, styles.say]}>{home.lines.ask_recommend.text}</Text>
          <Button label="좋아요" onPress={recommend} />
          <Button label="아니요" onPress={() => setStep("input")} kind="plain" />
        </>
      )}
      {step === "confirm" && jake && (
        <>
          <JakeSays text={jake.text} />
          <Button label="이걸로 할게요" onPress={pick} />
          <Button label="다른 걸로요" onPress={another} kind="plain" />
        </>
      )}
      {step === "working" && (
        <>
          {jake && <JakeSays text={jake.text} />}
          <Waiting text={status} />
        </>
      )}
      {error && <Text style={common.error}>{error}</Text>}
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
});
