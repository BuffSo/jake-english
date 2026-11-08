// While the mic is on, its level is read every 0.1 s for the voice line and the speech watch (spec record-feedback 2, 4).
import { SPEECH_RULE } from "../flow/speechWatch";
import { LEVEL_EVERY_MS, startLevelPoll } from "./levelPoll";

beforeEach(() => jest.useFakeTimers());

test("each reading goes to the voice line", () => {
  const levels = [-60, -20, undefined];
  const seen: (number | undefined)[] = [];
  const stop = startLevelPoll({ read: () => levels.shift(), onLevel: (db) => seen.push(db) });
  jest.advanceTimersByTime(3 * LEVEL_EVERY_MS);
  expect(seen).toEqual([-60, -20, undefined]);
  stop();
});

test("quiet calls onNoSpeech once, at the rule's wait", () => {
  const onNoSpeech = jest.fn();
  const stop = startLevelPoll({ read: () => -90, onLevel: () => {}, onNoSpeech });
  jest.advanceTimersByTime(SPEECH_RULE.waitMs - LEVEL_EVERY_MS);
  expect(onNoSpeech).not.toHaveBeenCalled();
  jest.advanceTimersByTime(LEVEL_EVERY_MS);
  expect(onNoSpeech).toHaveBeenCalledTimes(1);
  jest.advanceTimersByTime(5000);
  expect(onNoSpeech).toHaveBeenCalledTimes(1);
  stop();
});

test("speech keeps onNoSpeech from being called", () => {
  const onNoSpeech = jest.fn();
  let n = 0;
  const stop = startLevelPoll({ read: () => (++n >= 10 && n <= 15 ? -10 : -90), onLevel: () => {}, onNoSpeech });
  jest.advanceTimersByTime(30_000);
  expect(onNoSpeech).not.toHaveBeenCalled();
  stop();
});

test("without onNoSpeech nothing is cancelled (the situation screen)", () => {
  const onLevel = jest.fn();
  const stop = startLevelPoll({ read: () => -90, onLevel });
  jest.advanceTimersByTime(30_000);
  expect(onLevel).toHaveBeenCalled();
  stop();
});

test("stop ends the readings", () => {
  const read = jest.fn(() => -90);
  const onNoSpeech = jest.fn();
  const stop = startLevelPoll({ read, onLevel: () => {}, onNoSpeech });
  jest.advanceTimersByTime(LEVEL_EVERY_MS);
  stop();
  const calls = read.mock.calls.length;
  jest.advanceTimersByTime(30_000);
  expect(read.mock.calls.length).toBe(calls);
  expect(onNoSpeech).not.toHaveBeenCalled();
});

test("a reading that throws counts as no level, so it never cancels", () => {
  const onNoSpeech = jest.fn();
  const seen: (number | undefined)[] = [];
  const stop = startLevelPoll({
    read: () => {
      throw new Error("recorder gone");
    },
    onLevel: (db) => seen.push(db),
    onNoSpeech,
  });
  jest.advanceTimersByTime(30_000);
  expect(onNoSpeech).not.toHaveBeenCalled();
  expect(seen[0]).toBeUndefined();
  stop();
});

test("a long pause after speech calls onSpeechEnd once, and never onNoSpeech", () => {
  const onNoSpeech = jest.fn();
  const onSpeechEnd = jest.fn();
  let n = 0;
  const stop = startLevelPoll({ read: () => (++n >= 10 && n <= 15 ? -10 : -90), onLevel: () => {}, onNoSpeech, onSpeechEnd });
  jest.advanceTimersByTime(1500 + SPEECH_RULE.endMs - LEVEL_EVERY_MS);
  expect(onSpeechEnd).not.toHaveBeenCalled();
  jest.advanceTimersByTime(LEVEL_EVERY_MS);
  expect(onSpeechEnd).toHaveBeenCalledTimes(1);
  jest.advanceTimersByTime(20_000);
  expect(onSpeechEnd).toHaveBeenCalledTimes(1);
  expect(onNoSpeech).not.toHaveBeenCalled();
  stop();
});
