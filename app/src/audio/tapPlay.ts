// A tap on a play button, acted on (spec play-button-feedback 3): `playTap` decides; this stops the queue or calls
// `play`, which stops what plays and queues the button's sound with its tag.
import { playTap } from "../flow/playTap";
import type { SoundQueue } from "./player";

export function tapPlay(sounds: SoundQueue, tag: string, play: () => void, at: number = Date.now()): void {
  const what = playTap(sounds.nowTag(), tag, at);
  if (what === "stop") sounds.clear();
  else if (what === "play") play();
}
