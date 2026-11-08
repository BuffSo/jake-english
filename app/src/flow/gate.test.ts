import { createGate, createHold, createLatch, runThenHold, stopThenSend, TAP_HOLD_MS, tapThenHold } from "./gate";

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

// spec record-cancel-skip 5: 「■ 말하기 끝」 and 「취소」 tapped together, either one first
test("a cancel while a stop runs does nothing, and the stop sends", async () => {
  const gate = createGate();
  const send = jest.fn(async () => {});
  let finish!: (v: string) => void;
  const stop = stopThenSend(gate, () => new Promise<string>((r) => (finish = r)), send);
  const cancel = jest.fn(async () => true);
  expect(await runThenHold(gate, createHold(), cancel)).toBe(false);
  expect(cancel).not.toHaveBeenCalled();
  finish("file:///rec.m4a");
  await stop;
  expect(send).toHaveBeenCalledWith("file:///rec.m4a");
});

test("a stop while a cancel runs sends nothing", async () => {
  const gate = createGate();
  const send = jest.fn(async () => {});
  let finish!: () => void;
  const cancel = runThenHold(gate, createHold(), () => new Promise<boolean>((r) => (finish = () => r(true))));
  await stopThenSend(gate, async () => "file:///rec.m4a", send);
  finish();
  expect(await cancel).toBe(true);
  expect(send).not.toHaveBeenCalled();
});

// The second tap of a double tap lands on the button the redraw puts in the same place (「취소」 → 「건너뛰기」). In
// saved practice the next sentence may be another conversation's, which mounts a new screen with a new gate (final
// review): the hold is not the gate's.
test("after a cancel or skip the next tap is turned away a moment, on a new screen's gate too", async () => {
  let t = 1000;
  const hold = createHold(() => t);
  expect(await runThenHold(createGate(), hold, async () => true)).toBe(true);
  expect(hold.on).toBe(true);
  const second = jest.fn(async () => true);
  expect(await runThenHold(createGate(), hold, second)).toBe(false);
  expect(second).not.toHaveBeenCalled();
  t += TAP_HOLD_MS;
  expect(hold.on).toBe(false);
  expect(await runThenHold(createGate(), hold, second)).toBe(true);
});

test("nothing done holds nothing", async () => {
  const hold = createHold(() => 0);
  expect(await runThenHold(createGate(), hold, async () => false)).toBe(false);
  expect(hold.on).toBe(false);
});

// PR #45 review: 「다시 해 보기」 redraws the bar with 「건너뛰기」 where it was, so its double tap skipped the line
test("a tap that puts 「건너뛰기」 under it holds the next tap", async () => {
  let t = 1000;
  const hold = createHold(() => t);
  const again = jest.fn();
  tapThenHold(hold, again);
  expect(again).toHaveBeenCalledTimes(1);
  const skip = jest.fn(async () => true);
  expect(await runThenHold(createGate(), hold, skip)).toBe(false);
  expect(skip).not.toHaveBeenCalled();
  t += TAP_HOLD_MS;
  expect(await runThenHold(createGate(), hold, skip)).toBe(true);
});
