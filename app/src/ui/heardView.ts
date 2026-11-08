// What was heard, without the 「들린 말:」 label: one faded line cut with 「…」 until its bubble or row opens, then all
// of it (2026-11-08 user: 「들린 말: 이거 표시 안 해도 될 것 같은데 … 일부만 보이고 클릭하면 확장 펼치기」, then
// 「한 줄로 해 줘」; spec docs/superpowers/specs/2026-11-08-heard-line-collapsed-design.md 1). It may be Korean
// (said to teacher Ryan), so it goes through `keepWords` like every Korean line on these screens.
import type { TryRef } from "../api/types";
import { keepWords } from "./keepWords";

export function heardView(text: string, open: boolean): { text: string; lines: 1 | undefined } {
  return { text: keepWords(text), lines: open ? undefined : 1 };
}

// What keeps what was just heard open: the try, so the next try comes folded even with the same words (final review
// of heard-line-collapsed). The words when the try is unknown (an old server sends no try number).
export function heardKey(heard: string, rec: TryRef | null): string {
  return rec ? `${rec.rp_id}:${rec.idx}:${rec.n}` : heard;
}
