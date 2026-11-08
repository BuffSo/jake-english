// The corrections screen 「대화 돌아보기」 as a pure reducer (spec free-talk-design 7): one saved fix per screen, with
// the learner's own words, the corrected sentence to follow, and the practice result shown below it. The screen loads
// the line and does the sounds; this decides what it shows. `tries` grows with every recording, so an event of an
// earlier try is dropped.
import type { AttemptEvent, ScriptLine, TalkEnd, TalkItem, TryRef } from "../api/types";
import type { ErrorCode } from "../api/client";
import { NO_SPEECH, messageFor } from "./state";

export type FixPhase = "loading" | "ready" | "recording" | "evaluating" | "evaluated" | "error";

export type FixState = {
  rpId: string;
  items: TalkItem[];
  at: number;
  line: ScriptLine | null; // the fix line once loaded
  phase: FixPhase;
  tries: number;
  heard: string | null;
  heardRec: TryRef | null;
  feedback: string;
  message: string | null;
  reading: boolean; // 「읽는 법 보기」 open
};

export type FixAction =
  | { type: "lineLoaded"; line: ScriptLine }
  | { type: "lineFailed"; message: string }
  | { type: "retry" }
  | { type: "recordStart" }
  | { type: "recordCancel" }
  | { type: "noSpeech" }
  | { type: "recordStop" }
  | { type: "event"; tries: number; e: AttemptEvent }
  | { type: "failed"; tries: number; message: string }
  | { type: "again" }
  | { type: "next" }
  | { type: "toggleReading" };

const fresh = { line: null, phase: "loading" as FixPhase, tries: 0, heard: null, heardRec: null, feedback: "", message: null, reading: false };
const noResult = { heard: null, heardRec: null, feedback: "" };

export function fixInitial(rpId: string, end: TalkEnd): FixState {
  return { rpId, items: end.items, at: 0, ...fresh };
}

export const isLastFix = (s: FixState) => s.at >= s.items.length - 1;
export const nextLabel = (s: FixState): "다음 ›" | "끝" => (isLastFix(s) ? "끝" : "다음 ›");
export const fixCount = (s: FixState): string | null => (s.items.length >= 2 ? `${s.at + 1}/${s.items.length}` : null);

export function fixReduce(s: FixState, a: FixAction): FixState {
  switch (a.type) {
    case "lineLoaded":
      return s.phase === "loading" ? { ...s, line: a.line, phase: "ready", message: null } : s;
    case "lineFailed":
      return s.phase === "loading" ? { ...s, phase: "error", message: a.message } : s;
    case "retry":
      return s.phase === "error" && !s.line ? { ...s, phase: "loading", message: null } : s;
    case "recordStart":
      if ((s.phase !== "ready" && s.phase !== "evaluated") || !s.line) return s;
      return { ...s, ...noResult, phase: "recording", tries: s.tries + 1, message: null };
    case "recordCancel":
      return s.phase === "recording" ? { ...s, phase: "ready" } : s;
    case "noSpeech":
      return s.phase === "recording" ? { ...s, phase: "ready", message: NO_SPEECH } : s;
    case "recordStop":
      return s.phase === "recording" ? { ...s, phase: "evaluating" } : s;
    case "event": {
      if (a.tries !== s.tries || s.phase !== "evaluating" || !s.line) return s;
      const e = a.e;
      switch (e.type) {
        case "heard":
          return {
            ...s,
            heard: e.text,
            heardRec: e.n ? { rp_id: s.rpId, idx: s.line.idx, n: e.n } : null,
          };
        case "text":
          return { ...s, feedback: s.feedback + e.delta };
        case "done":
          return { ...s, phase: "evaluated" };
        case "error": {
          const soft = e.code === "no_speech" || e.code === "too_long";
          return { ...s, phase: soft ? "ready" : "error", message: messageFor(e.code as ErrorCode, e.say ?? undefined) };
        }
        default:
          return s; // `audio` only tells the screen to preload
      }
    }
    case "failed":
      return a.tries === s.tries && s.phase === "evaluating" ? { ...s, phase: "error", message: a.message } : s;
    case "again":
      return s.phase === "evaluated" ? { ...s, ...noResult, phase: "ready" } : s;
    case "next":
      if (s.phase === "evaluating" || s.phase === "recording" || isLastFix(s)) return s;
      return { ...s, at: s.at + 1, ...fresh };
    case "toggleReading":
      return { ...s, reading: !s.reading };
  }
}
