// Records the learner. The file is uploaded to the Mac and then deleted from the phone (spec 「녹음과 기록」).
import { RecordingPresets, requestRecordingPermissionsAsync, useAudioRecorder } from "expo-audio";
import { useRef, useState } from "react";

const MAX_MS = 60_000; // the server takes up to 60 seconds

export function useRecorder() {
  const recorder = useAudioRecorder({ ...RecordingPresets.HIGH_QUALITY, numberOfChannels: 1 });
  const [recording, setRecording] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  async function start(onAutoStop: () => void): Promise<void> {
    const perm = await requestRecordingPermissionsAsync();
    if (!perm.granted) throw new Error("mic");
    await recorder.prepareToRecordAsync();
    recorder.record();
    setRecording(true);
    timer.current = setTimeout(onAutoStop, MAX_MS);
  }

  async function stop(): Promise<string> {
    clearTimeout(timer.current);
    await recorder.stop();
    setRecording(false);
    if (!recorder.uri) throw new Error("no recording");
    return recorder.uri;
  }

  return { start, stop, recording };
}
