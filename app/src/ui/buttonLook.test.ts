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
