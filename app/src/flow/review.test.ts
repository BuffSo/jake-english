import keys from "../../../contract/sentence-keys.json";
import { sentenceKey } from "./review";

test("sentence keys match the contract", () => {
  for (const [text, key] of keys as [string, string][]) expect(sentenceKey(text)).toBe(key);
});

import type { TranscriptLine, Try } from "../api/types";
import { comparePair, dayKo, toggleRow } from "./review";

test("dayKo reads a date or a time", () => {
  expect(dayKo("2026-11-05")).toBe("11월 5일");
  expect(dayKo("2026-01-17T10:00:00")).toBe("1월 17일");
});

test("toggleRow opens one row at a time", () => {
  expect(toggleRow(null, "3")).toBe("3");
  expect(toggleRow("3", "5")).toBe("5");
  expect(toggleRow("5", "5")).toBeNull();
});

describe("comparePair", () => {
  const tryOf = (n: number, followed: boolean): Try => ({ n, mode: "turn", heard: "x", followed, issues: [], point_ko: "" });
  const lineWith = (tries: Try[], first: TranscriptLine["first"]) =>
    ({ line: { idx: 3 }, tries, first }) as unknown as TranscriptLine;
  const first = { rp_id: "aaaaaaaaaaaa", idx: 3, n: 1 };

  test("no first recording, no pair", () => {
    expect(comparePair("bbbbbbbbbbbb", lineWith([tryOf(1, true)], null))).toBeNull();
  });

  test("then is this run's last followed try", () => {
    expect(comparePair("bbbbbbbbbbbb", lineWith([tryOf(1, true), tryOf(2, false)], first))).toEqual({
      first,
      then: { rp_id: "bbbbbbbbbbbb", idx: 3, n: 1 },
    });
  });

  test("nothing followed in this run: the first recording alone", () => {
    expect(comparePair("bbbbbbbbbbbb", lineWith([tryOf(1, false)], first))).toEqual({ first, then: null });
  });
});
