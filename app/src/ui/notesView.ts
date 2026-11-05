// How the line to say looks (spec roleplay-practice 8): plain text with a 「읽는 법 보기」 button (closed), the three
// lines (open), a note that they are being made (loading), or plain text alone when there are no notes to show
// (they could not be made); the line and the mic work in every case.
import type { ThreeLine } from "../api/types";

export type NotesView = "plain" | "closed" | "loading" | "open";

export function notesView(three: ThreeLine | "loading" | null, open: boolean): NotesView {
  if (three === null) return "plain";
  if (!open) return "closed";
  return three === "loading" ? "loading" : "open";
}
