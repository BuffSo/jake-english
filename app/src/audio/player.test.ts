// The queue tells screens whether a sound is playing, so buttons that would cut Ryan off can wait
// (spec roleplay-practice 9). expo-audio's player is replaced by one the test finishes by hand.
const mockFinish: ((s: { didJustFinish: boolean }) => void)[] = [];
const mockPlayed: unknown[] = [];
jest.mock("expo-audio", () => ({
  createAudioPlayer: () => ({
    addListener: (_: string, cb: (s: { didJustFinish: boolean }) => void) => mockFinish.push(cb),
    replace: (src: unknown) => mockPlayed.push(src),
    play: () => {},
    pause: () => {},
  }),
}));

import { SoundQueue } from "./player";

beforeEach(() => {
  mockFinish.length = 0;
  mockPlayed.length = 0;
  jest.useFakeTimers();
});

const finish = () => mockFinish.forEach((cb) => cb({ didJustFinish: true }));

test("playing is reported when sound starts and when the queue runs dry", () => {
  const q = new SoundQueue();
  const seen: boolean[] = [];
  q.subscribe((p) => seen.push(p));
  q.enqueue("a");
  q.enqueue("b");
  expect(q.isPlaying()).toBe(true);
  finish();
  expect(q.isPlaying()).toBe(true);
  finish();
  expect(q.isPlaying()).toBe(false);
  expect(seen).toEqual([true, false]);
});

test("clear reports quiet", () => {
  const q = new SoundQueue();
  const seen: boolean[] = [];
  q.subscribe((p) => seen.push(p));
  q.enqueue("a");
  q.clear();
  expect([q.isPlaying(), seen]).toEqual([false, [true, false]]);
});

test("a stopped subscription hears nothing", () => {
  const q = new SoundQueue();
  const seen: boolean[] = [];
  q.subscribe((p) => seen.push(p))();
  q.enqueue("a");
  expect(seen).toEqual([]);
});

// 「🔊 처음 녹음」 plays the first recording, a short pause, then this run's: many recordings end right on the last
// word, so back to back the two ran together (spec review-practice 4, todo 01)
test("a pause holds the next sound until it has passed", () => {
  const q = new SoundQueue();
  q.enqueue("a");
  q.enqueuePause(600);
  q.enqueue("b");
  finish();
  jest.advanceTimersByTime(599);
  expect(mockPlayed).toEqual(["a"]);
  expect(q.isPlaying()).toBe(true);
  jest.advanceTimersByTime(1);
  expect(mockPlayed).toEqual(["a", "b"]);
});

test("clear drops a pause on its way", () => {
  const q = new SoundQueue();
  q.enqueue("a");
  q.enqueuePause(600);
  q.enqueue("b");
  finish();
  q.clear();
  jest.advanceTimersByTime(1000);
  expect(mockPlayed).toEqual(["a"]);
  expect(q.isPlaying()).toBe(false);
});
