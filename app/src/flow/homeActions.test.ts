import type { Home } from "../api/types";
import { createHomeLoad, leaveHome } from "./homeActions";

const home = { lines: {}, images: {} } as unknown as Home;

test("leaving the first screen stops Ryan before the next screen opens", () => {
  // final review: the tip plays after the question, while the cards can be pressed; 「복습하기」 has no Ryan
  const calls: string[] = [];
  leaveHome({ clear: () => calls.push("clear") }, () => calls.push("go"));
  expect(calls).toEqual(["clear", "go"]);
});

test("a second retry while the first is asking the Mac sends no second /home", async () => {
  // final review: `/home?tip=1` now uses up the day's tip, so a double tap on 「다시 시도」 could lose it
  let answer: (h: Home) => void = () => {};
  const getHome = jest.fn(() => new Promise<Home>((r) => (answer = r)));
  const onHome = jest.fn();
  const load = createHomeLoad(getHome, onHome, jest.fn());
  const first = load();
  void load();
  expect(getHome).toHaveBeenCalledTimes(1);
  answer(home);
  await first;
  expect(onHome).toHaveBeenCalledTimes(1);
  expect(onHome).toHaveBeenCalledWith(home);
});

test("once the Mac has answered, a retry asks again", async () => {
  const getHome = jest.fn(async () => home);
  const load = createHomeLoad(getHome, jest.fn(), jest.fn());
  await load();
  await load();
  expect(getHome).toHaveBeenCalledTimes(2);
});

test("a failed /home goes to the error, not to the screen", async () => {
  const err = new Error("down");
  const onHome = jest.fn();
  const onError = jest.fn();
  await createHomeLoad(jest.fn(async () => Promise.reject(err)), onHome, onError)();
  expect(onHome).not.toHaveBeenCalled();
  expect(onError).toHaveBeenCalledWith(err);
});
