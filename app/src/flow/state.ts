// Screen flow as a reducer, so taps that arrive at the wrong moment (double taps, taps while Ryan is
// still talking) are ignored in one place.
import type { ErrorCode } from "../api/client";
import type { AttemptEvent, Roleplay, ScriptLine } from "../api/types";

export type Screen = "home" | "situation" | "roleplay" | "end";
export type Phase = "loading" | "ryan" | "ready" | "recording" | "evaluating" | "evaluated" | "error";
export type Bubble = { kind: "ryan" | "user" | "feedback"; text: string; idx?: number };

export type State = {
  screen: Screen;
  roleplay: Roleplay | null;
  idx: number;
  mode: "turn" | "retry";
  phase: Phase;
  line: ScriptLine | null;
  seen: Record<number, ScriptLine>;
  heard: string | null;
  feedback: string;
  reply: ScriptLine | null;
  nextIdx: number | null;
  message: string | null;
  errorFrom: "loading" | "evaluating" | null;
  returnToEnd: boolean;
  history: Bubble[];
};

export type Action =
  | { type: "home" }
  | { type: "chooseRoleplay" }
  | { type: "created"; roleplay: Roleplay }
  | { type: "lineLoaded"; line: ScriptLine }
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
  | { type: "retryFromEnd"; idx: number };

export const initial: State = {
  screen: "home",
  roleplay: null,
  idx: 0,
  mode: "turn",
  phase: "loading",
  line: null,
  seen: {},
  heard: null,
  feedback: "",
  reply: null,
  nextIdx: null,
  message: null,
  errorFrom: null,
  returnToEnd: false,
  history: [],
};

export const OFFLINE = "맥에 연결할 수 없어요. 맥과 인터넷 연결을 확인해 주세요.";

function messageFor(code: ErrorCode, say?: { text: string }): string {
  if (say?.text) return say.text;
  if (code === "offline") return OFFLINE;
  if (code === "claude_unavailable") return "지금은 라이언이 대답할 수 없어요. 맥의 인터넷 연결을 확인해 주세요.";
  return "문제가 생겼어요. 다시 해 볼까요?";
}

const freshTurn = { heard: null, feedback: "", reply: null, message: null, errorFrom: null } as const;

// What was said in this turn, as conversation bubbles (what the learner said, Ryan's feedback, Ryan's reply).
function exchange(s: State): Bubble[] {
  return [
    ...(s.heard ? [{ kind: "user" as const, text: s.heard }] : []),
    ...(s.feedback ? [{ kind: "feedback" as const, text: s.feedback }] : []),
    ...(s.reply ? [{ kind: "ryan" as const, text: s.reply.text, idx: s.reply.idx }] : []),
  ];
}

export function reduce(s: State, a: Action): State {
  switch (a.type) {
    case "home":
      return { ...initial };
    case "chooseRoleplay":
      return { ...initial, screen: "situation" };
    case "created":
      return { ...initial, screen: "roleplay", roleplay: a.roleplay, phase: "loading" };
    case "lineLoaded":
      if (s.phase !== "loading") return s;
      return {
        ...s,
        ...freshTurn,
        line: a.line,
        seen: { ...s.seen, [a.line.idx]: a.line },
        phase: a.line.speaker === "ryan" ? "ryan" : "ready",
        nextIdx: s.mode === "retry" ? s.nextIdx : null,
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
      return { ...s, phase: "error", message: messageFor(a.code, a.say), errorFrom: s.phase === "loading" ? "loading" : "evaluating" };
    case "retry":
      if (s.phase !== "error") return s;
      return { ...s, phase: s.errorFrom === "loading" ? "loading" : "ready", message: null, errorFrom: null };
    case "again":
      // keep the turn that just happened (an off-script reply included) before trying the line again
      if (s.phase !== "evaluated") return s;
      return { ...s, ...freshTurn, history: [...s.history, ...exchange(s)], mode: "retry", phase: "ready" };
    case "next": {
      if (s.phase !== "evaluated") return s;
      if (s.returnToEnd) return { ...s, screen: "end", returnToEnd: false, mode: "turn" };
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
    case "retryFromEnd":
      return { ...s, ...freshTurn, screen: "roleplay", idx: a.idx, mode: "retry", returnToEnd: true, phase: "loading", line: null };
  }
}
