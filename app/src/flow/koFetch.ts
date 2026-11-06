// Fetching Sohee's interpretation for one screen and playing her voice, without React, so the timing can be tested
// (spec docs/superpowers/specs/2026-11-06-korean-translation-design.md 2, 4; final review). The text shows as soon
// as it comes; her sound comes a moment later, so whether it may play is asked again when it arrives.
import type { ScriptLine } from "../api/types";
import { koOf, type Ko, type KoEntry } from "./interpret";

export type KoDeps = {
  getKo: (idx: number) => Promise<{ text: string }>;
  getKoAudio: (idx: number) => Promise<{ audio: string }>;
  play: (audio: string) => void; // stops what plays and plays this
  allow: (auto: boolean) => boolean; // auto: playing by herself when the line opens; else a tap on her line
  onChange: (got: Record<number, KoEntry>) => void;
};

export type KoFetch = {
  // the line was opened: fetch the text if needed, then the sound, and play it if `stillOpen()` and `allow(true)`
  // still hold when it arrives
  open: (idx: number, line: ScriptLine | undefined, stillOpen: () => boolean) => void;
  // a tap on Sohee's line: plays while `stillHere()` and `allow(false)` hold, fetching the sound first if it is
  // missing (a sound that could not be made, or was not made while she could not play, is made now)
  replay: (idx: number, line: ScriptLine | undefined, stillHere: () => boolean) => void;
  start: () => void;
  stop: () => void; // the screen went away: nothing plays or changes after this
};

const isKo = (e: KoEntry | undefined): e is Ko => typeof e === "object";

export function createKoFetch(deps: KoDeps): KoFetch {
  let got: Record<number, KoEntry> = {};
  let alive = true;
  const texts: Record<number, Promise<Ko | null>> = {}; // one text request per line at a time
  const opened: Record<number, number> = {}; // the latest opening of each line: only it may play

  function put(idx: number, e: KoEntry) {
    if (!alive) return;
    got = { ...got, [idx]: e };
    deps.onChange(got);
  }

  const current = (idx: number, line?: ScriptLine) => got[idx] ?? koOf(line);

  function text(idx: number): Promise<Ko | null> {
    if (idx in texts) return texts[idx];
    put(idx, "loading");
    const p = deps
      .getKo(idx)
      .then(({ text: t }) => {
        const ko: Ko = { text: t, audio: null };
        put(idx, ko);
        return ko;
      })
      .catch(() => {
        put(idx, "failed");
        return null;
      })
      .finally(() => {
        delete texts[idx];
      });
    texts[idx] = p;
    return p;
  }

  async function sound(idx: number, line?: ScriptLine): Promise<string | null> {
    const ko = current(idx, line);
    if (!isKo(ko)) return null;
    if (ko.audio) return ko.audio;
    try {
      const { audio } = await deps.getKoAudio(idx);
      const now = current(idx, line);
      put(idx, { ...(isKo(now) ? now : ko), audio });
      return audio;
    } catch {
      return null; // the text stays; a tap on it tries the sound again
    }
  }

  return {
    open(idx, line, stillOpen) {
      const mine = (opened[idx] ?? 0) + 1;
      opened[idx] = mine;
      const go = () => alive && opened[idx] === mine && stillOpen() && deps.allow(true);
      void (async () => {
        if (!isKo(current(idx, line)) && !(await text(idx))) return;
        const ko = current(idx, line);
        // Her sound is made only when it could play now. Made while Ryan's feedback is on its way, her urgent sound
        // would wait ahead of his sentences in the voice worker's queue and hold him up (final review).
        if (!(isKo(ko) && ko.audio) && !go()) return;
        const audio = await sound(idx, line);
        if (audio && go()) deps.play(audio);
      })();
    },
    replay(idx, line, stillHere) {
      const go = () => alive && stillHere() && deps.allow(false);
      if (!go()) return;
      void (async () => {
        const audio = await sound(idx, line);
        if (audio && go()) deps.play(audio);
      })();
    },
    start() {
      alive = true;
    },
    stop() {
      alive = false;
    },
  };
}
