import type { SavedItem } from "../api/types";
import { createSavedStore } from "./savedStore";

const item = (text: string, key: string): SavedItem => ({
  key,
  rp_id: "aaaaaaaaaaaa",
  idx: 1,
  speaker: "user",
  text,
  title_ko: "카페에서 주문하기",
  at: "2026-11-07T10:00:00",
});

function setup(listed: SavedItem[] = []) {
  let stored = listed;
  let release: () => void = () => {};
  const set = jest.fn(
    (_rp: string, _idx: number, on: boolean) =>
      new Promise<void>((resolve) => {
        release = () => {
          stored = on ? [item("Sure.", "sure")] : [];
          resolve();
        };
      }),
  );
  const onFail = jest.fn();
  const store = createSavedStore({ list: async () => stored, set, onFail, changed: () => {} });
  return { store, set, onFail, release: () => release() };
}

test("pendingKeys: a second tap on the same sentence waits for the first", async () => {
  const { store, set, release } = setup();
  const first = store.toggle("aaaaaaaaaaaa", 1, "Sure.");
  expect(store.pending("sure!")).toBe(true);
  await store.toggle("aaaaaaaaaaaa", 1, "Sure.");
  expect(set).toHaveBeenCalledTimes(1);
  release();
  await first;
  expect(store.pending("Sure.")).toBe(false);
});

test("a saved sentence shows as saved, by its sentence key", async () => {
  const { store, release } = setup();
  const done = store.toggle("aaaaaaaaaaaa", 1, "Sure.");
  release();
  await done;
  expect(store.has("sure")).toBe(true);
  expect(store.items()).toEqual([item("Sure.", "sure")]);
});

test("a failed save changes nothing and says so once", async () => {
  const set = jest.fn(async () => {
    throw new Error("offline");
  });
  const onFail = jest.fn();
  const store = createSavedStore({ list: async () => [], set, onFail, changed: () => {} });
  await store.refresh();
  await store.toggle("aaaaaaaaaaaa", 1, "Sure.");
  expect(store.has("Sure.")).toBe(false);
  expect(onFail).toHaveBeenCalledTimes(1);
});

test("unsaving a saved sentence turns it off", async () => {
  const { store, set, release } = setup([item("Sure.", "sure")]);
  await store.refresh();
  const done = store.toggle("aaaaaaaaaaaa", 1, "SURE!");
  expect(set).toHaveBeenCalledWith("aaaaaaaaaaaa", 1, false);
  release();
  await done;
  expect(store.has("Sure.")).toBe(false);
});

test("a list that could not be loaded says so until it loads", async () => {
  let fail = true;
  const store = createSavedStore({
    list: async () => {
      if (fail) throw new Error("offline");
      return [];
    },
    set: async () => {},
    onFail: () => {},
    changed: () => {},
  });
  await store.refresh();
  expect(store.items()).toBeNull();
  expect(store.lastError()).toBeInstanceOf(Error);
  fail = false;
  await store.refresh();
  expect(store.lastError()).toBeNull();
  expect(store.items()).toEqual([]);
});

// The Mac took the change but the list could not be loaded again: the row must go, and a second 「빼기」 must not
// save it back (todo 12-1)
function failingAfterFirstList() {
  let calls = 0;
  const set = jest.fn(async (_rp: string, _idx: number, _on: boolean) => {});
  const store = createSavedStore({
    list: async () => {
      calls += 1;
      if (calls > 1) throw new Error("offline");
      return [item("Sure.", "sure")];
    },
    set,
    onFail: () => {},
    changed: () => {},
  });
  return { store, set };
}

test("removing takes a sentence off the list at once, even when the list cannot be loaded again", async () => {
  const { store, set } = failingAfterFirstList();
  await store.refresh();
  await store.remove("aaaaaaaaaaaa", 1, "Sure.");
  expect(set).toHaveBeenCalledWith("aaaaaaaaaaaa", 1, false);
  expect(store.items()).toEqual([]);
  expect(store.has("Sure.")).toBe(false);
});

test("remove never saves: a sentence already out is sent out again", async () => {
  const set = jest.fn(async (_rp: string, _idx: number, _on: boolean) => {});
  const store = createSavedStore({ list: async () => [], set, onFail: () => {}, changed: () => {} });
  await store.refresh();
  await store.remove("aaaaaaaaaaaa", 1, "Sure.");
  expect(set).toHaveBeenCalledWith("aaaaaaaaaaaa", 1, false);
});

test("unsaving with toggle also takes it off the list when the list cannot be loaded again", async () => {
  const { store } = failingAfterFirstList();
  await store.refresh();
  await store.toggle("aaaaaaaaaaaa", 1, "Sure.");
  expect(store.items()).toEqual([]);
});
