// How long the voice line in 「● 말하기 끝」 is for a mic level (spec record-feedback 2): short and still when the
// room is quiet, full when speaking up. Measured on the phone (2026-11-08): a quiet room -55~-63, a voice -18~-40.
export const LINE_FLOOR_DB = -55;
export const LINE_TOP_DB = -20;
export const LINE_MIN = 0.08; // the line never goes away while recording

// share of the line's full length, LINE_MIN..1
export function voiceShare(db: number | undefined): number {
  if (db === undefined || db <= LINE_FLOOR_DB) return LINE_MIN;
  if (db >= LINE_TOP_DB) return 1;
  return LINE_MIN + ((1 - LINE_MIN) * (db - LINE_FLOOR_DB)) / (LINE_TOP_DB - LINE_FLOOR_DB);
}
