// The drop request of 「↻ 다시 말하기」 (spec talk-resay 3 「앱이 맥에 알리지 못했을 때」). The request goes at the tap;
// before the next turn is uploaded and before 「대화 끝내기」 the screen awaits `settle`, so a drop that did not reach
// the Mac is sent once more, and if that fails too the error is thrown and the turn is not sent (the Mac would answer
// the dropped words). Only the Mac's refusal is final: HTTP 404 (a server without the route, or not my turn) and 409
// (ended, busy, not_last, hinted). A refusal repeats on every retry and would stall the talk for good, so the entry is
// dropped and the turn goes. Anything else did not reach the Mac or was not answered (offline, a timeout, a 5xx, an
// error that is not an `ApiError`) and is retried once by `settle`, then thrown.
// The drops reach the Mac in the order they were tapped: each is sent only once the one before it has reached the Mac
// (succeeded or was refused). Two can be open at once (↻ on T3, 「취소」, ↻ on T1): sent side by side, the drop of T1
// could land while T3 is live, be refused `not_last`, and leave T1 and Ryan's reply to it live on the Mac after the
// retried drop of T3. A drop queued behind one that did not reach the Mac is not sent and fails offline too; `settle`
// then sends them again in order, earlier first. No React, so the timing can be tested (as `soheeChance`).
import { ApiError } from "../api/client";

export type Dropper = {
  drop: (idx: number) => void;
  settle: () => Promise<void>;
};

const refused = (e: unknown) => e instanceof ApiError && (e.status === 404 || e.status === 409);

export function createDropper(send: (idx: number) => Promise<unknown>): Dropper {
  // the drops not yet known to have reached the Mac, in the order tapped, each with its latest request
  let open: { idx: number; sent: Promise<unknown> }[] = [];
  let running: Promise<void> | null = null;

  // sent once the drop before it has reached the Mac; not sent at all when that one did not
  const after = (earlier: Promise<unknown>, idx: number) =>
    earlier.then(
      () => send(idx),
      (e) => (refused(e) ? send(idx) : Promise.reject(new ApiError("offline"))),
    );

  async function run() {
    // the first open drop each time, so a drop tapped while this runs is settled here too, after the earlier ones
    while (open.length > 0) {
      const d = open[0];
      try {
        await d.sent;
      } catch (e) {
        if (!refused(e)) {
          d.sent = send(d.idx); // once more; a drop tapped meanwhile waits for this one
          try {
            await d.sent;
          } catch (e2) {
            if (!refused(e2)) throw e2; // stays open, its request failed, for the next settle
          }
        }
      }
      open = open.filter((o) => o !== d);
    }
  }

  return {
    drop: (idx) => {
      if (open.some((d) => d.idx === idx)) return; // a double tap sends one request
      const earlier = open[open.length - 1];
      const sent = earlier ? after(earlier.sent, idx) : send(idx);
      sent.catch(() => {}); // settled later; no unhandled rejection meanwhile
      open.push({ idx, sent });
    },
    settle: () => {
      // two at once share one run, so a failed drop is re-sent once
      running ??= run().finally(() => {
        running = null;
      });
      return running;
    },
  };
}
