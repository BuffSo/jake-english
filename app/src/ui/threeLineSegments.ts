// Turns a three-line note into styled pieces: strong, weak, plain, and in the reading line the Korean sounds (`sound`,
// the pronunciation line's color, spec three-line-listen 1). How each is drawn: `syllableLook`.
// Rules: docs/guide/PRONUNCIATION_한글발음_세줄표시_20261105.md
import type { Syllable, ThreeLine } from "../api/types";

export type Style = "strong" | "weak" | "plain" | "sound";
export type Seg = { text: string; style: Style };

const styleOf = (m: Syllable["m"]): Style => (m === "s" ? "strong" : m === "w" ? "weak" : "plain");

export function englishSegments(t: ThreeLine): Seg[][] {
  return t.words.map((w) => w.syl.map((s) => ({ text: s.en, style: styleOf(s.m) })));
}

function koreanOf(s: Syllable): Seg[] {
  if (s.m === "s" && s.hi && s.ko.includes(s.hi)) {
    const at = s.ko.indexOf(s.hi);
    return [
      { text: s.ko.slice(0, at), style: "plain" as Style },
      { text: s.hi, style: "strong" as Style },
      { text: s.ko.slice(at + s.hi.length), style: "plain" as Style },
    ].filter((x) => x.text !== "");
  }
  return s.ko ? [{ text: s.ko, style: s.m === "w" ? "weak" : "plain" }] : [];
}

// One group per run of linked words; groups are shown with a space between them.
export function koreanSegments(t: ThreeLine): Seg[][] {
  const groups: Seg[][] = [];
  let cur: Seg[] = [];
  for (const w of t.words) {
    for (const s of w.syl) cur.push(...koreanOf(s));
    if (!w.link) {
      if (cur.length) groups.push(cur);
      cur = [];
    }
  }
  if (cur.length) groups.push(cur);
  return groups;
}

// The server marks the Korean sounds of the reading line with [[...]]; they show in 「」.
export function readingSegments(reading: string): Seg[] {
  // split() with a capture group puts the marked parts at the odd places
  return reading
    .trim()
    .split(/\[\[(.*?)\]\]/)
    .map((text, i): Seg => (i % 2 ? { text: `「${text}」`, style: "sound" } : { text, style: "plain" }))
    .filter((s) => s.text !== "");
}
