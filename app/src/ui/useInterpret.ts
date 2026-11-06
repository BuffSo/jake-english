// Sohee's interpretation for the lines of one roleplay: fetches the text, then her sound of it, and plays her voice
// (spec docs/superpowers/specs/2026-11-06-korean-translation-design.md 2, 4). The text shows as soon as it comes;
// the sound comes a moment later, so whether it may play is asked when it arrives (`stillOpen`, `allow(true)`).
import { useEffect, useRef, useState } from "react";

import { api } from "../api";
import type { ScriptLine } from "../api/types";
import type { SoundQueue } from "../audio/player";
import { koOf, type Ko, type KoEntry } from "../flow/interpret";

export type Interpret = {
  // what this screen got, or what the server already keeps on the line
  entry: (idx: number, line?: ScriptLine) => KoEntry | undefined;
  // the line was opened: fetch the text if needed, then the sound, and play it if `stillOpen()` and `allow(true)`
  // still hold when it arrives
  open: (idx: number, line: ScriptLine | undefined, stillOpen: () => boolean) => void;
  // a tap on Sohee's line: plays when `allow(false)`, fetching the sound first if it is missing (a sound that could
  // not be made is tried again)
  replay: (idx: number, line?: ScriptLine) => void;
};

const isKo = (e: KoEntry | undefined): e is Ko => typeof e === "object";

export function useInterpret(rpId: string, sounds: SoundQueue, allow: (auto: boolean) => boolean): Interpret {
  const [got, setGot] = useState<Record<number, KoEntry>>({});
  const latest = useRef(got); // for the async code, which outlives the render it started in
  const allowNow = useRef(allow);
  allowNow.current = allow;
  const mounted = useRef(true);
  const texts = useRef<Record<number, Promise<Ko | null>>>({}); // one text request per line at a time
  const opened = useRef<Record<number, number>>({}); // the latest opening of each line: only it may play

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);

  function put(idx: number, e: KoEntry) {
    latest.current = { ...latest.current, [idx]: e };
    if (mounted.current) setGot(latest.current);
  }

  const current = (idx: number, line?: ScriptLine) => latest.current[idx] ?? koOf(line);

  function play(audio: string) {
    sounds.clear();
    sounds.enqueue(api.audioSource(audio));
  }

  function text(idx: number): Promise<Ko | null> {
    const asked = texts.current[idx];
    if (asked) return asked;
    put(idx, "loading");
    const p = api
      .getKo(rpId, idx)
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
        delete texts.current[idx];
      });
    texts.current[idx] = p;
    return p;
  }

  async function sound(idx: number, line?: ScriptLine): Promise<string | null> {
    const ko = current(idx, line);
    if (!isKo(ko)) return null;
    if (ko.audio) return ko.audio;
    try {
      const { audio } = await api.getKoAudio(rpId, idx);
      const now = current(idx, line);
      put(idx, { ...(isKo(now) ? now : ko), audio });
      return audio;
    } catch {
      return null; // the text stays; a tap on it tries the sound again
    }
  }

  return {
    entry: (idx, line) => got[idx] ?? koOf(line),
    open(idx, line, stillOpen) {
      const mine = (opened.current[idx] ?? 0) + 1;
      opened.current[idx] = mine;
      void (async () => {
        const ko = current(idx, line);
        if (!isKo(ko) && !(await text(idx))) return;
        const audio = await sound(idx, line);
        if (audio && mounted.current && opened.current[idx] === mine && stillOpen() && allowNow.current(true)) play(audio);
      })();
    },
    replay(idx, line) {
      if (!allowNow.current(false)) return;
      void (async () => {
        const audio = await sound(idx, line);
        if (audio && mounted.current && allowNow.current(false)) play(audio);
      })();
    },
  };
}
