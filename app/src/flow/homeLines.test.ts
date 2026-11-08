import type { Home } from "../api/types";
import { homeLines, homeSounds } from "./homeLines";

const said = (text: string) => ({ text, audio: text.padEnd(64, "0") });
const lines: Home["lines"] = {
  greeting: said("greeting"),
  ask_mode: said("ask_mode"),
  ask_again: said("ask_again"),
  ask_situation: said("ask_situation"),
  ask_recommend: said("ask_recommend"),
  ask_topic: said("ask_topic"),
  ask_how: said("ask_how"),
  ask_pick: said("ask_pick"),
  ask_describe: said("ask_describe"),
};

test("when the app has just started Ryan greets, then asks which way to talk", () => {
  expect(homeLines({ lines }, false).map((l) => l.text)).toEqual(["greeting", "ask_mode"]);
});

test("coming back to the first screen Ryan only asks again, with no greeting", () => {
  expect(homeLines({ lines }, true).map((l) => l.text)).toEqual(["ask_again"]);
});

test("an older server without the ask-again line still skips the greeting", () => {
  const { ask_again, ...old } = lines;
  expect(homeLines({ lines: old }, true).map((l) => l.text)).toEqual(["ask_mode"]);
});

// spec ryan-shadowing-tip 2, 3: the day's first start only, heard after the question and never shown. As text it pushed
// the 「복습하기」 card off the bottom of the phone (2026-11-08 user)

test("on the day's first start Ryan greets, asks, then says the shadowing tip", () => {
  expect(homeSounds({ lines, tip: said("tip") }, false).map((l) => l.text)).toEqual(["greeting", "ask_mode", "tip"]);
});

test("the tip is heard but not shown", () => {
  const home = { lines, tip: said("tip") };
  expect(homeLines(home, false).map((l) => l.text)).toEqual(["greeting", "ask_mode"]);
});

test("coming back he does not say the tip again", () => {
  expect(homeSounds({ lines, tip: said("tip") }, true).map((l) => l.text)).toEqual(["ask_again"]);
});

test("an older server without a tip greets and asks as before", () => {
  expect(homeSounds({ lines }, false).map((l) => l.text)).toEqual(["greeting", "ask_mode"]);
});
