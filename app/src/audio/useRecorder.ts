// Records the learner. The file is uploaded to the Mac and then deleted from the phone (spec 「녹음과 기록」).
// Starting, stopping and cancelling each play a cue with a vibration (spec record-feedback 1), and while the mic is on
// its level is read for the voice line and, on the roleplay screen, for throwing a recording without speech away (4).
import { RecordingPresets, requestRecordingPermissionsAsync, useAudioRecorder } from "expo-audio";
import { File } from "expo-file-system";
import { useCallback, useEffect, useRef, useState } from "react";

import { RECORD_LIMIT_MS } from "../config";
import { playCue } from "./cues";
import { startLevelPoll } from "./levelPoll";

type Level = (db: number | undefined) => void;

export function useRecorder() {
  const recorder = useAudioRecorder({ ...RecordingPresets.HIGH_QUALITY, numberOfChannels: 1, isMeteringEnabled: true });
  const [recording, setRecording] = useState(false);
  // when the mic came on; null while it is off. The red dot, the voice line and 「녹음이 곧 끝나요」 go by it.
  const [liveSince, setLiveSince] = useState<number | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  // read through a ref: the auto-stop callback was created when recording started and sees old state
  const active = useRef(false);
  const stopPoll = useRef<(() => void) | undefined>(undefined);
  const levelSubs = useRef(new Set<Level>());

  // the auto-stop and the level readings must not go on after the screen is gone
  useEffect(
    () => () => {
      clearTimeout(timer.current);
      stopPoll.current?.();
    },
    [],
  );

  function micOff() {
    clearTimeout(timer.current);
    stopPoll.current?.();
    stopPoll.current = undefined;
    active.current = false;
    setLiveSince(null);
  }

  // `onNoSpeech`: called once when no speech came in time after the mic came on; `onSpeechEnd`: called once after a
  // long pause following speech (the roleplay screen only)
  async function start(onAutoStop: () => void, opts: { onNoSpeech?: () => void; onSpeechEnd?: () => void } = {}): Promise<void> {
    const perm = await requestRecordingPermissionsAsync();
    if (!perm.granted) throw new Error("mic");
    await recorder.prepareToRecordAsync();
    // the mic comes on as the start cue ends: a cue heard means recording, and the cue is not in the recording.
    // A cue that cannot play is waited for its length, so recording still works (spec record-feedback 1).
    await playCue("start");
    recorder.record();
    active.current = true;
    setRecording(true);
    setLiveSince(Date.now());
    timer.current = setTimeout(onAutoStop, RECORD_LIMIT_MS);
    stopPoll.current = startLevelPoll({
      read: () => recorder.getStatus().metering,
      onLevel: (db) => levelSubs.current.forEach((cb) => cb(db)),
      onNoSpeech: opts.onNoSpeech,
      onSpeechEnd: opts.onSpeechEnd,
    });
  }

  async function stop(): Promise<string> {
    micOff();
    await recorder.stop();
    setRecording(false);
    if (!recorder.uri) throw new Error("no recording");
    void playCue("end");
    return recorder.uri;
  }

  // leaving the screen while recording (back button): stop and delete, nothing is sent and no cue plays
  async function discard(): Promise<void> {
    if (!active.current) return;
    micOff();
    try {
      await recorder.stop();
    } catch {
      // already stopped
    }
    setRecording(false);
    try {
      if (recorder.uri) new File(recorder.uri).delete();
    } catch {
      // already gone
    }
  }

  // 「취소」 and the cancel for no speech: as `discard`, with the cancel cue. Nothing to cancel, no cue.
  async function cancel(): Promise<void> {
    if (!active.current) return;
    await discard();
    void playCue("cancel");
  }

  // the voice line listens to the level while the mic is on; the returned function stops listening. The same
  // function every render, so the line does not subscribe again each time the screen draws.
  const onLevel = useCallback((cb: Level): (() => void) => {
    levelSubs.current.add(cb);
    return () => {
      levelSubs.current.delete(cb);
    };
  }, []);

  return { start, stop, discard, cancel, onLevel, recording, liveSince, isRecording: () => active.current };
}
