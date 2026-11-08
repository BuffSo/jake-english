// How a `Button` is drawn (spec docs/superpowers/specs/2026-11-08-button-colors-design.md 1). Three looks:
// - primary: what to do first on the screen or in the row, filled blue with white words
// - secondary: anything else that can be pressed, white with a blue border and blue words. It used to be filled light
//   gray, which looked switched off (2026-11-07 user: 「연회색이면 disable 된줄 착각할수도 있어」)
// - disabled: whatever the kind, the same gray. It used to be the kind's look at half opacity, so a disabled blue
//   button turned light blue and a disabled gray one looked like a pressable gray one.
// Pressing only dims the button; it no longer looks like a disabled one.
import { colors } from "./theme";

export type ButtonKind = "primary" | "secondary";
export type ButtonLook = { background: string; text: string; border: string; opacity: number };

// Both kinds have a border this wide (the primary one in its own fill colour), so the two are the same height
export const BUTTON_BORDER = 2;
const PRESSED_OPACITY = 0.7;

export function buttonLook(kind: ButtonKind, state: { disabled?: boolean; pressed?: boolean }): ButtonLook {
  if (state.disabled) return { background: colors.off, text: colors.offText, border: colors.off, opacity: 1 };
  const look =
    kind === "primary"
      ? { background: colors.primary, text: colors.onColor, border: colors.primary }
      : { background: colors.bg, text: colors.primary, border: colors.primary };
  return { ...look, opacity: state.pressed ? PRESSED_OPACITY : 1 };
}
