// Records the learner. The file is uploaded to the Mac and then deleted from the phone (spec 「녹음과 기록」).
import { RecordingPresets, requestRecordingPermissionsAsync, useAudioRecorder } from "expo-audio";
import { File } from "expo-file-system";
import { useEffect, useRef, useState } from "react";

import { RECORD_LIMIT_MS } from "../config";

export function useRecorder() {
  const recorder = useAudioRecorder({ ...RecordingPresets.HIGH_QUALITY, numberOfChannels: 1 });
  const [recording, setRecording] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  // read through a ref: the auto-stop callback was created when recording started and sees old state
  const active = useRef(false);

  useEffect(() => () => clearTimeout(timer.current), []); // the auto-stop must not fire after the screen is gone

  async function start(onAutoStop: () => void): Promise<void> {
    const perm = await requestRecordingPermissionsAsync();
    if (!perm.granted) throw new Error("mic");
    await recorder.prepareToRecordAsync();
    recorder.record();
    active.current = true;
    setRecording(true);
    timer.current = setTimeout(onAutoStop, RECORD_LIMIT_MS);
  }

  async function stop(): Promise<string> {
    clearTimeout(timer.current);
    active.current = false;
    await recorder.stop();
    setRecording(false);
    if (!recorder.uri) throw new Error("no recording");
    return recorder.uri;
  }

  // leaving the screen while recording (back button): stop and delete, nothing is sent
  async function discard(): Promise<void> {
    if (!active.current) return;
    clearTimeout(timer.current);
    active.current = false;
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

  return { start, stop, discard, recording, isRecording: () => active.current };
}
