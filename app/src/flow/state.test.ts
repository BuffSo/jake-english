import roleplayJson from "../../../contract/roleplay.json";
import type { Roleplay, ScriptLine } from "../api/types";
import { initial, reduce, type State } from "./state";

const rp = roleplayJson as unknown as Roleplay;
const userLine = rp.lines[1] as ScriptLine;
const ryanLine = rp.lines[0] as ScriptLine;

function at(phase: State["phase"], extra: Partial<State> = {}): State {
  const s = reduce(reduce(initial, { type: "created", roleplay: rp }), { type: "lineLoaded", line: userLine });
  return { ...s, idx: 1, phase, ...extra };
}

test("created starts the roleplay at line 0", () => {
  const s = reduce(initial, { type: "created", roleplay: rp });
  expect(s.screen).toBe("roleplay");
  expect(s.idx).toBe(0);
  expect(s.phase).toBe("loading");
});

test("ryan line plays, then moves to the next line", () => {
  let s = reduce(reduce(initial, { type: "created", roleplay: rp }), { type: "lineLoaded", line: ryanLine });
  expect(s.phase).toBe("ryan");
  s = reduce(s, { type: "ryanDone" });
  expect(s.idx).toBe(1);
  expect(s.phase).toBe("loading");
  expect(s.history.at(-1)).toEqual({ kind: "ryan", text: ryanLine.text, idx: 0 });
});

test("record is ignored while evaluating", () => {
  const s = at("evaluating");
  expect(reduce(s, { type: "recordStart" })).toBe(s);
});

test("next is ignored until evaluation is done", () => {
  const s = at("evaluating");
  expect(reduce(s, { type: "next" })).toBe(s);
});

test("done event marks evaluated and keeps the server's next index", () => {
  let s = at("evaluating");
  s = reduce(s, { type: "event", e: { type: "heard", text: "I'd like a cup of copy", followed: true } });
  s = reduce(s, { type: "event", e: { type: "text", delta: "좋아요. " } });
  s = reduce(s, { type: "event", e: { type: "text", delta: "다음으로 가요." } });
  s = reduce(s, { type: "event", e: { type: "done", next: 5, issues: 1 } });
  expect(s.phase).toBe("evaluated");
  expect(s.nextIdx).toBe(5);
  expect(s.feedback).toBe("좋아요. 다음으로 가요.");
  s = reduce(s, { type: "next" });
  expect(s.idx).toBe(5);
  expect(s.phase).toBe("loading");
  expect(s.history.map((b) => b.kind)).toEqual(["user", "feedback"]);
});

test("no_speech returns to ready with Ryan's words", () => {
  const say = { text: "잘 안 들렸어요.", audio: "d".repeat(64) };
  const s = reduce(at("evaluating"), { type: "event", e: { type: "error", code: "no_speech", say } });
  expect(s.phase).toBe("ready");
  expect(s.message).toBe("잘 안 들렸어요.");
});

test("a reply line is shown and next skips past it", () => {
  const reply: ScriptLine = { idx: 2, speaker: "ryan", text: "No worries!", kind: "reply", three: null, audio: "f".repeat(64) };
  let s = at("evaluating");
  s = reduce(s, { type: "event", e: { type: "heard", text: "I don't know", followed: false } });
  s = reduce(s, { type: "event", e: { type: "reply", line: reply } });
  s = reduce(s, { type: "event", e: { type: "done", next: 3, issues: 0 } });
  s = reduce(s, { type: "next" });
  expect(s.idx).toBe(3);
  expect(s.history.at(-1)).toEqual({ kind: "ryan", text: "No worries!", idx: 2 });
});

test("again keeps the line and the earlier next index", () => {
  let s = reduce(at("evaluating"), { type: "event", e: { type: "done", next: 2, issues: 1 } });
  s = reduce(s, { type: "again" });
  expect(s.mode).toBe("retry");
  expect(s.phase).toBe("ready");
  s = reduce({ ...s, phase: "evaluating" }, { type: "event", e: { type: "done", next: 1, issues: 0 } });
  expect(s.nextIdx).toBe(2);
});

test("a missing line ends the roleplay", () => {
  expect(reduce(at("loading"), { type: "lineMissing" }).screen).toBe("end");
});

test("retry from end comes back to end", () => {
  let s = reduce({ ...at("loading"), screen: "end" }, { type: "retryFromEnd", idx: 1 });
  expect(s.screen).toBe("roleplay");
  expect(s.mode).toBe("retry");
  s = reduce(reduce(s, { type: "lineLoaded", line: userLine }), { type: "recordStart" });
  s = reduce(reduce(s, { type: "recordStop" }), { type: "event", e: { type: "done", next: 1, issues: 0 } });
  expect(reduce(s, { type: "next" }).screen).toBe("end");
});

test("offline error keeps the line and offers retry", () => {
  let s = reduce(at("evaluating"), { type: "failed", code: "offline" });
  expect(s.phase).toBe("error");
  expect(s.message).toBe("맥에 연결할 수 없어요. 맥과 인터넷 연결을 확인해 주세요.");
  s = reduce(s, { type: "retry" });
  expect(s.phase).toBe("ready");
  expect(s.idx).toBe(1);
});

test("loading error retries the load", () => {
  const s = reduce(reduce(at("loading"), { type: "failed", code: "offline" }), { type: "retry" });
  expect(s.phase).toBe("loading");
});

test("again after an off-script turn keeps Ryan's reply in the conversation", () => {
  // final review: 「다시 해 보기」 cleared the reply, so it never reached the bubbles
  const reply: ScriptLine = { idx: 2, speaker: "ryan", text: "No worries!", kind: "reply", three: null, audio: "f".repeat(64) };
  let s = at("evaluating");
  s = reduce(s, { type: "event", e: { type: "heard", text: "I don't know", followed: false } });
  s = reduce(s, { type: "event", e: { type: "reply", line: reply } });
  s = reduce(s, { type: "event", e: { type: "done", next: 3, issues: 0 } });
  s = reduce(s, { type: "again" });
  s = reduce(reduce(s, { type: "recordStart" }), { type: "recordStop" });
  s = reduce(s, { type: "event", e: { type: "heard", text: "I'd like a cup of coffee", followed: true } });
  s = reduce(s, { type: "event", e: { type: "done", next: 1, issues: 0 } });
  s = reduce(s, { type: "next" });
  expect(s.idx).toBe(3);
  expect(s.history.filter((b) => b.text === "No worries!")).toHaveLength(1);
  expect(s.history.map((b) => b.text)).toEqual(["I don't know", "No worries!", "I'd like a cup of coffee"]);
});

test("a late failure after leaving the roleplay is ignored", () => {
  // PR #12 review: an old attempt stream failing after 「처음으로」 put the next roleplay into the error state
  const home = reduce(at("evaluating"), { type: "home" });
  expect(reduce(home, { type: "failed", code: "offline" })).toBe(home);
  const ready = at("ready");
  expect(reduce(ready, { type: "failed", code: "offline" })).toBe(ready);
});
