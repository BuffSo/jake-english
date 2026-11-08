// The cues that say the mic started, stopped or was cancelled, with a vibration each (spec record-feedback 1). The
// sounds are made in code (`cueSound`), written to the phone's cache once at start-up, and played from there: making
// them at the tap would be late.
import { createAudioPlayer, type AudioPlayer } from "expo-audio";
import { File, Paths } from "expo-file-system";
import { Vibration } from "react-native";

import { cueMs, cueWav, type Cue } from "./cueSound";

// start once short, end twice short, cancel once longer (Android: wait, vibrate, wait, vibrate)
export const VIBRATE: Record<Cue, number | number[]> = { start: 50, end: [0, 50, 80, 50], cancel: 180 };

const CUES: Cue[] = ["start", "end", "cancel"];
// a cue whose end is never reported is given up this long after its length (starting to play takes a moment)
const LATE_MS = 300;

const players: Partial<Record<Cue, AudioPlayer>> = {};

// Ends when `listen` reports the end or `capMs` has passed, whichever comes first, and stops listening then.
export function waitForEnd(listen: (done: () => void) => () => void, capMs: number): Promise<void> {
  return new Promise((resolve) => {
    let over = false;
    let stop: (() => void) | undefined;
    const finish = () => {
      if (over) return;
      over = true;
      clearTimeout(timer);
      stop?.();
      resolve();
    };
    const timer = setTimeout(finish, capMs);
    stop = listen(finish);
    if (over) stop(); // reported at once, before `stop` was known
  });
}

const wait = (ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms));

// Makes the three sounds and their players. A cue that fails stays silent: `playCue` then waits its length, so the mic
// still comes on (spec record-feedback 1).
export async function prepareCues(): Promise<void> {
  for (const cue of CUES) {
    try {
      const file = new File(Paths.cache, `cue-${cue}.wav`);
      await file.write(cueWav(cue)); // makes the file, or writes over last start's
      players[cue] = createAudioPlayer({ uri: file.uri });
    } catch {
      // this cue stays silent
    }
  }
}

// Vibrates and plays the cue from its start. Ends when the sound has played, a little after its length at most, or
// after its length when it cannot play.
export function playCue(cue: Cue): Promise<void> {
  Vibration.vibrate(VIBRATE[cue]);
  const player = players[cue];
  const ms = cueMs(cue);
  if (!player) return wait(ms);
  try {
    const ended = waitForEnd((done) => {
      const sub = player.addListener("playbackStatusUpdate", (s) => {
        if (s.didJustFinish) done();
      });
      return () => sub.remove();
    }, ms + LATE_MS);
    player.seekTo(0).catch(() => {});
    player.play();
    return ended;
  } catch {
    return wait(ms);
  }
}
