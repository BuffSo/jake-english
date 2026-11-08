import * as fs from "fs";
import * as path from "path";

import { NdjsonSplitter } from "./ndjson";
import {
  EVENT_TYPES,
  HEARD_TRY_KEYS,
  ISSUE_KEYS,
  LINE_KEYS,
  PAST_KEYS,
  PICK_KEYS,
  RESUME_KEYS,
  ROLEPLAY_KEYS,
  SAVED_KEYS,
  SUMMARY_KEYS,
  SYLLABLE_KEYS,
  TOPIC_KEYS,
  TRANSCRIPT_KEYS,
  TRY_KEYS,
} from "./types";
import roleplay from "../../../contract/roleplay.json";
import lineUser from "../../../contract/line-user.json";
import summary from "../../../contract/summary.json";
import past from "../../../contract/past.json";
import saved from "../../../contract/saved.json";
import homeTopics from "../../../contract/home-topics.json";
import resume from "../../../contract/resume.json";

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
    expect(sorted(Object.keys(l))).toEqual(sorted(TRANSCRIPT_KEYS));
    expect(sorted(Object.keys(l.line))).toEqual(sorted(LINE_KEYS));
    for (const t of l.tries) {
      expect(sorted(Object.keys(t))).toEqual(sorted(TRY_KEYS));
      for (const i of t.issues) expect(sorted(Object.keys(i))).toEqual(sorted(ISSUE_KEYS));
    }
  }
});

test("past and saved examples have the keys the review screens read", () => {
  for (const i of past.items) expect(sorted(Object.keys(i))).toEqual(sorted(PAST_KEYS));
  for (const i of saved.items) expect(sorted(Object.keys(i))).toEqual(sorted(SAVED_KEYS));
});

test("home topics example has the keys the situation screen reads", () => {
  for (const t of homeTopics.topics) {
    expect(sorted(Object.keys(t))).toEqual(sorted(TOPIC_KEYS));
    for (const p of t.picks) expect(sorted(Object.keys(p))).toEqual(sorted(PICK_KEYS));
  }
});

test("resume example has the keys the situation screen reads", () => {
  expect(sorted(Object.keys(resume.resume))).toEqual(sorted(RESUME_KEYS));
  expect(sorted(Object.keys(resume.resume.roleplay))).toEqual(sorted(ROLEPLAY_KEYS));
  expect(resume.resume.said.length).toBeGreaterThan(0);
  for (const s of resume.resume.said) expect(sorted(Object.keys(s))).toEqual(sorted(HEARD_TRY_KEYS));
});
