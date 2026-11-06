import { SPEAKERS } from "./speakers";

test("the line I am to say is on the right, named as my turn", () => {
  // on the phone the learner read Ryan's line: nothing said whose line was whose (2026-11-06)
  expect(SPEAKERS.now).toEqual({ name: "내 차례", side: "right" });
  expect(SPEAKERS.mine).toEqual({ name: "나", side: "right" });
});

test("Ryan, his feedback and Jake are on the left, each with a name", () => {
  expect(SPEAKERS.ryan).toEqual({ name: "라이언", side: "left" });
  expect(SPEAKERS.feedback).toEqual({ name: "라이언", side: "left" });
  expect(SPEAKERS.jake).toEqual({ name: "제이크", side: "left" });
});
