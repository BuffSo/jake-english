// Helpers for 「다시 연습」 (spec docs/superpowers/specs/2026-11-07-review-practice-design.md).

// The same sentence, case and punctuation aside. The server has the same rule (`server/je_server/review.py`);
// contract/sentence-keys.json keeps the two in step.
export function sentenceKey(text: string): string {
  return (text.toLowerCase().replace(/’/g, "'").match(/[a-z0-9']+/g) ?? []).join(" ");
}
