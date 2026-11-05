import { StatusBar } from "react-native";

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
  danger: "#C92A2A",
};

export const top = (StatusBar.currentHeight ?? 24) + 12;
