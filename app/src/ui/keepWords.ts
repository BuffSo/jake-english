// Korean that wraps between words only. Android breaks a line between any two Hangul letters, so 「반가워요」 came out
// as 「반가워」 and 「요」 on two lines (2026-11-07, emulator; spec review-screens 7). A word joiner (U+2060) forbids a
// break where it stands and shows nothing, so lines break at the spaces. Only for Korean shown on screen: English
// already breaks at spaces. Never send or compare text that went through here.
//
// Android also breaks between a Hangul letter and what is stuck to it: a digit (「11월」, 「7일에」), a Latin letter or
// a closing bracket (Ryan's 「coffee를」, 「「coffee」를」), so those are joined too (2026-11-08, todo 12-2, 3). Korean
// separates words with spaces, so a word with Hangul in it breaks only at a space.
const WJ = "\u2060";
// syllables and the letters written on their own (「ㅋㅋ」, 「ㅠㅠ」), todo review-screens minors follow-up 2
const HANGUL = /[가-힣ㄱ-ㅎㅏ-ㅣ]/;
// a letter and the next one, neither a space nor a joiner already there (so a second pass adds nothing)
const PAIR = /([^\s\u2060])(?=([^\s\u2060]))/g;

function joins(a: string, b: string): boolean {
  return HANGUL.test(a) || HANGUL.test(b);
}

export function keepWords(text: string): string {
  // the halves of an emoji are not Hangul, so nothing goes between them
  return text.replace(PAIR, (a: string, _a: string, b: string) => (joins(a, b) ? a + WJ : a));
}

// One word drawn in pieces of different styles (the stressed letter of the Korean pronunciation is its own `Text`):
// each piece is kept, and a piece ends with a joiner when it and the next one are parts of one word.
export function keepPieces(pieces: string[]): string[] {
  return pieces.map((p, i) => {
    const kept = keepWords(p);
    const next = pieces[i + 1];
    if (!p || !next) return kept;
    const a = p[p.length - 1];
    const b = next[0];
    return /[\s\u2060]/.test(a) || /[\s\u2060]/.test(b) || !joins(a, b) ? kept : kept + WJ;
  });
}
