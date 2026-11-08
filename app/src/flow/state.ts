// Screen flow as a reducer, so taps that arrive at the wrong moment (double taps, taps while Ryan is
// still talking) are ignored in one place.
import type { ErrorCode } from "../api/client";
import type { AttemptEvent, AttemptMode, HeardTry, Progress, Resume, Roleplay, Said, ScriptLine, TryRef } from "../api/types";
import { passRecorded, recordedOf, resumeHistory, resumeSeen } from "./resume";
import type { SituationStart } from "./situation";

// past and saved: the two tabs of 「복습하기」 (spec review-screens 2; it was a menu of two buttons before). The last
// conversation of a past situation is the end screen with `past` set (spec review-practice 3).
export type Screen = "home" | "situation" | "roleplay" | "end" | "past" | "saved";
export type Phase = "loading" | "ryan" | "ready" | "recording" | "evaluating" | "evaluated" | "error";
// a learner bubble keeps the script line next to what was heard (spec roleplay-practice 2), its line number for
// 「이 줄 다시」 (9), and the recording of that turn for 「🔊 내 녹음」 (spec three-line-listen 3). Its `text` is ""
// for a line skipped without a recording: the script only (spec record-cancel-skip 3).
// `skipped`: my line passed with 「건너뛰기」, no recording; its text is empty and only the script shows (spec
// record-cancel-skip 3)
export type Bubble = {
  kind: "ryan" | "user" | "feedback";
  text: string;
  idx?: number;
  script?: string;
  rec?: TryRef;
  skipped?: true;
};
// Practice: the learner's lines again (mine) or Ryan's lines to follow (shadow), in order. From the end screen it
// goes back to the end; from a past bubble in the roleplay (one line) it goes back to the roleplay (spec 9).
// 「이 줄 다시」 is mine with one line. From the saved list (spec review-practice 7) each line may belong to another
// roleplay: `runs[i]` is the roleplay of `order[i]`, and `kind` follows the line on screen.
export type Practice = {
  kind: "mine" | "shadow";
  order: number[];
  at: number;
  from: "end" | "roleplay" | "saved";
  runs?: Roleplay[];
};

export type State = {
  screen: Screen;
  roleplay: Roleplay | null;
  jake: Said | null; // the recommended situation in Jake's voice, shown on top of the roleplay to hear again
  idx: number;
  mode: AttemptMode;
  progress: Progress | null; // 「내 대사 no/total」 from the server, roleplay only
  phase: Phase;
  line: ScriptLine | null;
  // the line's three-line notes are open: each line starts plain and opens only when asked (spec roleplay-practice 8)
  reading: boolean;
  // Sohee's interpretation of the line to say is open; like the notes, each line starts without it
  // (spec korean-translation 2)
  interpreting: boolean;
  seen: Record<number, ScriptLine>;
  heard: string | null;
  // the recording of this turn, from `heard` (spec three-line-listen 4); null before it and from an older server
  heardRec: TryRef | null;
  feedback: string;
  // the line was not followed and teacher Ryan answered: 「다시 해 보기」 or 「건너뛰기」, never 「다음」 (spec
  // record-cancel-skip 2). 「다시 해 보기」 leaves nothing in the conversation and keeps the mode, so a first turn
  // stays a turn (spec offscript-aside 5, 6). Set by `heard`; cleared by `done` when the Mac found words heard
  // differently, which makes it a try at the line.
  aside: boolean;
  nextIdx: number | null;
  message: string | null;
  errorFrom: "loading" | "evaluating" | null;
  practice: Practice | null;
  // the roleplay as it was when a past line was picked for practice; restored as it is when the practice ends. Not
  // named after resuming, which is the newest conversation from the Mac (`resumed`, spec resume-roleplay; todo
  // 20261108_32 2)
  beforePractice: State | null;
  // counts practices, so the same line practised twice plays its model again (see `modelKey`)
  practiceNo: number;
  closingPlayed: boolean; // the end screen's closing words are said once, not again after each practice
  history: Bubble[];
  // the end screen shows a past situation's last conversation (spec review-practice 3); `roleplay` comes with
  // `pastLoaded`, newest run first
  past: { group: string; title: string } | null;
  // where a roleplay started from 「다시 연습」 goes back to, and its end screen too (spec review-practice 9)
  returnTo: State | null;
  beforeOpen: boolean; // the line before, in saved-sentence practice: hidden until asked (spec review-practice 7)
  // the topic and step the roleplay's situation was picked from: back from its end screen opens the situation screen
  // there (spec situation-topics 2); null starts it at the topics. Back from the roleplay mid-way always starts at
  // the topics, whose last row resumes it (spec resume-roleplay 5)
  situationFrom: SituationStart | null;
  // the mic came on in this conversation or practice: until then the turn shows 「🎤를 누르고 말하세요」 (spec
  // record-feedback 3). Set when it is on, not at the tap: a refused permission or a mic that did not start keeps it
  // (todo 20261108_34 5)
  micUsed: boolean;
  // a resumed conversation's lines of mine recorded before, by line: 「다음」 and 「건너뛰기」 pass them as bubbles on the
  // way to the next unrecorded line (spec resume-unrecorded 3). null when the conversation was not resumed.
  recorded: Record<number, HeardTry> | null;
};

export type Action =
  | { type: "home" }
  | { type: "back" }
  | { type: "endPractice" }
  | { type: "chooseRoleplay" }
  | { type: "created"; roleplay: Roleplay; jake?: Said | null; from?: SituationStart }
  | { type: "lineLoaded"; line: ScriptLine; progress?: Progress }
  | { type: "lineMissing" }
  | { type: "ryanDone" }
  | { type: "recordStart" }
  | { type: "micOn" }
  | { type: "micFailed" }
  | { type: "recordStop" }
  | { type: "recordCancel" }
  | { type: "noSpeech" }
  | { type: "skip" }
  | { type: "event"; e: AttemptEvent }
  | { type: "failed"; code: ErrorCode; say?: { text: string } }
  | { type: "retry" }
  | { type: "again" }
  | { type: "next" }
  | { type: "startPractice"; kind: "mine" | "shadow"; order: number[] }
  | { type: "restarted"; roleplay: Roleplay }
  | { type: "closingPlayed" }
  | { type: "toggleReading" }
  | { type: "interpret"; open: boolean }
  | { type: "practiseLine"; kind: "mine" | "shadow"; idx: number }
  | { type: "openReview" }
  | { type: "openPast" }
  | { type: "openSaved" }
  | { type: "openPastRun"; group: string; title: string }
  | { type: "pastLoaded"; roleplay: Roleplay }
  | { type: "startSaved"; runs: Roleplay[]; order: number[] }
  | { type: "toggleBefore" }
  | { type: "resumed"; resume: Resume };

export const initial: State = {
  screen: "home",
  roleplay: null,
  jake: null,
  idx: 0,
  mode: "turn",
  progress: null,
  phase: "loading",
  line: null,
  reading: false,
  interpreting: false,
  seen: {},
  heard: null,
  heardRec: null,
  feedback: "",
  aside: false,
  nextIdx: null,
  message: null,
  errorFrom: null,
  practice: null,
  beforePractice: null,
  practiceNo: 0,
  closingPlayed: false,
  history: [],
  past: null,
  returnTo: null,
  beforeOpen: false,
  situationFrom: null,
  micUsed: false,
  recorded: null,
};

// after the recording was thrown away for having no speech in it (spec record-feedback 4)
export const NO_SPEECH = "말소리가 없어 녹음을 멈췄어요.";

// the mic did not come on: no permission, or the recorder failed (todo 20261108_34 1); the situation screen says the same
export const MIC_FAILED = "마이크를 쓸 수 없어요. 앱의 마이크 권한을 확인해 주세요.";

// The message on screen is drawn as an error (red): after a failure, and when the mic could not be used. The notice
// after no speech is not one.
export function messageIsError(s: State): boolean {
  return s.phase === "error" || s.message === MIC_FAILED;
}

export const OFFLINE = "맥에 연결할 수 없어요. 맥과 인터넷 연결을 확인해 주세요.";

function messageFor(code: ErrorCode, say?: { text: string }): string {
  if (say?.text) return say.text;
  if (code === "offline") return OFFLINE;
  if (code === "claude_unavailable") return "지금은 라이언이 대답할 수 없어요. 맥의 인터넷 연결을 확인해 주세요.";
  return "문제가 생겼어요. 다시 해 볼까요?";
}

// The learner's own turn with nothing playing for the flow: replaying a sound (Jake's line) may clear the
// queue then. In Ryan's turn the queue's idle callback moves the roleplay on, and clearing would drop it.
export function canReplay(p: Phase): boolean {
  return p === "ready" || p === "evaluated";
}

// A sound asked for from a bubble in the roleplay (🔊, a tap on a bubble or Sohee's line): while my turn waits, also
// after an evaluation failed (its recording is saved, spec three-line-listen 4), and not over Ryan's answer or his
// error sound, which it would cut off (5). Not while recording, evaluating or in Ryan's turn, whose idle callback
// moves the roleplay on. 「🔊 다시 듣기」 at the bottom is not held back.
export function mayListen(p: Phase, answering: boolean): boolean {
  return (canReplay(p) || p === "error") && !answering;
}

// 「건너뛰기」: my turn waits for a recording, before recording or after teacher Ryan's answer, which offers only
// 「다시 해 보기」. Not after a try that offers 「다음」, which moves on already (spec record-cancel-skip 2).
export function canSkip(s: State): boolean {
  return s.screen === "roleplay" && toSay(s) && (s.phase === "ready" || (s.phase === "evaluated" && s.aside));
}

// the line on screen is the learner's to say: theirs, or Ryan's to follow in shadow practice
function toSay(s: State): boolean {
  return s.line !== null && (s.line.speaker === "user" || s.mode === "shadow");
}

// 「🎤를 누르고 말하세요」 above the buttons: my turn, before the mic was ever started in this conversation or practice
// (spec record-feedback 3). Not every turn: the screen would get noisy, and the cue and the red dot already tell at the
// tap whether the mic came on.
export function showMicHint(s: State): boolean {
  return s.screen === "roleplay" && s.phase === "ready" && toSay(s) && !s.micUsed;
}

// A 「건너뛰기」 the Mac is told of: one inside the conversation moves its place past the line (spec resume-roleplay 3).
// A practice has no place, and its line may be another conversation's (saved sentences), which must not move.
export function notifiesSkip(s: State): boolean {
  return !s.practice && s.line !== null;
}

// A recording whose evaluation records the line and moves the conversation's place when the Mac has finished it: the
// roleplay's own turn. The situation screen waits for it before asking where to resume (spec resume-roleplay 4,
// resume-unrecorded 1).
export function movesPlace(s: State): boolean {
  return s.mode === "turn";
}

const freshTurn = { heard: null, heardRec: null, feedback: "", aside: false, message: null, errorFrom: null } as const;

// The conversation moving on to line `idx` after a line of mine, with `history` so far. A resumed one passes the lines
// of mine recorded before, as bubbles (spec resume-unrecorded 3); any other goes line by line.
function moveOn(s: State, idx: number, history: Bubble[]): State {
  const turn = { ...s, ...freshTurn, nextIdx: null, mode: "turn" as const, phase: "loading" as const, line: null };
  if (!s.recorded || !s.roleplay) return { ...turn, idx, history };
  const p = passRecorded(s.roleplay, s.recorded, idx);
  return { ...turn, idx: p.idx, history: [...history, ...p.passed], seen: { ...s.seen, ...p.seen } };
}

// Leaving a practice. From the end screen: back on the end screen, ready for the next one. From the roleplay: the
// roleplay exactly as it was, so nothing is said again and the evaluation on screen stays (spec 9).
function leavePractice(s: State): State {
  if (s.practice?.from === "roleplay" && s.beforePractice) return { ...s.beforePractice, practiceNo: s.practiceNo };
  if (s.practice?.from === "saved") return { ...initial, screen: "saved" };
  return { ...s, ...freshTurn, screen: "end", practice: null, mode: "turn" };
}

// Saved sentences are practised the way their line is: Ryan's by following him, mine by saying it again.
export function kindOf(line: ScriptLine): "mine" | "shadow" {
  return line.speaker === "ryan" ? "shadow" : "mine";
}

function kindAt(rp: Roleplay, idx: number): "mine" | "shadow" {
  const line = rp.lines[idx];
  return line ? kindOf(line) : "mine";
}

// The next line of a practice, or out of it after the last. A saved-sentence practice may move to another roleplay.
function advance(s: State): State {
  const p = s.practice!;
  const at = p.at + 1;
  if (at >= p.order.length) return leavePractice(s);
  const idx = p.order[at];
  // one line at a time: the screen shows the line being practised, not what came before
  const next = { ...s, ...freshTurn, practice: { ...p, at }, idx, history: [], phase: "loading" as const, line: null };
  if (p.from !== "saved" || !p.runs) return next;
  const kind = kindAt(p.runs[at], idx);
  return { ...next, roleplay: p.runs[at], practice: { ...p, at, kind }, mode: kind === "shadow" ? "shadow" : "practice" };
}

// Back to where 「이 상황 다시 하기」 was pressed. A practice comes back to its line, loaded and heard afresh.
function restore(rt: State): State {
  if (rt.screen !== "roleplay") return rt;
  return { ...rt, ...freshTurn, phase: "loading", line: null, history: [], practiceNo: rt.practiceNo + 1 };
}

// The practice button a bubble in the roleplay gets (spec 9): Ryan's lines to follow, my lines to say again. Not my
// line on screen (「다시 해 보기」 covers it), not a line the app has not loaded, and none inside a practice. Ryan's
// line just said is still the screen's line until the next one comes, and keeps its button (todo practice-midway 2).
export function practiceFor(s: State, b: Pick<Bubble, "kind" | "idx">): "mine" | "shadow" | null {
  if (s.practice || b.idx === undefined || !s.seen[b.idx]) return null;
  if (b.kind === "user" && b.idx === s.line?.idx) return null;
  if (b.kind === "ryan") return "shadow";
  if (b.kind === "user") return "mine";
  return null;
}

// Whether the roleplay screen goes away. Back from a line practised mid-roleplay stays on it, so the screen must
// drop only that practice's recording and stream, not everything after it.
export function leavesScreen(s: State): boolean {
  return s.practice?.from !== "roleplay";
}

// What the screen remembers to play a line's model once. Inside a practice it carries the practice number: the
// screen stays mounted for a practice from the roleplay, and the same line practised again must play it again. In the
// roleplay a line keeps one key, so 「다시 해 보기」 does not play the model again (spec roleplay-practice; the user
// kept it, 2026-11-08): 「🔊 다시 듣기」 plays it.
export function modelKey(s: State): string | null {
  if (!s.line) return null;
  return s.practice ? `${s.line.idx}:${s.mode}:${s.practiceNo}` : `${s.line.idx}`;
}

// What leaving the roleplay screen sends. From a practice it is `endPractice`, which does nothing outside one: two
// taps on 「뒤로」 before the screen draws again both see the practice, and a second `back` would leave the restored
// roleplay without asking (todo practice-midway 1).
export function leaveAction(s: State): Action {
  return s.practice ? { type: "endPractice" } : { type: "back" };
}

// What was said in this turn, as conversation bubbles (what the learner said, Ryan's feedback).
function exchange(s: State): Bubble[] {
  return [
    ...(s.heard
      ? [{ kind: "user" as const, text: s.heard, script: s.line?.text, idx: s.line?.idx, rec: s.heardRec ?? undefined }]
      : []),
    ...(s.feedback ? [{ kind: "feedback" as const, text: s.feedback }] : []),
  ];
}

export function reduce(s: State, a: Action): State {
  switch (a.type) {
    case "home":
      return { ...initial };
    case "back":
      // the on-screen back button and the phone's back key: the screen before this one
      // 「복습하기」 goes home from either tab: switching tabs is not a step back (spec review-screens 2)
      if (s.screen === "situation" || s.screen === "past" || s.screen === "saved") return { ...initial };
      if (s.screen === "roleplay" && s.practice) return leavePractice(s);
      if ((s.screen === "roleplay" || s.screen === "end") && s.returnTo) return restore(s.returnTo);
      if (s.screen === "end" && s.past) return { ...initial, screen: "past" };
      // a conversation left mid-way: the topic step, whose last row resumes it (spec resume-roleplay 5, the user's
      // choice); it used to come back to the step it was picked from, like the end screen still does
      if (s.screen === "roleplay") return { ...initial, screen: "situation" };
      if (s.screen === "end") return { ...initial, screen: "situation", situationFrom: s.situationFrom };
      return s;
    case "endPractice":
      return s.screen === "roleplay" && s.practice ? leavePractice(s) : s;
    case "chooseRoleplay":
      return { ...initial, screen: "situation" };
    case "created":
      if (s.screen !== "situation") return s; // a script that comes back after the learner left
      return {
        ...initial,
        screen: "roleplay",
        roleplay: a.roleplay,
        jake: a.jake ?? null,
        phase: "loading",
        situationFrom: a.from ?? null,
      };
    case "lineLoaded":
      if (s.phase !== "loading") return s;
      return {
        ...s,
        ...freshTurn,
        line: a.line,
        reading: false,
        interpreting: false,
        beforeOpen: false,
        seen: { ...s.seen, [a.line.idx]: a.line },
        // in shadow practice Ryan's line is the learner's to say, with or without its sound
        phase: a.line.speaker === "ryan" && s.mode !== "shadow" ? "ryan" : "ready",
        nextIdx: s.mode === "retry" ? s.nextIdx : null,
        progress: a.progress ?? s.progress,
      };
    case "lineMissing":
      // a saved sentence whose line is gone is skipped, not the end of a roleplay
      if (s.practice?.from === "saved") return advance(s);
      return { ...s, screen: "end" };
    case "ryanDone":
      if (s.phase !== "ryan" || !s.line) return s;
      return { ...s, history: [...s.history, { kind: "ryan", text: s.line.text, idx: s.line.idx }], idx: s.idx + 1, phase: "loading" };
    case "recordStart":
      if (s.phase !== "ready" && s.phase !== "evaluated") return s;
      return { ...s, phase: "recording", message: null };
    case "micOn":
      return s.screen === "roleplay" ? { ...s, micUsed: true } : s;
    case "micFailed":
      // back to before speaking, saying why; the first-turn hint stays if the mic was never on (todo 20261108_34 1, 5)
      return s.phase === "recording" ? { ...s, phase: "ready", message: MIC_FAILED } : s;
    case "recordCancel":
      return s.phase === "recording" ? { ...s, phase: "ready" } : s;
    case "noSpeech":
      // thrown away like 「취소」, with a line saying why (spec record-feedback 4)
      return s.phase === "recording" ? { ...s, phase: "ready", message: NO_SPEECH } : s;
    case "recordStop":
      if (s.phase !== "recording") return s;
      return { ...s, ...freshTurn, phase: "evaluating" };
    case "event": {
      if (s.phase !== "evaluating") return s;
      const e = a.e;
      if (e.type === "heard") {
        const rec = e.n && s.roleplay && s.line ? { rp_id: s.roleplay.id, idx: s.line.idx, n: e.n } : null;
        return { ...s, heard: e.text, heardRec: rec, aside: !e.followed };
      }
      if (e.type === "text") return { ...s, feedback: s.feedback + e.delta };
      // an aside is not a turn: where 「다음」 goes stays as it was. A line not followed but with points from the Mac
      // was a try at it, and moves on like a followed one (offscript-aside 6).
      if (e.type === "done" && s.aside && e.issues === 0) return { ...s, phase: "evaluated" };
      if (e.type === "done" && s.aside) return reduce({ ...s, aside: false }, a);
      if (e.type === "done")
        return { ...s, phase: "evaluated", nextIdx: s.mode === "turn" || s.nextIdx === null ? e.next : s.nextIdx };
      if (e.type === "error") {
        const soft = e.code === "no_speech" || e.code === "too_long";
        return {
          ...s,
          phase: soft ? "ready" : "error",
          message: messageFor(e.code as ErrorCode, e.say ?? undefined),
          errorFrom: soft ? null : "evaluating",
        };
      }
      return s;
    }
    case "failed":
      // only a request this screen is waiting for can fail it; a stream left behind on leaving cannot
      if (s.screen !== "roleplay" || (s.phase !== "loading" && s.phase !== "evaluating")) return s;
      return { ...s, phase: "error", message: messageFor(a.code, a.say), errorFrom: s.phase === "loading" ? "loading" : "evaluating" };
    case "retry":
      if (s.phase !== "error") return s;
      return { ...s, phase: s.errorFrom === "loading" ? "loading" : "ready", message: null, errorFrom: null };
    case "again":
      // keep the turn that just happened before trying the line again; an aside leaves nothing and keeps the mode
      if (s.phase !== "evaluated") return s;
      if (s.aside) return { ...s, ...freshTurn, phase: "ready" };
      return { ...s, ...freshTurn, history: [...s.history, ...exchange(s)], mode: s.practice ? s.mode : "retry", phase: "ready" };
    case "next": {
      if (s.phase !== "evaluated" || s.aside) return s;
      if (s.practice) return advance(s);
      return moveOn(s, s.nextIdx ?? s.idx + 1, [...s.history, ...exchange(s)]);
    }
    case "skip": {
      // where 「다음」 goes, without a recording: nothing is sent, so the line has no try (spec record-cancel-skip 2)
      if (!canSkip(s)) return s;
      if (s.practice) return advance(s);
      const line = s.line!;
      // the line stays in the conversation as its script, unless a try at it is there already (spec 3); teacher
      // Ryan's answer is not kept, as after 「다시 해 보기」
      const said = s.history.some((b) => b.kind === "user" && b.idx === line.idx);
      const skipped: Bubble = { kind: "user", text: "", script: line.text, idx: line.idx, skipped: true };
      return moveOn(s, s.nextIdx ?? s.idx + 1, said ? s.history : [...s.history, skipped]);
    }
    case "startPractice":
      if (s.screen !== "end" || a.order.length === 0) return s;
      return {
        ...s,
        ...freshTurn,
        screen: "roleplay",
        mode: a.kind === "shadow" ? "shadow" : "practice",
        practice: { kind: a.kind, order: a.order, at: 0, from: "end" },
        practiceNo: s.practiceNo + 1,
        micUsed: false,
        idx: a.order[0],
        history: [],
        line: null,
        reading: false,
        interpreting: false,
        phase: "loading",
        progress: null,
      };
    case "practiseLine": {
      // a past line, straight from what the app already holds, so nothing waits on the server (spec 9); its notes
      // open when asked, as on any line
      const line = s.seen[a.idx];
      if (s.screen !== "roleplay" || s.practice || !canReplay(s.phase) || !line || a.idx === s.line?.idx) return s;
      if (line.speaker !== (a.kind === "shadow" ? "ryan" : "user")) return s;
      return {
        ...s,
        ...freshTurn,
        mode: a.kind === "shadow" ? "shadow" : "practice",
        practice: { kind: a.kind, order: [a.idx], at: 0, from: "roleplay" },
        practiceNo: s.practiceNo + 1,
        micUsed: false,
        beforePractice: s,
        idx: a.idx,
        line,
        reading: false,
        interpreting: false,
        nextIdx: null,
        history: [],
        phase: "ready",
      };
    }
    case "restarted": {
      // the same script as a new roleplay (spec roleplay-practice 6); Jake's recommended situation stays on top.
      // Started from 「다시 연습」 (a past view or saved practice), back leads there (spec review-practice 9).
      const fromSaved = s.screen === "roleplay" && s.practice?.from === "saved";
      if (s.screen !== "end" && !fromSaved) return s;
      const returnTo = s.returnTo ?? (s.past || fromSaved ? s : null);
      return {
        ...initial,
        screen: "roleplay",
        roleplay: a.roleplay,
        jake: fromSaved ? null : s.jake,
        phase: "loading",
        returnTo,
        situationFrom: returnTo ? null : s.situationFrom,
      };
    }
    case "closingPlayed":
      return { ...s, closingPlayed: true };
    case "toggleReading":
      return s.line ? { ...s, reading: !s.reading } : s;
    case "interpret":
      return s.line ? { ...s, interpreting: a.open } : s;
    case "openReview":
      // 「복습하기」 opens on the past tab (spec review-screens 2)
      return s.screen === "home" ? { ...initial, screen: "past" } : s;
    case "openPast":
    case "openSaved": {
      // the tabs, taken only on 「복습하기」
      const tab = a.type === "openPast" ? "past" : "saved";
      return s.screen === "past" || s.screen === "saved" ? { ...initial, screen: tab } : s;
    }
    case "openPastRun":
      if (s.screen !== "past") return s;
      return { ...initial, screen: "end", past: { group: a.group, title: a.title }, closingPlayed: true };
    case "pastLoaded":
      // the lines are known at once, so a practice from here shows the line before (spec roleplay-practice 4)
      if (s.screen !== "end" || !s.past) return s;
      return { ...s, roleplay: a.roleplay, seen: Object.fromEntries(a.roleplay.lines.map((l) => [l.idx, l])) };
    case "startSaved": {
      if (s.screen !== "saved" || a.order.length === 0 || a.runs.length !== a.order.length) return s;
      const kind = kindAt(a.runs[0], a.order[0]);
      return {
        ...initial,
        screen: "roleplay",
        roleplay: a.runs[0],
        mode: kind === "shadow" ? "shadow" : "practice",
        practice: { kind, order: a.order, at: 0, from: "saved", runs: a.runs },
        practiceNo: s.practiceNo + 1,
        idx: a.order[0],
        phase: "loading",
      };
    }
    case "toggleBefore":
      return s.line ? { ...s, beforeOpen: !s.beforeOpen } : s;
    case "resumed": {
      // the newest conversation from where it stopped, with what was said before it (spec resume-roleplay 2), passing
      // its lines recorded before (spec resume-unrecorded 3); only from the situation screen, so a second tap on the
      // row does nothing
      if (s.screen !== "situation") return s;
      const r = a.resume;
      return {
        ...initial,
        screen: "roleplay",
        roleplay: r.roleplay,
        idx: r.at,
        history: resumeHistory(r),
        seen: resumeSeen(r),
        progress: r.progress,
        phase: "loading",
        recorded: recordedOf(r),
      };
    }
  }
}
