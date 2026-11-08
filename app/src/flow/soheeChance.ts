// 「소희 찬스」 in the free talk (spec free-talk-design 9): Sohee whispers a hint for Ryan's last line (the meaning in
// Korean and English openers), and on request the full sentence. A chance belongs to one Ryan line and stays in the
// talk. The rules are pure functions; `createSoheeChance` does the requests and her voice without React, so the
// timing can be tested (as `koFetch` does for her interpretation).
//
// Step 1 once per line, on my turn, then step 2 once (spec 9 「누를 수 있는 때」, 「2단계」). A failure of either
// step can be asked again. Her voice plays by herself only on my turn with nothing playing, and only for the line she
// was asked about: a hint that comes after Ryan's next reply stays quiet (spec 「확인 방법」: a late hint must not land
// in the next turn).
import type { Hint, HintFull } from "../api/types";
import { createGate } from "./gate";
import { mayListenTalk, type TalkState } from "./talk";

export type Chance =
  | { idx: number; step: "thinking" }
  | { idx: number; step: "failed" }
  // fullFailed: 「전체 문장 보기」 failed; the hint stays and it may be asked again
  | { idx: number; step: "hint"; hint: Hint; fullFailed?: boolean }
  | { idx: number; step: "fullLoading"; hint: Hint }
  | { idx: number; step: "full"; hint: Hint; full: HintFull };
export type Chances = Record<number, Chance>;

export type ChanceAction =
  | { type: "asked"; idx: number }
  | { type: "hint"; idx: number; hint: Hint }
  | { type: "failed"; idx: number }
  | { type: "fullAsked"; idx: number }
  | { type: "full"; idx: number; full: HintFull }
  | { type: "fullFailed"; idx: number };

export const HINT_FAILED = "지금은 소희가 도와줄 수 없어요. 다시 눌러 볼까요?";

// Her voice: the hint (its Korean line and 「이렇게 시작해 보세요.」) and step 2's 「이렇게 말해 봐요.」, apart so only
// the one playing bounces its 🔊. Ryan's English model sounds of the openers and the full sentence (`n` = their count).
export const soheeTag = (idx: number) => `sohee:${idx}`;
export const soheeFullTag = (idx: number) => `sohee:${idx}:full`;
export const hintSoundTag = (idx: number, n: number) => `hint:${idx}:${n}`;

// Ryan's latest reply, whatever the phase: its Sohee bubble stays open while I record and wait, and folds once a newer
// reply comes. His fixed `help` line after a Korean turn is not a reply, so the chance stays on the reply before it.
export function lastReply(s: TalkState): number | null {
  for (let i = s.bubbles.length - 1; i >= 0; i -= 1) {
    const b = s.bubbles[i];
    if (b.kind === "ryan") return b.idx;
  }
  return null;
}

// the line 「소희 찬스」 is for: Ryan's latest reply, once he has said it and while my turn waits
export const chanceTarget = (s: TalkState): number | null => (mayListenTalk(s) ? lastReply(s) : null);

// the big button: a target with no chance on it yet, or a failed one
export function canAskHint(s: TalkState, c: Chances): boolean {
  const t = chanceTarget(s);
  if (t === null) return false;
  const got = c[t];
  return got === undefined || got.step === "failed";
}

// 「그래도 어려우면 전체 문장 보기」: after the hint, once, on the target and my turn
export const canAskFull = (s: TalkState, c: Chance | undefined): boolean =>
  c !== undefined && c.step === "hint" && chanceTarget(s) === c.idx;

// her voice plays only on my turn, nothing recording, never over Ryan (as her interpretation, `useInterpret`)
export const maySohee = (s: TalkState) => mayListenTalk(s);

// by herself: on my turn, nothing playing, and only for the line she was asked about
export const soheeMayPlay = (s: TalkState, idx: number, playing: boolean) =>
  maySohee(s) && chanceTarget(s) === idx && !playing;

// Each step moves only from the one before it; what comes out of turn changes nothing
export function chanceReduce(c: Chances, a: ChanceAction): Chances {
  const now = c[a.idx];
  const put = (next: Chance): Chances => ({ ...c, [a.idx]: next });
  switch (a.type) {
    case "asked":
      return now === undefined || now.step === "failed" ? put({ idx: a.idx, step: "thinking" }) : c;
    case "hint":
      return now?.step === "thinking" ? put({ idx: a.idx, step: "hint", hint: a.hint }) : c;
    case "failed":
      return now?.step === "thinking" ? put({ idx: a.idx, step: "failed" }) : c;
    case "fullAsked":
      return now?.step === "hint" ? put({ idx: a.idx, step: "fullLoading", hint: now.hint }) : c;
    case "full":
      return now?.step === "fullLoading" ? put({ idx: a.idx, step: "full", hint: now.hint, full: a.full }) : c;
    case "fullFailed":
      return now?.step === "fullLoading" ? put({ idx: a.idx, step: "hint", hint: now.hint, fullFailed: true }) : c;
  }
}

export type ChanceDeps = {
  getHint: (idx: number) => Promise<Hint>;
  getHintAudio: (idx: number) => Promise<{ audio: string }>;
  showFull: (idx: number) => Promise<HintFull>;
  getHintSound: (idx: number, n: number) => Promise<{ audio: string }>;
  talk: () => TalkState; // the talk as it is now, not as last drawn
  playing: () => boolean;
  play: (audio: string, tag: string) => void; // stops what plays and plays her voice
  onChange: (c: Chances) => void;
};

export type SoheeChance = {
  ask: () => Promise<void>; // 「소희 찬스」 on the target
  askFull: (idx: number) => Promise<void>; // 「전체 문장 보기」
  // a tap on her line: plays on my turn (stopping what plays, as a bubble's 🔊), making the sound first if missing
  replay: (idx: number, which: "hint" | "full") => Promise<void>;
  ryanSound: (idx: number, n: number) => Promise<string | null>; // Ryan's model sound; null when it could not be made
  start: () => void;
  stop: () => void; // the screen went away: nothing plays or changes after this
};

export function createSoheeChance(deps: ChanceDeps): SoheeChance {
  let chances: Chances = {};
  let alive = true;
  // one ask per button and line at a time (REVIEW.md 「앱 화면」): the hint calls Claude. Per line, so a hint for an
  // older line still on its way does not hold up the next one.
  const gates: Record<string, ReturnType<typeof createGate>> = {};
  const gate = (k: string) => (gates[k] ??= createGate());
  // sounds asked for once and kept; a failure is forgotten, so the next tap asks again
  const made: Record<string, Promise<string | null>> = {};
  const once = (k: string, get: () => Promise<{ audio: string }>) =>
    (made[k] ??= get()
      .then((r) => r.audio)
      .catch(() => {
        delete made[k];
        return null;
      }));

  function act(a: ChanceAction) {
    if (!alive) return;
    chances = chanceReduce(chances, a);
    deps.onChange(chances);
  }

  function voice(idx: number, which: "hint" | "full"): Promise<string | null> {
    if (which === "hint") return once(soheeTag(idx), () => deps.getHintAudio(idx));
    const c = chances[idx];
    return Promise.resolve(c?.step === "full" ? c.full.say.audio : null);
  }

  // By herself when the step's text comes. The sound is made only when it could play now: made while I record or
  // Ryan speaks, her urgent sound would wait ahead of his sentences in the voice worker (as `koFetch`).
  async function speak(idx: number, which: "hint" | "full") {
    const go = () => alive && soheeMayPlay(deps.talk(), idx, deps.playing());
    if (!go()) return;
    const audio = await voice(idx, which);
    if (audio && go()) deps.play(audio, which === "hint" ? soheeTag(idx) : soheeFullTag(idx));
  }

  return {
    ask: async () => {
      const idx = chanceTarget(deps.talk());
      if (idx === null) return;
      await gate(`hint:${idx}`).run(async () => {
        if (!alive || !canAskHint(deps.talk(), chances)) return;
        act({ type: "asked", idx });
        try {
          act({ type: "hint", idx, hint: await deps.getHint(idx) });
        } catch {
          act({ type: "failed", idx });
          return;
        }
        void speak(idx, "hint");
      });
    },
    askFull: async (idx) => {
      await gate(`full:${idx}`).run(async () => {
        if (!alive || !canAskFull(deps.talk(), chances[idx])) return;
        act({ type: "fullAsked", idx });
        try {
          act({ type: "full", idx, full: await deps.showFull(idx) });
        } catch {
          act({ type: "fullFailed", idx });
          return;
        }
        void speak(idx, "full");
      });
    },
    replay: async (idx, which) => {
      const go = () => alive && maySohee(deps.talk());
      if (!go()) return;
      const audio = await voice(idx, which);
      if (audio && go()) deps.play(audio, which === "hint" ? soheeTag(idx) : soheeFullTag(idx));
    },
    ryanSound: (idx, n) => once(hintSoundTag(idx, n), () => deps.getHintSound(idx, n)),
    start: () => {
      alive = true;
    },
    stop: () => {
      alive = false;
    },
  };
}
