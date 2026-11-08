// Whether anything was said since the mic came on (spec record-feedback 4). Fed the mic level every 0.1 s or so;
// says "silent" once no speech came for `waitMs`, and the screen then throws the recording away. One loud reading
// (the tap, a bump of the phone) is not speech: loud time has to add up to `loudMs`, as on the Mac (`has_speech`).
// Once speech is heard it stays heard, and "ended" comes after `endMs` with no speech: the screen then ends the
// recording as 「말하기 끝」 does. The learner still ends with the button; the long pause is for when they forget
// (user, 2026-11-08).
export type SpeechRule = {
  level: number; // dBFS at or over which a reading is loud (Android: the loudest sample since the last reading)
  loudMs: number; // loud time that makes speech
  waitMs: number; // with no speech by then, silent
  skipMs: number; // readings this soon after the mic came on are not counted
  endMs: number; // after speech, this long with no speech ends the recording
  overRoomDb: number; // for the pause, speech also stands this far over the room's floor
};

// Measured on the phone (2026-11-08, peak dBFS every 0.1 s): a quiet room sat at -55~-63 with short sounds now and
// then up to -30; the learner's voice from the Mac speaker read -18~-40 at a normal level and -40~-50 played soft. The
// level is under the soft voice so a quiet speaker is not cut off; 0.3 s of loud keeps one or two room sounds out.
// 5 s from the mic coming on and 8 s of pause after speech: the user's calls (2026-11-08). The pause is longer since
// that recording is sent: cut early, a line not finished would be evaluated, and pausing to find the next word is
// common.
// In a noisy room the level alone never let the pause end: a fan or chatter read over -45 all the time, and a test
// recording went on to 55 s (todo 20261108_34 6). So the pause goes by speech that also stands `overRoomDb` over the
// room's floor (the main session's pick, the user's 「ㅇㅋ」, 2026-11-08; the dB to be set on the phone). Measured on the
// phone with made-up fan and chatter 12 dB under the learner's voice from the Mac speaker: the fan read -43~-38 and the
// chatter -51~-35 once the voice stopped, and the voice up to -18. At 10 dB the chatter still broke the pause; at 14 dB
// both ended 7~8 s after the last word. On the Mac, 756 made-up cases at 14 dB: none was cut while it was said, none
// ended within a second of its last word, and none was thrown away.
export const SPEECH_RULE: SpeechRule = { level: -45, loudMs: 300, waitMs: 5000, skipMs: 300, endMs: 8000, overRoomDb: 14 };

export type Heard = "listening" | "speech" | "silent" | "ended";

const FIRST_STEP_MS = 100; // the first counted reading stands for this much time
const MOST_STEP_MS = 250; // a reading after a long gap (the app was busy) stands for no more than this
// the room's floor: the counted reading a twentieth of the way up from the quietest. The readings count the learner's
// own voice, and talking on with few gaps between words would lift a floor taken higher up (a fifth was), and the bar
// over it, cutting the line while it is said (PR #60 review). For the same reason, once a second of readings is in it
// only goes down: in a quiet room the floor so found stays under the level from then on. An odd low reading in the
// first second sinks it for good; the bar is then the level alone, as before.
const FLOOR_SHARE = 0.05;
const FLOOR_SETTLES = 10; // readings in the floor (1 s) after which it only goes down
// readings this soon after the mic came on stay out of the floor: on the phone the first ones read 10~20 dB under the
// room as the mic comes on (a fan at -40 read -50, -45, then -40), and a floor that only goes down would keep them
const FLOOR_FROM_MS = 700;

type Reading = { atMs: number; db: number; step: number };

export function createSpeechWatch(rule: SpeechRule = SPEECH_RULE) {
  let loud = 0;
  let prev: number | undefined;
  let gotLevel = false;
  let heard = false;
  const counted: Reading[] = [];
  const low: number[] = []; // the counted levels, quietest first
  let floor = -Infinity; // the room's floor, set with the first reading in it; until then the bar is the level

  // Speech for the pause stands over the level and over the room's floor. All the readings are judged again by the
  // floor known now: speaking from the first reading, the floor is not known yet. Without such speech adding up to
  // `loudMs` the pause never ends: in a room as loud as the voice it goes on to the button or 55 s, as before. A soft
  // voice only a little over chatter can still be taken for room and cut while it is said: at 10 dB 10 of the 756
  // made-up cases ended within a second of the last word, none at 14 dB. In a quiet room the floor is far under the
  // level, and this is the level alone.
  function paused(atMs: number): boolean {
    const bar = Math.max(rule.level, floor + rule.overRoomDb);
    let speech = 0;
    let last: number | undefined;
    for (let i = counted.length - 1; i >= 0; i--) {
      const r = counted[i];
      if (r.db < bar) continue;
      speech += r.step;
      last ??= r.atMs;
    }
    return last !== undefined && speech >= rule.loudMs && atMs - last >= rule.endMs;
  }

  return {
    feed(atMs: number, db: number | undefined): Heard {
      const step = prev === undefined ? FIRST_STEP_MS : Math.min(atMs - prev, MOST_STEP_MS);
      prev = atMs;
      if (atMs >= rule.skipMs && db !== undefined) {
        gotLevel = true;
        if (db >= rule.level) loud += step;
        if (loud >= rule.loudMs) heard = true;
        counted.push({ atMs, db, step });
        if (atMs >= FLOOR_FROM_MS) {
          low.splice(placeOf(low, db), 0, db);
          const now = low[Math.floor((low.length - 1) * FLOOR_SHARE)];
          if (low.length <= FLOOR_SETTLES || now < floor) floor = now;
        }
      }
      if (heard) return paused(atMs) ? "ended" : "speech";
      // without any level the watch cannot tell: losing what was said is worse than a quiet recording sent. The
      // throwing away goes by the level alone, never the room: a room over it keeps the recording, as before.
      return gotLevel && atMs >= rule.waitMs ? "silent" : "listening";
    },
  };
}

// where `db` goes in the sorted `low`
function placeOf(low: number[], db: number): number {
  let a = 0;
  let b = low.length;
  while (a < b) {
    const m = (a + b) >> 1;
    if (low[m] < db) a = m + 1;
    else b = m;
  }
  return a;
}
