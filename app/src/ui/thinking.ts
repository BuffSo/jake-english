// Who thinks while the app waits, and which pictures show it (docs/superpowers/specs/2026-11-06-waiting-animation-design.md)

import type { Thinking } from "../api/types";

export type Who = "jake" | "ryan";
export type { Thinking };

// The person named in the waiting text thinks; Ryan otherwise, since he makes the script, listens and evaluates
// (2026-11-06 user: Jake while he picks a situation, Ryan for every other wait)
export function waiterOf(text: string): Who {
  return text.startsWith("제이크") ? "jake" : "ryan";
}

// No pictures before /home has come back, or from a server older than the thinking faces: the wait shows no face
export function framesFor(thinking: Thinking | null | undefined, who: Who): string[] {
  return thinking?.[who] ?? [];
}
