import type { Roleplay, Said, ScriptLine, TalkEnd, TalkEvent } from "../api/types";
import roleplayJson from "../../../contract/roleplay.json";
import talkJson from "../../../contract/talk.json";
import { MIC_FAILED, NO_SPEECH } from "./state";
import {
  canEnd,
  canSpeak,
  cutOf,
  englishTurns,
  heardCount,
  isCurrent,
  lineSounds,
  mayListenTalk,
  talkMessageIsError,
  replaysSituation,
  savedBefore,
  talkInitial,
  talkReduce,
  turnNo,
  type TalkAction,
  type TalkState,
} from "./talk";

const key = (c: string) => c.repeat(64);
const parts: Said[] = [
  { text: "Hi!", audio: key("a") },
  { text: "How are you?", audio: key("b") },
  { text: "What did you do today?", audio: key("c") },
];
const first = { ...(talkJson as unknown as Roleplay).lines[0], parts };
const roleplay = { ...(talkJson as unknown as Roleplay), lines: [first] } as Roleplay;
const replyParts: Said[] = [
  { text: "Nice!", audio: key("d") },
  { text: "Is it a big park?", audio: key("e") },
];

const run = (s: TalkState, ...as: TalkAction[]) => as.reduce(talkReduce, s);
const ev = (s: TalkState, e: TalkEvent): TalkAction => ({ type: "event", turn: s.turn, e });
const opened = () => run(talkInitial, { type: "opened", roleplay });
const ready = () => run(opened(), { type: "ryanDone" });
const heardE: TalkEvent = { type: "heard", text: "I walk to the park.", n: 1, idx: 1, korean: false };
const replyE: TalkEvent = { type: "reply", idx: 2, kind: "reply", parts: replyParts };
// my turn spoken and Ryan's answer fully in: phase ryan, done
function answered(): TalkState {
  let s = run(ready(), { type: "recordStart", heard: null }, { type: "recordStop" });
  s = run(s, ev(s, heardE), ev(s, { type: "text", delta: "Nice! " }), ev(s, { type: "text", delta: "Is it a big park?" }));
  return run(s, ev(s, replyE), ev(s, { type: "done", idx: 2 }));
}

test("opening shows Ryan's question and his turn ends when it is played", () => {
  expect(talkInitial.phase).toBe("opening");
  expect(talkInitial.turn).toBe(0);
  const s = opened();
  expect(s.phase).toBe("ryan");
  expect(s.bubbles).toEqual([{ kind: "ryan", idx: 0, text: first.text, parts, heard: null }]);
  expect(s.done).toBe(true);
  expect(talkReduce(s, { type: "ryanDone" }).phase).toBe("ready");
});

test("ryanDone waits for done", () => {
  const s0 = run(ready(), { type: "recordStart", heard: null }, { type: "recordStop" });
  const s = run(s0, ev(s0, heardE), ev(s0, replyE));
  expect(s.phase).toBe("ryan");
  expect(s.done).toBe(false);
  expect(talkReduce(s, { type: "ryanDone" })).toBe(s);
  expect(talkReduce(talkReduce(s, ev(s, { type: "done", idx: 2 })), { type: "ryanDone" }).phase).toBe("ready");
});

test("the mic cuts Ryan off once his text is complete", () => {
  const s0 = answered();
  const s = talkReduce(s0, { type: "recordStart", heard: 1 });
  expect(s.phase).toBe("recording");
  expect(cutOf(s)).toBe(1);
  expect(s.turn).toBe(s0.turn + 1);
  expect(s.micUsed).toBe(true);
  // a cut at or past the whole answer is no cut
  expect(cutOf(talkReduce(s0, { type: "recordStart", heard: 2 }))).toBeNull();
  expect(cutOf(talkReduce(s0, { type: "recordStart", heard: null }))).toBeNull();
});

test("no mic while Ryan is thinking or still writing", () => {
  const rec = run(ready(), { type: "recordStart", heard: null });
  const waiting = talkReduce(rec, { type: "recordStop" });
  const replying = talkReduce(waiting, ev(waiting, { type: "text", delta: "Nice" }));
  expect(replying.phase).toBe("replying");
  for (const s of [waiting, replying, rec]) expect(talkReduce(s, { type: "recordStart", heard: null })).toBe(s);
  for (const s of [waiting, replying, rec]) expect(canSpeak(s)).toBe(false);
});

test("a second recordStart or endStart does nothing", () => {
  const rec = talkReduce(ready(), { type: "recordStart", heard: null });
  expect(talkReduce(rec, { type: "recordStart", heard: null })).toBe(rec);
  const ending = talkReduce(ready(), { type: "endStart", heard: null });
  expect(ending.phase).toBe("ending");
  expect(talkReduce(ending, { type: "endStart", heard: null })).toBe(ending);
});

test("cancel after cutting Ryan off gives my turn, still cut", () => {
  const s = run(answered(), { type: "recordStart", heard: 1 }, { type: "recordCancel" });
  expect(s.phase).toBe("ready");
  expect(cutOf(s)).toBe(1);
  expect(mayListenTalk(s)).toBe(true);
});

test("events of an older turn are dropped", () => {
  const s = run(ready(), { type: "recordStart", heard: null }, { type: "recordStop" });
  expect(isCurrent(s, s.turn)).toBe(true);
  expect(isCurrent(s, s.turn - 1)).toBe(false);
  expect(talkReduce(s, { type: "event", turn: s.turn - 1, e: heardE })).toBe(s);
  expect(talkReduce(s, { type: "failed", turn: s.turn - 1, message: "x" })).toBe(s);
});

test("heard adds my bubble with its recording", () => {
  const s0 = run(ready(), { type: "recordStart", heard: null }, { type: "recordStop" });
  const s = talkReduce(s0, ev(s0, heardE));
  expect(s.heardIn).toBe(true);
  expect(s.bubbles[1]).toEqual({
    kind: "me",
    idx: 1,
    text: "I walk to the park.",
    rec: { rp_id: roleplay.id, idx: 1, n: 1 },
    korean: false,
  });
});

test("Ryan's text streams then becomes his line", () => {
  const s0 = run(ready(), { type: "recordStart", heard: null }, { type: "recordStop" });
  let s = run(s0, ev(s0, heardE), ev(s0, { type: "text", delta: "Nice! " }));
  expect(s.phase).toBe("replying");
  s = run(s, ev(s, { type: "text", delta: "Is it a big park?" }));
  expect(s.pending).toBe("Nice! Is it a big park?");
  s = talkReduce(s, ev(s, replyE));
  expect(s.phase).toBe("ryan");
  expect(s.pending).toBe("");
  expect(s.bubbles[2]).toEqual({ kind: "ryan", idx: 2, text: "Nice! Is it a big park?", parts: replyParts, heard: null });
});

test("done hands back my turn when the sounds end", () => {
  const s = answered();
  expect(s.done).toBe(true);
  expect(s.phase).toBe("ryan");
  expect(talkReduce(s, { type: "ryanDone" }).phase).toBe("ready");
});

test("Korean heard gets Ryan's fixed English line asking for English", () => {
  const s0 = run(ready(), { type: "recordStart", heard: null }, { type: "recordStop" });
  const help: Said[] = [{ text: "Could you try that in English? Short is fine.", audio: key("f") }];
  const s = run(
    s0,
    ev(s0, { ...heardE, text: "주말에 한 일", korean: true }),
    ev(s0, { type: "reply", idx: 2, kind: "help", parts: help }),
    ev(s0, { type: "done", idx: 2 }),
  );
  expect(s.bubbles[1]).toMatchObject({ kind: "me", korean: true });
  expect(s.bubbles[2]).toEqual({ kind: "help", idx: 2, text: help[0].text, audio: key("f") });
  expect(englishTurns(s)).toBe(0);
});

test("no speech goes back to my turn with Ryan's words", () => {
  const s = run(answered(), { type: "recordStart", heard: 1 }, { type: "noSpeech" });
  expect(s.phase).toBe("ready");
  expect(s.message).toBe(NO_SPEECH);
  expect(cutOf(s)).toBe(1);
});

test("a mic that did not start gives my turn back saying why, in red", () => {
  const s = run(answered(), { type: "recordStart", heard: 1 }, { type: "micFailed" });
  expect(s.phase).toBe("ready");
  expect(s.message).toBe(MIC_FAILED);
  expect(talkMessageIsError(s)).toBe(true);
  expect(cutOf(s)).toBe(1); // like 「취소」: the cut stays for the next turn
  const r = ready();
  expect(talkReduce(r, { type: "micFailed" })).toBe(r);
});

test("failures are said in red, as in the roleplay; no speech and a long turn are not", () => {
  const s0 = run(ready(), { type: "recordStart", heard: null }, { type: "recordStop" });
  const say = { text: "잘 안 들렸어요.", audio: key("h") };
  const down = talkReduce(s0, ev(s0, { type: "error", code: "claude_unavailable", say: null }));
  const lost = talkReduce(s0, { type: "failed", turn: s0.turn, message: "맥에 연결할 수 없어요." });
  const unheard = talkReduce(s0, ev(s0, { type: "error", code: "no_speech", say }));
  const tooLong = talkReduce(s0, ev(s0, { type: "error", code: "too_long", say }));
  const silent = run(ready(), { type: "recordStart", heard: null }, { type: "noSpeech" });
  for (const s of [down, lost]) expect(talkMessageIsError(s)).toBe(true);
  for (const s of [unheard, tooLong, silent, ready()]) expect(talkMessageIsError(s)).toBe(false);
  // speaking again clears it; an opening or ending that failed is red
  expect(talkMessageIsError(talkReduce(down, { type: "recordStart", heard: null }))).toBe(false);
  expect(talkMessageIsError(talkReduce(talkInitial, { type: "openFailed", message: "x" }))).toBe(true);
});

test("Claude down drops the half reply and keeps my bubble", () => {
  const s0 = run(ready(), { type: "recordStart", heard: null }, { type: "recordStop" });
  const s = run(
    s0,
    ev(s0, heardE),
    ev(s0, { type: "text", delta: "Nice" }),
    ev(s0, { type: "error", code: "claude_unavailable", say: { text: "지금은 대답할 수 없어요.", audio: key("g") } }),
  );
  expect(s.phase).toBe("ready");
  expect(s.pending).toBe("");
  expect(s.message).toBe("지금은 대답할 수 없어요.");
  expect(s.bubbles.map((b) => b.kind)).toEqual(["ryan", "me"]);
  const bare = run(s0, ev(s0, { type: "error", code: "claude_unavailable", say: null }));
  expect(bare.message).toBe("지금은 라이언이 대답할 수 없어요. 맥의 인터넷 연결을 확인해 주세요.");
});

test("a failed request gives my turn back", () => {
  const s0 = run(ready(), { type: "recordStart", heard: null }, { type: "recordStop" });
  const s = talkReduce(s0, { type: "failed", turn: s0.turn, message: "맥에 연결할 수 없어요." });
  expect(s.phase).toBe("ready");
  expect(s.message).toBe("맥에 연결할 수 없어요.");
});

test("ending only from my turn or while Ryan speaks", () => {
  expect(canEnd(ready())).toBe(true);
  expect(canEnd(opened())).toBe(true);
  const s = answered();
  const cut = talkReduce(s, { type: "endStart", heard: 1 });
  expect(cut.phase).toBe("ending");
  expect(cutOf(cut)).toBe(1);
  for (const bad of [
    talkInitial,
    talkReduce(ready(), { type: "recordStart", heard: null }),
    run(ready(), { type: "recordStart", heard: null }, { type: "recordStop" }),
  ]) {
    expect(canEnd(bad)).toBe(false);
    expect(talkReduce(bad, { type: "endStart", heard: null })).toBe(bad);
  }
});

test("ending moves past the turn Ryan is answering: its late sounds and events are dropped", () => {
  // 「대화 끝내기」 while Ryan speaks: the reply's stream is still open and its later sentences' sounds come in while
  // the fixes are made (spec 6 「라이언 소리를 멈추고」). The screen plays a sound only for the current turn (`isCurrent`)
  const s0 = answered();
  const s = talkReduce(s0, { type: "endStart", heard: 1 });
  expect(s.turn).toBe(s0.turn + 1);
  expect(isCurrent(s, s0.turn)).toBe(false);
  expect(cutOf(s)).toBe(1); // the cut still goes with the end
  for (const e of [{ type: "audio", key: key("e") }, { type: "done", idx: 2 }] as TalkEvent[]) {
    expect(talkReduce(s, { type: "event", turn: s0.turn, e })).toBe(s);
  }
  expect(talkReduce(s, { type: "failed", turn: s0.turn, message: "x" })).toBe(s);
  // from my turn too, as 「🎤 말하기」 does; a second end does not move it again
  const r = ready();
  const fromReady = talkReduce(r, { type: "endStart", heard: null });
  expect(fromReady.turn).toBe(r.turn + 1);
  expect(talkReduce(fromReady, { type: "endStart", heard: null }).turn).toBe(fromReady.turn);
});

const end: TalkEnd = { items: [], say: null };

test("ended shows the fixes", () => {
  const s = run(ready(), { type: "endStart", heard: null }, { type: "ended", end });
  expect(s.phase).toBe("fixes");
  expect(s.end).toBe(end);
});

test("a failed end can be tried again", () => {
  const e = run(ready(), { type: "endStart", heard: null }, { type: "endFailed", message: "안 돼요" });
  expect(e.phase).toBe("error");
  expect(e.errorFrom).toBe("ending");
  expect(e.message).toBe("안 돼요");
  const s = talkReduce(e, { type: "retry" });
  expect(s.phase).toBe("ending");
  expect(s.message).toBeNull();
});

test("a failed opening can be tried again", () => {
  const e = talkReduce(talkInitial, { type: "openFailed", message: "서버가 옛 것이에요" });
  expect(e.phase).toBe("error");
  expect(e.errorFrom).toBe("opening");
  const s = talkReduce(e, { type: "retry" });
  expect(s.phase).toBe("opening");
  expect(s.errorFrom).toBeNull();
  expect(talkReduce(s, { type: "retry" })).toBe(s);
});

test("turnNo counts my turns", () => {
  expect(turnNo(ready())).toBe(1);
  const s0 = run(ready(), { type: "recordStart", heard: null }, { type: "recordStop" });
  expect(turnNo(s0)).toBe(1);
  const heard = talkReduce(s0, ev(s0, heardE));
  expect(turnNo(heard)).toBe(1);
  expect(turnNo(answered())).toBe(2);
});

test("englishTurns leaves Korean turns out", () => {
  const s0 = run(ready(), { type: "recordStart", heard: null }, { type: "recordStop" });
  const s = run(s0, ev(s0, heardE), ev(s0, { ...heardE, idx: 3, korean: true }));
  expect(s.bubbles.filter((b) => b.kind === "me")).toHaveLength(2);
  expect(englishTurns(s)).toBe(1);
});

test("heardCount is 0 before any sound and all once the last started", () => {
  expect(heardCount(parts, new Set())).toBe(0);
  expect(heardCount(parts, new Set([key("b")]))).toBe(2);
  expect(heardCount(parts, new Set([key("a"), key("b"), key("c")]))).toBe(3);
  expect(heardCount(parts, new Set([key("z")]))).toBe(0);
});

test("lineSounds plays a reply's parts in order and a line's own sound otherwise", () => {
  expect(lineSounds({ parts, audio: null })).toEqual([key("a"), key("b"), key("c")]);
  expect(lineSounds({ parts: null, audio: key("x") })).toEqual([key("x")]);
  expect(lineSounds({ parts: null, audio: null })).toEqual([]);
});

const withLines = (lines: Partial<ScriptLine>[]) => ({ ...roleplay, lines: lines as ScriptLine[] }) as Roleplay;
const L = (idx: number, speaker: "ryan" | "user", kind: ScriptLine["kind"], fixOf?: number): Partial<ScriptLine> => ({
  idx,
  speaker,
  kind,
  fix: fixOf === undefined ? null : { of: fixOf, said: "", why_ko: "", why_audio: null },
});

test("the line before a saved fix is Ryan's line before the turn it fixes", () => {
  const rp = withLines([L(0, "ryan", "reply"), L(1, "user", "turn"), L(2, "ryan", "reply"), L(3, "user", "turn"), L(4, "ryan", "reply"), L(5, "user", "turn"), L(6, "ryan", "reply"), L(7, "user", "fix", 5)]);
  expect(savedBefore(rp, rp.lines[7])?.idx).toBe(4);
});

test("the line before a saved fix skips Ryan's help lines", () => {
  const rp = withLines([L(0, "ryan", "reply"), L(1, "user", "ask"), L(2, "ryan", "help"), L(3, "user", "turn"), L(4, "user", "fix", 3)]);
  expect(savedBefore(rp, rp.lines[4])?.idx).toBe(0);
  const none = withLines([L(0, "ryan", "help"), L(1, "user", "turn"), L(2, "user", "fix", 1)]);
  expect(savedBefore(none, none.lines[2])).toBeUndefined();
});

test("a roleplay line keeps the line right before it", () => {
  const rp = withLines([L(0, "ryan", "script"), L(1, "user", "script"), L(2, "ryan", "script")]);
  expect(savedBefore(rp, rp.lines[1])?.idx).toBe(0);
  expect(savedBefore(rp, rp.lines[2])?.idx).toBe(1);
  expect(savedBefore(rp, rp.lines[0])).toBeUndefined();
});

test("a free talk is not played again from saved practice", () => {
  expect(replaysSituation(roleplay)).toBe(false);
  expect(replaysSituation(roleplayJson as unknown as Roleplay)).toBe(true);
  const old = { ...(roleplayJson as unknown as Roleplay) } as Partial<Roleplay>;
  delete old.kind;
  expect(replaysSituation(old as Roleplay)).toBe(true);
});
