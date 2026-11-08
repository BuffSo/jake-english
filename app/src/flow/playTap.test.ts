// A tap on a play button: play, stop what it plays, or nothing (spec play-button-feedback 3)
import { TAP_HOLD_MS } from "./gate";
import { playTap } from "./playTap";

const quiet = { tag: null, since: 0 };

test("a tap on a quiet button plays", () => {
  expect(playTap(quiet, "rec:1", 5000)).toBe("play");
});

test("a tap on the playing button stops it", () => {
  expect(playTap({ tag: "rec:1", since: 1000 }, "rec:1", 1000 + TAP_HOLD_MS)).toBe("stop");
  expect(playTap({ tag: "rec:1", since: 1000 }, "rec:1", 9000)).toBe("stop");
});

test("a second tap within the hold is ignored", () => {
  // a double tap must not become 「play, then stop at once」
  expect(playTap({ tag: "rec:1", since: 1000 }, "rec:1", 1000 + TAP_HOLD_MS - 1)).toBe("ignore");
});

test("a tap on another button plays", () => {
  expect(playTap({ tag: "rec:1", since: 1000 }, "listen", 1100)).toBe("play");
});
