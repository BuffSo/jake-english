import { InRowButton } from "./InRowButton";
import { StarButton } from "./Star";

// A disabled Pressable inside a tappable row hands the tap to the row (final review): a busy button only dims.
test("a busy star dims but still takes the tap", () => {
  const onPress = jest.fn();
  const el = StarButton({ saved: true, busy: true, onPress });
  expect(el.type).toBe(InRowButton);
  expect(el.props).toMatchObject({ label: "★ 모아 둠", dim: true, onPress });
});

test("an in-row button never disables its Pressable", () => {
  const el = InRowButton({ label: "빼기 ✕", dim: true, onPress: () => {} });
  expect(el.props.disabled).toBeUndefined();
});
