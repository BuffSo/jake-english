import { NdjsonSplitter } from "./ndjson";

test("splits lines across chunks", () => {
  const s = new NdjsonSplitter();
  expect(s.push('{"type":"heard","te')).toEqual([]);
  expect(s.push('xt":"hi","followed":true}\n{"type":"done"')).toEqual([{ type: "heard", text: "hi", followed: true }]);
  expect(s.push(',"next":2,"issues":0}\n')).toEqual([{ type: "done", next: 2, issues: 0 }]);
  expect(s.flush()).toEqual([]);
});

test("ignores blank lines and flushes a last line without newline", () => {
  const s = new NdjsonSplitter();
  expect(s.push("\n\n")).toEqual([]);
  expect(s.push('{"type":"done","next":1,"issues":0}')).toEqual([]);
  expect(s.flush()).toEqual([{ type: "done", next: 1, issues: 0 }]);
});
