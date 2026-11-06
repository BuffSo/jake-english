// Who says each bubble, like a messenger: the others on the left in gray, me on the right in blue, a name above each
// bubble (2026-11-06 user, after the phone test: they read Ryan's line as theirs). `now`: the line to say this turn,
// also in shadow practice, where it is Ryan's line (the learner says it). Blue matches the 「내 대사 1/3」 count; yellow
// stays Ryan's feedback.
export type Part = "ryan" | "feedback" | "jake" | "mine" | "now";
export type Speaker = { name: string; side: "left" | "right" };

export const SPEAKERS: Record<Part, Speaker> = {
  ryan: { name: "라이언", side: "left" },
  feedback: { name: "라이언", side: "left" },
  jake: { name: "제이크", side: "left" },
  mine: { name: "나", side: "right" },
  now: { name: "내 차례", side: "right" },
};
