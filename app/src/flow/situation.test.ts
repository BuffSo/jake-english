import type { Topic } from "../api/types";
import { backFrom, clearsTurnedDown, HOW_LABEL, howChoices, lineFor, resumeFrom, startStep, topicsOf, canStart, resumeOnBack } from "./situation";

const usa: Topic = { id: "usa", name_ko: "미국 여행하기", placeholder_ko: "예", picks: [{ id: "u-hotel-checkin", title_ko: "뉴욕 호텔 체크인" }] };
const other: Topic = { id: "other", name_ko: "그 밖의 상황", placeholder_ko: "예", picks: [] };

test("the list button shows only when the topic has a list", () => {
  // 「그 밖의 상황」 starts without one; adding lines to the list file makes the button appear (spec 2)
  expect(howChoices(usa)).toEqual(["list", "jake", "describe"]);
  expect(howChoices(other)).toEqual(["jake", "describe"]);
  expect(HOW_LABEL).toEqual({ list: "목록에서 고르기", jake: "제이크에게 추천받기", describe: "직접 말하거나 쓰기" });
});

test("back goes one step at a time", () => {
  expect(backFrom("topic", "how")).toBeNull(); // leaves the screen
  expect(backFrom("how", "how")).toBe("topic");
  expect(backFrom("list", "list")).toBe("how");
  expect(backFrom("describe", "describe")).toBe("how");
  expect(backFrom("askRecommend", "describe")).toBe("describe");
});

test("back from Jake's suggestion or a wait returns to where it started", () => {
  expect(backFrom("confirm", "how")).toBe("how");
  expect(backFrom("confirm", "describe")).toBe("describe");
  expect(backFrom("working", "list")).toBe("list");
});

test("the screen starts at the topic, or where the roleplay was picked", () => {
  expect(startStep(null)).toBe("topic");
  expect(startStep({ topic: "usa", step: "list" })).toBe("list");
  expect(startStep({ topic: "usa", step: "how" })).toBe("how");
});

test("Ryan's line for each step", () => {
  expect(lineFor("topic")).toBe("ask_topic");
  expect(lineFor("how")).toBe("ask_how");
  expect(lineFor("list")).toBe("ask_pick");
  expect(lineFor("describe")).toBe("ask_describe");
  expect(lineFor("askRecommend")).toBe("ask_recommend");
  expect(lineFor("working")).toBeNull();
  expect(lineFor("confirm")).toBeNull();
});

test("going back to the topics forgets the suggestions turned down", () => {
  // a suggestion turned down in one topic must not steer Jake in another
  expect(clearsTurnedDown("topic")).toBe(true);
  expect(clearsTurnedDown("how")).toBe(false);
  expect(clearsTurnedDown("describe")).toBe(false);
});

test("an older Mac server without topics still opens the screen", () => {
  // final review: the new app crashed on 「상황 역할극」 when the Mac server was older (no `topics` in /home)
  const t = topicsOf({});
  expect(t.map((x) => [x.id, x.picks.length])).toEqual([["other", 0]]);
  expect(howChoices(t[0])).toEqual(["jake", "describe"]);
  const usaOnly = [usa];
  expect(topicsOf({ topics: usaOnly })).toBe(usaOnly);
});

test("nothing new starts while the screen is already waiting", () => {
  // PR #28 review: a second quick tap on a list card could send a second POST /roleplays before the re-render (the
  // guide APP_Expo_앱_뼈대와_서버_연결: a new button that asks the server must not ask twice)
  expect(canStart("working")).toBe(false);
  for (const s of ["topic", "how", "list", "describe", "askRecommend", "confirm"] as const) expect(canStart(s)).toBe(true);
});

// todo 05-1: back from a roleplay comes to the step its situation was picked from, but not to an empty list
describe("resumeFrom", () => {
  const empty: Topic = { ...usa, picks: [] };

  test("keeps the step of a known topic", () => {
    expect(resumeFrom({ topic: "usa", step: "list" }, [usa])).toEqual({ topic: "usa", step: "list" });
    expect(resumeFrom({ topic: "usa", step: "describe" }, [usa])).toEqual({ topic: "usa", step: "describe" });
  });

  test("opens how-to-pick when the topic's list is now empty", () => {
    expect(resumeFrom({ topic: "usa", step: "list" }, [empty])).toEqual({ topic: "usa", step: "how" });
  });

  test("starts at the topics for a topic the server no longer has, or nothing to resume", () => {
    expect(resumeFrom({ topic: "gone", step: "list" }, [usa])).toBeNull();
    expect(resumeFrom(null, [usa])).toBeNull();
  });
});

// todo 20261108_32 1: going back while a script was being made, the Mac still makes it the newest conversation; the
// topics' row asked when the screen opened is then the wrong one and must be asked again once the topics are back
describe("asking where to resume again on the way back (resumeOnBack)", () => {
  test("back from the wait remembers the script left being made, and asks nothing yet", () => {
    expect(resumeOnBack("describe", { making: true, madeLeft: false })).toEqual({ madeLeft: true, askAgain: false });
  });

  test("back on the topics after it asks again, once", () => {
    const back = resumeOnBack("topic", { making: false, madeLeft: true });
    expect(back).toEqual({ madeLeft: false, askAgain: true });
    expect(resumeOnBack("topic", { making: false, madeLeft: back.madeLeft })).toEqual({ madeLeft: false, askAgain: false });
  });

  test("a script still being made when the topics come back asks again too", () => {
    expect(resumeOnBack("topic", { making: true, madeLeft: false })).toEqual({ madeLeft: false, askAgain: true });
  });

  test("nothing left behind: the row stays as it was", () => {
    expect(resumeOnBack("topic", { making: false, madeLeft: false })).toEqual({ madeLeft: false, askAgain: false });
    expect(resumeOnBack("how", { making: false, madeLeft: false })).toEqual({ madeLeft: false, askAgain: false });
  });

  test("leaving the screen asks nothing", () => {
    expect(resumeOnBack(null, { making: true, madeLeft: true })).toEqual({ madeLeft: true, askAgain: false });
  });
});
