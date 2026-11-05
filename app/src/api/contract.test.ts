import * as fs from "fs";
import * as path from "path";

import { NdjsonSplitter } from "./ndjson";
import { EVENT_TYPES, LINE_KEYS, ROLEPLAY_KEYS, SUMMARY_KEYS, SYLLABLE_KEYS, TRY_KEYS } from "./types";
import roleplay from "../../../contract/roleplay.json";
import lineUser from "../../../contract/line-user.json";
import summary from "../../../contract/summary.json";

const sorted = (a: readonly string[]) => [...a].sort();

test("roleplay example has the keys the app reads", () => {
  expect(sorted(Object.keys(roleplay))).toEqual(sorted(ROLEPLAY_KEYS));
  for (const l of roleplay.lines) expect(sorted(Object.keys(l))).toEqual(sorted(LINE_KEYS));
});

test("user line example has three lines with syllable keys", () => {
  expect(sorted(Object.keys(lineUser))).toEqual(sorted(LINE_KEYS));
  for (const w of lineUser.three.words) for (const s of w.syl) expect(sorted(Object.keys(s))).toEqual(sorted(SYLLABLE_KEYS));
});

test("every example event type is known", () => {
  const text = fs.readFileSync(path.join(__dirname, "../../../contract/attempt-events.ndjson"), "utf8");
  const events = new NdjsonSplitter().push(text) as { type: string }[];
  expect(events.length).toBeGreaterThan(3);
  for (const e of events) expect(EVENT_TYPES).toContain(e.type);
});

test("summary example has the keys the end screen reads", () => {
  expect(sorted(Object.keys(summary))).toEqual(sorted(SUMMARY_KEYS));
  for (const l of summary.lines) {
    expect(sorted(Object.keys(l.line))).toEqual(sorted(LINE_KEYS));
    for (const t of l.tries) expect(sorted(Object.keys(t))).toEqual(sorted(TRY_KEYS));
  }
});
