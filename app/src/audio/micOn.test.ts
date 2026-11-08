import { turnMicOn } from "./micOn";

// the steps `useRecorder.start` takes, each one recorded in order
function steps(over: Partial<Parameters<typeof turnMicOn>[0]> = {}) {
  const done: string[] = [];
  return {
    done,
    steps: {
      permit: async () => (done.push("permit"), true),
      prepare: async () => void done.push("prepare"),
      cue: async (c: "start" | "cancel") => void done.push(`cue:${c}`),
      record: () => void done.push("record"),
      ...over,
    },
  };
}

test("the mic comes on after the start cue", async () => {
  const { done, steps: s } = steps();
  await turnMicOn(s);
  expect(done).toEqual(["permit", "prepare", "cue:start", "record"]);
});

// todo 20261108_34 1: the start cue said 「recording」, so a mic that then does not come on says so with the cancel cue
test("a mic that fails after the start cue plays the cancel cue and fails", async () => {
  const { done, steps: s } = steps({
    record: () => {
      done.push("record");
      throw new Error("busy");
    },
  });
  await expect(turnMicOn(s)).rejects.toThrow("busy");
  expect(done).toEqual(["permit", "prepare", "cue:start", "record", "cue:cancel"]);
});

// spec record-feedback 1: no cue when the mic could not be readied; the error line on screen tells it
test("no permission: no cue, no recording", async () => {
  const { done, steps: s } = steps({ permit: async () => (done.push("permit"), false) });
  await expect(turnMicOn(s)).rejects.toThrow("mic");
  expect(done).toEqual(["permit"]);
});

test("a failed preparation plays no cue", async () => {
  const { done, steps: s } = steps({
    prepare: async () => {
      done.push("prepare");
      throw new Error("prepare");
    },
  });
  await expect(turnMicOn(s)).rejects.toThrow("prepare");
  expect(done).toEqual(["permit", "prepare"]);
});
