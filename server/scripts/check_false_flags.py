"""Count how often the evaluation points at a sound in a recording that read the script correctly.

Runs only on this Mac: whisper transcribes the recording locally and nothing goes to Anthropic.
Prints counts and the flagged word and sound pairs, not the transcript.
Run: uv run python scripts/check_false_flags.py <recording> <script text file, one line per sentence>
"""
from __future__ import annotations

import asyncio
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from je_server import audio  # noqa: E402
from je_server.asr import Whisper  # noqa: E402
from je_server.compare import find_issues, similarity, word_pairs, words  # noqa: E402
from je_server.config import load_settings  # noqa: E402


async def main(recording: Path, script: Path) -> None:
    s = load_settings()
    lines = [l.strip() for l in script.read_text(encoding="utf-8").splitlines() if l.strip()]
    target = " ".join(lines)
    w = Whisper(s.whisper_exe, s.whisper_model, s.whisper_port)
    await w.start()
    try:
        with tempfile.TemporaryDirectory() as d:
            wav = Path(d) / "rec.wav"
            secs = await audio.to_wav16k(recording, wav)
            speech = await audio.has_speech(wav)
            dbfs, _ = audio._loudest_dbfs(wav)
            heard = await w.transcribe(wav, "en")
    finally:
        await w.stop()
    issues = find_issues(target, heard, limit=99)
    print(f"seconds {secs:.1f}, loudest {dbfs:.1f} dBFS, has_speech {speech}")
    print(f"script words {len(words(target))}, heard words {len(words(heard))}, similarity {similarity(target, heard):.2f}")
    print(f"changed word pairs {len(word_pairs(target, heard))}, flagged {len(issues)}")
    for i in issues:
        print(f"  flagged: {i.target} -> {i.heard} ({i.sound[0]}/{i.sound[1]})")


if __name__ == "__main__":
    asyncio.run(main(Path(sys.argv[1]), Path(sys.argv[2])))
