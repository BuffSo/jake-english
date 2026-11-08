// Whether anything was said since the mic came on (spec record-feedback 4). Fed the mic level every 0.1 s or so;
// says "silent" once no speech came for `waitMs`, and the screen then throws the recording away. One loud reading
// (the tap, a bump of the phone) is not speech: loud time has to add up to `loudMs`, as on the Mac (`has_speech`).
// Once speech is heard it stays heard, and "ended" comes after `endMs` with no loud reading: the screen then ends the
// recording as 「말하기 끝」 does. The learner still ends with the button; the long pause is for when they forget
// (user, 2026-11-08).
export type SpeechRule = {
  level: number; // dBFS at or over which a reading is loud (Android: the loudest sample since the last reading)
  loudMs: number; // loud time that makes speech
  waitMs: number; // with no speech by then, silent
  skipMs: number; // readings this soon after the mic came on are not counted
  endMs: number; // after speech, this long with no loud reading ends the recording
};

// Measured on the phone (2026-11-08, peak dBFS every 0.1 s): a quiet room sat at -55~-63 with short sounds now and
// then up to -30; the learner's voice from the Mac speaker read -18~-40 at a normal level and -40~-50 played soft. The
// level is under the soft voice so a quiet speaker is not cut off; 0.3 s of loud keeps one or two room sounds out.
// 5 s from the mic coming on and 8 s of pause after speech: the user's calls (2026-11-08). The pause is longer since
// that recording is sent: cut early, a line not finished would be evaluated, and pausing to find the next word is
// common.
export const SPEECH_RULE: SpeechRule = { level: -45, loudMs: 300, waitMs: 5000, skipMs: 300, endMs: 8000 };

export type Heard = "listening" | "speech" | "silent" | "ended";

const FIRST_STEP_MS = 100; // the first counted reading stands for this much time
const MOST_STEP_MS = 250; // a reading after a long gap (the app was busy) stands for no more than this

export function createSpeechWatch(rule: SpeechRule = SPEECH_RULE) {
  let loud = 0;
  let prev: number | undefined;
  let gotLevel = false;
  let heard = false;
  let lastLoud = 0;
  return {
    feed(atMs: number, db: number | undefined): Heard {
      const step = prev === undefined ? FIRST_STEP_MS : Math.min(atMs - prev, MOST_STEP_MS);
      prev = atMs;
      if (atMs >= rule.skipMs && db !== undefined) {
        gotLevel = true;
        if (db >= rule.level) {
          loud += step;
          lastLoud = atMs;
        }
        if (loud >= rule.loudMs) heard = true;
      }
      if (heard) return atMs - lastLoud >= rule.endMs ? "ended" : "speech";
      // without any level the watch cannot tell: losing what was said is worse than a quiet recording sent
      return gotLevel && atMs >= rule.waitMs ? "silent" : "listening";
    },
  };
}
