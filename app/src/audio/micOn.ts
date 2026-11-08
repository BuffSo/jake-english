// The steps that turn the mic on, in order (spec record-feedback 1), kept apart from `useRecorder` so they can be
// tested without a recorder: permission, getting ready, the start cue, and only then the mic, so a cue heard means
// recording and the cue is not in the recording. Nothing ready, no cue: the screen says the mic cannot be used.
export async function turnMicOn(steps: {
  permit: () => Promise<boolean>;
  prepare: () => Promise<void>;
  cue: (c: "start" | "cancel") => Promise<void>;
  record: () => void;
}): Promise<void> {
  if (!(await steps.permit())) throw new Error("mic");
  await steps.prepare();
  await steps.cue("start");
  try {
    steps.record();
  } catch (e) {
    // the start cue already said 「recording」: the cancel cue takes it back (todo 20261108_34 1)
    void steps.cue("cancel");
    throw e;
  }
}
