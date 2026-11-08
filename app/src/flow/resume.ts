// A resumed conversation, rebuilt from the Mac's record (spec docs/superpowers/specs/2026-11-08-resume-roleplay-design.md
// 2): the lines before the place it starts from, as the bubbles the roleplay screen would have shown. Only the
// conversation: no feedback and no answers from teacher Ryan, which stay on the end screen.
import type { Resume, ScriptLine } from "../api/types";
import type { Bubble } from "./state";

const before = (r: Resume) => r.roleplay.lines.filter((l) => l.idx < r.at);

// Ryan's lines as his bubbles; mine with what was heard and its recording, or the script only when it was skipped
export function resumeHistory(r: Resume): Bubble[] {
  const heard = new Map(r.said.map((s) => [s.idx, s]));
  return before(r).map((l): Bubble => {
    if (l.speaker === "ryan") return { kind: "ryan", text: l.text, idx: l.idx };
    const s = heard.get(l.idx);
    if (!s) return { kind: "user", text: "", script: l.text, idx: l.idx, skipped: true };
    return { kind: "user", text: s.heard, script: l.text, idx: l.idx, rec: { rp_id: r.roleplay.id, idx: l.idx, n: s.n } };
  });
}

// The lines the screen knows already, so their bubbles can open their notes and be practised (`practiceFor`)
export function resumeSeen(r: Resume): Record<number, ScriptLine> {
  return Object.fromEntries(before(r).map((l) => [l.idx, l]));
}

// The resume row's second line: which conversation, and which line of mine comes next
export function resumeLabel(r: Resume): string {
  return `${r.roleplay.frame.title_ko} · 내 대사 ${r.progress.no}/${r.progress.total}`;
}
