"""Vowel values for each aligned recording (spec stress-log 「어떻게 재나」 4), run by scripts/measure_stress.py.

Runs in the MFA environment's Python, not the server's: it needs parselmouth (Praat) and praatio, which only that
environment has. So it imports nothing from je_server, only the standard library, numpy, parselmouth and praatio.

    <MFA env>/bin/python -I stress_features.py <corpus folder> <MFA output folder> <output json>

For every TextGrid MFA wrote, reads the WAV beside it in the corpus and keeps, per vowel, its length, its loudest
intensity (dB) and its highest and median pitch (semitones over 100 Hz), with Praat's default settings like the
2026-11-05 test. The pitch and intensity curves are never written out (ADR-0004). Words are copied from the TextGrid
into the output file only; nothing is printed.
"""
from __future__ import annotations

import csv
import json
import math
import sys
from pathlib import Path

import numpy as np
import parselmouth
from praatio import textgrid


def semitones(hz: float) -> float:
    return 12 * math.log2(hz / 100)


def _num(x: float) -> float | None:
    return None if x is None or math.isnan(x) else round(float(x), 2)


class Curves:
    """Praat's intensity and pitch of one recording (Praat defaults: pitch 75-600 Hz)."""

    def __init__(self, wav: Path):
        sound = parselmouth.Sound(str(wav))
        self.intensity = sound.to_intensity()
        self.pitch = sound.to_pitch()
        self.ix, self.iv = self.intensity.xs(), self.intensity.values[0]
        self.px, self.pf = self.pitch.xs(), self.pitch.selected_array["frequency"]

    def vowel(self, start: float, end: float) -> dict:
        mid = (start + end) / 2
        inside = (self.ix >= start) & (self.ix <= end)
        db = float(self.iv[inside].max()) if inside.any() else self.intensity.get_value(mid)
        voiced = self.pf[(self.px >= start) & (self.px <= end) & (self.pf > 0)]
        if voiced.size:
            st_max, st_med = semitones(float(voiced.max())), semitones(float(np.median(voiced)))
        else:
            hz = self.pitch.get_value_at_time(mid)
            st_max = st_med = semitones(hz) if hz and not math.isnan(hz) else None
        return {"dur": round(end - start, 3), "db": _num(db), "st": _num(st_max), "st_med": _num(st_med)}


def quality(out_dir: Path) -> dict[str, dict]:
    """MFA's per-file alignment scores from alignment_analysis.csv, by file name."""
    path = out_dir / "alignment_analysis.csv"
    if not path.exists():
        return {}
    found = {}
    with path.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            found[row["file"]] = {k: float(row[k]) if row.get(k) not in (None, "") else None
                                  for k in ("speech_log_likelihood", "phone_duration_deviation")}
    return found


def measure(wav: Path, grid: Path) -> list[dict]:
    tg = textgrid.openTextgrid(str(grid), includeEmptyIntervals=False)
    curves = Curves(wav)
    phones = tg.getTier("phones").entries
    words = []
    for w in tg.getTier("words").entries:
        mine = [p for p in phones if w.start - 1e-6 <= p.start < w.end - 1e-6]
        syl = [{"p": p.label, "start": round(p.start, 3), "end": round(p.end, 3), **curves.vowel(p.start, p.end)}
               for p in mine if p.label[-1:].isdigit()]
        words.append({"w": w.label, "start": round(w.start, 3), "end": round(w.end, 3),
                      "phones": [p.label for p in mine], "syl": syl})
    return words


def main(corpus: Path, out_dir: Path, dest: Path) -> None:
    scores = quality(out_dir)
    files = {}
    for grid in sorted(out_dir.rglob("*.TextGrid")):
        wav = corpus / grid.relative_to(out_dir).with_suffix(".wav")
        if not wav.exists():
            continue
        files[grid.stem] = {"words": measure(wav, grid),
                            "quality": scores.get(grid.stem, {"speech_log_likelihood": None,
                                                              "phone_duration_deviation": None})}
    dest.write_text(json.dumps({"praat": parselmouth.PRAAT_VERSION, "files": files}, ensure_ascii=False),
                    encoding="utf-8")


if __name__ == "__main__":
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    main(Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]))
