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

// spec play-button-feedback 1: the 🔊 of the button that asked for a sound bounces while that sound plays
describe("tags", () => {
  type Now = { tag: string | null; since: number };
  const watch = (q: SoundQueue) => {
    const seen: (string | null)[] = [];
    q.subscribeTag((now: Now) => seen.push(now.tag));
    return seen;
  };

  test("a tagged sound sets the tag until it finishes", () => {
    const q = new SoundQueue();
    q.enqueue("a", "rec:1");
    expect(q.nowTag().tag).toBe("rec:1");
    finish();
    expect(q.nowTag().tag).toBeNull();
  });

  test("the tag is set at once, while the sound is still being fetched", () => {
    jest.setSystemTime(1000);
    const q = new SoundQueue();
    q.enqueue("a", "rec:1");
    expect(q.nowTag()).toEqual({ tag: "rec:1", since: 1000 });
  });

  test("a pair keeps its tag through the pause", () => {
    jest.setSystemTime(1000);
    const q = new SoundQueue();
    const seen = watch(q);
    q.enqueue("a", "first:3");
    q.enqueuePause(600, "first:3");
    q.enqueue("b", "first:3");
    jest.setSystemTime(3000);
    finish();
    expect(q.nowTag()).toEqual({ tag: "first:3", since: 1000 });
    jest.advanceTimersByTime(600);
    expect(q.nowTag().tag).toBe("first:3");
    finish();
    expect(q.nowTag().tag).toBeNull();
    expect(seen).toEqual(["first:3", null]);
  });

  test("clear drops the tag", () => {
    const q = new SoundQueue();
    q.enqueue("a", "listen");
    q.clear();
    expect(q.nowTag().tag).toBeNull();
  });

  test("an untagged sound after a tagged one clears it", () => {
    const q = new SoundQueue();
    q.enqueue("a", "bubble:2");
    q.enqueue("b");
    finish();
    expect(q.isPlaying()).toBe(true);
    expect(q.nowTag().tag).toBeNull();
  });

  test("the tag clears when the queue moves on without a finish", () => {
    // a sound that never reports its end (bad file, lost connection) is passed after STUCK_MS
    const q = new SoundQueue();
    q.enqueue("a", "rec:1");
    jest.advanceTimersByTime(30_000);
    expect(q.isPlaying()).toBe(false);
    expect(q.nowTag().tag).toBeNull();
  });

  test("listeners hear only changes, and stop when unsubscribed", () => {
    const q = new SoundQueue();
    const seen: (string | null)[] = [];
    const stop = q.subscribeTag((now: Now) => seen.push(now.tag));
    q.enqueue("a", "ko:4");
    q.enqueue("b", "ko:4");
    finish();
    q.clear();
    stop();
    q.enqueue("c", "listen");
    expect(seen).toEqual(["ko:4", null]);
  });

  test("a new tag replaces the one playing", () => {
    jest.setSystemTime(1000);
    const q = new SoundQueue();
    q.enqueue("a", "rec:1");
    jest.setSystemTime(2000);
    q.clear();
    q.enqueue("b", "rec:2");
    expect(q.nowTag()).toEqual({ tag: "rec:2", since: 2000 });
  });
});
