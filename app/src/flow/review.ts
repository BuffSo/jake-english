// Helpers for 「다시 연습」 (spec docs/superpowers/specs/2026-11-07-review-practice-design.md).
import type { TranscriptLine, TryRef } from "../api/types";

// The same sentence, case and punctuation aside. The server has the same rule (`server/je_server/review.py`);
// contract/sentence-keys.json keeps the two in step.
export function sentenceKey(text: string): string {
  return (text.toLowerCase().replace(/’/g, "'").match(/[a-z0-9']+/g) ?? []).join(" ");
}

// 「11월 5일」 from "2026-11-05" or "2026-11-05T10:00:00"
export function dayKo(iso: string): string {
  const [, m, d] = iso.slice(0, 10).split("-").map(Number);
  return `${m}월 ${d}일`;
}

// One row open at a time: tapping the open row closes it (spec review-practice 8)
export function toggleRow(open: string | null, key: string): string | null {
  return open === key ? null : key;
}

// 「🔊 처음 녹음」: the first recording, then this run's last try that followed the line (spec review-practice 4)
export function comparePair(rpId: string, l: TranscriptLine): { first: TryRef; then: TryRef | null } | null {
  if (!l.first) return null;
  const last = [...l.tries].reverse().find((t) => t.followed);
  return { first: l.first, then: last ? { rp_id: rpId, idx: l.line.idx, n: last.n } : null };
}

// Tapping a row (key "<place>:<line>", or just "<line>"): the row left open, and the lines whose notes and Sohee's
// line close. Both the row that closes and the one that opens: a line keeps its open notes by line number, so a
// bubble that changed its key (Ryan's reply moving into the conversation) must not open with them (PR #27 review).
export function tapRow(open: string | null, key: string): { open: string | null; close: number[] } {
  const lineOf = (k: string) => Number(k.split(":").pop());
  if (open === key) return { open: null, close: [lineOf(key)] };
  const close = open === null ? [lineOf(key)] : [lineOf(open), lineOf(key)];
  return { open: key, close: [...new Set(close)] };
}

// Where to scroll so an opened row's buttons show, or null when they already do (spec review-practice 8). `row.y`
// is from the top of the list; a row taller than the screen keeps its top in view.
export function scrollToShow(
  row: { y: number; height: number },
  view: { offset: number; height: number },
  margin = 12,
): number | null {
  const bottom = row.y + row.height + margin;
  if (bottom <= view.offset + view.height) return null;
  return Math.min(row.y, bottom - view.height);
}
