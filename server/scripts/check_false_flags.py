"""Count how often the evaluation points at something (spec 「잰 것」 따라 말한 차례에서 짚는 수).

Runs only on this Mac: whisper transcribes locally and nothing goes to Anthropic.

Recording mode: a recording that read the script correctly, so every difference is a false flag (or a slip).
Prints counts and the differing word pairs, not the transcript.
    JE_WHISPER_PORT=<free port> uv run python scripts/check_false_flags.py <recording> <script, one line per sentence>
(use a whisper port the running Mac server is not using)

Records mode: the followed turns saved by the app, with the old rule (stored issues) and the current one.
Prints numbers only, no words.
    uv run python scripts/check_false_flags.py --records
"""
from __future__ import annotations

import asyncio
import sys
import tempfile
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from je_server.compare import compare, similarity, words  # noqa: E402
from je_server.config import load_settings  # noqa: E402
from je_server.models import Roleplay  # noqa: E402


async def recording(path: Path, script: Path) -> None:
    from je_server import audio
    from je_server.asr import Whisper

    s = load_settings()
    lines = [l.strip() for l in script.read_text(encoding="utf-8").splitlines() if l.strip()]
    target = " ".join(lines)
    w = Whisper(s.whisper_exe, s.whisper_model, s.whisper_port)
    await w.start()
    try:
        with tempfile.TemporaryDirectory() as d:
            wav = Path(d) / "rec.wav"
            secs = await audio.to_wav16k(path, wav)
            speech = await audio.has_speech(wav)
            dbfs, _ = audio._loudest_dbfs(wav)
            heard = await w.transcribe(wav, "en")
    finally:
        await w.stop()
    c = compare(target, heard)
    print(f"seconds {secs:.1f}, loudest {dbfs:.1f} dBFS, has_speech {speech}")
    print(f"script words {len(words(target))}, heard words {len(words(heard))}, similarity {similarity(target, heard):.2f}")
    print(f"differences {len(c.diffs)}")
    for i in c.diffs:
        print(f"  {i.target or '-'} -> {i.heard or '-'} ({'/'.join(i.sound) if i.sound else 'no listed sound'})")


def records() -> None:
    root = load_settings().data_dir / "roleplays"
    followed = old = new = 0
    per_turn: Counter[str] = Counter()
    for f in sorted(root.glob("*/roleplay.json")):
        rp = Roleplay.model_validate_json(f.read_text(encoding="utf-8"))
        text = {l.idx: l.text for l in rp.lines}
        for idx, tries in rp.attempts.items():
            for a in tries:
                if not a.followed or idx not in text:
                    continue
                followed += 1
                old += bool(a.issues)
                n = len(compare(text[idx], a.heard).diffs)
                new += bool(n)
                if n:
                    per_turn["3+" if n >= 3 else str(n)] += 1
    print(f"followed turns {followed}, old rule flagged {old}, new rule flagged {new}")
    print("differences per flagged turn: " + ", ".join(f"{k}: {per_turn[k]}" for k in ("1", "2", "3+")))


if __name__ == "__main__":
    if sys.argv[1:] == ["--records"]:
        records()
    else:
        asyncio.run(recording(Path(sys.argv[1]), Path(sys.argv[2])))
