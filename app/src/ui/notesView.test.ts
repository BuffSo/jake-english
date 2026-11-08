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
  expect(lineNotes(withNotes, undefined, false)).toBe(three);
  expect(lineNotes(line, three, false)).toBe(three);
  expect(lineNotes(line, "loading", false)).toBe("loading");
});

// todo line-notes minors 3: the first frame of a line comes before the fetch starts, and a failed fetch is not tried
// again on every 「다시 해 보기」, so the button neither appears a frame late nor blinks
test("notes not asked for yet count as on their way; notes that could not be fetched leave the plain line", () => {
  expect(lineNotes(line, undefined, false)).toBe("loading");
  expect(notesView(lineNotes(line, undefined, false), false)).toBe("closed");
  expect(lineNotes(line, undefined, true)).toBeNull();
  expect(lineNotes(withNotes, undefined, true)).toBe(three);
});

test("notes being fetched still show the button, closed", () => {
  expect(notesView(lineNotes(line, "loading", false), false)).toBe("closed");
});

test("the notes are fetched only when the line has none, none were asked for and none failed", () => {
  expect(needsNotes(line, undefined, false)).toBe(true);
  expect([
    needsNotes(withNotes, undefined, false),
    needsNotes(line, "loading", false),
    needsNotes(line, three, false),
    needsNotes(line, undefined, true),
  ]).toEqual([false, false, false, false]);
});
