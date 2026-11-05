import lineUser from "../../../contract/line-user.json";
import type { ThreeLine } from "../api/types";
import { notesView } from "./notesView";

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
