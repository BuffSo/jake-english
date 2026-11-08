// The recording is thrown away when no speech came for a while after the mic came on (spec record-feedback 4).
import { createSpeechWatch, SPEECH_RULE, type Heard, type SpeechRule } from "./speechWatch";

const rule: SpeechRule = { level: -40, loudMs: 200, waitMs: 8000, skipMs: 300 };
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
  expect(said.get(20000)).toBe("speech");
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

test("the rule in use starts from 8 s and 0.2 s", () => {
  expect(SPEECH_RULE.waitMs).toBe(8000);
  expect(SPEECH_RULE.loudMs).toBe(200);
});
