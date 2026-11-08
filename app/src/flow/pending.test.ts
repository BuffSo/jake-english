import { askAfter, createPending, RESUME_WAIT_MS } from "./pending";

// whether a promise has settled, without waiting for it
async function done(p: Promise<unknown>): Promise<boolean> {
  let settled = false;
  p.then(
    () => (settled = true),
    () => (settled = true),
  );
  for (let i = 0; i < 20; i++) await Promise.resolve(); // the chain inside `settled` is several turns deep
  return settled;
}

beforeEach(() => jest.useFakeTimers());
afterEach(() => jest.useRealTimers());

test("settled is at once with nothing tracked", async () => {
  expect(await done(createPending().settled(RESUME_WAIT_MS))).toBe(true);
});

test("settled waits for what was tracked", async () => {
  const pending = createPending();
  let finish!: () => void;
  const sent = pending.track(new Promise<void>((r) => (finish = r)));
  const waiting = pending.settled(RESUME_WAIT_MS);
  expect(await done(waiting)).toBe(false);
  finish();
  await sent;
  expect(await done(waiting)).toBe(true);
});

test("a failed promise counts as settled", async () => {
  const pending = createPending();
  let fail!: (e: Error) => void;
  const sent = pending.track(new Promise<void>((_, reject) => (fail = reject)));
  const caught = sent.catch((e: Error) => e.message); // the caller still gets the failure
  const waiting = pending.settled(RESUME_WAIT_MS);
  fail(new Error("offline"));
  expect(await caught).toBe("offline");
  expect(await done(waiting)).toBe(true);
});

test("settled gives up after maxMs", async () => {
  const pending = createPending();
  pending.track(new Promise<void>(() => {}));
  const waiting = pending.settled(RESUME_WAIT_MS);
  jest.advanceTimersByTime(RESUME_WAIT_MS - 1);
  expect(await done(waiting)).toBe(false);
  jest.advanceTimersByTime(1);
  expect(await done(waiting)).toBe(true);
});

test("askAfter asks only once what was tracked has settled", async () => {
  const pending = createPending();
  let finish!: () => void;
  pending.track(new Promise<void>((r) => (finish = r)));
  const ask = jest.fn(async () => "asked");
  const answer = askAfter(pending, ask);
  expect(await done(answer)).toBe(false);
  expect(ask).not.toHaveBeenCalled();
  finish();
  expect(await answer).toBe("asked");
  expect(ask).toHaveBeenCalledTimes(1);
});
