// The recording is thrown away when no speech came for a while after the mic came on (spec record-feedback 4).
import { createSpeechWatch, SPEECH_RULE, type Heard, type SpeechRule } from "./speechWatch";

const rule: SpeechRule = { level: -40, loudMs: 200, waitMs: 8000, skipMs: 300, endMs: 8000, overRoomDb: 10 };
const QUIET = -60;
const LOUD = -20;

// reads every 100 ms from 100 ms on; `levels(ms)` gives the reading at that time. Returns what each reading said.
function run(until: number, levels: (ms: number) => number | undefined, r: SpeechRule = rule): Map<number, Heard> {
  const watch = createSpeechWatch(r);
  const said = new Map<number, Heard>();
  for (let ms = 100; ms <= until; ms += 100) said.set(ms, watch.feed(ms, levels(ms)));
  return said;
}

test("quiet turns silent at waitMs, not before", () => {
  const said = run(8000, () => QUIET);
  expect(said.get(7900)).toBe("listening");
  expect(said.get(8000)).toBe("silent");
});

test("one loud reading is not speech", () => {
  // the tap on the button, or a bump of the phone
  const said = run(8000, (ms) => (ms === 1000 ? LOUD : QUIET));
  expect(said.get(1000)).toBe("listening");
  expect(said.get(8000)).toBe("silent");
});

test("loud readings adding up to loudMs are speech", () => {
  const said = run(1100, (ms) => (ms === 1000 || ms === 1100 ? LOUD : QUIET));
  expect(said.get(1000)).toBe("listening");
  expect(said.get(1100)).toBe("speech");
});

test("loud readings need not be next to each other", () => {
  const said = run(3000, (ms) => (ms === 1000 || ms === 2500 ? LOUD : QUIET));
  expect(said.get(2500)).toBe("speech");
});

test("once speech is heard it never turns silent", () => {
  const said = run(20000, (ms) => (ms >= 1000 && ms <= 1300 ? LOUD : QUIET));
  expect(said.get(8000)).toBe("speech");
  expect([...said.values()]).not.toContain("silent");
});

// spec record-feedback 4 (user, 2026-11-08): a long pause after speaking ends the recording, as 「말하기 끝」 does
test("a pause of endMs after the last loud reading ends it", () => {
  const said = run(10000, (ms) => (ms >= 1000 && ms <= 1300 ? LOUD : QUIET));
  expect(said.get(9200)).toBe("speech");
  expect(said.get(9300)).toBe("ended"); // 8 s after the last loud reading at 1300
});

test("short pauses between words do not end it", () => {
  // speaking, then 1 s, 2 s and 3 s pauses, each followed by more speech
  const talk = (ms: number) => (ms >= 1000 && ms <= 1500) || (ms >= 2500 && ms <= 3000) || (ms >= 5000 && ms <= 5500) || (ms >= 8500 && ms <= 9000);
  const said = run(16000, (ms) => (talk(ms) ? LOUD : QUIET));
  expect([...said.entries()].filter(([ms]) => ms <= 16000).map(([, h]) => h)).not.toContain("ended");
  expect(said.get(16000)).toBe("speech");
});

test("one loud reading during the pause starts the pause over", () => {
  const said = run(14000, (ms) => ((ms >= 1000 && ms <= 1300) || ms === 6000 ? LOUD : QUIET));
  expect(said.get(13900)).toBe("speech");
  expect(said.get(14000)).toBe("ended"); // 8 s after 6000
});

test("without speech it never ends, it turns silent", () => {
  const said = run(20000, () => QUIET);
  expect([...said.values()]).not.toContain("ended");
});

test("readings before skipMs do not count", () => {
  const said = run(8000, (ms) => (ms <= 300 ? LOUD : QUIET));
  expect(said.get(8000)).toBe("silent");
});

test("a reading at the level counts as loud", () => {
  const said = run(1100, (ms) => (ms >= 1000 ? rule.level : QUIET));
  expect(said.get(1100)).toBe("speech");
});

test("never silent when no level ever came", () => {
  // a phone whose recorder gives no level: losing what was said is worse than sending a quiet recording
  const said = run(20000, () => undefined);
  expect(said.get(20000)).toBe("listening");
});

test("a long gap between readings counts at most 250 ms of loud", () => {
  const watch = createSpeechWatch({ ...rule, loudMs: 400 });
  expect(watch.feed(1000, LOUD)).toBe("listening"); // first reading: 100 ms
  expect(watch.feed(5000, LOUD)).toBe("listening"); // 4 s later, but 250 ms at most: 350 in all
  expect(watch.feed(5100, LOUD)).toBe("speech"); // 450
});

test("the rule in use: 5 s and 8 s (user), -45 dBFS and 0.3 s, 14 dB over the room (measured on the phone)", () => {
  expect(SPEECH_RULE).toEqual({ level: -45, loudMs: 300, waitMs: 5000, skipMs: 300, endMs: 8000, overRoomDb: 14 });
});

// A noisy room (todo 20261108_34 6): a sound over the level all the time kept the pause from ever ending, and a test
// recording went on to 55 s. For the pause a reading must stand over the room's floor too. The rule here has the level
// at -40; the made-up rooms below read over it.
const FAN = [-36, -37, -35, -36, -38, -36, -35, -37]; // a steady sound, about -36
// a sound going up and down, -42 to -34: as wide as the made-up chatter of many voices read on the Mac
const CHATTER = [-38, -35, -41, -36, -34, -39, -42, -35, -37, -40];
const roomAt = (room: number[], ms: number) => room[(ms / 100) % room.length];

test("after speech, a steady room sound over the level does not keep the pause from ending", () => {
  const said = run(14000, (ms) => (ms >= 1000 && ms <= 3000 ? -15 : roomAt(FAN, ms)));
  expect(said.get(10900)).toBe("speech");
  expect(said.get(11000)).toBe("ended"); // 8 s after the last speech at 3000
});

test("after speech, a room sound going up and down does not keep the pause from ending", () => {
  const said = run(14000, (ms) => (ms >= 1000 && ms <= 3000 ? -15 : roomAt(CHATTER, ms)));
  expect(said.get(10900)).toBe("speech");
  expect(said.get(11000)).toBe("ended");
});

test("in a noisy room, short pauses between words do not end it", () => {
  const talk = (ms: number) => (ms >= 1000 && ms <= 1500) || (ms >= 3500 && ms <= 4000) || (ms >= 7000 && ms <= 7500);
  const said = run(15500, (ms) => (talk(ms) ? -15 : roomAt(CHATTER, ms)));
  expect([...said.entries()].filter(([ms]) => ms < 15500).map(([, h]) => h)).not.toContain("ended");
  expect(said.get(15500)).toBe("ended"); // 8 s after 7500
});

// Measured on the phone (2026-11-08): the first readings as the mic comes on are 10~20 dB under the room (a fan at
// -40 read -50, then -45, then -40). The floor must not take them, or it sinks and the fan breaks every pause.
test("readings as the mic comes on, under the room, do not sink the floor", () => {
  const said = run(14000, (ms) => (ms === 400 ? -50 : ms === 500 ? -45 : ms >= 1000 && ms <= 3000 ? -15 : roomAt(FAN, ms)), SPEECH_RULE);
  expect(said.get(10900)).toBe("speech");
  expect(said.get(11000)).toBe("ended"); // 8 s after the last speech at 3000
});

test("a sound never standing over the room's floor does not end it: it goes on, as it did before", () => {
  // what the room gives with no speech, or speech no louder than the room: losing a line said softly is worse
  const said = run(30000, (ms) => roomAt(FAN, ms));
  expect([...said.values()]).not.toContain("ended");
  expect([...said.values()]).not.toContain("silent"); // over the level: never thrown away, as before
  expect(said.get(30000)).toBe("speech");
});

test("a room sound jumping more than overRoomDb over its floor keeps it going, as before", () => {
  // talk nearby: its loud bits cannot be told from the learner by level, so the pause is not ended on a guess
  const talk = [-48, -47, -49, -46, -48, -47, -45, -48, -49, -33]; // -33 every second, 15 dB over the floor
  const said = run(30000, (ms) => (ms >= 1000 && ms <= 3000 ? -15 : roomAt(talk, ms)));
  expect([...said.values()]).not.toContain("ended");
});

// PR #60 review: the floor counts the learner's own voice. Talking on with few gaps, the room readings are a small share
// and the floor must not climb to the voice, or the bar does and the line is cut while it is being said.
const ON = [-30, -26, -33, -28, -24, -31, -27, -34, -29, -60]; // talking on, one reading in ten a gap to the room
const talkingOn = (ms: number) => (ms <= 3000 ? -14 : ms <= 18000 ? ON[(ms / 100) % ON.length] : QUIET);

test("talking on with few gaps in a quiet room is not cut while it is said", () => {
  const said = run(26000, talkingOn, SPEECH_RULE);
  expect([...said.entries()].filter(([ms]) => ms <= 18000).map(([, h]) => h)).not.toContain("ended");
  expect(said.get(26000)).toBe("ended"); // 8 s after the talk ended at 18000
});

test("a soft voice talking on after a quiet start is not cut while it is said", () => {
  const soft = [-41, -44, -47, -42, -49, -45, -43, -48, -46, -42, -44, -60];
  const said = run(36000, (ms) => (ms < 2000 ? QUIET : ms <= 2800 && ms >= 2500 ? -30 : ms <= 27000 ? soft[(ms / 100) % soft.length] : QUIET), SPEECH_RULE);
  expect([...said.entries()].filter(([ms]) => ms <= 27000).map(([, h]) => h)).not.toContain("ended");
});

test("speech from the first counted reading still ends after the pause", () => {
  // the room's floor is not known yet while the learner speaks at once; the pause is judged by the floor known now
  const said = run(11000, (ms) => (ms <= 1500 ? -20 : QUIET));
  expect(said.get(9400)).toBe("speech");
  expect(said.get(9500)).toBe("ended"); // 8 s after 1500
});

// readings taken on the phone (2026-11-08), every 0.1 s from the mic coming on
test("a quiet room with a couple of short sounds turns silent at 5 s", () => {
  const room = [-63, -56, -57, -59, -59, -64, -53, -50, -61, -54, -50, -54, -38, -37, -47, -52, -54, -59, -60];
  const said = run(5000, (ms) => room[ms / 100 - 1] ?? -60, SPEECH_RULE);
  expect(said.get(5000)).toBe("silent");
});

test("a voice played soft from the Mac speaker is speech", () => {
  const soft = [-47, -45, -51, -43, -41, -47, -40, -44, -54, -46, -44, -49];
  const said = run(1200, (ms) => soft[ms / 100 - 1] ?? -60, { ...SPEECH_RULE, skipMs: 0 });
  expect(said.get(1200)).toBe("speech");
});
