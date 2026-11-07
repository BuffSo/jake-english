// Korean that wraps between words only. Android breaks a line between any two Hangul letters, so 「반가워요」 came out
// as 「반가워」 and 「요」 on two lines (2026-11-07, emulator; spec review-screens 7). A word joiner (U+2060) between
// two Hangul letters forbids a break there and shows nothing, so lines break at the spaces. Only for Korean shown on
// screen: English already breaks at spaces.
const WJ = "\u2060";
const BETWEEN_HANGUL = /([가-힣])(?=[가-힣])/g;

export function keepWords(text: string): string {
  return text.replace(BETWEEN_HANGUL, `$1${WJ}`);
}
