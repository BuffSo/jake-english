// What was heard, drawn as one faded line until its bubble or row opens (spec heard-line-collapsed 1)
import { heardView } from "./heardView";
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
