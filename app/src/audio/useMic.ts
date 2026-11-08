// The recording buttons of the free-talk screens (spec free-talk-design 「제약」: the same buttons as the roleplay):
// 「🎤 말하기」 / 「🎤 따라 말하기」, 「● 말하기 끝」 and 「취소」, with the cues, the voice line, the cancel after 5 s
// without speech and the stop after an 8 s pause.
//
// A copy of the roleplay screen's wiring, in the same order and with the same guards: `doStart`, `stopRec`, the file
// deletion of `sendRec`, `doCancel`, `doSilentCancel` and the button handlers above them (`startRecording`,
// `stopRecording`, `cancelRecording`, `silentCancel`) in `app/src/screens/RoleplayScreen.tsx`. One gate for every
// start, stop and cancel; a 「취소」 tapped while the mic is still starting is kept for when it is on; taps are held a
// moment after a cancel; leaving bumps `epoch`, so a start, stop or answer from before drops itself. The rules live in
// `app/src/flow/gate.ts` and `gate.test.ts` keeps them. The roleplay screen does not use this yet, so the two copies
// must change together until it does (docs/todo 20261108_44_todo_roleplay_use_usemic.md).
import { File } from "expo-file-system";
import { useEffect, useRef } from "react";

import { createGate, createStartCancel, runThenHold, startKeepingCancel, stopThenSend, tapHold } from "../flow/gate";
import { useRecorder } from "./useRecorder";

export type MicOptions = {
  // read inside the gate, so a double tap that got past the redraw finds the screen already recording
  canStart: () => boolean;
  // stop the sounds and tell the screen it is recording; runs before the mic comes on (`startKeepingCancel`)
  beforeStart: () => void;
  // the recording was thrown away (「취소」, a cancel kept while the mic was starting, or a stop that failed)
  onCancelled: () => void;
  // no speech came in time after the mic came on: thrown away the way 「취소」 does (spec record-feedback 4)
  onNoSpeech: () => void;
  // the mic did not come on (no permission, the recorder failed). Left out, it is told as a cancel. The roleplay
  // screen says why (`micFailed`, todo 20261108_34 1).
  onFailed?: () => void;
  // the recording is stopped and about to be sent
  onStopped: () => void;
  // Sends the recording and reads the answer, outside the gate; handles its own errors. `live()` turns false when the
  // screen is left (`leave`, unmount), so a late answer drops itself. The file is deleted after it, sent or not.
  send: (uri: string, live: () => boolean) => Promise<void>;
};

export function useMic(o: MicOptions) {
  const rec = useRecorder();
  // the callbacks of the last render: the auto-stop and the no-speech cancel were handed over when the mic came on
  const opts = useRef(o);
  opts.current = o;
  // one start or stop at a time; the recording is sent and the answer read outside it (`stopThenSend`)
  const gate = useRef(createGate()).current;
  // a 「취소」 tapped while the mic is still starting, kept for when it is on (todo 26 1)
  const startCancel = useRef(createStartCancel()).current;
  const mounted = useRef(true);
  // bumped by every leave(): a start, stop or answer that began before it sees the number change and drops itself
  const epoch = useRef(0);

  useEffect(() => {
    mounted.current = true;
    return () => {
      // gone mid-answer: the stream may still answer; its sounds and errors must not reach other screens
      mounted.current = false;
    };
  }, []);

  const left = (my: number) => !mounted.current || epoch.current !== my;

  // a start right after 「취소」 is the second tap of a double tap, on the button the redraw put there
  const start = () => void (tapHold.on ? undefined : gate.run(doStart));
  const stop = () => void stopThenSend(gate, stopRec, sendRec);
  // 「취소」 goes through the same gate and then holds taps a moment (spec record-cancel-skip 5). While the mic starts
  // the gate is busy: the cancel is kept and done when it is on.
  const cancel = () => void (startCancel.ask() ? undefined : runThenHold(gate, tapHold, doCancel));
  // no speech for a while after the mic came on: thrown away the way 「취소」 does, through the same gate and hold, so
  // a 「말하기 끝」 at the same moment either sends first or finds nothing (spec record-feedback 4, 5).
  // `levelPoll` calls this once and never again, and `runThenHold` does nothing while taps are held: a recording
  // without speech would then go on to 55 s. Nothing holds taps while the mic is on today; a new hold that can start
  // during a recording must not drop this cancel (todo 20261108_34 3).
  const silentCancel = () => void runThenHold(gate, tapHold, doSilentCancel);

  async function doCancel(): Promise<boolean> {
    if (!rec.isRecording()) return false; // a stop or the auto-stop got there first
    await rec.cancel();
    opts.current.onCancelled();
    return true;
  }

  async function doSilentCancel(): Promise<boolean> {
    if (!rec.isRecording()) return false; // a stop or 「취소」 got there first
    await rec.cancel();
    opts.current.onNoSpeech();
    return true;
  }

  async function doStart() {
    if (!opts.current.canStart()) return;
    const my = epoch.current;
    opts.current.beforeStart();
    const how = await startKeepingCancel(
      startCancel,
      // a long pause after speaking ends it as 「말하기 끝」 does, through the same gate (spec record-feedback 4)
      () => rec.start(stop, { onNoSpeech: silentCancel, onSpeechEnd: stop }),
      () => left(my),
    );
    // no permission or the mic did not start: back to before speaking (todo 20261108_34 1)
    if (how === "failed") (opts.current.onFailed ?? opts.current.onCancelled)();
    // left while the mic was starting (permission prompt)
    else if (how === "left") await rec.discard();
    // 「취소」 tapped while the mic was starting: thrown away now that it is on, as `doCancel` does (todo 26 1)
    else if (how === "cancelled") {
      await rec.cancel();
      opts.current.onCancelled();
      tapHold.start();
    }
  }

  // Stops the recorder, inside the gate. Gives the recording and the leave count it was made under, when it is to be
  // sent; the sending happens outside the gate (`stopThenSend`).
  async function stopRec(): Promise<{ uri: string; my: number } | undefined> {
    if (!rec.isRecording()) return undefined; // already stopped (auto-stop and a tap)
    const my = epoch.current;
    let uri: string;
    try {
      uri = await rec.stop();
    } catch {
      opts.current.onCancelled();
      return undefined;
    }
    if (left(my)) {
      // left while the recorder was stopping: `discard()` found it already stopped, so delete it here unsent
      deleteFile(uri);
      return undefined;
    }
    opts.current.onStopped();
    return { uri, my };
  }

  async function sendRec({ uri, my }: { uri: string; my: number }) {
    try {
      await opts.current.send(uri, () => !left(my));
    } finally {
      deleteFile(uri); // sent to the Mac; nothing stays on the phone
    }
  }

  // Leaving the screen: a recording in progress is deleted without being sent, and a start, stop or answer still
  // on its way drops itself (`epoch`, set before anything is awaited: PR #13 review). The screen stops its sounds.
  async function leave(): Promise<void> {
    epoch.current += 1;
    await rec.discard();
  }

  return { start, stop, cancel, leave, liveSince: rec.liveSince, onLevel: rec.onLevel };
}

function deleteFile(uri: string) {
  try {
    new File(uri).delete();
  } catch {
    // already gone
  }
}
