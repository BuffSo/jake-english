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
    // back is the only way out since 「처음으로」 went (2026-11-06 user): from a practice it never loses the roleplay
    const s = midway("ready");
    expect(askFirst(s)).toBe(true);
    const inside = reduce(s, { type: "practiseLine", kind: "mine", idx: 1 });
    expect(askFirst(inside)).toBe(false);
    const fromEnd = reduce(end(), { type: "startPractice", kind: "mine", order: [1] });
    expect(askFirst(fromEnd)).toBe(false);
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

  test("back from a roleplay returns to the step the situation came from", () => {
    // picking another card should not mean choosing the topic and the way again
    const s = reduce(reduce(started(), { type: "lineLoaded", line: ryanLine }), { type: "back" });
    expect([s.screen, s.situationFrom, s.roleplay]).toEqual(["situation", from, null]);
    const e = reduce({ ...started(), screen: "end" }, { type: "back" });
    expect([e.screen, e.situationFrom]).toEqual(["situation", from]);
  });

  test("restarting keeps where back leads", () => {
    const copy = { ...rp, id: "b".repeat(12) };
    const s = reduce({ ...started(), screen: "end" }, { type: "restarted", roleplay: copy });
    expect(reduce(s, { type: "back" }).situationFrom).toEqual(from);
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
