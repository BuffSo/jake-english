import { circleFace } from "./faces";

test("Jake's face while his suggestion waits for the learner's pick", () => {
  expect(circleFace("confirm", "listening", true)).toBe("jake");
});

test("Ryan's listening face when Ryan asks or waits for the situation", () => {
  expect(circleFace("input", "jake", true)).toBe("listening");
  expect(circleFace("askRecommend", "listening", true)).toBe("listening");
});

test("Ryan stays when Jake's picture is missing or failed to load", () => {
  expect(circleFace("confirm", "listening", false)).toBe("listening");
});

test("a wait keeps the face it started with until the thinking face takes over", () => {
  // 「이걸로 할게요」 or 「다른 걸로요」: Jake's face must not turn into Ryan's for the first moment of the wait
  expect(circleFace("working", "jake", true)).toBe("jake");
  expect(circleFace("working", "listening", true)).toBe("listening");
});
