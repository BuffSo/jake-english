import type { Home, Said } from "../api/types";

// What Ryan says on the first screen, in order. He greets once, when the app starts; coming back he only asks
// again (2026-11-06 user: 「다시 첫 화면으로 오면 또 안녕하세요로 시작해. 이상하지?」). The app cannot tell why the
// learner came back, so the line assumes nothing about a finished roleplay.
export function homeLines(lines: Home["lines"], returning: boolean): Said[] {
  if (!returning) return [lines.greeting, lines.ask_mode];
  return [lines.ask_again ?? lines.ask_mode]; // an older server has no ask_again
}
