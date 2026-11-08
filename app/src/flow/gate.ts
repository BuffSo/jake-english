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

// How long the gate stays shut after a cancel or a skip (spec record-cancel-skip 5)
export const TAP_HOLD_MS = 400;

// Runs `fn` inside the gate; when it did something, the gate stays shut until `wait` ends. After 「취소」 the screen
// redraws 「건너뛰기」 where it was, and after 「건너뛰기」 in a practice the next line puts 「건너뛰기」 there again:
// the second tap of a double tap must find the gate shut, not skip a line (spec record-cancel-skip 5). Starting the
// mic goes through the same gate, so a tap on 「🎤 말하기」 right after a skip starts nothing for the line left.
export async function runThenHold(
  gate: ReturnType<typeof createGate>,
  fn: () => Promise<boolean>,
  wait: () => Promise<void>,
): Promise<boolean> {
  const done = await gate.run(async () => {
    const did = await fn();
    if (did) await wait();
    return did;
  });
  return done === true;
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
