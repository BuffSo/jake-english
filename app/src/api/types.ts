// Same shapes as server/je_server/models.py. contract/*.json holds examples both sides test against.

export type Mark = "s" | "w" | "n";
export type Syllable = { en: string; ko: string; m: Mark; hi: string };
export type Word = { syl: Syllable[]; emph: boolean; link: boolean };
export type ThreeLine = { words: Word[]; reading: string };
export type Speaker = "ryan" | "user";
export type ScriptLine = {
  idx: number;
  speaker: Speaker;
  text: string;
  kind: "script" | "reply";
  three: ThreeLine | null;
  audio: string | null;
};
export type Frame = { title_ko: string; user_role_ko: string; ryan_role_ko: string; place_ko: string; goal_ko: string };
export type Issue = { target: string; heard: string; sound: [string, string]; explain: string };
export type Attempt = {
  n: number;
  mode: "turn" | "retry";
  heard: string;
  followed: boolean;
  issues: Issue[];
  say_ko: string;
  audio: string[];
  timings: Record<string, number>;
};
export type Roleplay = {
  id: string;
  created: string;
  situation: string;
  frame: Frame;
  lines: ScriptLine[];
  attempts: Record<string, Attempt[]>;
  pos: number;
};
export type Said = { text: string; audio: string };
export type Home = {
  lines: { greeting: Said; ask_mode: Said; ask_situation: Said; ask_recommend: Said };
  images: { front: string; listening: string };
};
export type Summary = { say: Said; retry: number[] };
export type AttemptEvent =
  | { type: "heard"; text: string; followed: boolean }
  | { type: "text"; delta: string }
  | { type: "audio"; key: string }
  | { type: "reply"; line: ScriptLine }
  | { type: "error"; code: string; say: Said | null }
  | { type: "done"; next: number; issues: number };

// Key lists checked against contract/ by the tests; the type checks below keep them in step with the types.
export const ROLEPLAY_KEYS = ["id", "created", "situation", "frame", "lines", "attempts", "pos"] as const;
export const LINE_KEYS = ["idx", "speaker", "text", "kind", "three", "audio"] as const;
export const SYLLABLE_KEYS = ["en", "ko", "m", "hi"] as const;
export const EVENT_TYPES = ["heard", "text", "audio", "reply", "error", "done"] as const;

type Same<A, B> = [A] extends [B] ? ([B] extends [A] ? true : never) : never;
export const KEYS_MATCH: [
  Same<keyof Roleplay, (typeof ROLEPLAY_KEYS)[number]>,
  Same<keyof ScriptLine, (typeof LINE_KEYS)[number]>,
  Same<keyof Syllable, (typeof SYLLABLE_KEYS)[number]>,
  Same<AttemptEvent["type"], (typeof EVENT_TYPES)[number]>,
] = [true, true, true, true];
