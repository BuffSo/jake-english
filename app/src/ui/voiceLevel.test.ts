// The thin voice line in 「● 말하기 끝」 grows with the mic level (spec record-feedback 2).
import { LINE_FLOOR_DB, LINE_MIN, LINE_TOP_DB, voiceShare } from "./voiceLevel";

test("quiet and no reading draw the shortest line", () => {
  expect(voiceShare(LINE_FLOOR_DB - 30)).toBe(LINE_MIN);
  expect(voiceShare(LINE_FLOOR_DB)).toBe(LINE_MIN);
  expect(voiceShare(undefined)).toBe(LINE_MIN);
  expect(voiceShare(-160)).toBe(LINE_MIN);
});

test("loud draws the whole line", () => {
  expect(voiceShare(LINE_TOP_DB)).toBe(1);
  expect(voiceShare(0)).toBe(1);
});

test("in between grows with the level", () => {
  const mid = voiceShare((LINE_FLOOR_DB + LINE_TOP_DB) / 2);
  expect(mid).toBeGreaterThan(LINE_MIN);
  expect(mid).toBeLessThan(1);
  expect(voiceShare(LINE_TOP_DB - 1)).toBeGreaterThan(mid);
});
