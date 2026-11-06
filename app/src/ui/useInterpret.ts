// Sohee's interpretation for the lines of one roleplay on one screen (spec
// docs/superpowers/specs/2026-11-06-korean-translation-design.md 2, 4). The fetching and the rules for when her
// voice plays live in `flow/koFetch.ts`, where they are tested; this wires them to React, the server and the sound
// queue.
import { useEffect, useRef, useState } from "react";

import { api } from "../api";
import type { ScriptLine } from "../api/types";
import type { SoundQueue } from "../audio/player";
import { koOf, type KoEntry } from "../flow/interpret";
import { createKoFetch, type KoFetch } from "../flow/koFetch";

export type Interpret = {
  // what this screen got, or what the server already keeps on the line
  entry: (idx: number, line?: ScriptLine) => KoEntry | undefined;
  open: KoFetch["open"];
  replay: KoFetch["replay"];
};

export function useInterpret(rpId: string, sounds: SoundQueue, allow: (auto: boolean) => boolean): Interpret {
  const [got, setGot] = useState<Record<number, KoEntry>>({});
  const id = useRef(rpId);
  id.current = rpId;
  const allowNow = useRef(allow); // read when a sound arrives, after the render that made it
  allowNow.current = allow;
  const ko = useRef<KoFetch | null>(null);
  if (ko.current === null) {
    ko.current = createKoFetch({
      getKo: (idx) => api.getKo(id.current, idx),
      getKoAudio: (idx) => api.getKoAudio(id.current, idx),
      play: (audio) => {
        sounds.clear();
        sounds.enqueue(api.audioSource(audio));
      },
      allow: (auto) => allowNow.current(auto),
      onChange: setGot,
    });
  }
  const k = ko.current;

  useEffect(() => {
    k.start();
    return () => k.stop();
  }, [k]);

  return { entry: (idx, line) => got[idx] ?? koOf(line), open: k.open, replay: k.replay };
}
