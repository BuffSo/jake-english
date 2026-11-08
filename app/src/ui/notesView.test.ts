import lineUser from "../../../contract/line-user.json";
import type { ScriptLine, ThreeLine } from "../api/types";
import { lineNotes, needsNotes, notesView } from "./notesView";

const three = lineUser.three as ThreeLine;

test("closed notes show the plain line with a button", () => {
  expect([notesView(three, false), notesView("loading", false)]).toEqual(["closed", "closed"]);
});

test("open notes show the three lines, or that they are being made", () => {
  expect([notesView(three, true), notesView("loading", true)]).toEqual(["open", "loading"]);
});

test("a line without notes shows only the plain text", () => {
  // the notes could not be made: the line and the mic still work (spec roleplay-practice 8)
  expect([notesView(null, false), notesView(null, true)]).toEqual(["plain", "plain"]);
});

// spec dont-wait-for-line-notes 2: the learner's line comes before its notes; the screen fetches them
const line = { ...(lineUser as unknown as ScriptLine), three: null };
const withNotes = { ...line, three };

test("the line's own notes come first, then the fetched ones", () => {
  expect(lineNotes(withNotes, undefined)).toBe(three);
  expect(lineNotes(line, three)).toBe(three);
  expect(lineNotes(line, "loading")).toBe("loading");
  expect(lineNotes(line, undefined)).toBeNull();
});

test("notes being fetched still show the button, closed", () => {
  expect(notesView(lineNotes(line, "loading"), false)).toBe("closed");
});

test("the notes are fetched only when the line has none and none were asked for", () => {
  expect(needsNotes(line, undefined)).toBe(true);
  expect([needsNotes(withNotes, undefined), needsNotes(line, "loading"), needsNotes(line, three)]).toEqual([
    false,
    false,
    false,
  ]);
});
