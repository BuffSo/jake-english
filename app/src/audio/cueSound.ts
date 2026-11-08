// The short sounds that say the mic started, stopped or was cancelled (spec record-feedback 1), made here as WAV
// bytes. Sound files cannot be committed: the commit check refuses every audio file, since it cannot tell a made tone
// from a recording of someone, and its exceptions are not widened. The values are the draft the user picked (A), at
// half its amplitude (-6 dB): at the draft's it was louder than Ryan's voice (todo 20261108_34 2, the numbers in the
// test). The cancel cue was changed after: its loudness is matched to the start cue's on the phone speaker (below).
export type Cue = "start" | "end" | "cancel";

export const CUE_RATE = 22050;

// `overtones`: [multiple of hz, weight] mixed in, the note itself weighing 1; divided by the weights' sum, so the peak
// is at most `gain` (lower, since the parts do not peak together)
type Note = { hz: number; ms: number; decay: number; gain: number; overtones?: [number, number][] };
type Part = Note | { gapMs: number };

const UP: Part[] = [
  { hz: 659, ms: 80, decay: 8, gain: 0.25 },
  { gapMs: 20 },
  { hz: 880, ms: 110, decay: 10, gain: 0.25 },
];
const DOWN: Part[] = [
  { hz: 880, ms: 80, decay: 8, gain: 0.25 },
  { gapMs: 20 },
  { hz: 659, ms: 110, decay: 10, gain: 0.25 },
];
const PARTS: Record<Cue, Part[]> = {
  start: UP, // two notes going up
  end: DOWN, // the same two going down
  // one low note. Its overtones carry it out of a phone speaker, which gives little at 392 Hz: as a pure tone it came
  // out 11 dB under the start cue (todo 20261108_43). The note is still heard at 392 Hz. The user picked this from a
  // draft (2026-11-08); its gain is set by measuring the phone speaker (docs/guide/APP_녹음_중_알리기_20261108.md).
  cancel: [{ hz: 392, ms: 260, decay: 9, gain: 0.5, overtones: [[2, 0.8], [3, 0.5]] }],
};

const ATTACK_MS = 4; // no click at the start of a note
const RELEASE_MS = 20; // nor at its end

const count = (ms: number) => Math.round((ms / 1000) * CUE_RATE);

function note({ hz, ms, decay, gain, overtones = [] }: Note): number[] {
  const n = count(ms);
  const attack = count(ATTACK_MS);
  const release = count(RELEASE_MS);
  const parts: [number, number][] = [[1, 1], ...overtones];
  const weight = parts.reduce((sum, [, w]) => sum + w, 0);
  const out: number[] = [];
  for (let i = 0; i < n; i++) {
    const t = i / CUE_RATE;
    let env = Math.exp(-t * decay);
    if (i < attack) env *= i / attack;
    if (i > n - release) env *= (n - i) / release;
    const wave = parts.reduce((sum, [k, w]) => sum + w * Math.sin(2 * Math.PI * hz * k * t), 0) / weight;
    out.push(wave * env * gain);
  }
  return out;
}

export function cueMs(cue: Cue): number {
  return PARTS[cue].reduce((ms, p) => ms + ("gapMs" in p ? p.gapMs : p.ms), 0);
}

export function cueSamples(cue: Cue): Float32Array {
  const out: number[] = [];
  for (const p of PARTS[cue]) out.push(...("gapMs" in p ? new Array<number>(count(p.gapMs)).fill(0) : note(p)));
  return Float32Array.from(out);
}

// 16-bit mono PCM in a standard 44-byte WAV header
export function cueWav(cue: Cue): Uint8Array {
  const samples = cueSamples(cue);
  const bytes = new Uint8Array(44 + samples.length * 2);
  const v = new DataView(bytes.buffer);
  const text = (at: number, s: string) => [...s].forEach((ch, i) => v.setUint8(at + i, ch.charCodeAt(0)));
  text(0, "RIFF");
  v.setUint32(4, bytes.length - 8, true);
  text(8, "WAVE");
  text(12, "fmt ");
  v.setUint32(16, 16, true); // fmt chunk size
  v.setUint16(20, 1, true); // PCM
  v.setUint16(22, 1, true); // mono
  v.setUint32(24, CUE_RATE, true);
  v.setUint32(28, CUE_RATE * 2, true); // bytes per second
  v.setUint16(32, 2, true); // bytes per frame
  v.setUint16(34, 16, true); // bits
  text(36, "data");
  v.setUint32(40, samples.length * 2, true);
  samples.forEach((s, i) => v.setInt16(44 + i * 2, Math.round(Math.max(-1, Math.min(1, s)) * 32767), true));
  return bytes;
}
