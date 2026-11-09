import { syllableLook } from "./threeLineLook";
import { colors } from "./theme";

// How a syllable of the three lines is drawn. The English line marks stress by weight alone, in its own black; the
// Korean pronunciation line keeps the orange (2026-11-09 user: 「영문은 그냥 진하기로만 구분해도」).

test("a strong syllable in the English line is bold in the line's own color, not orange", () => {
  expect(syllableLook("strong", "en", 24)).toEqual({ fontWeight: "800" });
});

test("a strong syllable in the Korean line stays bold dark orange", () => {
  expect(syllableLook("strong", "ko", 17)).toEqual({ color: colors.stress, fontWeight: "800" });
});

test("a weak syllable in the English line stays small and gray (2026-11-09 user: B, not plain black)", () => {
  const look = syllableLook("weak", "en", 24);
  expect(look?.color).toBe(colors.weak);
  expect(look?.fontSize).toBeCloseTo(18.72);
});

test("a weak syllable in the Korean line stays small and gray", () => {
  const look = syllableLook("weak", "ko", 17);
  expect(look?.color).toBe(colors.weak);
  expect(look?.fontSize).toBeCloseTo(13.26);
});

test("a plain syllable takes the line's look in both lines", () => {
  expect(syllableLook("plain", "en", 24)).toBeUndefined();
  expect(syllableLook("plain", "ko", 17)).toBeUndefined();
});
