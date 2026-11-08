import type { Resume, Roleplay, ScriptLine } from "../api/types";
import { resumeHistory, resumeLabel, resumeSeen } from "./resume";

// a made-up conversation: Ryan, me, Ryan, me, Ryan
const RP = "aaaaaaaaaaaa";
const texts: [ScriptLine["speaker"], string][] = [
  ["ryan", "Hi, welcome. Do you have a reservation?"],
  ["user", "Yes, I booked a room for two nights."],
  ["ryan", "Great. Can I see your ID, please?"],
  ["user", "Sure, here you go."],
  ["ryan", "Thank you. Enjoy your stay."],
];
const lines: ScriptLine[] = texts.map(([speaker, text], idx) => ({
  idx,
  speaker,
  text,
  kind: "script",
  three: null,
  audio: null,
  ko: null,
  ko_audio: null,
}));
const roleplay: Roleplay = {
  id: RP,
  created: "2026-11-08T10:00:00",
  situation: "호텔 체크인",
  frame: { title_ko: "호텔 체크인하기", user_role_ko: "투숙객", ryan_role_ko: "호텔 직원", place_ko: "호텔 프런트", goal_ko: "체크인" },
  lines,
  attempts: {},
  pos: 2,
  origin: null,
  topic: null,
  pick: null,
};
const resume = (at: number, said: Resume["said"], ended = false): Resume => ({
  roleplay: { ...roleplay, pos: at },
  at,
  progress: { no: 2, total: 2 },
  said,
  ended,
});

test("the lines before the start, with what was heard", () => {
  const r = resume(2, [{ idx: 1, heard: "Yes, I booked a room for two nights.", n: 2 }]);
  expect(resumeHistory(r)).toEqual([
    { kind: "ryan", text: lines[0].text, idx: 0 },
    { kind: "user", text: "Yes, I booked a room for two nights.", script: lines[1].text, idx: 1, rec: { rp_id: RP, idx: 1, n: 2 } },
  ]);
  expect(Object.keys(resumeSeen(r)).map(Number)).toEqual([0, 1]);
});

test("a skipped line keeps its script only", () => {
  const r = resume(4, [{ idx: 1, heard: "Yes, I booked a room.", n: 1 }]);
  expect(resumeHistory(r)[3]).toEqual({ kind: "user", text: "", script: lines[3].text, idx: 3, skipped: true });
  expect(resumeSeen(r)[2]).toEqual(lines[2]);
});

test("nothing before the first line", () => {
  expect(resumeHistory(resume(0, []))).toEqual([]);
  expect(resumeSeen(resume(0, []))).toEqual({});
});

test("the label of a conversation left mid-way", () => {
  expect(resumeLabel(resume(2, [], false))).toBe("호텔 체크인하기 · 내 대사 2/2");
});

test("the label of a conversation gone to the end: how many lines of mine are unrecorded", () => {
  const said = [{ idx: 3, heard: "Sure, here you go.", n: 1 }];
  expect(resumeLabel(resume(0, said, true))).toBe("호텔 체크인하기 · 녹음 안 한 줄 1개");
  expect(resumeLabel(resume(0, [], true))).toBe("호텔 체크인하기 · 녹음 안 한 줄 2개");
});
