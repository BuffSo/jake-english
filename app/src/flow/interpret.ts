// Sohee's interpretation of a script line (spec docs/superpowers/specs/2026-11-06-korean-translation-design.md):
// how it shows and when her voice may play. Her sound comes a moment after the text, so whether it may play is
// asked again when it arrives, not when the line was opened.
import type { ScriptLine } from "../api/types";
import { canReplay, mayListen, type Phase } from "./state";

export type Ko = { text: string; audio: string | null };
// folded: a failure that was shown a moment and folded away (todo 20261106_10 1); the next tap tries again
export type KoEntry = Ko | "loading" | "failed" | "folded";
export type KoView = "closed" | "loading" | "failed" | "open";
export type Where = "roleplay" | "end";

// what the server already made and keeps on the line, so it is not asked for again
export function koOf(line: ScriptLine | undefined): Ko | undefined {
  return line?.ko ? { text: line.ko, audio: line.ko_audio } : undefined;
}

// A failure shows 「지금은 통역할 수 없어요」 a moment, then the line folds (`FAIL_SHOW_MS`); a tap tries again
export function koView(entry: KoEntry | undefined, open: boolean): KoView {
  if (entry === "failed") return "failed";
  if (!open || entry === "folded") return "closed";
  return entry === undefined || entry === "loading" ? "loading" : "open";
}

// What a tap on 「통역」 does, the same for every button: opens a closed line, or a failed one to try again; closes an
// open or loading one (PR #24 review: the rule was written out on each screen)
export function koOpensOnTap(view: KoView): boolean {
  return view === "closed" || view === "failed";
}

// Played by herself when the line opens: in the roleplay only while my turn waits and nothing plays, so she never
// lands in a recording or over Ryan, his feedback or the model. The end screen has no turn and plays like its 🔊.
export function mayAutoPlay(where: Where, phase: Phase, playing: boolean): boolean {
  return where === "end" || (canReplay(phase) && !playing);
}

// A tap on her line: in the roleplay while my turn waits, stopping what plays, but not Ryan's answer (spec
// three-line-listen 5); on the end screen always
export function mayReplay(where: Where, phase: Phase, answering: boolean): boolean {
  return where === "end" || mayListen(phase, answering);
}
