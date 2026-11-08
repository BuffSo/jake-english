// Whether Ryan's answer to a recording is still playing (spec three-line-listen 5): a bubble's 🔊 must not cut him
// off. The roleplay marks each sound of his answer as it queues it; the answer is over when the queue stops,
// whether it played out or something cleared it (「🔊 다시 듣기」, leaving). A sound the learner asks for afterwards
// is not an answer. Without React, so it can be tested; `useAnswering` wires it to the screen.
import type { SoundQueue } from "./player";

export type AnswerWatch = { mark: () => void; stop: () => void };

export function createAnswerWatch(
  sounds: Pick<SoundQueue, "subscribe" | "isPlaying">,
  onChange: (answering: boolean) => void,
): AnswerWatch {
  let answering = false;
  let alive = true;
  const set = (v: boolean) => {
    if (!alive || answering === v) return;
    answering = v;
    onChange(v);
  };
  const unsubscribe = sounds.subscribe((playing) => {
    if (!playing) set(false);
  });
  return {
    // call right after queueing a sound of the answer
    mark: () => {
      if (sounds.isPlaying()) set(true);
    },
    stop: () => {
      alive = false;
      unsubscribe();
    },
  };
}
