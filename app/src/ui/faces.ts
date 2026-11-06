// Which face the situation screen's big circle shows, and where the face sits in each tall picture.

// The situation screen's steps. confirm: Jake has suggested a situation and waits for 「이걸로 할게요」 or
// 「다른 걸로요」 (2026-11-06, user).
export type Step = "input" | "askRecommend" | "working" | "confirm";
export type Face = "listening" | "jake";

// Jake's own face while his suggestion waits for 「이걸로 할게요」 or 「다른 걸로요」 (2026-11-06 user, after the phone
// test); 「추천받아 볼까요?」 is Ryan asking, so it stays Ryan's listening face. `jake`: Jake's picture is there (an
// older server has none, and one that fails to load leaves Ryan). A wait keeps the face it started with, `before`:
// the thinking face takes over only once the wait has gone on a while, and a short wait changes nothing.
export function circleFace(step: Step, before: Face, jake: boolean): Face {
  if (step === "working") return before;
  return step === "confirm" && jake ? "jake" : "listening";
}

// The square around the face in each picture (572×1024 PNG in the private assets folder), in its pixels. The circle
// shows only this square.
export const FACE_BOX: Record<Face, { x: number; y: number; size: number }> = {
  listening: { x: 100, y: 60, size: 440 },
  jake: { x: 66, y: 175, size: 440 },
};
