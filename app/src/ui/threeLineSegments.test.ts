import lineUser from "../../../contract/line-user.json";
import type { ThreeLine, Word } from "../api/types";
import { englishSegments, koreanSegments, readingSegments } from "./threeLineSegments";

const three = lineUser.three as ThreeLine;

test("english marks strong and weak syllables", () => {
  const words = englishSegments(three);
  expect(words.at(-1)).toEqual([
    { text: "cof", style: "strong" },
    { text: "fee.", style: "weak" },
  ]);
  expect(words[0]).toEqual([{ text: "I'd", style: "plain" }]);
});

test("korean highlights only the hi letter", () => {
  const w: Word = {
    syl: [
      { en: "sta", ko: "스테이", m: "s", hi: "테" },
      { en: "tion", ko: "션", m: "n", hi: "" },
    ],
    emph: false,
    link: false,
  };
  expect(koreanSegments({ words: [w], reading: "" })[0]).toEqual([
    { text: "스", style: "plain" },
    { text: "테", style: "strong" },
    { text: "이", style: "plain" },
    { text: "션", style: "plain" },
  ]);
});

test("linked words share one korean group", () => {
  const groups = koreanSegments(three);
  // 아잇 / 라이+커 / 커+퍼 / 카+피
  expect(groups).toHaveLength(4);
  expect(groups[2]).toEqual([
    { text: "커", style: "plain" },
    { text: "퍼", style: "weak" },
  ]);
});

test("reading refs show as corner brackets", () => {
  expect(readingSegments("앞을 세게, [[카-피]].")).toEqual([{ text: "앞을 세게, 「카-피」.", style: "plain" }]);
  expect(readingSegments("")).toEqual([]);
});
