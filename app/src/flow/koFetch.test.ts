import type { ScriptLine } from "../api/types";
import { createKoFetch, FAIL_SHOW_MS, type KoDeps } from "./koFetch";
import { koView, type KoEntry } from "./interpret";

type Deferred<T> = { promise: Promise<T>; resolve: (v: T) => void; reject: (e: unknown) => void };
function deferred<T>(): Deferred<T> {
  let resolve!: (v: T) => void;
  let reject!: (e: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}
const flush = () => new Promise((r) => setTimeout(r, 0));

const plain: ScriptLine = { idx: 2, speaker: "ryan", text: "What can I get you?", kind: "script", three: null, audio: null, ko: null, ko_audio: null };
const KEY = "c".repeat(64);

function setup(allowed = true) {
  const texts: Deferred<{ text: string }>[] = [];
  const sounds: Deferred<{ audio: string }>[] = [];
  const played: string[] = [];
  let got: Record<number, KoEntry> = {};
  const state = { allowed };
  const deps: KoDeps = {
    getKo: () => {
      const d = deferred<{ text: string }>();
      texts.push(d);
      return d.promise;
    },
    getKoAudio: () => {
      const d = deferred<{ audio: string }>();
      sounds.push(d);
      return d.promise;
    },
    play: (a) => played.push(a),
    allow: () => state.allowed,
    onChange: (g) => {
      got = g;
    },
  };
  return { ko: createKoFetch(deps), texts, sounds, played, state, got: () => got };
}

test("open: the text shows first, then her voice plays when it comes", async () => {
  const t = setup();
  t.ko.open(2, plain, () => true);
  await flush();
  expect(t.got()[2]).toBe("loading");
  t.texts[0].resolve({ text: "뭐 드릴까요?" });
  await flush();
  expect(t.got()[2]).toEqual({ text: "뭐 드릴까요?", audio: null });
  t.sounds[0].resolve({ audio: KEY });
  await flush();
  expect(t.played).toEqual([KEY]);
  expect(t.got()[2]).toEqual({ text: "뭐 드릴까요?", audio: KEY });
});

test("closing before the sound comes keeps her quiet (Review Focus 1)", async () => {
  const t = setup();
  let open = true;
  t.ko.open(2, plain, () => open);
  await flush();
  t.texts[0].resolve({ text: "뭐 드릴까요?" });
  await flush();
  open = false;
  t.sounds[0].resolve({ audio: KEY });
  await flush();
  expect(t.played).toEqual([]);
});

test("a sound that comes after the turn got busy is not played (Review Focus 2)", async () => {
  const t = setup();
  t.ko.open(2, { ...plain, ko: "뭐 드릴까요?" }, () => true);
  await flush();
  t.state.allowed = false; // the learner started recording, or Ryan started speaking
  t.sounds[0].resolve({ audio: KEY });
  await flush();
  expect(t.played).toEqual([]);
});

test("her sound is not made while she could not play: it would wait ahead of Ryan's feedback", async () => {
  // final review: Sohee's urgent sound went before Ryan's feedback sentences in the voice worker's queue
  const t = setup(false);
  t.ko.open(2, plain, () => true);
  t.texts[0].resolve({ text: "뭐 드릴까요?" });
  await flush();
  expect(t.got()[2]).toEqual({ text: "뭐 드릴까요?", audio: null });
  expect(t.sounds).toHaveLength(0);
});

test("a replay that comes after leaving for a practice does not play (final review)", async () => {
  const t = setup();
  let here = true;
  t.ko.replay(2, { ...plain, ko: "뭐 드릴까요?" }, () => here);
  here = false; // 「따라 말하기 ›」: the same screen, another line
  t.sounds[0].resolve({ audio: KEY });
  await flush();
  expect(t.played).toEqual([]);
});

test("a replay plays what is kept without asking, and only while allowed", async () => {
  const t = setup();
  const kept = { ...plain, ko: "뭐 드릴까요?", ko_audio: KEY };
  t.ko.replay(2, kept, () => true);
  await flush();
  expect([t.played, t.sounds.length]).toEqual([[KEY], 0]);
  t.state.allowed = false;
  t.ko.replay(2, kept, () => true);
  await flush();
  expect(t.played).toEqual([KEY]);
});

test("only the latest opening plays", async () => {
  const t = setup();
  const line = { ...plain, ko: "뭐 드릴까요?" };
  t.ko.open(2, line, () => true);
  t.ko.open(2, line, () => true);
  await flush();
  t.sounds.forEach((s) => s.resolve({ audio: KEY }));
  await flush();
  expect(t.played).toEqual([KEY]);
});

test("a text that fails shows as failed, and the next opening asks again", async () => {
  const t = setup();
  t.ko.open(2, plain, () => true);
  t.texts[0].reject(new Error("503"));
  await flush();
  expect(t.got()[2]).toBe("failed");
  t.ko.open(2, plain, () => true);
  await flush();
  expect([t.texts.length, t.got()[2]]).toEqual([2, "loading"]);
});

test("after the screen goes away nothing plays or changes", async () => {
  const t = setup();
  t.ko.open(2, { ...plain, ko: "뭐 드릴까요?" }, () => true);
  await flush();
  t.ko.stop();
  t.sounds[0].resolve({ audio: KEY });
  await flush();
  expect([t.played, t.got()[2]]).toEqual([[], undefined]);
});

describe("a failure note shows a moment, then folds (todo 20261106_10 1)", () => {
  // the failure note is 「짧게 보이고 접는다」 (spec korean-translation 2): not left until the next tap
  beforeEach(() => jest.useFakeTimers());
  afterEach(() => jest.useRealTimers());
  const tick = (ms = 0) => jest.advanceTimersByTimeAsync(ms);

  test("a failure folds after FAIL_SHOW_MS and a tap asks again", async () => {
    const t = setup();
    t.ko.open(2, plain, () => true);
    t.texts[0].reject(new Error("503"));
    await tick();
    expect(t.got()[2]).toBe("failed");
    await tick(FAIL_SHOW_MS);
    expect(t.got()[2]).toBe("folded");
    expect(koView(t.got()[2], true)).toBe("closed");
    t.ko.open(2, plain, () => true);
    await tick();
    expect([t.texts.length, t.got()[2]]).toEqual([2, "loading"]);
  });

  test("a new opening before the fold is not folded by the old timer", async () => {
    const t = setup();
    t.ko.open(2, plain, () => true);
    t.texts[0].reject(new Error("503"));
    await tick(1000);
    t.ko.open(2, plain, () => true);
    t.texts[1].resolve({ text: "뭐 드릴까요?" });
    await tick(FAIL_SHOW_MS);
    expect(t.got()[2]).toEqual({ text: "뭐 드릴까요?", audio: null });
  });

  test("a second failure gets its own moment", async () => {
    const t = setup();
    t.ko.open(2, plain, () => true);
    t.texts[0].reject(new Error("503"));
    await tick(FAIL_SHOW_MS - 1000);
    t.ko.open(2, plain, () => true);
    t.texts[1].reject(new Error("503"));
    await tick(1000); // the first failure's moment is over, the second one's is not
    expect(t.got()[2]).toBe("failed");
    await tick(FAIL_SHOW_MS);
    expect(t.got()[2]).toBe("folded");
  });
});
