// `createAnswerWatch` as React state for the roleplay screen (spec three-line-listen 5).
import { useEffect, useRef, useState } from "react";

import { createAnswerWatch, type AnswerWatch } from "./answerWatch";
import type { SoundQueue } from "./player";

export function useAnswering(sounds: SoundQueue): { answering: boolean; mark: () => void } {
  const [answering, setAnswering] = useState(false);
  const watch = useRef<AnswerWatch | null>(null);
  useEffect(() => {
    const w = createAnswerWatch(sounds, setAnswering);
    watch.current = w;
    return () => {
      w.stop();
      watch.current = null;
    };
  }, [sounds]);
  return { answering, mark: () => watch.current?.mark() };
}
