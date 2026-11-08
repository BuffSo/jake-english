// Reads the mic level every 0.1 s while the mic is on: for the voice line in 「● 말하기 끝」 (spec record-feedback 2)
// and, when the screen asks for it, for the speech watch that throws a recording without speech away and ends one
// after a long pause (4). Kept out of `useRecorder` so it can be tested without a recorder.
import { createSpeechWatch, type SpeechRule } from "../flow/speechWatch";

export const LEVEL_EVERY_MS = 100;
// expo-audio on Android gives this when the recorder's amplitude is 0 or cannot be read, never undefined. A live mic is
// never that silent (a quiet room read -55~-63), so it is no reading: a phone whose amplitude is always 0 must not have
// every recording cancelled at 5 s (final review).
const NO_AMPLITUDE_DB = -160;

type Options = {
  read: () => number | undefined; // the level now (dBFS), or nothing
  onLevel: (db: number | undefined) => void;
  onNoSpeech?: () => void; // called once when no speech came in time; none on the situation screen
  onSpeechEnd?: () => void; // called once after a long pause following speech; none on the situation screen
  rule?: SpeechRule;
  now?: () => number;
};

// Starts reading at once; the returned function stops it.
export function startLevelPoll({ read, onLevel, onNoSpeech, onSpeechEnd, rule, now = Date.now }: Options): () => void {
  const from = now();
  const watch = createSpeechWatch(rule);
  let told = false;
  const timer = setInterval(() => {
    let db: number | undefined;
    try {
      db = read();
    } catch {
      db = undefined; // a recorder going away mid-read: no level, which never cancels
    }
    if (db !== undefined && !(db > NO_AMPLITUDE_DB)) db = undefined;
    onLevel(db);
    if ((!onNoSpeech && !onSpeechEnd) || told) return;
    const heard = watch.feed(now() - from, db);
    if (heard === "silent" && onNoSpeech) {
      told = true;
      onNoSpeech();
    } else if (heard === "ended" && onSpeechEnd) {
      told = true;
      onSpeechEnd();
    }
  }, LEVEL_EVERY_MS);
  return () => clearInterval(timer);
}
