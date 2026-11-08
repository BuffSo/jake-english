import type { Home, Said } from "../api/types";

// What Ryan says on the first screen, in order, as text under his picture. He greets once, when the app starts;
// coming back he only asks again (2026-11-06 user: 「다시 첫 화면으로 오면 또 안녕하세요로 시작해. 이상하지?」). The
// app cannot tell why the learner came back, so the line assumes nothing about a finished roleplay.
export function homeLines(home: Pick<Home, "lines">, returning: boolean): Said[] {
  const { lines } = home;
  if (!returning) return [lines.greeting, lines.ask_mode];
  return [lines.ask_again ?? lines.ask_mode]; // an older server has no ask_again
}

// What Ryan says aloud: the lines above, then on the day's first start his shadowing tip, after the question. The tip
// is heard, not shown: as text it pushed the 「복습하기」 card off the bottom of the phone (spec ryan-shadowing-tip 2, 3;
// 2026-11-08 user).
export function homeSounds(home: Pick<Home, "lines" | "tip">, returning: boolean): Said[] {
  const said = homeLines(home, returning);
  return !returning && home.tip ? [...said, home.tip] : said;
}
