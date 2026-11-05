import { whenSilent } from "./whenSilent";

// A sound queue that stays busy until the test says the last sound ended.
function fakeSounds() {
  let waiting: (() => void)[] = [];
  return {
    onIdle(cb: () => void) {
      waiting.push(cb);
    },
    finish() {
      const cbs = waiting;
      waiting = [];
      cbs.forEach((cb) => cb());
    },
  };
}

const tick = () => new Promise((r) => setTimeout(r, 0));

test("the result waits until the sound ends", async () => {
  // 2026-11-05 on the phone: the script came back while Jake was still asking for the situation, the
  // roleplay screen opened and its first line cut him off
  const sounds = fakeSounds();
  let got: string | undefined;
  whenSilent(sounds, Promise.resolve("script")).then((v) => (got = v));
  await tick();
  expect(got).toBeUndefined();
  sounds.finish();
  await tick();
  expect(got).toBe("script");
});

test("a sound that ended first does not hold the result", async () => {
  const sounds = { onIdle: (cb: () => void) => cb() };
  expect(await whenSilent(sounds, Promise.resolve(1))).toBe(1);
});

test("a failure comes back without waiting for the sound", async () => {
  const sounds = fakeSounds();
  await expect(whenSilent(sounds, Promise.reject(new Error("offline")))).rejects.toThrow("offline");
});
