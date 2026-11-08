// The queue tells screens whether a sound is playing, so buttons that would cut Ryan off can wait
// (spec roleplay-practice 9). expo-audio's player is replaced by one the test finishes by hand.
const mockFinish: ((s: { didJustFinish: boolean }) => void)[] = [];
const mockPlayed: unknown[] = [];
// what the queue asked of the player's pause and remove, in order
const mockCalls: string[] = [];
jest.mock("expo-audio", () => ({
  createAudioPlayer: () => ({
    addListener: (_: string, cb: (s: { didJustFinish: boolean }) => void) => mockFinish.push(cb),
    replace: (src: unknown) => mockPlayed.push(src),
    play: () => {},
    pause: () => mockCalls.push("pause"),
    remove: () => mockCalls.push("remove"),
  }),
}));

import { SoundQueue } from "./player";

beforeEach(() => {
  mockFinish.length = 0;
  mockPlayed.length = 0;
  mockCalls.length = 0;
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

// phone check 2026-11-08: a recording runs up to 55 s; at 30 s the watchdog passed it while it still played, so its 🔊
// stopped bouncing and a tap on it played it again instead of stopping it
test("a sound that keeps playing is not passed by the watchdog", () => {
  const q = new SoundQueue();
  q.enqueue("long", "rec:1");
  for (let s = 0; s < 50; s++) {
    jest.advanceTimersByTime(1000);
    mockFinish.forEach((cb) => (cb as (st: { didJustFinish: boolean; playing: boolean; currentTime: number }) => void)({ didJustFinish: false, playing: true, currentTime: s + 1 }));
  }
  expect(q.isPlaying()).toBe(true);
  expect(q.nowTag().tag).toBe("rec:1");
  finish();
  expect(q.nowTag().tag).toBeNull();
});

test("a late playing report during a pause does not stretch the pause", () => {
  const q = new SoundQueue();
  q.enqueue("a", "first:1");
  q.enqueuePause(600, "first:1");
  q.enqueue("b", "first:1");
  finish();
  mockFinish.forEach((cb) => (cb as (st: { didJustFinish: boolean; playing: boolean }) => void)({ didJustFinish: false, playing: true }));
  jest.advanceTimersByTime(600);
  expect(mockPlayed).toEqual(["a", "b"]);
});

// final review: a sound that fails to load reports an error and never its end; its 🔊 must not bounce in silence
type St = { didJustFinish: boolean; playing?: boolean; currentTime?: number; error?: string | null };
const report = (st: St) => mockFinish.forEach((cb) => (cb as (s: St) => void)(st));

test("an error ends the sound at once", () => {
  const q = new SoundQueue();
  q.enqueue("bad", "rec:1");
  report({ didJustFinish: false, playing: false, error: "Source error" });
  expect(q.nowTag().tag).toBeNull();
  expect(q.isPlaying()).toBe(false);
});

test("buffering reports with no progress do not hold the watchdog off", () => {
  const q = new SoundQueue();
  q.enqueue("slow", "rec:1");
  for (let s = 0; s < 30; s++) {
    jest.advanceTimersByTime(1000);
    report({ didJustFinish: false, playing: true, currentTime: 0, error: null });
  }
  expect(q.nowTag().tag).toBeNull();
});

// todo 20261108_42: a phone reinstall opened the app twice in one process. The first app root was closed, but its
// queue played on: its greeting, asked for before the close, arrived after it, so Ryan's two lines sounded twice.
describe("close", () => {
  test("stops what plays and drops what waits", () => {
    const q = new SoundQueue();
    q.enqueue("a");
    q.enqueue("b");
    q.close();
    finish();
    expect(mockPlayed).toEqual(["a"]);
    expect(q.isPlaying()).toBe(false);
  });

  test("a sound asked for after the close is not played", () => {
    const q = new SoundQueue();
    q.close();
    q.enqueue("late");
    q.enqueuePause(600);
    expect(mockPlayed).toEqual([]);
    expect(q.isPlaying()).toBe(false);
  });

  // expo-audio's `remove()` on Android only lets the player go: a greeting already playing plays on unless it is
  // paused first (final review)
  test("pauses what plays, then lets the phone's player go", () => {
    const q = new SoundQueue();
    q.enqueue("a");
    q.close();
    expect(mockCalls).toEqual(["pause", "remove"]);
  });

  // the screens under the root are taken down after it, and may still stop the queue or wait for quiet
  test("after the close the player is left alone, and waiting for quiet ends at once", () => {
    const q = new SoundQueue();
    q.close();
    q.clear();
    expect(mockCalls).toEqual(["pause", "remove"]);
    const done = jest.fn();
    q.onIdle(done);
    expect(done).toHaveBeenCalled();
  });
});
