// The tag of the sound playing now, as React state (spec play-button-feedback 1): a play button's 🔊 bounces while it
// is its own. Re-renders only when the tag changes.
import { useCallback, useSyncExternalStore } from "react";

import type { SoundQueue } from "./player";

export function usePlayingTag(sounds: SoundQueue): string | null {
  const subscribe = useCallback((cb: () => void) => sounds.subscribeTag(cb), [sounds]);
  return useSyncExternalStore(subscribe, () => sounds.nowTag().tag);
}
