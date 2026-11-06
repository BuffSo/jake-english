import roleplayJson from "../../../contract/roleplay.json";
import type { Roleplay, ScriptLine } from "../api/types";
import { askFirst, canReplay, initial, leavesScreen, modelKey, practiceFor, reduce, type State } from "./state";

const rp = roleplayJson as unknown as Roleplay;
const userLine = rp.lines[1] as ScriptLine;
const ryanLine = rp.lines[0] as ScriptLine;
const situation = reduce(initial, { type: "chooseRoleplay" });

function at(phase: State["phase"], extra: Partial<State> = {}): State {
  const s = reduce(reduce(situation, { type: "created", roleplay: rp }), { type: "lineLoaded", line: userLine });
  return { ...s, idx: 1, phase, ...extra };
}

test("created starts the roleplay at line 0", () => {
  const s = reduce(situation, { type: "created", roleplay: rp });
  expect(s.screen).toBe("roleplay");
  expect(s.idx).toBe(0);
  expect(s.phase).toBe("loading");
});

test("ryan line plays, then moves to the next line", () => {
  let s = reduce(reduce(situation, { type: "created", roleplay: rp }), { type: "lineLoaded", line: ryanLine });
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
  const reply: ScriptLine = { idx: 2, speaker: "ryan", text: "No worries!", kind: "reply", three: null, audio: "f".repeat(64), ko: null, ko_audio: null };
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

test("one line from the end comes back to end", () => {
  let s = reduce({ ...at("loading"), screen: "end" }, { type: "startPractice", kind: "mine", order: [1] });
  expect(s.screen).toBe("roleplay");
  expect(s.mode).toBe("practice");
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
  const reply: ScriptLine = { idx: 2, speaker: "ryan", text: "No worries!", kind: "reply", three: null, audio: "f".repeat(64), ko: null, ko_audio: null };
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

const jake = { text: "카페에서 주문하는 상황으로 연습하고 싶어.", audio: "a".repeat(64) };

test("Jake's recommended situation stays with the roleplay", () => {
  // 2026-11-05 on the phone: after Ryan's first line the user wanted to hear Jake's line again
  let s = reduce(situation, { type: "created", roleplay: rp, jake });
  expect(s.jake).toEqual(jake);
  s = reduce(reduce(s, { type: "lineLoaded", line: ryanLine }), { type: "ryanDone" });
  s = reduce(s, { type: "lineMissing" });
  expect(s.jake).toEqual(jake);
  expect(reduce(s, { type: "home" }).jake).toBeNull();
});

test("a typed situation has no Jake line", () => {
  expect(reduce(situation, { type: "created", roleplay: rp }).jake).toBeNull();
});

test("Jake's line can be played again only while nothing else is going on", () => {
  // clearing the queue in Ryan's turn would drop the callback that moves the roleplay on
  expect(canReplay("ready")).toBe(true);
  expect(canReplay("evaluated")).toBe(true);
  for (const p of ["loading", "ryan", "recording", "evaluating", "error"] as const) expect(canReplay(p)).toBe(false);
});

test("a script that comes back after leaving the situation screen does not open the roleplay", () => {
  // the back button leaves while the script is still being made
  expect(reduce(initial, { type: "created", roleplay: rp })).toBe(initial);
});

describe("back goes to the screen before", () => {
  test("situation to home", () => {
    expect(reduce(situation, { type: "back" }).screen).toBe("home");
  });

  test("roleplay to situation, leaving the roleplay", () => {
    const s = reduce(at("ready", { jake }), { type: "back" });
    expect(s.screen).toBe("situation");
    expect(s.roleplay).toBeNull();
    expect(s.jake).toBeNull();
    expect(s.history).toEqual([]);
  });

  test("a line retried from the end goes back to the end", () => {
    let s = reduce({ ...at("loading"), screen: "end" }, { type: "startPractice", kind: "mine", order: [1] });
    s = reduce(reduce(s, { type: "lineLoaded", line: userLine }), { type: "back" });
    expect(s.screen).toBe("end");
    expect(s.roleplay).toBe(rp);
    expect(s.practice).toBeNull();
    expect(s.mode).toBe("turn");
  });

  test("end to situation", () => {
    const s = reduce({ ...at("loading"), screen: "end" }, { type: "back" });
    expect(s.screen).toBe("situation");
    expect(s.roleplay).toBeNull();
  });

  test("home has nothing before it", () => {
    expect(reduce(initial, { type: "back" })).toBe(initial);
  });
});

// --- practice after the roleplay (spec roleplay-practice 1, 2, 4, 5, 6) --------------------------------------------

const end = (extra: Partial<State> = {}): State => ({ ...at("evaluated"), screen: "end", ...extra });

test("line progress is kept for the header", () => {
  const s = reduce(reduce(situation, { type: "created", roleplay: rp }), {
    type: "lineLoaded",
    line: ryanLine,
    progress: { no: 1, total: 3 },
  });
  expect(s.progress).toEqual({ no: 1, total: 3 });
});

test("the learner's bubble keeps the script line and what was heard", () => {
  let s = at("evaluating");
  s = reduce(s, { type: "event", e: { type: "heard", text: "I like a cup of copy", followed: true } });
  s = reduce(s, { type: "event", e: { type: "done", next: 2, issues: 0 } });
  s = reduce(s, { type: "next" });
  expect(s.history[0]).toEqual({ kind: "user", text: "I like a cup of copy", script: userLine.text, idx: 1 });
});

test("practice of my lines goes through the order and back to the end", () => {
  let s = reduce(end(), { type: "startPractice", kind: "mine", order: [1, 3] });
  expect([s.screen, s.mode, s.idx, s.phase, s.history]).toEqual(["roleplay", "practice", 1, "loading", []]);
  s = reduce(reduce(s, { type: "lineLoaded", line: userLine }), { type: "recordStart" });
  s = reduce(reduce(s, { type: "recordStop" }), { type: "event", e: { type: "done", next: 1, issues: 0 } });
  s = reduce(s, { type: "again" });
  expect([s.mode, s.phase]).toEqual(["practice", "ready"]);
  s = { ...s, phase: "evaluated" };
  s = reduce(s, { type: "next" });
  expect([s.idx, s.practice?.at, s.history]).toEqual([3, 1, []]);
  s = reduce({ ...s, phase: "evaluated" }, { type: "next" });
  expect([s.screen, s.practice, s.mode]).toEqual(["end", null, "turn"]);
});

test("back from practice returns to the end screen", () => {
  const s = reduce(reduce(end(), { type: "startPractice", kind: "shadow", order: [0, 2] }), { type: "back" });
  expect([s.screen, s.practice, s.mode]).toEqual(["end", null, "turn"]);
});

test("a Ryan line in shadow practice is the learner's to say", () => {
  const s = reduce(reduce(end(), { type: "startPractice", kind: "shadow", order: [0] }), { type: "lineLoaded", line: ryanLine });
  expect([s.mode, s.phase]).toEqual(["shadow", "ready"]);
});

test("shadow line without audio is ready", () => {
  const s = reduce(reduce(end(), { type: "startPractice", kind: "shadow", order: [0] }), {
    type: "lineLoaded",
    line: { ...ryanLine, audio: null },
  });
  expect(s.phase).toBe("ready");
});

test("practice starts only from the end screen with lines", () => {
  const s = at("ready");
  expect(reduce(s, { type: "startPractice", kind: "mine", order: [1] })).toBe(s);
  const e = end();
  expect(reduce(e, { type: "startPractice", kind: "mine", order: [] })).toBe(e);
});

test("restarted opens the copied roleplay and keeps Jake's line", () => {
  const jake = { text: "카페에서 주문하는 상황으로 연습해 보면 어때요?", audio: "a".repeat(64) };
  const copy = { ...rp, id: "b".repeat(12) };
  const s = reduce(end({ jake, closingPlayed: true }), { type: "restarted", roleplay: copy });
  expect([s.screen, s.roleplay?.id, s.jake, s.idx, s.closingPlayed]).toEqual(["roleplay", copy.id, jake, 0, false]);
  const playing = at("ready");
  expect(reduce(playing, { type: "restarted", roleplay: copy })).toBe(playing); // only from the end screen
});

test("closing is marked as played", () => {
  expect(reduce(end(), { type: "closingPlayed" }).closingPlayed).toBe(true);
});

// --- notes start closed (spec roleplay-practice 8) ---------------------------------------------------------------

describe("notes start closed (spec roleplay-practice 8)", () => {
  test("a new line starts with its notes closed", () => {
    expect(reduce({ ...at("loading"), reading: true }, { type: "lineLoaded", line: userLine }).reading).toBe(false);
  });

  test("toggleReading opens and closes", () => {
    const s = reduce(at("ready"), { type: "toggleReading" });
    expect(s.reading).toBe(true);
    expect(reduce(s, { type: "toggleReading" }).reading).toBe(false);
  });

  test("again keeps the notes open on the same line", () => {
    expect(reduce(at("evaluated", { reading: true }), { type: "again" }).reading).toBe(true);
  });

  test("the next line starts closed again", () => {
    const s = reduce(at("evaluated", { reading: true, nextIdx: 2 }), { type: "next" });
    expect(reduce(s, { type: "lineLoaded", line: ryanLine }).reading).toBe(false);
  });

  test("a practice line from the end starts closed", () => {
    expect(reduce(end({ reading: true }), { type: "startPractice", kind: "mine", order: [1] }).reading).toBe(false);
  });
});

// --- Sohee's interpretation of the line to say, like the notes (spec korean-translation 2) ---------------------

describe("the line to say starts without Sohee's interpretation (spec korean-translation 2)", () => {
  test("interpret opens and closes it", () => {
    const s = reduce(at("ready"), { type: "interpret", open: true });
    expect(s.interpreting).toBe(true);
    expect(reduce(s, { type: "interpret", open: false }).interpreting).toBe(false);
  });

  test("it can open while Ryan or the mic is busy: it only adds a line", () => {
    expect(reduce(at("recording"), { type: "interpret", open: true }).interpreting).toBe(true);
  });

  test("nothing to interpret without a line", () => {
    const s = { ...at("loading"), line: null };
    expect(reduce(s, { type: "interpret", open: true })).toBe(s);
  });

  test("again keeps it open; the next line starts closed", () => {
    expect(reduce(at("evaluated", { interpreting: true }), { type: "again" }).interpreting).toBe(true);
    const s = reduce(at("evaluated", { interpreting: true, nextIdx: 2 }), { type: "next" });
    expect(reduce(s, { type: "lineLoaded", line: ryanLine }).interpreting).toBe(false);
  });

  test("a practice starts closed, from the end or mid-roleplay, and the roleplay comes back as it was", () => {
    expect(reduce(end({ interpreting: true }), { type: "startPractice", kind: "mine", order: [1] }).interpreting).toBe(false);
    const before = { ...at("ready", { interpreting: true }), seen: { 0: ryanLine, 1: userLine } };
    const inside = reduce(before, { type: "practiseLine", kind: "shadow", idx: 0 });
    expect(inside.interpreting).toBe(false);
    expect(reduce(inside, { type: "back" }).interpreting).toBe(true);
  });
});

// --- one line in the middle of the roleplay (spec roleplay-practice 9) ---------------------------------------------

describe("one line in the middle of the roleplay (spec roleplay-practice 9)", () => {
  const ryan2 = rp.lines[2] as ScriptLine;
  const user3: ScriptLine = { ...userLine, idx: 3, text: "Just one, thanks." };
  // the learner is on line 3; lines 0-2 are behind
  const midway = (phase: State["phase"], extra: Partial<State> = {}): State => ({
    ...reduce(situation, { type: "created", roleplay: rp }),
    idx: 3,
    line: user3,
    phase,
    progress: { no: 2, total: 2 },
    seen: { 0: ryanLine, 1: userLine, 2: ryan2, 3: user3 },
    history: [
      { kind: "ryan", text: ryanLine.text, idx: 0 },
      { kind: "user", text: "I'd like a cup of coffee", script: userLine.text, idx: 1 },
      { kind: "feedback", text: "좋아요." },
      { kind: "ryan", text: ryan2.text, idx: 2 },
    ],
    ...extra,
  });

  test("my past line opens at once from the line the app holds", () => {
    const s = reduce(midway("ready"), { type: "practiseLine", kind: "mine", idx: 1 });
    expect([s.screen, s.mode, s.idx, s.phase, s.line, s.history, s.practice?.from]).toEqual([
      "roleplay",
      "practice",
      1,
      "ready",
      userLine,
      [],
      "roleplay",
    ]);
  });

  test("Ryan's past line opens as shadow", () => {
    const s = reduce(midway("evaluated"), { type: "practiseLine", kind: "shadow", idx: 2 });
    expect([s.mode, s.idx, s.phase, s.line]).toEqual(["shadow", 2, "ready", ryan2]);
  });

  test("next after the line comes back to the same spot", () => {
    const before = midway("evaluated", { heard: "Just one, thanks.", feedback: "좋아요.", nextIdx: 4, reading: true });
    let s = reduce(before, { type: "practiseLine", kind: "mine", idx: 1 });
    s = reduce(reduce(s, { type: "recordStart" }), { type: "recordStop" });
    s = reduce(reduce(s, { type: "event", e: { type: "done", next: 1, issues: 0 } }), { type: "next" });
    expect(s).toEqual({ ...before, practiceNo: before.practiceNo + 1 });
  });

  test("back from the line comes back to the roleplay", () => {
    const before = midway("ready");
    const s = reduce(reduce(before, { type: "practiseLine", kind: "shadow", idx: 0 }), { type: "back" });
    expect(s).toEqual({ ...before, practiceNo: before.practiceNo + 1 });
  });

  test("only while my turn is waiting", () => {
    for (const p of ["loading", "ryan", "recording", "evaluating", "error"] as const) {
      const s = midway(p);
      expect(reduce(s, { type: "practiseLine", kind: "mine", idx: 1 })).toBe(s);
    }
  });

  test("not the line on screen, an unseen line, the wrong speaker, or inside a practice", () => {
    const s = midway("ready");
    for (const a of [
      { kind: "mine", idx: 3 }, // the line on screen: 「다시 해 보기」 covers it
      { kind: "mine", idx: 5 }, // not seen yet
      { kind: "shadow", idx: 1 }, // my line is not Ryan's
      { kind: "mine", idx: 0 }, // Ryan's line is not mine
    ] as const)
      expect(reduce(s, { type: "practiseLine", ...a })).toBe(s);
    const inside = reduce(s, { type: "practiseLine", kind: "mine", idx: 1 });
    expect(reduce(inside, { type: "practiseLine", kind: "shadow", idx: 0 })).toBe(inside);
  });

  test("which bubbles get a practice button", () => {
    const s = midway("ready");
    expect(s.history.map((b) => practiceFor(s, b))).toEqual(["shadow", "mine", null, "shadow"]);
    expect(practiceFor(s, { kind: "user", idx: 3 })).toBeNull(); // the line on screen, tried again
    const reply: ScriptLine = { idx: 4, speaker: "ryan", text: "Sure thing!", kind: "reply", three: null, audio: null, ko: null, ko_audio: null };
    expect(practiceFor({ ...s, seen: { ...s.seen, 4: reply } }, { kind: "ryan", idx: 4 })).toBe("shadow");
    const inside = reduce(s, { type: "practiseLine", kind: "mine", idx: 1 });
    expect(practiceFor(inside, s.history[0])).toBeNull();
  });

  test("asks first only when a roleplay would be lost", () => {
    const s = midway("ready");
    expect([askFirst(s, "back"), askFirst(s, "home")]).toEqual([true, true]);
    const inside = reduce(s, { type: "practiseLine", kind: "mine", idx: 1 });
    expect([askFirst(inside, "back"), askFirst(inside, "home")]).toEqual([false, true]);
    const fromEnd = reduce(end(), { type: "startPractice", kind: "mine", order: [1] });
    expect([askFirst(fromEnd, "back"), askFirst(fromEnd, "home")]).toEqual([false, false]);
  });

  test("only back from a line practised mid-roleplay stays on the roleplay screen", () => {
    const s = midway("ready");
    const inside = reduce(s, { type: "practiseLine", kind: "mine", idx: 1 });
    const fromEnd = reduce(end(), { type: "startPractice", kind: "mine", order: [1] });
    expect([leavesScreen(inside, "back"), leavesScreen(inside, "home")]).toEqual([false, true]);
    expect([leavesScreen(s, "back"), leavesScreen(fromEnd, "back")]).toEqual([true, true]);
  });

  test("the roleplay line keeps its model key across a practice", () => {
    const before = midway("ready");
    const after = reduce(reduce(before, { type: "practiseLine", kind: "mine", idx: 1 }), { type: "back" });
    expect(modelKey(after)).toBe(modelKey(before));
  });

  test("two practices of the same line get different model keys", () => {
    const first = reduce(midway("ready"), { type: "practiseLine", kind: "mine", idx: 1 });
    const second = reduce(reduce(first, { type: "back" }), { type: "practiseLine", kind: "mine", idx: 1 });
    expect(modelKey(second)).not.toBe(modelKey(first));
  });
});
