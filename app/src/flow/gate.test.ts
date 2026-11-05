import { createGate } from "./gate";

test("a second call while the first runs is ignored", async () => {
  // PR #12 review: a double tap on 「■ 말하기 끝」 uploaded the same recording twice
  const gate = createGate();
  let calls = 0;
  let finish: () => void = () => {};
  const work = () =>
    new Promise<string>((resolve) => {
      calls += 1;
      finish = () => resolve("done");
    });
  const first = gate.run(work);
  const second = await gate.run(work);
  expect(second).toBeUndefined();
  expect(calls).toBe(1);
  finish();
  expect(await first).toBe("done");
  expect(gate.busy).toBe(false);
});

test("the gate opens again after a failure", async () => {
  const gate = createGate();
  await expect(gate.run(async () => Promise.reject(new Error("x")))).rejects.toThrow("x");
  expect(await gate.run(async () => 1)).toBe(1);
});
