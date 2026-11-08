// How long the voice line in 「● 말하기 끝」 is for a mic level (spec record-feedback 2): short and still when the
// room is quiet, full when speaking up. The range is measured on the phone (plan task 6).
export const LINE_FLOOR_DB = -50;
export const LINE_TOP_DB = -15;
export const LINE_MIN = 0.08; // the line never goes away while recording

// share of the line's full length, LINE_MIN..1
export function voiceShare(db: number | undefined): number {
  if (db === undefined || db <= LINE_FLOOR_DB) return LINE_MIN;
  if (db >= LINE_TOP_DB) return 1;
  return LINE_MIN + ((1 - LINE_MIN) * (db - LINE_FLOOR_DB)) / (LINE_TOP_DB - LINE_FLOOR_DB);
}
