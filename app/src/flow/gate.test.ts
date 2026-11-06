import { createGate, createLatch, stopThenSend } from "./gate";

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

// final review: back from a practice in the middle of the answer keeps the roleplay screen (spec roleplay-practice 9);
// with the stream inside the gate, the mic did nothing until the old answer had finished
test("the answer is sent after the gate is free again", async () => {
  const gate = createGate();
  let release!: () => void;
  const answering = new Promise<void>((r) => (release = r));
  const run = stopThenSend(gate, async () => "file:///rec.m4a", () => answering);
  await new Promise((r) => setTimeout(r, 0));
  expect(gate.busy).toBe(false);
  release();
  await run;
});

test("nothing is sent when stopping gives nothing", async () => {
  const gate = createGate();
  const send = jest.fn(async () => {});
  await stopThenSend(gate, async () => undefined, send);
  expect(send).not.toHaveBeenCalled();
});

test("a stop that arrives while another runs sends nothing", async () => {
  const gate = createGate();
  const send = jest.fn(async () => {});
  let finish!: () => void;
  const first = gate.run(() => new Promise<void>((r) => (finish = r)));
  await stopThenSend(gate, async () => "file:///rec.m4a", send);
  finish();
  await first;
  expect(send).not.toHaveBeenCalled();
});

// PR #18 review: a double tap on 「이걸로 할게요」 before the screen redrew asked for two scripts
test("a latch takes one answer per question", () => {
  const choice = createLatch();
  expect(choice.take()).toBe(false); // nothing asked yet
  choice.open();
  expect(choice.take()).toBe(true);
  expect(choice.take()).toBe(false); // the second tap of a double tap
  choice.open(); // the next suggestion
  expect(choice.take()).toBe(true);
});
