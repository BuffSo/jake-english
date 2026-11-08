// Whether anything was said since the mic came on (spec record-feedback 4). Fed the mic level every 0.1 s or so;
// says "silent" once no speech came for `waitMs`, and the screen then throws the recording away. One loud reading
// (the tap, a bump of the phone) is not speech: loud time has to add up to `loudMs`, as on the Mac (`has_speech`).
// Once speech is heard it stays heard: the learner ends with 「말하기 끝」 (user's decision).
export type SpeechRule = {
  level: number; // dBFS at or over which a reading is loud (Android: the loudest sample since the last reading)
  loudMs: number; // loud time that makes speech
  waitMs: number; // with no speech by then, silent
  skipMs: number; // readings this soon after the mic came on are not counted
};

// level and waitMs: measured on the phone (plan task 6)
export const SPEECH_RULE: SpeechRule = { level: -40, loudMs: 200, waitMs: 8000, skipMs: 300 };

export type Heard = "listening" | "speech" | "silent";

const FIRST_STEP_MS = 100; // the first counted reading stands for this much time
const MOST_STEP_MS = 250; // a reading after a long gap (the app was busy) stands for no more than this

export function createSpeechWatch(rule: SpeechRule = SPEECH_RULE) {
  let loud = 0;
  let prev: number | undefined;
  let gotLevel = false;
  let heard = false;
  return {
    feed(atMs: number, db: number | undefined): Heard {
      const step = prev === undefined ? FIRST_STEP_MS : Math.min(atMs - prev, MOST_STEP_MS);
      prev = atMs;
      if (atMs >= rule.skipMs && db !== undefined) {
        gotLevel = true;
        if (db >= rule.level) loud += step;
        if (loud >= rule.loudMs) heard = true;
      }
      if (heard) return "speech";
      // without any level the watch cannot tell: losing what was said is worse than a quiet recording sent
      return gotLevel && atMs >= rule.waitMs ? "silent" : "listening";
    },
  };
}
