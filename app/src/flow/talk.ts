// The free-talk screen's flow as a pure reducer (spec free-talk-design 2, 6). The screen does the sounds and requests
// and sends what happened as actions; this decides what the screen shows.
//
// Spec 2: Ryan asks the first question and the first turn is mine. The mic may cut Ryan off once his text is complete
// (phase `ryan`): `recordStart` carries how many of his sentences had started, kept on his bubble (`heard`) so the
// Mac is told what I did not hear, and a cancelled recording leaves it cut. `turn` grows with every recording, so a
// stream I left behind (a cut-off answer's late sounds, a late reply after 「뒤로」) is dropped by `isCurrent`.
// Spec 6: 「대화 끝내기」 works from my turn or while Ryan speaks (`canEnd`), takes the same cut, and shows the fixes.
// 「영어 차례가 없으면 첫 화면」: with no English turn there is nothing to review, so the screen decides by
// `englishTurns` and goes back instead of asking the Mac for fixes.
import type { Roleplay, Said, ScriptLine, TalkEnd, TalkEvent, TryRef } from "../api/types";
import type { ErrorCode } from "../api/client";
import { NO_SPEECH, messageFor } from "./state";

export type TalkPhase = "opening" | "ryan" | "ready" | "recording" | "waiting" | "replying" | "ending" | "fixes" | "error";

export type TalkBubble =
  | { kind: "ryan"; idx: number; text: string; parts: Said[]; heard: number | null }
  | { kind: "help"; idx: number; text: string; audio: string | null }
  | { kind: "me"; idx: number; text: string; rec: TryRef; korean: boolean };

export type TalkState = {
  phase: TalkPhase;
  roleplay: Roleplay | null;
  bubbles: TalkBubble[];
  turn: number; // grows with every recording; events carry the number of the turn they belong to
  heardIn: boolean; // my words came back in this turn
  pending: string; // Ryan's text so far, before his line is whole
  done: boolean; // everything Ryan has to say is in
  message: string | null;
  micUsed: boolean; // for the first-turn hint 「🎤를 누르고 말하세요」
  end: TalkEnd | null;
  errorFrom: "opening" | "ending" | null;
};

export const talkInitial: TalkState = {
  phase: "opening",
  roleplay: null,
  bubbles: [],
  turn: 0,
  heardIn: false,
  pending: "",
  done: false,
  message: null,
  micUsed: false,
  end: null,
  errorFrom: null,
};

export type TalkAction =
  | { type: "opened"; roleplay: Roleplay }
  | { type: "openFailed"; message: string }
  | { type: "retry" }
  | { type: "ryanDone" }
  | { type: "recordStart"; heard: number | null }
  | { type: "recordCancel" }
  | { type: "noSpeech" }
  | { type: "recordStop" }
  | { type: "event"; turn: number; e: TalkEvent }
  | { type: "failed"; turn: number; message: string }
  | { type: "endStart"; heard: number | null }
  | { type: "ended"; end: TalkEnd }
  | { type: "endFailed"; message: string };

export const canSpeak = (s: TalkState) => s.phase === "ready" || s.phase === "ryan";
export const canEnd = canSpeak;
// the 🔊, interpretation and my recording of past bubbles: only on my turn, not over Ryan's sound
export const mayListenTalk = (s: TalkState) => s.phase === "ready";
export const isCurrent = (s: TalkState, turn: number) => turn === s.turn;
export const englishTurns = (s: TalkState) => s.bubbles.filter((b) => b.kind === "me" && !b.korean).length;
// 「N번째」: my turns so far, plus the one being taken until my words come back
export const turnNo = (s: TalkState) =>
  s.bubbles.filter((b) => b.kind === "me").length + ((s.phase === "waiting" || s.phase === "replying") && s.heardIn ? 0 : 1);

// sentences up to the last one whose sound has started; 0 when none has
export function heardCount(parts: Said[], started: ReadonlySet<string>): number {
  let n = 0;
  parts.forEach((p, i) => {
    if (started.has(p.audio)) n = i + 1;
  });
  return n;
}

// How much of Ryan's last line I did not hear. The Mac takes it only when his reply is the last line (spec 2).
export function cutOf(s: TalkState): number | null {
  const last = s.bubbles[s.bubbles.length - 1];
  return last && last.kind === "ryan" ? last.heard : null;
}

export function lineSounds(line: Pick<ScriptLine, "parts" | "audio">): string[] {
  if (line.parts) return line.parts.map((p) => p.audio);
  return line.audio ? [line.audio] : [];
}

// the cut kept on Ryan's last bubble; a cut at or past the whole answer, or none, is no cut
function withCut(s: TalkState, heard: number | null): TalkBubble[] {
  const last = s.bubbles[s.bubbles.length - 1];
  if (s.phase !== "ryan" || !last || last.kind !== "ryan") return s.bubbles;
  const cut = heard !== null && heard < last.parts.length ? heard : null;
  return [...s.bubbles.slice(0, -1), { ...last, heard: cut }];
}

const joined = (parts: Said[]) => parts.map((p) => p.text).join(" ");

export function talkReduce(s: TalkState, a: TalkAction): TalkState {
  switch (a.type) {
    case "opened": {
      const line = a.roleplay.lines[0];
      const bubble: TalkBubble = { kind: "ryan", idx: line.idx, text: line.text, parts: line.parts ?? [], heard: null };
      return { ...s, phase: "ryan", roleplay: a.roleplay, bubbles: [bubble], done: true, message: null, errorFrom: null };
    }
    case "openFailed":
      return { ...s, phase: "error", message: a.message, errorFrom: "opening" };
    case "endFailed":
      return { ...s, phase: "error", message: a.message, errorFrom: "ending" };
    case "retry":
      if (s.phase !== "error" || !s.errorFrom) return s;
      return { ...s, phase: s.errorFrom, message: null, errorFrom: null };
    case "ryanDone":
      return s.phase === "ryan" && s.done ? { ...s, phase: "ready" } : s;
    case "recordStart":
      if (!canSpeak(s)) return s;
      return { ...s, phase: "recording", bubbles: withCut(s, a.heard), turn: s.turn + 1, micUsed: true, message: null };
    case "recordCancel":
      return s.phase === "recording" ? { ...s, phase: "ready" } : s;
    case "noSpeech":
      return s.phase === "recording" ? { ...s, phase: "ready", message: NO_SPEECH } : s;
    case "recordStop":
      return s.phase === "recording" ? { ...s, phase: "waiting", heardIn: false, pending: "", done: false } : s;
    case "event": {
      if (!isCurrent(s, a.turn) || !s.roleplay) return s;
      if (s.phase !== "waiting" && s.phase !== "replying" && s.phase !== "ryan") return s;
      const e = a.e;
      switch (e.type) {
        case "heard": {
          const me: TalkBubble = {
            kind: "me",
            idx: e.idx,
            text: e.text,
            rec: { rp_id: s.roleplay.id, idx: e.idx, n: e.n },
            korean: e.korean,
          };
          return { ...s, bubbles: [...s.bubbles, me], heardIn: true };
        }
        case "text":
          return { ...s, phase: s.phase === "waiting" ? "replying" : s.phase, pending: s.pending + e.delta };
        case "reply": {
          const bubble: TalkBubble =
            e.kind === "help"
              ? { kind: "help", idx: e.idx, text: joined(e.parts), audio: e.parts[0]?.audio ?? null }
              : { kind: "ryan", idx: e.idx, text: s.pending.trim() || joined(e.parts), parts: e.parts, heard: null };
          return { ...s, phase: "ryan", bubbles: [...s.bubbles, bubble], pending: "" };
        }
        case "done":
          return { ...s, done: true };
        case "error":
          return {
            ...s,
            phase: "ready",
            pending: "",
            message: messageFor(e.code as ErrorCode, e.say ?? undefined),
          };
        default:
          return s; // `audio` only tells the screen to preload
      }
    }
    case "failed":
      if (!isCurrent(s, a.turn)) return s;
      if (s.phase !== "waiting" && s.phase !== "replying" && s.phase !== "ryan") return s;
      return { ...s, phase: "ready", pending: "", message: a.message };
    case "endStart":
      if (!canEnd(s)) return s;
      return { ...s, phase: "ending", bubbles: withCut(s, a.heard), message: null };
    case "ended":
      return s.phase === "ending" ? { ...s, phase: "fixes", end: a.end } : s;
  }
}
