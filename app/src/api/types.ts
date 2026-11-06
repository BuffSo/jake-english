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
export type Issue = { target: string; heard: string; sound: [string, string] | null; explain: string };
// turn and retry are the roleplay's own tries; practice (the learner's lines again) and shadow (following Ryan's
// lines) are practice tries, from the end screen or from a past bubble mid-roleplay, and never move the roleplay on
export type AttemptMode = "turn" | "retry" | "practice" | "shadow";
export type Attempt = {
  n: number;
  mode: AttemptMode;
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
// thinking-face picture paths per person, cross-faded while the app waits (/home `images.thinking`)
export type Thinking = { jake: string[]; ryan: string[] };
export type Home = {
  lines: { greeting: Said; ask_mode: Said; ask_situation: Said; ask_recommend: Said };
  // jake: Jake's front picture, shown while his suggestion waits for the learner's pick (absent on an older server)
  images: { front: string; listening: string; jake?: string; thinking: Thinking };
};
export type Progress = { no: number; total: number }; // 「내 대사 no/total」
export type LineWithProgress = ScriptLine & { progress: Progress };
// One try at a line inside the roleplay, as the end screen shows it (server Engine.summary)
export type Try = {
  n: number;
  mode: "turn" | "retry";
  heard: string;
  followed: boolean;
  issues: { target: string; heard: string; say_ko: string }[]; // say_ko: the line the end screen shows
  point_ko: string;
};
export type TranscriptLine = { line: ScriptLine; tries: Try[] };
export type Summary = { say: Said; lines: TranscriptLine[] };
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
export const SUMMARY_KEYS = ["say", "lines"] as const;
export const TRY_KEYS = ["n", "mode", "heard", "followed", "issues", "point_ko"] as const;
export const ISSUE_KEYS = ["target", "heard", "say_ko"] as const;

type Same<A, B> = [A] extends [B] ? ([B] extends [A] ? true : never) : never;
export const KEYS_MATCH: [
  Same<keyof Roleplay, (typeof ROLEPLAY_KEYS)[number]>,
  Same<keyof ScriptLine, (typeof LINE_KEYS)[number]>,
  Same<keyof Syllable, (typeof SYLLABLE_KEYS)[number]>,
  Same<AttemptEvent["type"], (typeof EVENT_TYPES)[number]>,
  Same<keyof Summary, (typeof SUMMARY_KEYS)[number]>,
  Same<keyof Try, (typeof TRY_KEYS)[number]>,
  Same<keyof Try["issues"][number], (typeof ISSUE_KEYS)[number]>,
] = [true, true, true, true, true, true, true];
