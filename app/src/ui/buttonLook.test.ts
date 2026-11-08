import { BUTTON_BORDER, buttonLook } from "./buttonLook";
import { colors } from "./theme";

// spec button-colors 1: three looks, primary, secondary and disabled

test("a primary button is filled blue with white words", () => {
  expect(buttonLook("primary", {})).toEqual({ background: colors.primary, text: colors.onColor, border: colors.primary, opacity: 1 });
});

test("a secondary button is white with a blue border and blue words, so it does not look switched off", () => {
  expect(buttonLook("secondary", {})).toEqual({ background: colors.bg, text: colors.primary, border: colors.primary, opacity: 1 });
});

test("a disabled button looks the same whatever its kind", () => {
  expect(buttonLook("primary", { disabled: true })).toEqual(buttonLook("secondary", { disabled: true }));
  expect(buttonLook("primary", { disabled: true })).toEqual({ background: colors.off, text: colors.offText, border: colors.off, opacity: 1 });
});

test("a disabled button is neither of the pressable looks", () => {
  const off = buttonLook("secondary", { disabled: true });
  for (const kind of ["primary", "secondary"] as const) {
    const on = buttonLook(kind, {});
    expect(off.background).not.toBe(on.background);
    expect(off.text).not.toBe(on.text);
  }
});

test("pressing only dims the button, unlike a disabled one", () => {
  const pressed = buttonLook("secondary", { pressed: true });
  expect({ ...pressed, opacity: 1 }).toEqual(buttonLook("secondary", {}));
  expect(pressed.opacity).toBeLessThan(1);
  expect(pressed).not.toEqual(buttonLook("secondary", { disabled: true }));
});

test("both kinds have a border of the same width", () => {
  expect(BUTTON_BORDER).toBe(2);
});

// WCAG relative luminance and contrast ratio
function luminance(hex: string): number {
  const [r, g, b] = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255);
  const lin = (c: number) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4);
  return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b);
}
const contrast = (a: string, b: string) => {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
};

// todo 20261108_30 2: `#868E96` was 2.8:1 on the gray, read on the emulator but faint for a 15px small button's words
// in bright light. Darker, but still lighter than the app's gray text, so the button still reads as off.
test("a disabled button's words read on its gray and stay lighter than gray text", () => {
  expect(contrast(colors.offText, colors.off)).toBeGreaterThanOrEqual(3.5);
  expect(contrast(colors.offText, colors.off)).toBeLessThan(contrast(colors.sub, colors.off));
});
