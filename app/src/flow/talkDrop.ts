// The drop request of 「↻ 다시 말하기」 (spec talk-resay 3 「앱이 맥에 알리지 못했을 때」). The request goes at the tap;
// before the next turn is uploaded and before 「대화 끝내기」 the screen awaits `settle`, so a drop that did not reach
// the Mac is sent once more, and if that fails too the error is thrown and the turn is not sent (the Mac would answer
// the dropped words). Only a drop that has not reached the Mac blocks the turn: a failure that is `offline` or not an
// `ApiError` is retried and thrown, but an `ApiError` with any other code is the Mac's answer (404 on a server without
// the route, 409 ended/busy/not_last/hinted). A refusal repeats on every retry and would stall the talk for good, so it
// is final: the entry is dropped and the turn goes. No React, so the timing can be tested (as `soheeChance`).
import { ApiError } from "../api/client";

export type Dropper = {
  drop: (idx: number) => void;
  settle: () => Promise<void>;
};

const refused = (e: unknown) => e instanceof ApiError && e.code !== "offline";

export function createDropper(send: (idx: number) => Promise<unknown>): Dropper {
  // the drops not yet known to have reached the Mac, with the request sent at the tap
  let open: { idx: number; sent: Promise<unknown> }[] = [];
  let running: Promise<void> | null = null;

  async function run() {
    for (const d of [...open]) {
      try {
        await d.sent;
      } catch (e) {
        if (!refused(e)) {
          try {
            await send(d.idx); // once more
          } catch (e2) {
            if (!refused(e2)) {
              d.sent = Promise.reject(e2); // stays open for the next settle
              d.sent.catch(() => {});
              throw e2;
            }
          }
        }
      }
      open = open.filter((o) => o !== d);
    }
  }

  return {
    drop: (idx) => {
      if (open.some((d) => d.idx === idx)) return; // a double tap sends one request
      const sent = send(idx);
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
