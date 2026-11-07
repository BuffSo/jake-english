import type { Topic } from "../api/types";
import { backFrom, clearsTurnedDown, HOW_LABEL, howChoices, lineFor, startStep } from "./situation";

const usa: Topic = { id: "usa", name_ko: "미국 여행", placeholder_ko: "예", picks: [{ id: "u-hotel-checkin", title_ko: "뉴욕 호텔 체크인" }] };
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
