// What the first screen's buttons do besides opening the next screen (final review of first-screen-buttons).
import type { Home } from "../api/types";
import { createGate } from "./gate";

// Leaving the first screen stops Ryan. His shadowing tip comes after the question, while the cards can already be
// pressed (spec ryan-shadowing-tip 2), and 「복습하기」 has no Ryan (spec review-screens 2). The situation screen
// clears the queue itself; this covers every way out.
export function leaveHome(sounds: { clear: () => void }, go: () => void): void {
  sounds.clear();
  go();
}

// Asks the Mac for the first screen one request at a time: `/home?tip=1` uses up the day's tip, so a double tap on
// 「다시 시도」 must not send a second one (REVIEW.md 「앱 화면」, APP guide 「버튼을 두 번 누르면 같은 요청이 두 번 간다」).
export function createHomeLoad(
  getHome: () => Promise<Home>,
  onHome: (h: Home) => void,
  onError: (e: unknown) => void,
): () => Promise<void> {
  const gate = createGate();
  return async () => {
    await gate.run(async () => {
      try {
        onHome(await getHome());
      } catch (e) {
        onError(e);
      }
    });
  };
}
