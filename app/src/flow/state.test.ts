import roleplayJson from "../../../contract/roleplay.json";
import type { Resume, Roleplay, ScriptLine } from "../api/types";
import { resumeHistory, resumeSeen } from "./resume";
import { canReplay, canSkip, initial, leaveAction, leavesScreen, mayListen, messageIsError, MIC_FAILED, modelKey, movesPlace, NO_SPEECH, notifiesSkip, practiceFor, reduce, showMicHint, type State } from "./state";

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
    const reply: ScriptLine = { idx: 4, speaker: "ryan", text: "Sure thing!", kind: "reply", three: null, audio: null, ko: null, ko_audio: null, parts: null, heard_upto: null, fix: null };
    expect(practiceFor({ ...s, seen: { ...s.seen, 4: reply } }, { kind: "ryan", idx: 4 })).toBe("shadow");
    const inside = reduce(s, { type: "practiseLine", kind: "mine", idx: 1 });
    expect(practiceFor(inside, s.history[0])).toBeNull();
  });

  test("only back from a line practised mid-roleplay stays on the roleplay screen", () => {
    const s = midway("ready");
    const inside = reduce(s, { type: "practiseLine", kind: "mine", idx: 1 });
    const fromEnd = reduce(end(), { type: "startPractice", kind: "mine", order: [1] });
    expect(leavesScreen(inside)).toBe(false);
    expect([leavesScreen(s), leavesScreen(fromEnd)]).toEqual([true, true]);
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

  // todo practice-midway minors 1: both taps run on the state of one render, so the second still sees the practice
  test("back tapped twice before a render leaves only the practice", () => {
    const inside = reduce(midway("ready"), { type: "practiseLine", kind: "mine", idx: 1 });
    const once = reduce(inside, leaveAction(inside));
    expect(reduce(once, leaveAction(inside))).toEqual(once);
    expect([once.screen, once.practice, once.idx]).toEqual(["roleplay", null, 3]);
    const fromEnd = reduce(end(), { type: "startPractice", kind: "mine", order: [1] });
    const left = reduce(fromEnd, leaveAction(fromEnd));
    expect(reduce(left, leaveAction(fromEnd))).toEqual(left);
    expect(left.screen).toBe("end");
    expect(leaveAction(midway("ready"))).toEqual({ type: "back" }); // outside a practice: back as before
  });

  // todo practice-midway minors 2: Ryan's line just said stays the screen's line until the next one comes
  test("Ryan's newest bubble offers shadowing while the next line loads", () => {
    const s = reduce({ ...midway("ryan"), idx: 2, line: ryan2, history: midway("ryan").history.slice(0, 3) }, { type: "ryanDone" });
    expect([s.phase, s.line?.idx]).toEqual(["loading", 2]);
    expect(practiceFor(s, s.history.at(-1)!)).toBe("shadow");
  });

  // todo practice-midway minors 3: the spec plays a line's model once; trying it again does not play it again (user)
  test("trying the line again keeps its model key", () => {
    const turn = midway("evaluated", { heard: "Just one, thanks.", feedback: "좋아요." });
    expect(modelKey(reduce(turn, { type: "again" }))).toBe(modelKey(turn));
  });
});

// --- 복습하기 (spec review-practice 1, 3, 7, 9; review-screens 2: the menu became two tabs) -------------------------

describe("복습하기", () => {
  const review = reduce(initial, { type: "openReview" }); // opens on the past tab
  const pastList = review;
  const savedList = reduce(review, { type: "openSaved" });
  const pastView = reduce(pastList, { type: "openPastRun", group: rp.id, title: "길 묻기" });
  const shown = reduce(pastView, { type: "pastLoaded", roleplay: rp });
  const rpB = { ...rp, id: "bbbbbbbbbbbb" } as Roleplay;
  const copy = { ...rp, id: "cccccccccccc", origin: rp.id } as Roleplay;
  const evaluated = (s: State): State => ({ ...s, phase: "evaluated" });

  test("home opens 복습하기 on the past tab; back from either tab goes home", () => {
    expect(review.screen).toBe("past");
    expect(reduce(review, { type: "back" })).toEqual(initial);
    expect(reduce(savedList, { type: "back" })).toEqual(initial);
  });

  test("the tabs switch between past and saved", () => {
    expect(savedList.screen).toBe("saved");
    expect(reduce(savedList, { type: "openPast" }).screen).toBe("past");
  });

  test("the tabs are taken only on 복습하기", () => {
    expect(reduce(initial, { type: "openPast" })).toBe(initial);
    expect(reduce(initial, { type: "openSaved" })).toBe(initial);
    expect(reduce(at("ready"), { type: "openSaved" })).toEqual(at("ready"));
    expect(reduce(review, { type: "openReview" })).toBe(review);
  });

  test("a saved practice asked for before switching to the past tab does not start", () => {
    expect(reduce(pastList, { type: "startSaved", runs: [rp], order: [1] })).toBe(pastList);
  });

  test("openPastRun shows the end screen as a past view without closing words", () => {
    expect(pastView.screen).toBe("end");
    expect(pastView.past).toEqual({ group: rp.id, title: "길 묻기" });
    expect(pastView.roleplay).toBeNull();
    expect(pastView.closingPlayed).toBe(true);
    expect(shown.roleplay).toBe(rp);
    expect(reduce(at("ready"), { type: "pastLoaded", roleplay: rpB })).toEqual(at("ready"));
    expect(reduce(savedList, { type: "openPastRun", group: rp.id, title: "x" })).toBe(savedList);
  });

  test("back from a past view returns to the past list", () => {
    const s = reduce(shown, { type: "back" });
    expect(s.screen).toBe("past");
    expect(s.past).toBeNull();
  });

  test("practice from a past view comes back to it", () => {
    let s = reduce(shown, { type: "startPractice", kind: "mine", order: [1] });
    s = evaluated(reduce(s, { type: "lineLoaded", line: userLine }));
    s = reduce(s, { type: "next" });
    expect(s.screen).toBe("end");
    expect(s.past).toEqual(shown.past);
    expect(s.roleplay).toBe(rp);
  });

  test("restarted from a past view returns there", () => {
    let s = reduce(shown, { type: "restarted", roleplay: copy });
    expect(s.screen).toBe("roleplay");
    expect(s.roleplay).toBe(copy);
    expect(s.returnTo).toBe(shown);
    expect(s.past).toBeNull();
    expect(reduce(s, { type: "back" })).toBe(shown);
    // played to the end, then back from its end screen
    const done = reduce(s, { type: "lineMissing" });
    expect(done.screen).toBe("end");
    expect(reduce(done, { type: "back" })).toBe(shown);
    // again from that end screen: still back to the first past view
    s = reduce(done, { type: "restarted", roleplay: { ...copy, id: "dddddddddddd" } as Roleplay });
    expect(s.returnTo).toBe(shown);
  });

  test("restarted from a normal end keeps going to the situation screen", () => {
    const s = reduce(end(), { type: "restarted", roleplay: copy });
    expect(s.returnTo).toBeNull();
    expect(reduce(s, { type: "back" }).screen).toBe("situation");
  });

  test("saved practice walks lines across roleplays", () => {
    let s = reduce(savedList, { type: "startSaved", runs: [rp, rpB], order: [1, 0] });
    expect(s.screen).toBe("roleplay");
    expect(s.roleplay).toBe(rp);
    expect(s.idx).toBe(1);
    expect(s.mode).toBe("practice");
    expect(s.practice).toMatchObject({ kind: "mine", from: "saved", at: 0, order: [1, 0] });
    expect(s.phase).toBe("loading");
    s = evaluated(reduce(s, { type: "lineLoaded", line: userLine }));
    s = reduce(s, { type: "next" });
    expect(s.roleplay).toBe(rpB);
    expect(s.idx).toBe(0);
    expect(s.mode).toBe("shadow");
    expect(s.practice?.kind).toBe("shadow");
    expect(s.phase).toBe("loading");
    expect(s.history).toEqual([]);
    s = evaluated(reduce(s, { type: "lineLoaded", line: ryanLine }));
    s = reduce(s, { type: "next" });
    expect(s.screen).toBe("saved");
    expect(s.practice).toBeNull();
    expect(s.roleplay).toBeNull();
  });

  test("startSaved is only taken on the saved list and with lines", () => {
    expect(reduce(review, { type: "startSaved", runs: [rp], order: [1] })).toBe(review);
    expect(reduce(savedList, { type: "startSaved", runs: [], order: [] })).toBe(savedList);
  });

  test("back from saved practice returns to the saved list", () => {
    const s = reduce(reduce(savedList, { type: "startSaved", runs: [rp], order: [1] }), { type: "back" });
    expect(s.screen).toBe("saved");
    expect(s.practice).toBeNull();
  });

  test("a missing line in saved practice moves on", () => {
    let s = reduce(savedList, { type: "startSaved", runs: [rp, rpB], order: [1, 0] });
    s = reduce(s, { type: "lineMissing" });
    expect(s.screen).toBe("roleplay");
    expect(s.roleplay).toBe(rpB);
    expect(s.idx).toBe(0);
    s = reduce(s, { type: "lineMissing" });
    expect(s.screen).toBe("saved");
  });

  test("restarted from saved practice returns to the same line", () => {
    let p = reduce(savedList, { type: "startSaved", runs: [rp, rpB], order: [1, 0] });
    p = evaluated(reduce(p, { type: "lineLoaded", line: userLine }));
    p = reduce(p, { type: "next" });
    p = reduce(p, { type: "lineLoaded", line: ryanLine });
    const s = reduce(p, { type: "restarted", roleplay: copy });
    expect(s.screen).toBe("roleplay");
    expect(s.roleplay).toBe(copy);
    expect(s.practice).toBeNull();
    expect(s.returnTo).toBe(p);
    const back = reduce(s, { type: "back" });
    expect(back.practice?.at).toBe(1);
    expect(back.roleplay).toBe(rpB);
    expect(back.idx).toBe(0);
    expect(back.phase).toBe("loading");
    expect(back.line).toBeNull();
    expect(back.history).toEqual([]);
    expect(back.practiceNo).toBe(p.practiceNo + 1);
  });

  test("toggleBefore opens the previous line and a new line closes it", () => {
    let s = reduce(reduce(savedList, { type: "startSaved", runs: [rp], order: [1] }), { type: "lineLoaded", line: userLine });
    expect(s.beforeOpen).toBe(false);
    s = reduce(s, { type: "toggleBefore" });
    expect(s.beforeOpen).toBe(true);
    s = reduce({ ...s, phase: "loading" }, { type: "lineLoaded", line: userLine });
    expect(s.beforeOpen).toBe(false);
  });

  test("saved practice offers no midway practice", () => {
    const s = reduce(reduce(savedList, { type: "startSaved", runs: [rp], order: [1] }), { type: "lineLoaded", line: userLine });
    expect(practiceFor(s, { kind: "ryan", idx: 0 })).toBeNull();
  });

  test("home from anywhere clears the way back", () => {
    const s = reduce(reduce(shown, { type: "restarted", roleplay: copy }), { type: "home" });
    expect(s).toEqual(initial);
  });
});

test("a past view knows its lines, so practice shows the line before (final review)", () => {
  const past = reduce(reduce(reduce(reduce(initial, { type: "openReview" }), { type: "openPast" }), {
    type: "openPastRun",
    group: rp.id,
    title: "길 묻기",
  }), { type: "pastLoaded", roleplay: rp });
  const s = reduce(past, { type: "startPractice", kind: "mine", order: [1] });
  expect(s.seen[0]).toEqual(rp.lines[0]);
});

describe("situation topics (spec situation-topics 2, 5)", () => {
  const from = { topic: "usa", step: "list" as const };
  const started = () => reduce(situation, { type: "created", roleplay: rp, from });

  test("back from a roleplay mid-way goes to the topics; from its end screen to where it was picked", () => {
    // mid-way: the topic step shows the row to resume it (spec resume-roleplay 5, the user's choice). The end
    // screen still goes back to the step it came from, to pick another card there.
    const s = reduce(reduce(started(), { type: "lineLoaded", line: ryanLine }), { type: "back" });
    expect([s.screen, s.situationFrom, s.roleplay]).toEqual(["situation", null, null]);
    const e = reduce({ ...started(), screen: "end" }, { type: "back" });
    expect([e.screen, e.situationFrom]).toEqual(["situation", from]);
  });

  test("restarting keeps where back leads from the end screen", () => {
    const copy = { ...rp, id: "b".repeat(12) };
    const s = reduce({ ...started(), screen: "end" }, { type: "restarted", roleplay: copy });
    expect(reduce({ ...s, screen: "end" }, { type: "back" }).situationFrom).toEqual(from);
    expect(reduce(s, { type: "back" }).situationFrom).toBeNull(); // mid-way, to the topics
  });

  test("choosing roleplay on the home screen starts at the topics", () => {
    expect(reduce(initial, { type: "chooseRoleplay" }).situationFrom).toBeNull();
    expect(reduce(situation, { type: "created", roleplay: rp }).situationFrom).toBeNull();
  });

  const mineFirst: Roleplay = { ...rp, lines: rp.lines.slice(1).map((l, i) => ({ ...l, idx: i })) };

  test("a script that starts with my line starts on my turn", () => {
    // in the US the learner asks first (user, 2026-11-07)
    const first = mineFirst.lines[0];
    expect(first.speaker).toBe("user");
    const s = reduce(reduce(situation, { type: "created", roleplay: mineFirst }), { type: "lineLoaded", line: first });
    expect([s.phase, s.history]).toEqual(["ready", []]);
  });

  test("a script that ends with my line ends after it", () => {
    const last = { ...userLine, idx: 4 };
    let s = reduce(reduce(situation, { type: "created", roleplay: rp }), { type: "lineLoaded", line: last });
    s = reduce(reduce({ ...s, idx: 4 }, { type: "recordStart" }), { type: "recordStop" });
    s = reduce(s, { type: "event", e: { type: "done", next: 5, issues: 0 } });
    s = reduce(s, { type: "next" });
    expect([s.idx, s.phase]).toEqual([5, "loading"]);
    expect(reduce(s, { type: "lineMissing" }).screen).toBe("end");
  });
});

// spec offscript-aside 5, 6: a line not followed gets teacher Ryan's answer and the same line again
test("an aside offers only 다시 해 보기 and leaves no bubbles", () => {
  let s = at("evaluating"); // a roleplay turn being evaluated, mode "turn", idx 1
  s = reduce(s, { type: "event", e: { type: "heard", text: "다시 할게요", followed: false } });
  s = reduce(s, { type: "event", e: { type: "text", delta: "괜찮아요. 다시 해 볼까요?" } });
  s = reduce(s, { type: "event", e: { type: "done", next: 1, issues: 0 } });
  expect(s.phase).toBe("evaluated");
  expect(s.aside).toBe(true);
  expect(reduce(s, { type: "next" })).toBe(s);
  const again = reduce(s, { type: "again" });
  expect(again.history).toEqual(s.history);
  expect(again.mode).toBe("turn");
  expect(again.aside).toBe(false);
  expect(again.feedback).toBe("");
  expect(again.heard).toBeNull();
});

test("aside then follow moves on to the next line", () => {
  let s = at("evaluating");
  s = reduce(s, { type: "event", e: { type: "heard", text: "Wait.", followed: false } });
  s = reduce(s, { type: "event", e: { type: "done", next: 1, issues: 0 } });
  s = reduce(reduce(s, { type: "again" }), { type: "recordStart" });
  s = reduce(s, { type: "recordStop" });
  s = reduce(s, { type: "event", e: { type: "heard", text: "It's right over there.", followed: true } });
  s = reduce(s, { type: "event", e: { type: "done", next: 2, issues: 0 } });
  expect(reduce(s, { type: "next" }).idx).toBe(2);
});

test("an aside in a retry keeps where 다음 goes", () => {
  // followed turn (next 2) → 다시 해 보기 (retry) → aside: 다음 after the next followed retry still goes to 2
  let s = at("evaluating");
  s = reduce(s, { type: "event", e: { type: "heard", text: "It's right over there.", followed: true } });
  s = reduce(s, { type: "event", e: { type: "done", next: 2, issues: 0 } });
  s = reduce(reduce(reduce(s, { type: "again" }), { type: "recordStart" }), { type: "recordStop" });
  s = reduce(s, { type: "event", e: { type: "heard", text: "Wait.", followed: false } });
  s = reduce(s, { type: "event", e: { type: "done", next: 1, issues: 0 } });
  expect(s.nextIdx).toBe(2);
  expect(reduce(s, { type: "again" }).mode).toBe("retry");
});

test("a near miss with points moves on like a followed try", () => {
  // the server found words heard differently (issues > 0): a try at the line, not an aside (offscript-aside 6)
  let s = at("evaluating");
  s = reduce(s, { type: "event", e: { type: "heard", text: "It's light over hair.", followed: false } });
  s = reduce(s, { type: "event", e: { type: "done", next: 2, issues: 2 } });
  expect(s.aside).toBe(false);
  expect(s.nextIdx).toBe(2);
  const next = reduce(s, { type: "next" });
  expect(next.idx).toBe(2);
  expect(next.history.map((b) => b.kind)).toEqual(["user"]);
});

describe("the recording of each turn (spec three-line-listen 3, 4, 7)", () => {
  const heard = (s: State, n: number | undefined, followed = true) =>
    reduce(s, { type: "event", e: { type: "heard", text: "I'd like a cup of coffee", followed, ...(n ? { n } : {}) } });

  test("heard with n keeps the recording of this turn", () => {
    const s = heard(at("evaluating"), 3);
    expect(s.heardRec).toEqual({ rp_id: rp.id, idx: userLine.idx, n: 3 });
  });

  test("heard without n leaves no recording", () => {
    const s = heard(at("evaluating"), undefined);
    expect(s.heardRec).toBeNull();
    expect(s.heard).toBe("I'd like a cup of coffee");
  });

  test("each retry bubble keeps its own recording", () => {
    let s = heard(at("evaluating"), 1);
    s = reduce(s, { type: "event", e: { type: "done", next: 2, issues: 0 } });
    s = reduce(s, { type: "again" });
    expect(s.heardRec).toBeNull();
    s = reduce(reduce(s, { type: "recordStart" }), { type: "recordStop" });
    s = heard(s, 2);
    s = reduce(s, { type: "event", e: { type: "done", next: 2, issues: 0 } });
    s = reduce(s, { type: "next" });
    const mine = s.history.filter((b) => b.kind === "user");
    expect(mine.map((b) => b.rec?.n)).toEqual([1, 2]);
    expect(mine[0].rec).toEqual({ rp_id: rp.id, idx: userLine.idx, n: 1 });
  });

  test("an aside keeps its recording only while on screen", () => {
    let s = heard(at("evaluating"), 4, false);
    s = reduce(s, { type: "event", e: { type: "done", next: 1, issues: 0 } });
    expect(s.heardRec?.n).toBe(4);
    s = reduce(s, { type: "again" });
    expect(s.history.some((b) => b.kind === "user")).toBe(false);
    expect(s.heardRec).toBeNull();
  });
});

test("a bubble sound plays only while my turn waits and Ryan is not answering (spec three-line-listen 5)", () => {
  // an evaluation that failed after 「들린 말」 keeps 「🔊 내 녹음」 working: the recording is saved (spec 4, final review)
  const phases: State["phase"][] = ["loading", "ryan", "ready", "recording", "evaluating", "evaluated", "error"];
  expect(phases.filter((p) => mayListen(p, false))).toEqual(["ready", "evaluated", "error"]);
  expect(phases.filter((p) => mayListen(p, true))).toEqual([]);
});

describe("skip and cancel (spec record-cancel-skip)", () => {
  const skip = { type: "skip" } as const;
  const aside = (): State => {
    let s = at("evaluating");
    s = reduce(s, { type: "event", e: { type: "heard", text: "넘어가고 싶어요", followed: false } });
    s = reduce(s, { type: "event", e: { type: "text", delta: "다시 해 볼까요?" } });
    return reduce(s, { type: "event", e: { type: "done", next: 1, issues: 0 } });
  };

  test("cancel while recording goes back to ready and keeps the mode", () => {
    const s = reduce(reduce(at("ready", { mode: "retry" }), { type: "recordStart" }), { type: "recordCancel" });
    expect([s.phase, s.mode, s.history]).toEqual(["ready", "retry", []]);
  });

  test("skip is taken before recording and after teacher Ryan's answer only", () => {
    expect(canSkip(at("ready"))).toBe(true);
    expect(canSkip(aside())).toBe(true);
    const followed = reduce(at("evaluating"), { type: "event", e: { type: "done", next: 2, issues: 0 } });
    const ryanTurn = reduce(reduce(situation, { type: "created", roleplay: rp }), { type: "lineLoaded", line: ryanLine });
    const no = [at("recording"), at("evaluating"), followed, at("error"), at("loading"), ryanTurn, end({ phase: "ready" })];
    for (const s of no) {
      expect(canSkip(s)).toBe(false);
      expect(reduce(s, skip)).toBe(s);
    }
  });

  test("skip in the roleplay leaves my line as its script and moves on", () => {
    const s = reduce(at("ready"), skip);
    // todo 26 3: a skipped bubble says so, rather than by an empty text
    expect(s.history.at(-1)).toEqual({ kind: "user", text: "", script: userLine.text, idx: 1, skipped: true });
    expect([s.idx, s.phase, s.line, s.mode, s.heard]).toEqual([2, "loading", null, "turn", null]);
  });

  test("skip after teacher Ryan's answer leaves nothing of the answer", () => {
    const s = reduce(aside(), skip);
    expect(s.history).toEqual([{ kind: "user", text: "", script: userLine.text, idx: 1, skipped: true }]);
    expect([s.idx, s.feedback, s.aside]).toEqual([2, "", false]);
  });

  test("skipping a line already said adds no bubble", () => {
    let s = at("evaluating");
    s = reduce(s, { type: "event", e: { type: "heard", text: "It's right over there.", followed: true } });
    s = reduce(s, { type: "event", e: { type: "done", next: 2, issues: 0 } });
    s = reduce(reduce(s, { type: "again" }), skip);
    const mine = s.history.filter((b) => b.kind === "user" && b.idx === 1);
    expect(mine).toHaveLength(1);
    expect(mine[0].text).toBe("It's right over there.");
    expect(mine[0].skipped).toBeUndefined(); // a line said is not marked skipped
    expect(s.idx).toBe(2);
  });

  test("two skips from one old state move one line", () => {
    const once = reduce(at("ready"), skip);
    expect(reduce(once, skip)).toBe(once);
  });

  test("skip in a practice goes where 다음 goes", () => {
    let s = reduce(end(), { type: "startPractice", kind: "mine", order: [1, 3] });
    s = reduce(reduce(s, { type: "lineLoaded", line: userLine }), skip);
    expect([s.practice?.at, s.idx, s.history, s.phase]).toEqual([1, 3, [], "loading"]);
    s = reduce(reduce(s, { type: "lineLoaded", line: { ...userLine, idx: 3 } }), skip);
    expect([s.screen, s.practice]).toEqual(["end", null]);

    const before = { ...at("ready", { idx: 3, line: { ...userLine, idx: 3 } }), seen: { 1: userLine } };
    const one = reduce(before, { type: "practiseLine", kind: "mine", idx: 1 });
    expect(reduce(one, skip)).toEqual({ ...before, practiceNo: one.practiceNo });

    const saved = reduce(reduce(initial, { type: "openReview" }), { type: "openSaved" });
    const s1 = reduce(reduce(saved, { type: "startSaved", runs: [rp], order: [1] }), { type: "lineLoaded", line: userLine });
    expect(reduce(s1, skip).screen).toBe("saved");
  });

  test("skip in shadow practice is taken on Ryan's line and goes where 다음 goes", () => {
    // todo 26 2: canSkip is true on Ryan's line when the mode is shadow
    let s = reduce(reduce(end(), { type: "startPractice", kind: "shadow", order: [0, 2] }), { type: "lineLoaded", line: ryanLine });
    expect(canSkip(s)).toBe(true);
    s = reduce(s, skip);
    expect([s.practice?.at, s.idx, s.phase, s.history]).toEqual([1, 2, "loading", []]);
    s = reduce(reduce(s, { type: "lineLoaded", line: { ...ryanLine, idx: 2 } }), skip);
    expect([s.screen, s.practice, s.mode]).toEqual(["end", null, "turn"]);
  });

  test("a skipped line keeps its practice button", () => {
    const s = reduce(reduce(at("ready"), skip), { type: "lineLoaded", line: ryanLine });
    const bubble = s.history.at(-1)!;
    expect(practiceFor(s, bubble)).toBe("mine");
  });
});

describe("first-turn hint and the silent cancel (spec record-feedback 3, 4)", () => {
  const user = { ...rp.lines[1], idx: 1 } as ScriptLine;
  const seenAll = { 0: ryanLine, 1: userLine };

  test("the hint shows on my turn before the mic was ever used", () => {
    expect(at("ready").micUsed).toBe(false);
    expect(showMicHint(at("ready"))).toBe(true);
    expect(showMicHint(at("recording"))).toBe(false);
    expect(showMicHint(at("evaluating"))).toBe(false);
  });

  test("it goes for good once the mic comes on, even after a cancel", () => {
    const tapped = reduce(at("ready"), { type: "recordStart" });
    expect(showMicHint(tapped)).toBe(false); // hidden from the tap: the screen shows 「말하기 끝」
    const started = reduce(tapped, { type: "micOn" });
    expect(started.micUsed).toBe(true);
    expect(showMicHint(reduce(started, { type: "recordCancel" }))).toBe(false);
  });

  // todo 20261108_34 1, 5: a refused permission or a mic that did not start used to drop the hint for good and say
  // nothing on the conversation screen
  test("a mic that did not come on keeps the hint and says why", () => {
    const s = reduce(reduce(at("ready"), { type: "recordStart" }), { type: "micFailed" });
    expect([s.phase, s.micUsed, s.message]).toEqual(["ready", false, MIC_FAILED]);
    expect(showMicHint(s)).toBe(true);
    expect(messageIsError(s)).toBe(true);
    expect(MIC_FAILED).toBe("마이크를 쓸 수 없어요. 앱의 마이크 권한을 확인해 주세요.");
  });

  test("a failed mic after it was used once keeps it used", () => {
    const s = reduce(reduce(at("ready", { micUsed: true }), { type: "recordStart" }), { type: "micFailed" });
    expect(s.micUsed).toBe(true);
  });

  test("the mic failing is taken only while recording", () => {
    const ready = at("ready");
    expect(reduce(ready, { type: "micFailed" })).toBe(ready);
  });

  test("the notice after no speech is not drawn as an error, a failure is", () => {
    expect(messageIsError(reduce(at("recording"), { type: "noSpeech" }))).toBe(false);
    expect(messageIsError(at("error", { message: "x" }))).toBe(true);
  });

  test("a skip keeps it for the next turn", () => {
    const s = reduce(at("ready"), { type: "skip" });
    expect(s.micUsed).toBe(false);
    expect(showMicHint(reduce(s, { type: "lineLoaded", line: { ...user, idx: 3 } }))).toBe(true);
  });

  test("not on Ryan's turn, nor while a line loads", () => {
    const ryan = reduce(reduce(situation, { type: "created", roleplay: rp }), { type: "lineLoaded", line: ryanLine });
    expect(ryan.phase).toBe("ryan");
    expect(showMicHint(ryan)).toBe(false);
    expect(showMicHint(at("loading"))).toBe(false);
  });

  test("on Ryan's line to follow in shadow practice", () => {
    const s = reduce(reduce(end(), { type: "startPractice", kind: "shadow", order: [0] }), { type: "lineLoaded", line: ryanLine });
    expect(showMicHint(s)).toBe(true);
  });

  test("each new conversation and practice starts with it", () => {
    const used = (s: State): State => ({ ...s, micUsed: true });
    expect(reduce(situation, { type: "created", roleplay: rp }).micUsed).toBe(false);
    expect(reduce(used(end()), { type: "restarted", roleplay: { ...rp, id: "c".repeat(12) } }).micUsed).toBe(false);
    expect(reduce(used(end()), { type: "startPractice", kind: "mine", order: [1] }).micUsed).toBe(false);
    const mid = used(at("ready", { idx: 3, line: { ...user, idx: 3 }, seen: seenAll }));
    expect(reduce(mid, { type: "practiseLine", kind: "mine", idx: 1 }).micUsed).toBe(false);
  });

  test("back from a line practised mid-roleplay brings the roleplay back as it was", () => {
    const mid = at("ready", { idx: 3, line: { ...user, idx: 3 }, seen: seenAll });
    let s = reduce(mid, { type: "practiseLine", kind: "mine", idx: 1 });
    s = reduce(reduce(s, { type: "recordStart" }), { type: "micOn" });
    expect(s.micUsed).toBe(true);
    s = reduce(reduce(s, { type: "recordCancel" }), { type: "back" });
    expect(s.micUsed).toBe(false);
  });

  test("noSpeech goes back to before speaking with the notice, in the same mode", () => {
    const s = reduce(at("recording", { mode: "retry" }), { type: "noSpeech" });
    expect(s.phase).toBe("ready");
    expect(s.mode).toBe("retry");
    expect(s.message).toBe(NO_SPEECH);
    expect(NO_SPEECH).toBe("말소리가 없어 녹음을 멈췄어요.");
  });

  test("noSpeech outside recording does nothing", () => {
    for (const p of ["ready", "evaluating", "evaluated", "error"] as const) {
      const s = at(p);
      expect(reduce(s, { type: "noSpeech" })).toBe(s);
    }
  });

  test("the notice goes at the next start", () => {
    const s = reduce(reduce(at("recording"), { type: "noSpeech" }), { type: "recordStart" });
    expect(s.message).toBeNull();
  });
});

// --- resuming the last conversation (spec resume-roleplay 2, 4, 5) ----------------------------------------------

describe("resume", () => {
  const resume: Resume = {
    roleplay: { ...rp, pos: 2 },
    at: 2,
    progress: { no: 1, total: 1 },
    said: [{ idx: 1, heard: "I'd like a cup of coffee.", n: 1 }],
    ended: false,
  };
  const resumed = () => reduce(situation, { type: "resumed", resume });

  // spec record-feedback 3: a resumed conversation is a new run on this screen, so its first turn shows the hint
  test("a resumed conversation shows 「🎤를 누르고 말하세요」 on its first turn", () => {
    const s = reduce({ ...situation, micUsed: true }, { type: "resumed", resume });
    expect(s.micUsed).toBe(false);
    expect(showMicHint(reduce(s, { type: "lineLoaded", line: { ...userLine, idx: 3 } }))).toBe(true);
  });

  test("resuming opens the roleplay at its line with what was said before", () => {
    const s = resumed();
    expect([s.screen, s.idx, s.phase, s.mode]).toEqual(["roleplay", 2, "loading", "turn"]);
    expect(s.roleplay).toBe(resume.roleplay);
    expect(s.history).toEqual(resumeHistory(resume));
    expect(s.seen).toEqual(resumeSeen(resume));
    expect([s.progress, s.situationFrom, s.jake]).toEqual([resume.progress, null, null]);
  });

  test("resumed is taken only on the situation screen", () => {
    expect(reduce(initial, { type: "resumed", resume })).toBe(initial);
    const playing = at("ready");
    expect(reduce(playing, { type: "resumed", resume })).toBe(playing);
  });

  test("a second resumed does nothing", () => {
    // a double tap on the row: the second tap sees the roleplay screen
    const s = resumed();
    expect(reduce(s, { type: "resumed", resume })).toBe(s);
  });

  test("a past line of a resumed roleplay can be practised", () => {
    const s = resumed();
    expect(practiceFor(s, s.history[1])).toBe("mine");
    expect(practiceFor(s, s.history[0])).toBe("shadow");
  });

  test("back from a resumed roleplay goes to the topics", () => {
    const s = reduce(resumed(), { type: "back" });
    expect([s.screen, s.situationFrom, s.roleplay]).toEqual(["situation", null, null]);
  });
});

// --- a resumed conversation passes lines recorded before (spec resume-unrecorded 3) --------------------------------

describe("resume past recorded lines", () => {
  // made up: R0 U1 R2 U3 R4, gone to the end with U1 unrecorded
  const texts: [ScriptLine["speaker"], string][] = [
    ["ryan", "Good morning. How can I help?"],
    ["user", "I'd like to return this jacket."],
    ["ryan", "Do you have the receipt?"],
    ["user", "Yes, here it is."],
    ["ryan", "All done. Have a nice day."],
  ];
  const lines5: ScriptLine[] = texts.map(([speaker, text], idx) => ({ ...userLine, idx, speaker, text }));
  const said3 = { idx: 3, heard: "Yes, here it is.", n: 2 };
  const ended: Resume = { roleplay: { ...rp, lines: lines5, pos: 4 }, at: 0, progress: { no: 1, total: 2 }, said: [said3], ended: true };
  const resumedEnded = () => reduce(situation, { type: "resumed", resume: ended });
  // Ryan's line 0, then my line 1 waiting for the mic
  const readyAt1 = () => {
    const s = reduce(reduce(resumedEnded(), { type: "lineLoaded", line: lines5[0] }), { type: "ryanDone" });
    return reduce(s, { type: "lineLoaded", line: lines5[1] });
  };
  const evaluatedAt1 = () => {
    let s = reduce(reduce(readyAt1(), { type: "recordStart" }), { type: "recordStop" });
    s = reduce(s, { type: "event", e: { type: "heard", text: lines5[1].text, followed: true, n: 1 } });
    return reduce(s, { type: "event", e: { type: "done", next: 2, issues: 0 } });
  };

  test("resuming keeps the lines recorded before", () => {
    expect(resumedEnded().recorded).toEqual({ 3: said3 });
    expect(initial.recorded).toBeNull();
    expect(reduce(situation, { type: "created", roleplay: rp }).recorded).toBeNull();
  });

  test("「다음」 in a resumed conversation passes recorded lines as bubbles", () => {
    const s = reduce(evaluatedAt1(), { type: "next" });
    expect([s.idx, s.phase, s.mode]).toEqual([4, "loading", "turn"]);
    expect(s.history.map((b) => b.idx)).toEqual([0, 1, 2, 3]);
    expect(s.history[3]).toMatchObject({ kind: "user", text: said3.heard, rec: { idx: 3, n: 2 } });
    expect(s.seen[3]).toEqual(lines5[3]);
  });

  test("a skip in a resumed conversation passes recorded lines too", () => {
    const s = reduce(readyAt1(), { type: "skip" });
    expect(s.idx).toBe(4);
    expect(s.history.map((b) => [b.idx, !!b.skipped])).toEqual([[0, false], [1, true], [2, false], [3, false]]);
  });

  test("a practice from a resumed conversation comes back to it", () => {
    const s = reduce(readyAt1(), { type: "practiseLine", kind: "shadow", idx: 0 });
    expect(reduce(s, { type: "endPractice" }).recorded).toEqual({ 3: said3 });
  });
});

// --- what moves the conversation's place on the Mac (spec resume-roleplay 3, 4; final review) --------------------

describe("the place on the Mac", () => {
  test("a skip inside the conversation tells the Mac", () => {
    expect(notifiesSkip(at("ready"))).toBe(true);
  });

  test("a skip inside a practice does not", () => {
    // a saved sentence or a past line is another conversation's line: its place must not move
    const fromEnd = reduce(end(), { type: "startPractice", kind: "mine", order: [1] });
    const midway = reduce({ ...at("ready"), seen: { 0: ryanLine, 1: userLine } }, { type: "practiseLine", kind: "shadow", idx: 0 });
    expect([notifiesSkip(fromEnd), notifiesSkip(midway)]).toEqual([false, false]);
  });

  test("only a turn's evaluation moves the place", () => {
    expect(movesPlace(at("ready"))).toBe(true);
    for (const mode of ["retry", "practice", "shadow"] as const) expect(movesPlace(at("ready", { mode }))).toBe(false);
  });
});
