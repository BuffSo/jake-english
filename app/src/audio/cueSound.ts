// The short sounds that say the mic started, stopped or was cancelled (spec record-feedback 1), made here as WAV
// bytes. Sound files cannot be committed: the commit check refuses every audio file, since it cannot tell a made tone
// from a recording of someone, and its exceptions are not widened. The values are the draft the user picked (A), at
// half its loudness: at the draft's it was louder than Ryan's voice (todo 20261108_34 2, the numbers in the test).
export type Cue = "start" | "end" | "cancel";

export const CUE_RATE = 22050;

type Note = { hz: number; ms: number; decay: number; gain: number };
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
  cancel: [{ hz: 392, ms: 260, decay: 9, gain: 0.225 }], // one low note
};

const ATTACK_MS = 4; // no click at the start of a note
const RELEASE_MS = 20; // nor at its end

const count = (ms: number) => Math.round((ms / 1000) * CUE_RATE);

function note({ hz, ms, decay, gain }: Note): number[] {
  const n = count(ms);
  const attack = count(ATTACK_MS);
  const release = count(RELEASE_MS);
  const out: number[] = [];
  for (let i = 0; i < n; i++) {
    const t = i / CUE_RATE;
    let env = Math.exp(-t * decay);
    if (i < attack) env *= i / attack;
    if (i > n - release) env *= (n - i) / release;
    out.push(Math.sin(2 * Math.PI * hz * t) * env * gain);
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
