import { keepWords } from "./keepWords";

const WJ = "\u2060";

test("Korean breaks only between words", () => {
  expect(keepWords("반가워요")).toBe(`반${WJ}가${WJ}워${WJ}요`);
  // the joiner is written as an escape; if it ever became an empty string these would still match, the length not
  expect(keepWords("반가워요")).toHaveLength(7);
  expect(keepWords("오늘도 만나서")).toBe(`오${WJ}늘${WJ}도 만${WJ}나${WJ}서`);
});

test("text without Hangul stays as it is", () => {
  expect(keepWords("Could I get a latte?")).toBe("Could I get a latte?");
});

test("a word mixing Hangul with signs or digits is joined only between Hangul letters", () => {
  // 「반가워요.」 keeps its period free to stay with the word; 「11월」 is a number and a letter
  expect(keepWords("반가워요.")).toBe(`반${WJ}가${WJ}워${WJ}요.`);
  expect(keepWords("11월 7일")).toBe("11월 7일");
});
