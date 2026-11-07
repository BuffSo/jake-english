import { keepPieces, keepWords } from "./keepWords";

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

test("a Korean word stays whole with the digits, letters and signs on it", () => {
  // 「11월」 and 「7일에」 broke after the digit; Ryan's notes have 「coffee를」 and 「「coffee」를」 (todo 12-2, 3)
  expect(keepWords("11월 7일에")).toBe(`11${WJ}월 7${WJ}일${WJ}에`);
  expect(keepWords("2026")).toBe("2026"); // no Hangul: nothing to keep
  expect(keepWords("coffee를 세게")).toBe(`coffee${WJ}를 세${WJ}게`);
  expect(keepWords("「coffee」를")).toBe(`「coffee」${WJ}를`);
  expect(keepWords("연습(4)")).toBe(`연${WJ}습${WJ}(4)`);
  expect(keepWords("반가워요.")).toBe(`반${WJ}가${WJ}워${WJ}요${WJ}.`);
});

test("keepWords twice is keepWords once", () => {
  const once = keepWords("11월 7일에 모음 · coffee를");
  expect(keepWords(once)).toBe(once);
});

test("an emoji next to Hangul stays whole", () => {
  expect(keepWords("💬💬")).toBe("💬💬");
  expect(keepWords("💬대화")).toBe(`💬${WJ}대${WJ}화`);
});

test("pieces of one word in different styles stay one word", () => {
  expect(keepPieces(["스", "테", "이션"])).toEqual([`스${WJ}`, `테${WJ}`, `이${WJ}션`]);
  expect(keepPieces(["cof", "fee."])).toEqual(["cof", "fee."]);
  const parts = ["아잇 ", "라", "이커"];
  expect(keepPieces(parts).join("")).toBe(keepWords(parts.join("")));
});
