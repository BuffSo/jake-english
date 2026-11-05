// The queue tells screens whether a sound is playing, so buttons that would cut Ryan off can wait
// (spec roleplay-practice 9). expo-audio's player is replaced by one the test finishes by hand.
const mockFinish: ((s: { didJustFinish: boolean }) => void)[] = [];
jest.mock("expo-audio", () => ({
  createAudioPlayer: () => ({
    addListener: (_: string, cb: (s: { didJustFinish: boolean }) => void) => mockFinish.push(cb),
    replace: () => {},
    play: () => {},
    pause: () => {},
  }),
}));

import { SoundQueue } from "./player";

beforeEach(() => {
  mockFinish.length = 0;
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
