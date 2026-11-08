import type { Home, Said } from "../api/types";

// What Ryan says on the first screen, in order. He greets once, when the app starts; coming back he only asks
// again (2026-11-06 user: 「다시 첫 화면으로 오면 또 안녕하세요로 시작해. 이상하지?」). The app cannot tell why the
// learner came back, so the line assumes nothing about a finished roleplay. On the day's first start the Mac adds his
// shadowing tip, said between the greeting and the question and never on coming back (spec ryan-shadowing-tip 2).
export function homeLines(home: Pick<Home, "lines" | "tip">, returning: boolean): Said[] {
  const { lines, tip } = home;
  if (!returning) return tip ? [lines.greeting, tip, lines.ask_mode] : [lines.greeting, lines.ask_mode];
  return [lines.ask_again ?? lines.ask_mode]; // an older server has no ask_again
}
