// A resumed conversation, rebuilt from the Mac's record (spec docs/superpowers/specs/2026-11-08-resume-roleplay-design.md
// 2): the lines before the place it starts from, as the bubbles the roleplay screen would have shown. Only the
// conversation: no feedback and no answers from teacher Ryan, which stay on the end screen.
import type { HeardTry, Resume, Roleplay, ScriptLine } from "../api/types";
import type { Bubble } from "./state";

const before = (r: Resume) => r.roleplay.lines.filter((l) => l.idx < r.at);

// Ryan's lines as his bubbles; mine with what was heard and its recording, or the script only when it was skipped
function bubbleOf(rpId: string, l: ScriptLine, s: HeardTry | undefined): Bubble {
  if (l.speaker === "ryan") return { kind: "ryan", text: l.text, idx: l.idx };
  if (!s) return { kind: "user", text: "", script: l.text, idx: l.idx, skipped: true };
  return { kind: "user", text: s.heard, script: l.text, idx: l.idx, rec: { rp_id: rpId, idx: l.idx, n: s.n } };
}

export function resumeHistory(r: Resume): Bubble[] {
  const heard = new Map(r.said.map((s) => [s.idx, s]));
  return before(r).map((l) => bubbleOf(r.roleplay.id, l, heard.get(l.idx)));
}

// A resumed conversation's lines of mine recorded before it was resumed, by line (spec resume-unrecorded 3)
export function recordedOf(r: Resume): Record<number, HeardTry> {
  return Object.fromEntries(r.said.map((s) => [s.idx, s]));
}

// Where a resumed conversation goes on from `from`: to the line after my line before the next unrecorded line of mine,
// so Ryan's line leads in again, or, with none left, to the line after my last line, so the ending is said (or the
// end screen comes, when I end it). The lines in between are passed as bubbles, recorded ones with what was heard,
// and become known for practice (spec resume-unrecorded 3).
export function passRecorded(
  rp: Roleplay,
  recorded: Record<number, HeardTry>,
  from: number,
): { idx: number; passed: Bubble[]; seen: Record<number, ScriptLine> } {
  const mine = rp.lines.filter((l) => l.speaker === "user").map((l) => l.idx);
  const target = mine.find((i) => i >= from && !recorded[i]) ?? rp.lines.length;
  const lead = mine.filter((i) => i < target).pop();
  const idx = Math.max(from, lead === undefined ? 0 : lead + 1);
  const lines = rp.lines.filter((l) => l.idx >= from && l.idx < idx);
  return {
    idx,
    passed: lines.map((l) => bubbleOf(rp.id, l, recorded[l.idx])),
    seen: Object.fromEntries(lines.map((l) => [l.idx, l])),
  };
}

// The lines the screen knows already, so their bubbles can open their notes and be practised (`practiceFor`)
export function resumeSeen(r: Resume): Record<number, ScriptLine> {
  return Object.fromEntries(before(r).map((l) => [l.idx, l]));
}

// The resume row's second line: which conversation, and which line of mine comes next. One gone to the end has only
// its unrecorded lines left, and 「내 대사 1/3」 would read as starting over: how many it has (spec resume-unrecorded 4).
export function resumeLabel(r: Resume): string {
  const title = r.roleplay.frame.title_ko;
  if (!r.ended) return `${title} · 내 대사 ${r.progress.no}/${r.progress.total}`;
  const recorded = new Set(r.said.map((s) => s.idx));
  const left = r.roleplay.lines.filter((l) => l.speaker === "user" && !recorded.has(l.idx)).length;
  return `${title} · 녹음 안 한 줄 ${left}개`;
}
