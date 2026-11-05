// Whether the sound queue is playing, as React state: the screen re-renders when a sound starts or the queue runs
// dry, so a button can wait until Ryan has finished (spec roleplay-practice 9).
import { useCallback, useSyncExternalStore } from "react";

import type { SoundQueue } from "./player";

export function usePlaying(sounds: SoundQueue): boolean {
  const subscribe = useCallback((cb: () => void) => sounds.subscribe(cb), [sounds]);
  return useSyncExternalStore(subscribe, () => sounds.isPlaying());
}
