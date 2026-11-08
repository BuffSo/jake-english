// Same shapes as server/je_server/models.py. contract/*.json holds examples both sides test against.

export type Mark = "s" | "w" | "n";
export type Syllable = { en: string; ko: string; m: Mark; hi: string };
export type Word = { syl: Syllable[]; emph: boolean; link: boolean };
export type ThreeLine = { words: Word[]; reading: string };
export type Speaker = "ryan" | "user";
// reply: Ryan's English line; turn / ask / help / fix are free talk only: my English turn, my Korean turn, Ryan's
// fixed English line after it (asking for English), the corrected sentence
export type LineKind = "script" | "reply" | "turn" | "ask" | "help" | "fix";
export type Fix = { of: number; said: string; why_ko: string; why_audio: string | null };
export type ScriptLine = {
  idx: number;
  speaker: Speaker;
  text: string;
  kind: LineKind;
  three: ThreeLine | null;
  audio: string | null;
  // Sohee's Korean for the line and its sound key, made on the Mac only when asked (spec korean-translation 5)
  ko: string | null;
  ko_audio: string | null;
  // free talk only (spec free-talk-design 2, 8); null on other lines and on an older server
  parts: Said[] | null; // Ryan's answer sentence by sentence with the sound of each
  heard_upto: number | null; // sentences heard when cut off; null when heard to the end
  fix: Fix | null;
  // the Mac's own record of Sohee chance on Ryan's reply (spec free-talk-design 9), absent from an older server. It
  // holds the full sentence before 「전체 문장 보기」, so the app reads a hint through the hint routes only, never here
  hint?: unknown;
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
  at: string | null; // when it was recorded; null on tries made before 2026-11-07 (ADR-0011)
  // not followed, so teacher Ryan answered: not a turn (spec offscript-aside 6); absent on older tries
  aside?: boolean;
};
export type Roleplay = {
  id: string;
  created: string;
  situation: string;
  frame: Frame;
  lines: ScriptLine[];
  attempts: Record<string, Attempt[]>;
  pos: number;
  origin: string | null; // the first roleplay of its group when copied or picked again from a list (ADR-0011, 0013)
  // the situation topic's id; null on roleplays made before topics (spec situation-topics 7)
  topic: string | null;
  // the list line's id when picked from a topic's list (spec fixed-list-scripts 5); null otherwise
  pick: string | null;
  // "talk" for a free talk; a server from before free talk sends no kind, which is a roleplay
  kind: "roleplay" | "talk";
};
export type Said = { text: string; audio: string };
// thinking-face picture paths per person, cross-faded while the app waits (/home `images.thinking`)
export type Thinking = { jake: string[]; ryan: string[]; sohee?: string[] };
// Sohee chance (spec free-talk-design): Korean meaning + sentence starters, then the full sentence on request
export type Hint = { meaning_ko: string; starters: string[] };
export type HintFull = { text: string; say: Said };
// A situation topic and its prepared list (spec situation-topics 1, 3). The Mac keeps what Claude gets; the app only
// shows the names and sends the ids back.
export type Topic = { id: string; name_ko: string; placeholder_ko: string; picks: { id: string; title_ko: string }[] };
export type Home = {
  // ask_again: said instead of greeting + ask_mode when the learner comes back (absent on an older server).
  // ask_topic, ask_how, ask_pick, ask_describe: the situation screen's steps (spec situation-topics 6), absent on a
  // server from before topics
  lines: {
    greeting: Said;
    ask_mode: Said;
    ask_again?: Said;
    ask_situation: Said;
    ask_recommend: Said;
    ask_topic?: Said;
    ask_how?: Said;
    ask_pick?: Said;
    ask_describe?: Said;
  };
  // Ryan's shadowing tip: only on the Mac's day's first `/home?tip=1`, absent otherwise and on an older server
  // (spec ryan-shadowing-tip 4)
  tip?: Said;
  // jake: Jake's front picture, shown while his suggestion waits for the learner's pick (absent on an older server)
  // sohee: her face and whisper face; absent on a server from before the Sohee chance
  images: { front: string; listening: string; jake?: string; thinking: Thinking; sohee?: { face: string; whisper: string } };
  topics?: Topic[]; // absent on a server from before topics: use flow/situation `topicsOf`
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
// one recording: a try at a line of a roleplay, played through `recordingSource`
export type TryRef = { rp_id: string; idx: number; n: number };
// first: 「처음 녹음」, the earliest recording of this sentence in an earlier run of the same script (spec
// review-practice 4); null when there is none and on Ryan's lines
export type TranscriptLine = { line: ScriptLine; tries: Try[]; first: TryRef | null };
export type Summary = { say: Said; lines: TranscriptLine[] };
// 「지난 상황」: one script that was spoken in, with the first day it was done (spec review-practice 2)
export type PastItem = { group: string; title_ko: string; first: string; latest: string };
// the newest run of a script and its end-screen summary (spec review-practice 3)
export type PastRun = { roleplay: Roleplay; summary: Summary };
// What was heard on a recorded line of mine in a resumed conversation: the last try inside the roleplay and its
// recording number (spec resume-roleplay 2, resume-unrecorded 1)
export type HeardTry = { idx: number; heard: string; n: number };
// /resume: the newest conversation with a line of mine left unrecorded, the line to start from (`at`), the header's
// 「내 대사」 there, what was heard on every recorded line of mine, and whether it went to the end, so only its
// unrecorded lines are left (spec resume-roleplay 1, 2; resume-unrecorded 2-5). `ended` is absent on an older server,
// read as left mid-way.
export type Resume = { roleplay: Roleplay; at: number; progress: Progress; said: HeardTry[]; ended?: boolean };
// a saved sentence and the line it was saved from (spec review-practice 5, 6)
export type SavedItem = { key: string; rp_id: string; idx: number; speaker: Speaker; text: string; title_ko: string; at: string };
export type AttemptEvent =
  // n: the recording just saved on the Mac, to play it back (spec three-line-listen 7); absent on an older server
  | { type: "heard"; text: string; followed: boolean; n?: number }
  | { type: "text"; delta: string }
  | { type: "audio"; key: string }
  | { type: "error"; code: string; say: Said | null }
  | { type: "done"; next: number; issues: number };
// Free talk (spec free-talk-design 2; contract/talk-events.ndjson, talk-end.json). `heard` is my English turn heard: idx
// is its line, n its recording, korean whether it was heard again in Korean (then Ryan's fixed English `help` line
// follows, with no Claude).
export type TalkEvent =
  | { type: "heard"; text: string; n: number; idx: number; korean: boolean }
  | { type: "text"; delta: string }
  | { type: "reply"; idx: number; kind: "reply" | "help"; parts: Said[] }
  | { type: "audio"; key: string }
  | { type: "error"; code: string; say: Said | null }
  | { type: "done"; idx: number };
// one fix of the talk's end: the corrected line and the recording of the turn it fixes (null when there is none)
export type TalkItem = { line: ScriptLine; rec: TryRef | null };
// sohee: Sohee chances used in the talk, the hint and the full sentence each once (spec free-talk-design 9); absent
// from an older server
export type TalkEnd = { items: TalkItem[]; say: Said | null; sohee?: number };

// Key lists checked against contract/ by the tests; the type checks below keep them in step with the types.
export const ROLEPLAY_KEYS = ["id", "created", "situation", "frame", "lines", "attempts", "pos", "origin", "topic", "pick", "kind"] as const;
export const LINE_KEYS = ["idx", "speaker", "text", "kind", "three", "audio", "ko", "ko_audio", "parts", "heard_upto", "fix", "hint"] as const;
export const FIX_KEYS = ["of", "said", "why_ko", "why_audio"] as const;
export const SYLLABLE_KEYS = ["en", "ko", "m", "hi"] as const;
export const EVENT_TYPES = ["heard", "text", "audio", "error", "done"] as const;
export const TALK_EVENT_TYPES = ["heard", "text", "reply", "audio", "error", "done"] as const;
export const TALK_END_KEYS = ["items", "say", "sohee"] as const;
export const TALK_ITEM_KEYS = ["line", "rec"] as const;
export const SUMMARY_KEYS = ["say", "lines"] as const;
export const TRY_KEYS = ["n", "mode", "heard", "followed", "issues", "point_ko"] as const;
export const ISSUE_KEYS = ["target", "heard", "say_ko"] as const;
export const TRANSCRIPT_KEYS = ["line", "tries", "first"] as const;
export const PAST_KEYS = ["group", "title_ko", "first", "latest"] as const;
export const SAVED_KEYS = ["key", "rp_id", "idx", "speaker", "text", "title_ko", "at"] as const;
// /home `topics` (spec situation-topics; contract/home-topics.json)
export const TOPIC_KEYS = ["id", "name_ko", "placeholder_ko", "picks"] as const;
export const PICK_KEYS = ["id", "title_ko"] as const;
// /resume (contract/resume.json)
export const RESUME_KEYS = ["roleplay", "at", "progress", "said", "ended"] as const;
export const HEARD_TRY_KEYS = ["idx", "heard", "n"] as const;

type Same<A, B> = [A] extends [B] ? ([B] extends [A] ? true : never) : never;
export const KEYS_MATCH: [
  Same<keyof Roleplay, (typeof ROLEPLAY_KEYS)[number]>,
  Same<keyof ScriptLine, (typeof LINE_KEYS)[number]>,
  Same<keyof Syllable, (typeof SYLLABLE_KEYS)[number]>,
  Same<AttemptEvent["type"], (typeof EVENT_TYPES)[number]>,
  Same<keyof Summary, (typeof SUMMARY_KEYS)[number]>,
  Same<keyof Try, (typeof TRY_KEYS)[number]>,
  Same<keyof Try["issues"][number], (typeof ISSUE_KEYS)[number]>,
  Same<keyof TranscriptLine, (typeof TRANSCRIPT_KEYS)[number]>,
  Same<keyof PastItem, (typeof PAST_KEYS)[number]>,
  Same<keyof SavedItem, (typeof SAVED_KEYS)[number]>,
  Same<keyof Topic, (typeof TOPIC_KEYS)[number]>,
  Same<keyof Topic["picks"][number], (typeof PICK_KEYS)[number]>,
  Same<keyof Resume, (typeof RESUME_KEYS)[number]>,
  Same<keyof HeardTry, (typeof HEARD_TRY_KEYS)[number]>,
  Same<keyof Fix, (typeof FIX_KEYS)[number]>,
  Same<TalkEvent["type"], (typeof TALK_EVENT_TYPES)[number]>,
  Same<keyof TalkEnd, (typeof TALK_END_KEYS)[number]>,
  Same<keyof TalkItem, (typeof TALK_ITEM_KEYS)[number]>,
] = [true, true, true, true, true, true, true, true, true, true, true, true, true, true, true, true, true, true];
