// The cues play with a vibration; the mic waits for the start cue to end, and must not wait forever on a cue that
// cannot play (spec record-feedback 1).
type Listener = (s: { didJustFinish: boolean }) => void;
const mockListeners: Listener[] = [];
const mockPlays: string[] = [];
let mockFailPlayer = false;
jest.mock("expo-audio", () => ({
  createAudioPlayer: (src: { uri: string }) => {
    if (mockFailPlayer) throw new Error("no player");
    return {
      addListener: (_: string, cb: Listener) => {
        mockListeners.push(cb);
        return { remove: () => mockListeners.splice(mockListeners.indexOf(cb), 1) };
      },
      seekTo: async () => {},
      play: () => mockPlays.push(src.uri),
    };
  },
}));
jest.mock("expo-file-system", () => ({
  Paths: { cache: "file:///cache" },
  File: class {
    uri: string;
    constructor(dir: string, name: string) {
      this.uri = `${dir}/${name}`;
    }
    async write() {}
  },
}));
const mockVibrate = jest.fn();
jest.mock("react-native", () => ({ Vibration: { vibrate: (p: unknown) => mockVibrate(p) } }));

import { cueMs } from "./cueSound";
import { VIBRATE, waitForEnd } from "./cues";

// a fresh module per test: the players are kept in it once made
function fresh(): typeof import("./cues") {
  let mod!: typeof import("./cues");
  jest.isolateModules(() => {
    mod = require("./cues");
  });
  return mod;
}

beforeEach(() => {
  jest.useFakeTimers();
  mockListeners.length = 0;
  mockPlays.length = 0;
  mockFailPlayer = false;
  mockVibrate.mockClear();
});

const finished = () => [...mockListeners].forEach((cb) => cb({ didJustFinish: true }));

test("waitForEnd ends when done is called", async () => {
  let done!: () => void;
  const stop = jest.fn();
  const p = waitForEnd((d) => ((done = d), stop), 1000);
  let over = false;
  void p.then(() => (over = true));
  await Promise.resolve();
  expect(over).toBe(false);
  done();
  await p;
  expect(stop).toHaveBeenCalledTimes(1);
});

test("waitForEnd gives up after the cap", async () => {
  const stop = jest.fn();
  const p = waitForEnd(() => stop, 500);
  jest.advanceTimersByTime(500);
  await p;
  expect(stop).toHaveBeenCalledTimes(1);
});

test("waitForEnd stops listening once, even when done comes after the cap", async () => {
  let done!: () => void;
  const stop = jest.fn();
  const p = waitForEnd((d) => ((done = d), stop), 500);
  jest.advanceTimersByTime(500);
  await p;
  done();
  expect(stop).toHaveBeenCalledTimes(1);
});

test("vibrations: start once short, end twice, cancel once longer", () => {
  expect(VIBRATE).toEqual({ start: 50, end: [0, 50, 80, 50], cancel: 180 });
});

test("a prepared cue vibrates, plays from its file, and ends when the sound does", async () => {
  const { prepareCues, playCue } = fresh();
  await prepareCues();
  const p = playCue("start");
  expect(mockVibrate).toHaveBeenCalledWith(50);
  expect(mockPlays).toEqual(["file:///cache/cue-start.wav"]);
  finished();
  await p;
});

test("a cue that cannot play still vibrates and ends after its length", async () => {
  mockFailPlayer = true;
  const { prepareCues, playCue } = fresh();
  await prepareCues();
  const p = playCue("end");
  expect(mockVibrate).toHaveBeenCalledWith([0, 50, 80, 50]);
  let over = false;
  void p.then(() => (over = true));
  jest.advanceTimersByTime(cueMs("end") - 1);
  await Promise.resolve();
  expect(over).toBe(false);
  jest.advanceTimersByTime(1);
  await p;
});

test("a cue whose end never comes is given up a little after its length", async () => {
  const { prepareCues, playCue } = fresh();
  await prepareCues();
  const p = playCue("cancel");
  jest.advanceTimersByTime(cueMs("cancel") + 300);
  await p;
});

test("a cue asked for before the cues are ready waits its length", async () => {
  const { playCue } = fresh();
  const p = playCue("start");
  expect(mockVibrate).toHaveBeenCalledWith(50);
  expect(mockPlays).toEqual([]);
  jest.advanceTimersByTime(cueMs("start"));
  await p;
});
