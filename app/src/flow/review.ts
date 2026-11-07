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

// 「▶ 처음 녹음」: the first recording, then this run's last try that followed the line (spec review-practice 4)
export function comparePair(rpId: string, l: TranscriptLine): { first: TryRef; then: TryRef | null } | null {
  if (!l.first) return null;
  const last = [...l.tries].reverse().find((t) => t.followed);
  return { first: l.first, then: last ? { rp_id: rpId, idx: l.line.idx, n: last.n } : null };
}
