import type { AttemptEvent, ScriptLine, TalkEnd } from "../api/types";
import endJson from "../../../contract/talk-end.json";
import { MIC_FAILED } from "./state";
import { canTry, fixCount, fixInitial, fixMessageIsError, fixReduce, isLastFix, nextLabel, soheeLine, type FixAction, type FixState } from "./talkFix";

const end = endJson as unknown as TalkEnd;
const item = end.items[0];
const two: TalkEnd = { say: null, items: [item, { ...item, line: { ...item.line, idx: 9 } }] };
const run = (s: FixState, ...as: FixAction[]) => as.reduce(fixReduce, s);
const loaded = (e: TalkEnd = end) => run(fixInitial("rp1", e), { type: "lineLoaded", line: e.items[0].line });
const ev = (s: FixState, e: AttemptEvent): FixAction => ({ type: "event", tries: s.tries, e });
const evaluating = (e: TalkEnd = end) => run(loaded(e), { type: "recordStart" }, { type: "recordStop" });

test("opens on the first fix and loads its line", () => {
  const s = fixInitial("rp1", end);
  expect(s).toMatchObject({ rpId: "rp1", at: 0, phase: "loading", line: null, tries: 0, heard: null, reading: false });
  expect(s.items).toBe(end.items);
  const l = fixReduce(s, { type: "lineLoaded", line: item.line });
  expect(l.phase).toBe("ready");
  expect(l.line).toBe(item.line);
  const f = fixReduce(s, { type: "lineFailed", message: "안 됐어요" });
  expect(f.phase).toBe("error");
  expect(fixReduce(f, { type: "retry" }).phase).toBe("loading");
});

test("the practice result shows below and can be tried again", () => {
  let s = run(loaded(), { type: "recordStart" });
  expect(s).toMatchObject({ phase: "recording", tries: 1 });
  s = run(s, { type: "recordStop" });
  expect(s.phase).toBe("evaluating");
  s = run(s, ev(s, { type: "heard", text: "yesterday I went", followed: true, n: 3 }), ev(s, { type: "text", delta: "Good. " }), ev(s, { type: "text", delta: "Nice." }));
  expect(s.heard).toBe("yesterday I went");
  expect(s.heardRec).toEqual({ rp_id: "rp1", idx: item.line.idx, n: 3 });
  expect(s.feedback).toBe("Good. Nice.");
  s = run(s, ev(s, { type: "done", next: 0, issues: 0 }));
  expect(s.phase).toBe("evaluated");
  const again = fixReduce(s, { type: "again" });
  expect(again).toMatchObject({ phase: "ready", heard: null, heardRec: null, feedback: "", tries: 1 });
  // a second try from the evaluated screen clears the old result
  const second = fixReduce(s, { type: "recordStart" });
  expect(second).toMatchObject({ phase: "recording", tries: 2, heard: null, heardRec: null, feedback: "" });
  // recording does not start from ready-less phases
  expect(fixReduce(evaluating(), { type: "recordStart" }).tries).toBe(1);
  expect(fixReduce(fixInitial("rp1", end), { type: "recordStart" }).phase).toBe("loading");
  expect(fixReduce(run(loaded(), { type: "recordStart" }), { type: "recordCancel" }).phase).toBe("ready");
  // no `n` means no recording to play back
  const noN = run(evaluating(), ev(evaluating(), { type: "heard", text: "x", followed: false }));
  expect(noN.heardRec).toBeNull();
});

test("late events of an earlier try are dropped", () => {
  const s = run(loaded(), { type: "recordStart" }, { type: "recordStop" });
  expect(fixReduce(s, { type: "event", tries: 0, e: { type: "text", delta: "old" } })).toBe(s);
  expect(fixReduce(s, { type: "failed", tries: 0, message: "x" })).toBe(s);
  const f = fixReduce(s, { type: "failed", tries: 1, message: "끊겼어요" });
  expect(f).toMatchObject({ phase: "error", message: "끊겼어요" });
  const e = fixReduce(s, ev(s, { type: "error", code: "claude_unavailable", say: null }));
  expect(e.phase).toBe("error");
});

test("no speech keeps the fix ready with the words", () => {
  const rec = run(loaded(), { type: "recordStart" });
  const ns = fixReduce(rec, { type: "noSpeech" });
  expect(ns.phase).toBe("ready");
  expect(ns.message).toBeTruthy();
  const s = evaluating();
  const a = fixReduce(s, ev(s, { type: "error", code: "no_speech", say: { text: "잘 안 들렸어요.", audio: "a".repeat(64) } }));
  expect(a).toMatchObject({ phase: "ready", message: "잘 안 들렸어요." });
  const b = fixReduce(s, ev(s, { type: "error", code: "too_long", say: null }));
  expect(b.phase).toBe("ready");
  expect(b.message).toBeTruthy();
});

test("next goes to the next fix and the last says 끝", () => {
  const s = loaded(two);
  expect(isLastFix(s)).toBe(false);
  expect(nextLabel(s)).toBe("다음 ›");
  const n = fixReduce(s, { type: "next" });
  expect(n).toMatchObject({ at: 1, phase: "loading", line: null, tries: 0, heard: null, feedback: "", reading: false });
  expect(isLastFix(n)).toBe(true);
  expect(nextLabel(n)).toBe("끝");
  expect(fixReduce(n, { type: "next" })).toBe(n);
  expect(nextLabel(loaded())).toBe("끝");
});

test("next does nothing while recording or evaluating", () => {
  const rec = run(loaded(two), { type: "recordStart" });
  expect(fixReduce(rec, { type: "next" })).toBe(rec);
  const ev2 = run(loaded(two), { type: "recordStart" }, { type: "recordStop" });
  expect(fixReduce(ev2, { type: "next" })).toBe(ev2);
});

test("fixCount is shown only for two or more", () => {
  expect(fixCount(loaded())).toBeNull();
  expect(fixCount(loaded(two))).toBe("1/2");
  expect(fixCount(fixReduce(loaded(two), { type: "next" }))).toBe("2/2");
});

test("toggleReading flips the reading", () => {
  const s = fixReduce(loaded(), { type: "toggleReading" });
  expect(s.reading).toBe(true);
  expect(fixReduce(s, { type: "toggleReading" }).reading).toBe(false);
});

test("retry after an error with the line loaded makes the fix ready again", () => {
  const s = evaluating();
  const e = fixReduce(s, ev(s, { type: "error", code: "claude_unavailable", say: null }));
  expect(e.phase).toBe("error");
  const r = fixReduce(e, { type: "retry" });
  expect(r).toMatchObject({ phase: "ready", message: null, heard: null, feedback: "", tries: 1 });
  expect(fixReduce(r, { type: "recordStart" }).tries).toBe(2);
  expect(fixReduce(r, { type: "retry" })).toBe(r);
});

test("a mic that did not start goes back to ready saying why, in red", () => {
  const rec = run(loaded(), { type: "recordStart" });
  const f = fixReduce(rec, { type: "micFailed" });
  expect(f).toMatchObject({ phase: "ready", message: MIC_FAILED, tries: 1 });
  expect(fixMessageIsError(f)).toBe(true);
  const ready = loaded();
  expect(fixReduce(ready, { type: "micFailed" })).toBe(ready);
});

test("only a failure or a mic that cannot be used is drawn as an error", () => {
  const ns = run(loaded(), { type: "recordStart" }, { type: "noSpeech" });
  expect(ns.message).toBeTruthy();
  expect(fixMessageIsError(ns)).toBe(false);
  expect(fixMessageIsError(run(fixInitial("rp1", end), { type: "lineFailed", message: "안 됐어요" }))).toBe(true);
  expect(fixMessageIsError(loaded())).toBe(false);
});

test("canTry: the mic starts only on a loaded fix that is ready or evaluated", () => {
  expect(canTry(fixInitial("rp1", end))).toBe(false);
  expect(canTry(loaded())).toBe(true);
  expect(canTry(run(loaded(), { type: "recordStart" }))).toBe(false);
  expect(canTry(evaluating())).toBe(false);
  const done = run(evaluating(), { type: "event", tries: 1, e: { type: "done", next: 0, issues: 0 } });
  expect(done.phase).toBe("evaluated");
  expect(canTry(done)).toBe(true);
  // an error before the line loaded has no line to try
  expect(canTry(run(fixInitial("rp1", end), { type: "lineFailed", message: "x" }))).toBe(false);
});

test("soheeLine counts the Sohee chances used, and is null for none or an older server", () => {
  expect(soheeLine({ ...end, sohee: 2 })).toBe("소희 찬스 2번 썼어요");
  expect(soheeLine({ ...end, sohee: 1 })).toBe("소희 찬스 1번 썼어요");
  expect(soheeLine({ ...end, sohee: 0 })).toBeNull();
  const { sohee: _, ...older } = { ...end, sohee: 3 };
  expect(soheeLine(older)).toBeNull();
});
