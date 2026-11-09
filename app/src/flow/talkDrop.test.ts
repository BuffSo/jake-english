import { ApiError } from "../api/client";
import { createDropper } from "./talkDrop";

const offline = () => new ApiError("offline");
// the Mac's answers: a refusal (404, 409) or a server error, with its HTTP status as the client keeps it
const answer = (status: number) => new ApiError(status === 404 ? "not_found" : "unknown", undefined, status);
const flush = () => new Promise((r) => setTimeout(r, 0));

test("settle waits for the drop sent at the tap", async () => {
  let release!: () => void;
  const send = jest.fn(() => new Promise<void>((r) => (release = r)));
  const d = createDropper(send);
  d.drop(3);
  expect(send).toHaveBeenCalledWith(3);
  let done = false;
  const p = d.settle().then(() => (done = true));
  await Promise.resolve();
  expect(done).toBe(false);
  release();
  await p;
  expect(send).toHaveBeenCalledTimes(1);
});

test("settle retries a failed drop before the next turn", async () => {
  const send = jest.fn().mockRejectedValueOnce(offline()).mockResolvedValue({ dropped: 3 });
  const d = createDropper(send);
  d.drop(3);
  await d.settle();
  expect(send).toHaveBeenCalledTimes(2);
  await d.settle(); // cleared
  expect(send).toHaveBeenCalledTimes(2);
});

test("settle throws when the retry fails and tries again next time", async () => {
  const send = jest.fn().mockRejectedValue(offline());
  const d = createDropper(send);
  d.drop(3);
  await expect(d.settle()).rejects.toBeInstanceOf(ApiError);
  expect(send).toHaveBeenCalledTimes(2);
  send.mockResolvedValue({ dropped: 3 });
  await d.settle();
  expect(send).toHaveBeenCalledTimes(3);
  await d.settle();
  expect(send).toHaveBeenCalledTimes(3);
});

test("settle with nothing to drop asks nothing", async () => {
  const send = jest.fn();
  await createDropper(send).settle();
  expect(send).not.toHaveBeenCalled();
});

test("a refused drop (404, 409) is final and the turn goes", async () => {
  for (const status of [404, 409]) {
    const send = jest.fn().mockRejectedValue(answer(status));
    const d = createDropper(send);
    d.drop(3);
    await d.settle();
    expect(send).toHaveBeenCalledTimes(1);
    await d.settle();
    expect(send).toHaveBeenCalledTimes(1);
  }
});

test("a server error (500, 503) is not a refusal: retried, then thrown", async () => {
  for (const status of [500, 503]) {
    const send = jest.fn().mockRejectedValue(answer(status));
    const d = createDropper(send);
    d.drop(3);
    await expect(d.settle()).rejects.toMatchObject({ status });
    expect(send).toHaveBeenCalledTimes(2);
    send.mockResolvedValue({ dropped: 3 });
    await d.settle(); // still open: sent again
    expect(send).toHaveBeenCalledTimes(3);
  }
});

test("an ApiError with no status other than offline is retried too", async () => {
  const send = jest.fn().mockRejectedValue(new ApiError("unknown"));
  const d = createDropper(send);
  d.drop(3);
  await expect(d.settle()).rejects.toBeInstanceOf(ApiError);
  expect(send).toHaveBeenCalledTimes(2);
});

test("a refusal on the retry is final too", async () => {
  const send = jest.fn().mockRejectedValueOnce(offline()).mockRejectedValue(answer(404));
  const d = createDropper(send);
  d.drop(3);
  await d.settle();
  expect(send).toHaveBeenCalledTimes(2);
  await d.settle();
  expect(send).toHaveBeenCalledTimes(2);
});

test("the same line dropped twice sends one request", async () => {
  const send = jest.fn().mockResolvedValue({ dropped: 3 });
  const d = createDropper(send);
  d.drop(3);
  d.drop(3);
  await d.settle();
  expect(send).toHaveBeenCalledTimes(1);
});

test("two settles at once re-send a failed drop once", async () => {
  const send = jest.fn().mockRejectedValueOnce(offline()).mockResolvedValue({ dropped: 3 });
  const d = createDropper(send);
  d.drop(3);
  await Promise.all([d.settle(), d.settle()]);
  expect(send).toHaveBeenCalledTimes(2);
});

// [R0, T1, R2, T3, R4]: ↻ on T3, 「취소」, ↻ on T1. The drop of 1 must reach the Mac after the drop of 3, or it is
// refused (409 not_last) and the retried drop of 3 leaves T1 and R2 live on the Mac.
test("a drop queued behind a pending one is not sent until the earlier resolves", async () => {
  let release!: () => void;
  const send = jest
    .fn()
    .mockImplementationOnce(() => new Promise<void>((r) => (release = r)))
    .mockResolvedValue({ dropped: 1 });
  const d = createDropper(send);
  d.drop(3);
  d.drop(1);
  await flush();
  expect(send.mock.calls).toEqual([[3]]);
  release();
  await flush();
  expect(send.mock.calls).toEqual([[3], [1]]);
  await d.settle();
  expect(send).toHaveBeenCalledTimes(2);
});

test("a drop queued behind one that failed offline is not sent; settle sends them in order", async () => {
  const send = jest.fn().mockRejectedValueOnce(offline()).mockResolvedValue({});
  const d = createDropper(send);
  d.drop(3);
  d.drop(1);
  await flush();
  expect(send.mock.calls).toEqual([[3]]); // 1 waits for 3, which did not reach the Mac
  await d.settle();
  expect(send.mock.calls).toEqual([[3], [3], [1]]);
  await d.settle(); // both settled
  expect(send).toHaveBeenCalledTimes(3);
});

test("when the earlier drop's retry fails the later one is not sent, and both go in order next time", async () => {
  const send = jest.fn().mockRejectedValue(offline());
  const d = createDropper(send);
  d.drop(3);
  d.drop(1);
  await expect(d.settle()).rejects.toBeInstanceOf(ApiError);
  expect(send.mock.calls).toEqual([[3], [3]]);
  send.mockResolvedValue({});
  await d.settle();
  expect(send.mock.calls).toEqual([[3], [3], [3], [1]]);
});

test("a drop queued behind a refused one is sent", async () => {
  const send = jest.fn().mockRejectedValueOnce(answer(409)).mockResolvedValue({});
  const d = createDropper(send);
  d.drop(3);
  d.drop(1);
  await d.settle();
  expect(send.mock.calls).toEqual([[3], [1]]);
});

test("a drop made while settling is settled by the same settle, after the earlier", async () => {
  let release!: () => void;
  const send = jest
    .fn()
    .mockRejectedValueOnce(offline())
    .mockImplementationOnce(() => new Promise<void>((r) => (release = r)))
    .mockResolvedValue({});
  const d = createDropper(send);
  d.drop(3);
  let done = false;
  const p = d.settle().then(() => (done = true));
  await flush(); // the retry of 3 is on its way
  d.drop(1);
  await flush();
  expect(send.mock.calls).toEqual([[3], [3]]);
  release();
  await p;
  expect(done).toBe(true);
  expect(send.mock.calls).toEqual([[3], [3], [1]]);
});
