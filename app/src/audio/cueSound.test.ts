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

test("no cue is louder than half scale, and none is silent", () => {
  for (const cue of CUES) {
    const peak = Math.max(...Array.from(cueSamples(cue), Math.abs));
    expect(peak).toBeLessThanOrEqual(0.5);
    expect(peak).toBeGreaterThan(0.2);
  }
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
