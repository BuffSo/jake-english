import type { Hint, HintFull, Roleplay, Said, TalkEvent } from "../api/types";
import talkJson from "../../../contract/talk.json";
import {
  canAskFull,
  canAskHint,
  chanceReduce,
  chanceTarget,
  createSoheeChance,
  HINT_FAILED,
  hintSoundTag,
  lastReply,
  maySohee,
  soheeFullTag,
  soheeMayPlay,
  soheeTag,
  type ChanceDeps,
  type Chances,
} from "./soheeChance";
import { talkInitial, talkReduce, type TalkAction, type TalkState } from "./talk";

// made-up talk: Ryan's first question (line 0), my answer (1), his reply (2)
const key = (c: string) => c.repeat(64);
const parts: Said[] = [{ text: "What did you have for lunch?", audio: key("a") }];
const first = { ...(talkJson as unknown as Roleplay).lines[0], parts };
const roleplay = { ...(talkJson as unknown as Roleplay), lines: [first] } as Roleplay;
const run = (s: TalkState, ...as: TalkAction[]) => as.reduce(talkReduce, s);
const ev = (s: TalkState, e: TalkEvent): TalkAction => ({ type: "event", turn: s.turn, e });
const opened = () => run(talkInitial, { type: "opened", roleplay });
const ready = () => run(opened(), { type: "ryanDone" });
const recording = () => run(ready(), { type: "recordStart", heard: null });
const waiting = () => run(recording(), { type: "recordStop" });
// my turn spoken, Ryan's reply (line 2) in and played: my turn again, on his new line
function nextTurn(): TalkState {
  const s = waiting();
  return run(
    s,
    ev(s, { type: "heard", text: "I had a sandwich.", n: 1, idx: 1, korean: false }),
    ev(s, { type: "reply", idx: 2, kind: "reply", parts: [{ text: "Nice! Was it good?", audio: key("b") }] }),
    ev(s, { type: "done", idx: 2 }),
    { type: "ryanDone" },
  );
}

const hint: Hint = { meaning_ko: "점심에 뭘 먹었는지 물어요.", starters: ["I had…", "I usually eat…"] };
const full: HintFull = { text: "I had a sandwich at my desk.", say: { text: "이렇게 말해 봐요.", audio: key("f") } };
const asked = (c: Chances, idx = 0) => chanceReduce(c, { type: "asked", idx });
const hinted = (idx = 0) => chanceReduce(asked({}, idx), { type: "hint", idx, hint });

test("the hint can be asked once per Ryan line, on my turn only", () => {
  expect(chanceTarget(opened())).toBeNull(); // Ryan says his first question
  expect(canAskHint(opened(), {})).toBe(false);
  expect(chanceTarget(ready())).toBe(0);
  expect(canAskHint(ready(), {})).toBe(true);
  const thinking = asked({});
  expect(thinking[0]).toEqual({ idx: 0, step: "thinking" });
  expect(canAskHint(ready(), thinking)).toBe(false); // Sohee is thinking
  expect(canAskHint(ready(), hinted())).toBe(false); // used on this line
  expect(asked(hinted())).toEqual(hinted()); // a second ask changes nothing
  expect(canAskHint(recording(), {})).toBe(false);
  expect(canAskHint(waiting(), {})).toBe(false);
});

test("a failed hint can be asked again", () => {
  const failed = chanceReduce(asked({}), { type: "failed", idx: 0 });
  expect(failed[0]).toEqual({ idx: 0, step: "failed" });
  expect(canAskHint(ready(), failed)).toBe(true);
  expect(asked(failed)[0]).toEqual({ idx: 0, step: "thinking" });
  expect(HINT_FAILED).toBe("지금은 소희가 도와줄 수 없어요. 다시 눌러 볼까요?");
});

test("the full sentence only after the hint, once", () => {
  const s = ready();
  expect(canAskFull(s, undefined)).toBe(false);
  expect(canAskFull(s, asked({})[0])).toBe(false);
  const h = hinted();
  expect(canAskFull(s, h[0])).toBe(true);
  expect(canAskFull(recording(), h[0])).toBe(false); // my turn only
  const loading = chanceReduce(h, { type: "fullAsked", idx: 0 });
  expect(loading[0]).toEqual({ idx: 0, step: "fullLoading", hint });
  expect(canAskFull(s, loading[0])).toBe(false);
  const shown = chanceReduce(loading, { type: "full", idx: 0, full });
  expect(shown[0]).toEqual({ idx: 0, step: "full", hint, full });
  expect(canAskFull(s, shown[0])).toBe(false);
  expect(canAskHint(s, shown)).toBe(false);
  // a failed full sentence keeps the hint and may be asked again
  const failed = chanceReduce(loading, { type: "fullFailed", idx: 0 });
  expect(failed[0]).toEqual({ idx: 0, step: "hint", hint, fullFailed: true });
  expect(canAskFull(s, failed[0])).toBe(true);
  expect(chanceReduce(failed, { type: "fullAsked", idx: 0 })[0]).toEqual({ idx: 0, step: "fullLoading", hint });
  // what comes out of turn is dropped
  expect(chanceReduce(h, { type: "full", idx: 0, full })).toBe(h);
  expect(chanceReduce(asked({}), { type: "fullAsked", idx: 0 })[0].step).toBe("thinking");
});

test("late hint sound does not play while recording", () => {
  expect(maySohee(recording())).toBe(false);
  expect(maySohee(waiting())).toBe(false);
  expect(maySohee(opened())).toBe(false); // over Ryan
  expect(maySohee(ready())).toBe(true);
  expect(soheeMayPlay(ready(), 0, false)).toBe(true);
  expect(soheeMayPlay(ready(), 0, true)).toBe(false); // something plays
  expect(soheeMayPlay(recording(), 0, false)).toBe(false);
});

test("a hint for an older line stays but is not the target", () => {
  const s = nextTurn();
  expect(lastReply(s)).toBe(2);
  expect(chanceTarget(s)).toBe(2);
  const c = hinted(0);
  expect(c[0].step).toBe("hint"); // stays in the talk
  expect(canAskHint(s, c)).toBe(true); // the new line has none yet
  expect(canAskFull(s, c[0])).toBe(false);
  expect(soheeMayPlay(s, 0, false)).toBe(false); // her voice for the old line would land in this turn
  expect(soheeMayPlay(s, 2, false)).toBe(true);
  // the line stays the latest reply while I record and wait, so its bubble stays open
  expect(lastReply(waiting())).toBe(0);
});

test("the tags of her voice and of Ryan's sounds", () => {
  expect(soheeTag(2)).toBe("sohee:2");
  expect(soheeFullTag(2)).toBe("sohee:2:full");
  expect(hintSoundTag(2, 1)).toBe("hint:2:1");
});

// The screen's wiring without React: the requests, the gate and when her voice plays
function setup(talk: TalkState = ready()) {
  const at = { talk, playing: false };
  const pending: Record<string, { resolve: (v: unknown) => void; reject: (e: Error) => void }[]> = {};
  const wait = <T,>(name: string) =>
    new Promise<T>((resolve, reject) => {
      (pending[name] ??= []).push({ resolve: resolve as (v: unknown) => void, reject });
    });
  const calls = { getHint: 0, getHintAudio: 0, showFull: 0, getHintSound: 0 };
  const played: [string, string][] = [];
  let got: Chances = {};
  const deps: ChanceDeps = {
    getHint: () => (calls.getHint++, wait<Hint>("hint")),
    getHintAudio: () => (calls.getHintAudio++, wait<{ audio: string }>("audio")),
    showFull: () => (calls.showFull++, wait<HintFull>("full")),
    getHintSound: () => (calls.getHintSound++, wait<{ audio: string }>("sound")),
    talk: () => at.talk,
    playing: () => at.playing,
    play: (audio, tag) => played.push([audio, tag]),
    onChange: (c) => (got = c),
  };
  const sc = createSoheeChance(deps);
  const flush = () => new Promise((r) => setTimeout(r, 0));
  const answer = async (name: string, v: unknown) => {
    pending[name].shift()!.resolve(v);
    await flush();
  };
  const fail = async (name: string) => {
    pending[name].shift()!.reject(new Error("503"));
    await flush();
  };
  return { at, sc, calls, played, chances: () => got, answer, fail, flush };
}

describe("the Sohee chance on screen", () => {
  test("a double tap asks for the hint once, and her voice plays on my turn", async () => {
    const t = setup();
    void t.sc.ask();
    void t.sc.ask(); // the second tap of a double tap, before the redraw
    expect(t.calls.getHint).toBe(1);
    expect(t.chances()[0].step).toBe("thinking");
    await t.answer("hint", hint);
    expect(t.chances()[0]).toEqual({ idx: 0, step: "hint", hint });
    await t.answer("audio", { audio: key("s") });
    expect(t.played).toEqual([[key("s"), "sohee:0"]]);
    void t.sc.ask();
    expect(t.calls.getHint).toBe(1); // used on this line
  });

  test("a hint that comes while I record stays quiet, and a tap on it plays it later", async () => {
    const t = setup();
    void t.sc.ask();
    t.at.talk = recording();
    await t.answer("hint", hint);
    expect(t.chances()[0].step).toBe("hint"); // the bubble shows it while I speak
    expect(t.calls.getHintAudio).toBe(0); // not made while she could not play
    expect(t.played).toEqual([]);
    t.at.talk = ready();
    void t.sc.replay(0, "hint");
    await t.answer("audio", { audio: key("s") });
    expect(t.played).toEqual([[key("s"), "sohee:0"]]);
  });

  test("her voice that comes while I record or Ryan speaks is not played", async () => {
    const t = setup();
    void t.sc.ask();
    await t.answer("hint", hint);
    t.at.talk = recording(); // 「🎤 말하기」 while her sound was being made
    await t.answer("audio", { audio: key("s") });
    expect(t.played).toEqual([]);
    const u = setup();
    u.at.playing = true; // 「🔊 다시 듣기」 plays Ryan
    void u.sc.ask();
    await u.answer("hint", hint);
    expect(u.calls.getHintAudio).toBe(0);
    expect(u.played).toEqual([]);
  });

  test("a late hint for an older line does not land in the next turn", async () => {
    const t = setup();
    void t.sc.ask();
    t.at.talk = nextTurn();
    await t.answer("hint", hint);
    expect(t.chances()[0].step).toBe("hint");
    expect(t.calls.getHintAudio).toBe(0);
    expect(t.played).toEqual([]);
    void t.sc.ask(); // the new line
    expect(t.calls.getHint).toBe(2);
    expect(t.chances()[2].step).toBe("thinking");
  });

  test("a failure shows and the next tap asks again", async () => {
    const t = setup();
    void t.sc.ask();
    await t.fail("hint");
    expect(t.chances()[0].step).toBe("failed");
    void t.sc.ask();
    expect(t.calls.getHint).toBe(2);
  });

  test("the full sentence once, with her 「이렇게 말해 봐요.」", async () => {
    const t = setup();
    void t.sc.askFull(0);
    expect(t.calls.showFull).toBe(0); // not before the hint
    void t.sc.ask();
    await t.answer("hint", hint);
    await t.answer("audio", { audio: key("s") });
    void t.sc.askFull(0);
    void t.sc.askFull(0);
    expect(t.calls.showFull).toBe(1);
    await t.answer("full", full);
    expect(t.chances()[0]).toEqual({ idx: 0, step: "full", hint, full });
    expect(t.played).toEqual([
      [key("s"), "sohee:0"],
      [full.say.audio, "sohee:0:full"],
    ]);
    void t.sc.askFull(0);
    expect(t.calls.showFull).toBe(1);
  });

  test("a failed full sentence can be asked again", async () => {
    const t = setup();
    void t.sc.ask();
    t.at.playing = true;
    await t.answer("hint", hint);
    void t.sc.askFull(0);
    await t.fail("full");
    expect(t.chances()[0]).toEqual({ idx: 0, step: "hint", hint, fullFailed: true });
    void t.sc.askFull(0);
    expect(t.calls.showFull).toBe(2);
    await t.answer("full", full);
    expect(t.played).toEqual([]); // Ryan was playing
  });

  test("a tap on her line plays only on my turn", async () => {
    const t = setup();
    void t.sc.ask();
    t.at.playing = true;
    await t.answer("hint", hint);
    t.at.talk = recording();
    void t.sc.replay(0, "hint");
    expect(t.calls.getHintAudio).toBe(0);
    t.at.talk = ready();
    void t.sc.replay(0, "hint"); // a tap stops what plays
    await t.answer("audio", { audio: key("s") });
    expect(t.played).toEqual([[key("s"), "sohee:0"]]);
    void t.sc.replay(0, "hint");
    await t.flush();
    expect(t.calls.getHintAudio).toBe(1); // kept
    expect(t.played.length).toBe(2);
  });

  test("Ryan's sounds of the openers are asked once each; a failure asks again", async () => {
    const t = setup();
    const a = t.sc.ryanSound(0, 1);
    const b = t.sc.ryanSound(0, 1);
    expect(t.calls.getHintSound).toBe(1);
    await t.answer("sound", { audio: key("r") });
    expect(await a).toBe(key("r"));
    expect(await b).toBe(key("r"));
    const c = t.sc.ryanSound(0, 0);
    await t.fail("sound");
    expect(await c).toBeNull();
    void t.sc.ryanSound(0, 0);
    expect(t.calls.getHintSound).toBe(3);
  });

  test("nothing changes or plays once the screen is gone", async () => {
    const t = setup();
    void t.sc.ask();
    t.sc.stop();
    await t.answer("hint", hint);
    expect(t.chances()).toEqual({ 0: { idx: 0, step: "thinking" } });
    expect(t.played).toEqual([]);
  });
});
