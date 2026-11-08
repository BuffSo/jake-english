// Reads the mic level every 0.1 s while the mic is on: for the voice line in 「● 말하기 끝」 (spec record-feedback 2)
// and, when the screen asks for it, for the speech watch that throws a recording without speech away (4). Kept out of
// `useRecorder` so it can be tested without a recorder.
import { createSpeechWatch, type SpeechRule } from "../flow/speechWatch";

export const LEVEL_EVERY_MS = 100;

type Options = {
  read: () => number | undefined; // the level now (dBFS), or nothing
  onLevel: (db: number | undefined) => void;
  onNoSpeech?: () => void; // called once when no speech came in time; none on the situation screen
  rule?: SpeechRule;
  now?: () => number;
};

// Starts reading at once; the returned function stops it.
export function startLevelPoll({ read, onLevel, onNoSpeech, rule, now = Date.now }: Options): () => void {
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
    onLevel(db);
    if (!onNoSpeech || told) return;
    if (watch.feed(now() - from, db) === "silent") {
      told = true;
      onNoSpeech();
    }
  }, LEVEL_EVERY_MS);
  return () => clearInterval(timer);
}
