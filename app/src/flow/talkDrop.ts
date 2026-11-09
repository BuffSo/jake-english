// The drop request of 「↻ 다시 말하기」 (spec talk-resay 3 「앱이 맥에 알리지 못했을 때」). The request goes at the tap;
// before the next turn is uploaded and before 「대화 끝내기」 the screen awaits `settle`, so a drop that did not reach
// the Mac is sent once more, and if that fails too the error is thrown and the turn is not sent (the Mac would answer
// the dropped words). No React, so the timing can be tested (as `soheeChance`).
export type Dropper = {
  drop: (idx: number) => void;
  settle: () => Promise<void>;
};

export function createDropper(send: (idx: number) => Promise<unknown>): Dropper {
  // the drops not yet known to have reached the Mac, with the request sent at the tap
  let open: { idx: number; sent: Promise<unknown> }[] = [];
  return {
    drop: (idx) => {
      const sent = send(idx);
      sent.catch(() => {}); // settled later; no unhandled rejection meanwhile
      open.push({ idx, sent });
    },
    settle: async () => {
      const left = open;
      for (const d of left) {
        try {
          await d.sent;
        } catch {
          await send(d.idx); // once more; a failure stays in `open` for the next settle
          d.sent = Promise.resolve();
        }
        open = open.filter((o) => o !== d);
      }
    },
  };
}
