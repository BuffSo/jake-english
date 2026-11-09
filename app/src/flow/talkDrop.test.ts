import { createDropper } from "./talkDrop";

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
  const send = jest.fn().mockRejectedValueOnce(new Error("net")).mockResolvedValue({ dropped: 3 });
  const d = createDropper(send);
  d.drop(3);
  await d.settle();
  expect(send).toHaveBeenCalledTimes(2);
  await d.settle(); // cleared
  expect(send).toHaveBeenCalledTimes(2);
});

test("settle throws when the retry fails and tries again next time", async () => {
  const send = jest.fn().mockRejectedValue(new Error("net"));
  const d = createDropper(send);
  d.drop(3);
  await expect(d.settle()).rejects.toThrow("net");
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
