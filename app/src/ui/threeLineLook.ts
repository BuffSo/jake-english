// How one syllable of the three lines is drawn, by its mark and its line. `size` is the line's font size.
// The English line marks stress by weight alone, in its own black: the orange text read as a second color over the
// sentence (2026-11-09 user: 「영문은 그냥 진하기로만 구분해도」). The Korean pronunciation line keeps the bold dark
// orange (2026-11-06 user). Weak syllables are small and gray in both lines: plain black weak syllables in the English
// line were drawn too, and the user chose to keep the gray (2026-11-09).
import type { TextStyle } from "react-native";

import { colors } from "./theme";
import type { Style } from "./threeLineSegments";

export type Line = "en" | "ko";

export function syllableLook(style: Style, line: Line, size: number): TextStyle | undefined {
  if (style === "strong") return line === "en" ? { fontWeight: "800" } : { color: colors.stress, fontWeight: "800" };
  if (style === "weak") return { fontSize: size * 0.78, color: colors.weak };
  return undefined;
}
