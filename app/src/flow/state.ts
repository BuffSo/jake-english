// Screen flow as a reducer, so taps that arrive at the wrong moment (double taps, taps while Ryan is
// still talking) are ignored in one place.
import type { ErrorCode } from "../api/client";
import type { AttemptEvent, AttemptMode, Progress, Roleplay, Said, ScriptLine } from "../api/types";

export type Screen = "home" | "situation" | "roleplay" | "end";
export type Phase = "loading" | "ryan" | "ready" | "recording" | "evaluating" | "evaluated" | "error";
// a learner bubble keeps the script line next to what was heard (spec roleplay-practice 2)
export type Bubble = { kind: "ryan" | "user" | "feedback"; text: string; idx?: number; script?: string };
// Practice from the end screen: the learner's lines again (mine) or Ryan's lines to follow (shadow), in order.
// 「이 줄 다시」 is mine with one line.
export type Practice = { kind: "mine" | "shadow"; order: number[]; at: number };

export type State = {
  screen: Screen;
  roleplay: Roleplay | null;
  jake: Said | null; // the recommended situation in Jake's voice, shown on top of the roleplay to hear again
  idx: number;
  mode: AttemptMode;
  progress: Progress | null; // 「내 대사 no/total」 from the server, roleplay only
  phase: Phase;
  line: ScriptLine | null;
  // the line's three-line notes are open: each line starts plain and opens only when asked (spec roleplay-practice 8)
  reading: boolean;
  seen: Record<number, ScriptLine>;
  heard: string | null;
  feedback: string;
  reply: ScriptLine | null;
  nextIdx: number | null;
  message: string | null;
  errorFrom: "loading" | "evaluating" | null;
  practice: Practice | null;
  closingPlayed: boolean; // the end screen's closing words are said once, not again after each practice
  history: Bubble[];
};

export type Action =
  | { type: "home" }
  | { type: "back" }
  | { type: "chooseRoleplay" }
  | { type: "created"; roleplay: Roleplay; jake?: Said | null }
  | { type: "lineLoaded"; line: ScriptLine; progress?: Progress }
  | { type: "lineMissing" }
  | { type: "ryanDone" }
  | { type: "recordStart" }
  | { type: "recordStop" }
  | { type: "recordCancel" }
  | { type: "event"; e: AttemptEvent }
  | { type: "failed"; code: ErrorCode; say?: { text: string } }
  | { type: "retry" }
  | { type: "again" }
  | { type: "next" }
  | { type: "startPractice"; kind: "mine" | "shadow"; order: number[] }
  | { type: "restarted"; roleplay: Roleplay }
  | { type: "closingPlayed" }
  | { type: "toggleReading" };

export const initial: State = {
  screen: "home",
  roleplay: null,
  jake: null,
  idx: 0,
  mode: "turn",
  progress: null,
  phase: "loading",
  line: null,
  reading: false,
  seen: {},
  heard: null,
  feedback: "",
  reply: null,
  nextIdx: null,
  message: null,
  errorFrom: null,
  practice: null,
  closingPlayed: false,
  history: [],
};

export const OFFLINE = "맥에 연결할 수 없어요. 맥과 인터넷 연결을 확인해 주세요.";

function messageFor(code: ErrorCode, say?: { text: string }): string {
  if (say?.text) return say.text;
  if (code === "offline") return OFFLINE;
  if (code === "claude_unavailable") return "지금은 라이언이 대답할 수 없어요. 맥의 인터넷 연결을 확인해 주세요.";
  return "문제가 생겼어요. 다시 해 볼까요?";
}

// The learner's own turn with nothing playing for the flow: replaying a sound (Jake's line) may clear the
// queue then. In Ryan's turn the queue's idle callback moves the roleplay on, and clearing would drop it.
export function canReplay(p: Phase): boolean {
  return p === "ready" || p === "evaluated";
}

const freshTurn = { heard: null, feedback: "", reply: null, message: null, errorFrom: null } as const;

// leaving a practice: back on the end screen, ready for the next one
function toEnd(s: State): State {
  return { ...s, ...freshTurn, screen: "end", practice: null, mode: "turn" };
}

// What was said in this turn, as conversation bubbles (what the learner said, Ryan's feedback, Ryan's reply).
function exchange(s: State): Bubble[] {
  return [
    ...(s.heard ? [{ kind: "user" as const, text: s.heard, script: s.line?.text }] : []),
    ...(s.feedback ? [{ kind: "feedback" as const, text: s.feedback }] : []),
    ...(s.reply ? [{ kind: "ryan" as const, text: s.reply.text, idx: s.reply.idx }] : []),
  ];
}

export function reduce(s: State, a: Action): State {
  switch (a.type) {
    case "home":
      return { ...initial };
    case "back":
      // the on-screen back button and the phone's back key: the screen before this one
      if (s.screen === "situation") return { ...initial };
      if (s.screen === "roleplay" && s.practice) return toEnd(s);
      if (s.screen === "roleplay" || s.screen === "end") return { ...initial, screen: "situation" };
      return s;
    case "chooseRoleplay":
      return { ...initial, screen: "situation" };
    case "created":
      if (s.screen !== "situation") return s; // a script that comes back after the learner left
      return { ...initial, screen: "roleplay", roleplay: a.roleplay, jake: a.jake ?? null, phase: "loading" };
    case "lineLoaded":
      if (s.phase !== "loading") return s;
      return {
        ...s,
        ...freshTurn,
        line: a.line,
        reading: false,
        seen: { ...s.seen, [a.line.idx]: a.line },
        // in shadow practice Ryan's line is the learner's to say, with or without its sound
        phase: a.line.speaker === "ryan" && s.mode !== "shadow" ? "ryan" : "ready",
        nextIdx: s.mode === "retry" ? s.nextIdx : null,
        progress: a.progress ?? s.progress,
      };
    case "lineMissing":
      return { ...s, screen: "end" };
    case "ryanDone":
      if (s.phase !== "ryan" || !s.line) return s;
      return { ...s, history: [...s.history, { kind: "ryan", text: s.line.text, idx: s.line.idx }], idx: s.idx + 1, phase: "loading" };
    case "recordStart":
      if (s.phase !== "ready" && s.phase !== "evaluated") return s;
      return { ...s, phase: "recording", message: null };
    case "recordCancel":
      return s.phase === "recording" ? { ...s, phase: "ready" } : s;
    case "recordStop":
      if (s.phase !== "recording") return s;
      return { ...s, ...freshTurn, phase: "evaluating" };
    case "event": {
      if (s.phase !== "evaluating") return s;
      const e = a.e;
      if (e.type === "heard") return { ...s, heard: e.text };
      if (e.type === "text") return { ...s, feedback: s.feedback + e.delta };
      if (e.type === "reply") return { ...s, reply: e.line, seen: { ...s.seen, [e.line.idx]: e.line } };
      if (e.type === "done")
        return { ...s, phase: "evaluated", nextIdx: s.mode === "turn" || s.nextIdx === null ? e.next : s.nextIdx };
      if (e.type === "error") {
        const soft = e.code === "no_speech" || e.code === "too_long";
        return {
          ...s,
          phase: soft ? "ready" : "error",
          message: messageFor(e.code as ErrorCode, e.say ?? undefined),
          errorFrom: soft ? null : "evaluating",
        };
      }
      return s;
    }
    case "failed":
      // only a request this screen is waiting for can fail it; a stream left behind by 「처음으로」 cannot
      if (s.screen !== "roleplay" || (s.phase !== "loading" && s.phase !== "evaluating")) return s;
      return { ...s, phase: "error", message: messageFor(a.code, a.say), errorFrom: s.phase === "loading" ? "loading" : "evaluating" };
    case "retry":
      if (s.phase !== "error") return s;
      return { ...s, phase: s.errorFrom === "loading" ? "loading" : "ready", message: null, errorFrom: null };
    case "again":
      // keep the turn that just happened (an off-script reply included) before trying the line again
      if (s.phase !== "evaluated") return s;
      return { ...s, ...freshTurn, history: [...s.history, ...exchange(s)], mode: s.practice ? s.mode : "retry", phase: "ready" };
    case "next": {
      if (s.phase !== "evaluated") return s;
      if (s.practice) {
        const at = s.practice.at + 1;
        if (at >= s.practice.order.length) return toEnd(s);
        // one line at a time: the screen shows the line being practised, not what came before
        return { ...s, ...freshTurn, practice: { ...s.practice, at }, idx: s.practice.order[at], history: [], phase: "loading", line: null };
      }
      return {
        ...s,
        ...freshTurn,
        history: [...s.history, ...exchange(s)],
        idx: s.nextIdx ?? s.idx + 1,
        nextIdx: null,
        mode: "turn",
        phase: "loading",
        line: null,
      };
    }
    case "startPractice":
      if (s.screen !== "end" || a.order.length === 0) return s;
      return {
        ...s,
        ...freshTurn,
        screen: "roleplay",
        mode: a.kind === "shadow" ? "shadow" : "practice",
        practice: { kind: a.kind, order: a.order, at: 0 },
        idx: a.order[0],
        history: [],
        line: null,
        reading: false,
        phase: "loading",
        progress: null,
      };
    case "restarted":
      // the same script as a new roleplay (spec roleplay-practice 6); Jake's recommended situation stays on top
      if (s.screen !== "end") return s;
      return { ...initial, screen: "roleplay", roleplay: a.roleplay, jake: s.jake, phase: "loading" };
    case "closingPlayed":
      return { ...s, closingPlayed: true };
    case "toggleReading":
      return s.line ? { ...s, reading: !s.reading } : s;
  }
}
