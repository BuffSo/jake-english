// What was heard, drawn as one faded line until its bubble or row opens (spec heard-line-collapsed 1)
import { heardKey, heardView } from "./heardView";
import { keepWords } from "./keepWords";

test("no label, kept words", () => {
  expect(heardView("I'd like a cup of copy", false).text).toBe(keepWords("I'd like a cup of copy"));
  expect(heardView("커피 한 잔 주세요", true).text).toBe(keepWords("커피 한 잔 주세요"));
  expect(heardView("Hi there", false).text).not.toContain("들린 말");
});

test("folded is one line, open has no limit", () => {
  expect(heardView("Hi there", false).lines).toBe(1);
  expect(heardView("Hi there", true).lines).toBeUndefined();
});

// what was just heard opens by a tap and comes folded on the next try, even with the same words (final review)
test("each try has its own key, the words when the try is unknown", () => {
  const a = heardKey("Hi there", { rp_id: "r1", idx: 3, n: 1 });
  const b = heardKey("Hi there", { rp_id: "r1", idx: 3, n: 2 });
  expect(a).not.toBe(b);
  expect(heardKey("Hi there", null)).toBe("Hi there");
  expect(heardKey("Hi there", null)).not.toBe(heardKey("Hello", null));
});
