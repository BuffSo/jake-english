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
// fetched for it ("loading" while on their way), else none when they could not be fetched (`failed`). Not asked for
// yet counts as on the way: the screen asks as soon as the line is up, so the button is there from the first frame
// instead of a frame later, pushing 「통역」 and ☆ aside (todo line-notes minors 3).
type Fetched = ThreeLine | "loading" | undefined;

export function lineNotes(line: ScriptLine, fetched: Fetched, failed: boolean): ThreeLine | "loading" | null {
  return line.three ?? fetched ?? (failed ? null : "loading");
}

// Fetch the notes when the line came without them, they were not asked for yet and asking did not fail: a failed
// line is not asked again on each 「다시 해 보기」, which made the button blink while Claude was down.
export function needsNotes(line: ScriptLine, fetched: Fetched, failed: boolean): boolean {
  return !line.three && fetched === undefined && !failed;
}
