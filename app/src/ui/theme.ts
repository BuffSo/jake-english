export const colors = {
  bg: "#FFFFFF",
  text: "#1F2328",
  sub: "#5C6370",
  weak: "#8A8A8A",
  strong: "#FFE066",
  stress: "#D9480F", // stressed syllables in the three-line notes: bold dark orange text, no fill (2026-11-06 user)
  // the Korean pronunciation line, its 「발음」 tag and the sounds in the reading line: set apart from the English line
  // (spec three-line-listen 1, 2026-11-08 user)
  pron: "#4A6585",
  ryan: "#F1F3F5",
  user: "#E7F5FF",
  feedback: "#FFF9DB",
  primary: "#1C7ED6",
  review: "#0C8599", // 「복습하기」 on the first screen: teal, not gray, which read as a disabled button (spec review-screens 1)
  free: "#7048E8", // 「자유 대화」 on the first screen: purple, on that card only (spec free-talk-design 1)
  onColor: "#FFFFFF", // text and signs on a filled card
  onColorSub: "rgba(255,255,255,0.85)", // the smaller line on a filled card
  ryanTag: "#E9ECEF", // 「라이언」 on a gray card, one step darker than the card
  sohee: "#2F9E44", // Sohee's tag on her interpretation (spec korean-translation 2)
  soheeText: "#1F6F34", // her Korean: darker, to read on the gray and blue bubbles
  danger: "#C92A2A",
  // while recording, in the blue 「● 말하기 끝」: the blinking red dot (white ring) and the thin voice line (spec
  // record-feedback 2). A red band and a red button read as too loud (2026-11-08 user).
  recDot: "#FA5252",
  voiceLine: "#A5D8FF",
  // a button that cannot be pressed now, whatever its kind: a fixed gray, not a see-through blue or gray, which read
  // like a secondary button (spec button-colors 1). The words stay readable: 「평가하고 있어요」 says what is going on.
  off: "#E9ECEF",
  offText: "#868E96",
};

// The gap above each screen's content. The frame in App.tsx already keeps clear of the status bar; this used to
// add the bar's height too, when each screen kept clear of it alone.
export const top = 12;
