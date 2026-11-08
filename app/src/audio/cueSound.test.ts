// The cues are made in code: the commit check refuses sound files (spec record-feedback 1).
import { CUE_RATE, cueMs, cueSamples, cueWav, type Cue } from "./cueSound";

const CUES: Cue[] = ["start", "end", "cancel"];

test("each cue is a 16-bit mono WAV at CUE_RATE", () => {
  for (const cue of CUES) {
    const w = cueWav(cue);
    const text = (a: number, b: number) => String.fromCharCode(...w.slice(a, b));
    const v = new DataView(w.buffer, w.byteOffset, w.byteLength);
    expect(text(0, 4)).toBe("RIFF");
    expect(v.getUint32(4, true)).toBe(w.length - 8);
    expect(text(8, 12)).toBe("WAVE");
    expect(text(12, 16)).toBe("fmt ");
    expect(v.getUint16(20, true)).toBe(1); // PCM
    expect(v.getUint16(22, true)).toBe(1); // channels
    expect(v.getUint32(24, true)).toBe(CUE_RATE);
    expect(v.getUint16(34, true)).toBe(16);
    expect(text(36, 40)).toBe("data");
    expect(v.getUint32(40, true)).toBe(cueSamples(cue).length * 2);
    expect(w.length).toBe(44 + cueSamples(cue).length * 2);
  }
});

test("cue lengths: start and end 210 ms, cancel 260 ms", () => {
  expect(cueMs("start")).toBe(210);
  expect(cueMs("end")).toBe(210);
  expect(cueMs("cancel")).toBe(260);
  for (const cue of CUES) expect(Math.abs(cueSamples(cue).length - (cueMs(cue) / 1000) * CUE_RATE)).toBeLessThanOrEqual(1);
});

const rmsDb = (s: Float32Array) => 20 * Math.log10(Math.sqrt(s.reduce((sum, x) => sum + x * x, 0) / s.length));

// Quieter than Ryan's voice (spec record-feedback 1), judged by loudness over 400 ms (ffmpeg `ebur128`, the momentary
// max), which weighs by ear and spreads a 0.2 s cue over its window as the ear does. At half scale the start cue was
// -16.4 LUFS against -17.2 to -22.5 for six of Ryan's line sounds: louder than every one (todo 20261108_34 2,
// 2026-11-08). At a quarter it is -22.4, at or under all of them. Plain RMS still puts it 2 to 5 dB over the speech in
// those lines (-19 dBFS against -21 to -24), since it counts a short tone at full weight; the RMS bound below only pins
// today's value so a louder cue fails here.
test("no cue is louder than a quarter of full scale, and none is silent", () => {
  for (const cue of CUES) {
    const peak = Math.max(...Array.from(cueSamples(cue), Math.abs));
    expect(peak).toBeLessThanOrEqual(0.25);
    expect(peak).toBeGreaterThan(0.1);
  }
});

test("each cue's RMS is -19 dBFS or less", () => {
  for (const cue of CUES) expect(rmsDb(cueSamples(cue))).toBeLessThanOrEqual(-19);
});

// sign changes in a stretch tell its pitch: start goes up, end goes down, cancel is the lowest
function crossings(s: Float32Array, from: number, to: number): number {
  let n = 0;
  for (let i = from + 1; i < to; i++) if (s[i - 1] < 0 !== s[i] < 0) n += 1;
  return n;
}
const at = (ms: number) => Math.round((ms / 1000) * CUE_RATE);

test("start rises, end falls, cancel is low", () => {
  const s = cueSamples("start");
  const e = cueSamples("end");
  const c = cueSamples("cancel");
  expect(crossings(s, 0, at(60))).toBeLessThan(crossings(s, s.length - at(60), s.length));
  expect(crossings(e, 0, at(60))).toBeGreaterThan(crossings(e, e.length - at(60), e.length));
  expect(crossings(c, at(20), at(80))).toBeLessThan(crossings(s, 0, at(60)));
});
