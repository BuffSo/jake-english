import { TURNED_DOWN_MAX, turnDown } from "./turnedDown";

test("a turned-down suggestion is added at the end", () => {
  expect(turnDown(["A"], "B")).toEqual(["A", "B"]);
});

test("the same suggestion is kept once", () => {
  expect(turnDown(["A", "B"], "A")).toEqual(["B", "A"]);
});

test("only the last ones are kept, as many as the server takes", () => {
  let list: string[] = [];
  for (let i = 0; i < TURNED_DOWN_MAX + 3; i++) list = turnDown(list, `S${i}`);
  expect(TURNED_DOWN_MAX).toBe(10); // server/je_server/app.py `Recommend.skip` max_length
  expect(list).toHaveLength(TURNED_DOWN_MAX);
  expect(list[0]).toBe("S3");
  expect(list[TURNED_DOWN_MAX - 1]).toBe(`S${TURNED_DOWN_MAX + 2}`);
});
