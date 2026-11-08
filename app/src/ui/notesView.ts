// How the line to say looks (spec roleplay-practice 8): plain text with a 「읽는 법 보기」 button (closed), the three
// lines (open), a note that they are being made (loading), or plain text alone when there are no notes to show
// (they could not be made); the line and the mic work in every case.
import type { ScriptLine, ThreeLine } from "../api/types";

export type NotesView = "plain" | "closed" | "loading" | "open";

export function notesView(three: ThreeLine | "loading" | null, open: boolean): NotesView {
  if (three === null) return "plain";
  if (!open) return "closed";
  return three === "loading" ? "loading" : "open";
}

// The line to say comes before its notes (spec dont-wait-for-line-notes 2): the notes it came with, else the ones
// fetched for it ("loading" while on their way), else none.
type Fetched = ThreeLine | "loading" | undefined;

export function lineNotes(line: ScriptLine, fetched: Fetched): ThreeLine | "loading" | null {
  return line.three ?? fetched ?? null;
}

// Fetch the notes when the line came without them and they were not asked for yet.
export function needsNotes(line: ScriptLine, fetched: Fetched): boolean {
  return !line.three && fetched === undefined;
}
