import { framesFor, waiterOf } from "./thinking";

const thinking = { jake: ["/assets/jake-thinking-1.png", "/assets/jake-thinking-2.png"], ryan: ["/r1.png", "/r2.png"] };

test("the person named in the waiting text thinks, Ryan otherwise", () => {
  expect(waiterOf("제이크가 상황을 고르고 있어요")).toBe("jake");
  expect(waiterOf("라이언이 대본을 만들고 있어요")).toBe("ryan");
  expect(waiterOf("받아쓰고 있어요")).toBe("ryan");
  expect(waiterOf("다음 대사를 준비하고 있어요")).toBe("ryan");
  expect(waiterOf("")).toBe("ryan");
});

test("frames come from /home for that person", () => {
  expect(framesFor(thinking, "jake")).toEqual(["/assets/jake-thinking-1.png", "/assets/jake-thinking-2.png"]);
  expect(framesFor(thinking, "ryan")).toEqual(["/r1.png", "/r2.png"]);
});

test("no frames before /home or from an older server", () => {
  expect(framesFor(null, "jake")).toEqual([]);
  expect(framesFor(undefined, "ryan")).toEqual([]);
  expect(framesFor({ ryan: ["/r1.png"] } as never, "jake")).toEqual([]);
});

test("Sohee's frames, none from an older server", () => {
  expect(framesFor({ ...thinking, sohee: ["/s1.png"] }, "sohee")).toEqual(["/s1.png"]);
  expect(framesFor(thinking, "sohee")).toEqual([]);
});
