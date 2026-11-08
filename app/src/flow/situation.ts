// The situation screen's steps (spec situation-topics 2): the topic, how to pick the situation, then the list, Jake's
// suggestion or the learner's own words. Kept as plain functions so the screen's rules are tested without it.
import type { Home, Topic } from "../api/types";

// confirm: Jake has suggested a situation and waits for 「이걸로 할게요」 or 「다른 걸로요」 (2026-11-06, user).
// askRecommend: 「제이크에게 상황을 하나 추천받아 볼까요?」, asked only when the learner said 「모르겠어」 while describing.
export type SituationStep = "topic" | "how" | "list" | "describe" | "askRecommend" | "working" | "confirm";
// the step the situation was picked from: where back from a wait or Jake's suggestion goes, and where back from
// the roleplay's end screen comes to (spec 2, 6; mid-way back goes to the topics, spec resume-roleplay 5)
export type Origin = "how" | "list" | "describe";
export type SituationStart = { topic: string; step: Origin };
export type HowChoice = "list" | "jake" | "describe";

export const HOW_LABEL: Record<HowChoice, string> = {
  list: "목록에서 고르기",
  jake: "제이크에게 추천받기",
  describe: "직접 말하거나 쓰기",
};

// 「그 밖의 상황」: the topic without a role of its own, and the one a record from before topics belongs to. The Mac
// server has the same id (`topics.OTHER`).
export const OTHER_TOPIC = "other";

// A Mac server from before topics sends none: the screen still opens, with 「그 밖의 상황」 only, which works with
// that server as before (it ignores the topic it is sent). The new app crashed on it (final review, 2026-11-07).
const BEFORE_TOPICS: Topic[] = [
  { id: OTHER_TOPIC, name_ko: "그 밖의 상황", placeholder_ko: "예: 길에서 외국인이 지하철역을 물어보는 상황", picks: [] },
];

export function topicsOf(home: Pick<Home, "topics">): Topic[] {
  return home.topics?.length ? home.topics : BEFORE_TOPICS;
}

// 「목록에서 고르기」 only when the topic has a list: 「그 밖의 상황」 starts without one (spec 2)
export function howChoices(t: Topic): HowChoice[] {
  return t.picks.length > 0 ? ["list", "jake", "describe"] : ["jake", "describe"];
}

// One step back; null leaves the screen for the home screen.
export function backFrom(step: SituationStep, origin: Origin): SituationStep | null {
  switch (step) {
    case "topic":
      return null;
    case "how":
      return "topic";
    case "list":
    case "describe":
      return "how";
    case "askRecommend":
      return "describe";
    case "working":
    case "confirm":
      return origin;
  }
}

// Where the screen opens when the learner comes back from a roleplay's end screen: the step its situation was picked
// from, in the same topic (spec situation-topics 2, 6). A topic the server no longer has starts at the topics, and a
// list that has since emptied opens how to pick instead of a list without cards (todo 05).
export function resumeFrom(start: SituationStart | null, topics: Topic[]): SituationStart | null {
  const topic = start ? topics.find((t) => t.id === start.topic) : undefined;
  if (!start || !topic) return null;
  return start.step === "list" && topic.picks.length === 0 ? { ...start, step: "how" } : start;
}

export function startStep(start: SituationStart | null): SituationStep {
  return start ? start.step : "topic";
}

// What Ryan says on entering a step; the wait and Jake's suggestion have their own sounds.
export function lineFor(step: SituationStep): keyof Home["lines"] | null {
  const lines: Partial<Record<SituationStep, keyof Home["lines"]>> = {
    topic: "ask_topic",
    how: "ask_how",
    list: "ask_pick",
    describe: "ask_describe",
    askRecommend: "ask_recommend",
  };
  return lines[step] ?? null;
}

// Back at the topics, the suggestions turned down are forgotten: they belonged to the topic left behind.
export function clearsTurnedDown(next: SituationStep): boolean {
  return next === "topic";
}

// A tap that asks the server (a list card, 「시작」, Jake) starts nothing while the screen is already waiting: a second
// quick tap before the re-render would send the request twice (PR #28 review; guide APP_Expo_앱_뼈대와_서버_연결
// 「버튼을 두 번 누르면 같은 요청이 두 번 간다」).
export function canStart(now: SituationStep): boolean {
  return now !== "working";
}
