import { ApiError } from "../api/client";
import { createDropper } from "./talkDrop";

const offline = () => new ApiError("offline");

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

test("a refused drop is final and the turn goes", async () => {
  for (const code of ["not_found", "unknown"] as const) {
    const send = jest.fn().mockRejectedValue(new ApiError(code));
    const d = createDropper(send);
    d.drop(3);
    await d.settle();
    expect(send).toHaveBeenCalledTimes(1);
    await d.settle();
    expect(send).toHaveBeenCalledTimes(1);
  }
});

test("a refusal on the retry is final too", async () => {
  const send = jest.fn().mockRejectedValueOnce(offline()).mockRejectedValue(new ApiError("not_found"));
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
