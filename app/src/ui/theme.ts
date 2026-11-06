export const colors = {
  bg: "#FFFFFF",
  text: "#1F2328",
  sub: "#5C6370",
  weak: "#8A8A8A",
  strong: "#FFE066",
  stress: "#D9480F", // stressed syllables in the three-line notes: bold dark orange text, no fill (2026-11-06 user)
  ryan: "#F1F3F5",
  user: "#E7F5FF",
  feedback: "#FFF9DB",
  primary: "#1C7ED6",
  sohee: "#2F9E44", // Sohee's tag on her interpretation (spec korean-translation 2)
  soheeText: "#1F6F34", // her Korean: darker, to read on the gray and blue bubbles
  danger: "#C92A2A",
};

// The gap above each screen's content. The frame in App.tsx already keeps clear of the status bar; this used to
// add the bar's height too, when each screen kept clear of it alone.
export const top = 12;
