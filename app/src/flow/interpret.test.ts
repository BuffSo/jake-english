import type { ScriptLine } from "../api/types";
import { koOf, koView, mayAutoPlay, mayReplay } from "./interpret";
import type { Phase } from "./state";

const ko = { text: "뭐 드릴까요?", audio: null };
const PHASES: Phase[] = ["loading", "ryan", "ready", "recording", "evaluating", "evaluated", "error"];

test("a failed interpretation says so, open or closed, so a tap tries again", () => {
  expect([koView("failed", true), koView("failed", false)]).toEqual(["failed", "failed"]);
});

test("closed shows only the button; open shows the line, or that Sohee is on it", () => {
  expect([koView(ko, false), koView(undefined, false), koView("loading", false)]).toEqual(["closed", "closed", "closed"]);
  expect([koView(undefined, true), koView("loading", true), koView(ko, true)]).toEqual(["loading", "loading", "open"]);
});

test("a line the server already interpreted needs no call", () => {
  const line = { idx: 0, speaker: "ryan", text: "What can I get you?", kind: "script", three: null, audio: null } as const;
  expect(koOf({ ...line, ko: "뭐 드릴까요?", ko_audio: "a".repeat(64) } as ScriptLine)).toEqual({ text: "뭐 드릴까요?", audio: "a".repeat(64) });
  expect(koOf({ ...line, ko: null, ko_audio: null } as ScriptLine)).toBeUndefined();
  expect(koOf(undefined)).toBeUndefined();
});

test("in the roleplay Sohee plays by herself only while my turn waits in quiet", () => {
  // never into a recording, never over Ryan, his feedback or the model (spec korean-translation 2)
  expect(PHASES.filter((p) => mayAutoPlay("roleplay", p, false))).toEqual(["ready", "evaluated"]);
  expect(PHASES.filter((p) => mayAutoPlay("roleplay", p, true))).toEqual([]);
});

test("a tap on Sohee's line replays it while my turn waits, like 다시 듣기", () => {
  expect(PHASES.filter((p) => mayReplay("roleplay", p))).toEqual(["ready", "evaluated"]);
});

test("on the end screen she always plays, stopping what played before", () => {
  expect(PHASES.every((p) => mayAutoPlay("end", p, true) && mayReplay("end", p))).toBe(true);
});
