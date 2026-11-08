// Lets one async action run at a time; calls that arrive while it runs are ignored (double taps, the 60s
// auto-stop landing on a tap). PR #12 review.
export function createGate() {
  let busy = false;
  return {
    get busy() {
      return busy;
    },
    async run<T>(fn: () => Promise<T>): Promise<T | undefined> {
      if (busy) return undefined;
      busy = true;
      try {
        return await fn();
      } finally {
        busy = false;
      }
    },
  };
}

// Stopping the recorder goes through the gate (a double tap, the auto-stop landing on a tap); sending it and
// reading Ryan's answer come after, outside it. Back from a practice in the middle of the answer keeps the roleplay
// screen and its gate (spec roleplay-practice 9), and the mic must not wait for that old answer (final review).
export async function stopThenSend<T>(
  gate: ReturnType<typeof createGate>,
  stop: () => Promise<T | undefined>,
  send: (stopped: T) => Promise<void>,
): Promise<void> {
  const stopped = await gate.run(stop);
  if (stopped !== undefined) await send(stopped);
}

// How long taps are turned away after a cancel or a skip (spec record-cancel-skip 5)
export const TAP_HOLD_MS = 400;

// A short time when taps that start or skip are turned away. Not the gate's: the roleplay screen is keyed by its
// roleplay, and a saved-sentence practice that moves to another conversation's sentence mounts a new screen with a
// new gate, which would let the second tap of a double tap through (final review).
export function createHold(now: () => number = Date.now) {
  let until = 0;
  return {
    get on() {
      return now() < until;
    },
    start() {
      until = now() + TAP_HOLD_MS;
    },
  };
}

// The one hold every roleplay screen shares
export const tapHold = createHold();

// Runs `fn` inside the gate unless taps are held; when it did something, holds the next taps a moment. After 「취소」
// the screen redraws 「건너뛰기」 where it was, and after 「건너뛰기」 in a practice the next line puts 「건너뛰기」 there
// again: the second tap of a double tap must not skip a line (spec record-cancel-skip 5). Starting the mic checks the
// same hold, so a tap on 「🎤 말하기」 right after a skip starts nothing for the line left.
export async function runThenHold(
  gate: ReturnType<typeof createGate>,
  hold: ReturnType<typeof createHold>,
  fn: () => Promise<boolean>,
): Promise<boolean> {
  if (hold.on) return false;
  const did = await gate.run(fn);
  if (did) hold.start();
  return did === true;
}

// A tap whose redraw puts 「건너뛰기」 where it was: 「다시 해 보기」 after a try, 「다시 시도」 after an error. It does its
// work and holds the next tap, so the second tap of its double tap does not skip the line just chosen again (PR #45
// review).
export function tapThenHold(hold: ReturnType<typeof createHold>, fn: () => void): void {
  fn();
  hold.start();
}

// One answer per question: the first tap on either choice is taken, and later ones (the second tap of a double tap,
// before the screen redraws) are ignored until the next question opens it. Unlike the gate it holds nothing while the
// answer's work runs, so going back in the middle never leaves the next question shut. PR #18 review: a double tap on
// 「이걸로 할게요」 asked for two scripts.
export function createLatch() {
  let open = false;
  return {
    open() {
      open = true;
    },
    take(): boolean {
      if (!open) return false;
      open = false;
      return true;
    },
  };
}
