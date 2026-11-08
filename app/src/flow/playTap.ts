// What a tap on a play button does (spec play-button-feedback 3): a quiet button plays; the button whose sound plays
// stops it; but a second tap within TAP_HOLD_MS of its start is the second tap of a double tap and does nothing, so a
// double tap is not 「play, then stop at once」. Another button's tap plays its own sound, stopping the other.
import type { NowTag } from "../audio/player";
import { TAP_HOLD_MS } from "./gate";

export function playTap(now: NowTag, mine: string, at: number): "play" | "stop" | "ignore" {
  if (now.tag !== mine) return "play";
  return at - now.since < TAP_HOLD_MS ? "ignore" : "stop";
}
