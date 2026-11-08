"""Voice worker. Runs under the Mac's existing TTS virtualenv, not the server's (ADR-0009).

    <tts python> -I tts_worker.py <path to the TTS processing module>

It loads that module the way the existing render script does and repeats its steps: language chunks,
voice-likeness check with retries, optional pitch matching, even pauses, then WAV -> AAC (afconvert).
Unlike the render script it makes one sentence at a time and cuts Korean pauses inside a sentence short.
Protocol, one JSON object per line:
    -> {"ready": true, "refs": {"ryan": {"english": "<16 hex>", "korean": "<16 hex>"}, ...}}
    <- {"id": 1, "text": "...", "voice": "ryan" | "jake" | "sohee_clone", "lang": "english" | "korean", "rate": 1.3,
        "out": "/abs/x.m4a"}
    -> {"id": 1, "ok": true, "seconds": 1.8}  or  {"id": 1, "ok": false, "error": "TypeName"}
Library output goes to stderr so stdout carries only the protocol. Texts are not logged.
"""
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
import wave

# Longest pause kept inside a sentence, in seconds before the speed change. 2026-11-05 Jake paused 0.4 s after
# 「은행 창구에서」 and 0.3 s after 「외국인 고객이」 and the user heard the sentence as broken up. The module's
# own cap (0.75 s) is meant for the reply reader and stays for English model lines. Pauses between sentences
# are the voice's gap (0.6 s), since each sentence is made on its own.
KOREAN_PAUSE_CAP = 0.15
MODULE_PAUSE_CAP = 0.75


# The voices the server asks for (`tts.WORKER_VOICE` names them for the worker), and the languages it makes.
REF_VOICES = ("ryan", "jake", "sohee_clone")
LANGS = ("english", "korean")


def ref_prints(srv) -> dict[str, dict[str, str]]:
    """Each voice's reference recordings as a fingerprint by language, sent with {"ready": true} so the server puts
    it in the sound key: after a new recording and a restart, sounds are made again (todo
    voice-reference-in-sound-key). An English sound uses the voice's English recording only; a Korean one may read
    English words with that one too, so it carries all of the voice's recordings. A voice of the module's built-in
    speakers has none and gets "". A missing file still gives a fingerprint, so the worker starts and only that
    voice's sounds fail."""
    out: dict[str, dict[str, str]] = {}
    for voice in REF_VOICES:
        conf = srv.voice_conf(voice)
        refs = conf.get("ref") or {}
        uses = {"english": {srv.ref_name(conf, "english")} if refs else set(), "korean": set(refs.values())}
        out[voice] = {lang: _digest(srv.REF_DIR, uses[lang]) if uses[lang] else "" for lang in LANGS}
    return out


def _digest(ref_dir: str, names: set[str]) -> str:
    h = hashlib.sha256()
    for name in sorted(names):
        for ext in (".wav", ".txt"):
            h.update(f"{name}{ext}\0".encode())
            try:
                with open(os.path.join(ref_dir, name + ext), "rb") as f:
                    for chunk in iter(lambda: f.read(1 << 20), b""):
                        h.update(chunk)
            except OSError:
                h.update(b"\0missing")
    return h.hexdigest()[:16]


def sentences(part: str) -> list[str]:
    return [s for s in re.split(r"(?<=[.?!。])\s+", part.strip()) if s]


def split_parts(chunks: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """Korean chunks one sentence at a time, so their short pause cap keeps the pause between sentences. English
    chunks stay whole: the model lines did not change (final review: 「Mr. Smith」, 「3 p.m.」 would have been
    broken up, and their sound keys were kept)."""
    return [(s, lang) for chunk, lang in chunks for s in (sentences(chunk) if lang == "korean" else [chunk])]


def pause_cap(lang: str) -> float:
    return KOREAN_PAUSE_CAP if lang == "korean" else MODULE_PAUSE_CAP


def main() -> None:
    proto = os.fdopen(os.dup(1), "w", buffering=1, encoding="utf-8")
    os.dup2(2, 1)  # anything printed by the libraries lands on stderr
    sys.stdout = sys.stderr

    spec = importlib.util.spec_from_file_location("tts_server", sys.argv[1])
    srv = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(srv)

    import mlx.core as mx
    import numpy as np
    from mlx_audio.tts.utils import load_model

    kind = srv.voice_conf("ryan")["model"]
    player = srv.Player(load_model(srv.MODELS[kind]), kind)  # its queue threads stay idle

    def render(text: str, voice: str, lang: str, out: str, rate: float = 1.0) -> float:
        conf = srv.voice_conf(voice)
        player.ensure_model(conf["model"])
        pieces, sr = [], 24000
        # Korean speech may quote English, so let the module split by language; script lines stay English.
        # Then Korean one sentence at a time, so cutting pauses inside a sentence keeps the pause between them.
        parts = split_parts(srv.lang_chunks(text, "english" if lang == "english" else "auto"))
        for part, plang in parts:
            audio, sr = player.make(conf, part, plang)
            if conf["model"] == "base":
                name = srv.ref_name(conf, plang)
                score = player.voice_score(audio, sr, name)
                for _ in range(srv.VOICE_RETRIES):
                    if score >= srv.VOICE_MIN:
                        break
                    audio2, _ = player.make(conf, part, plang)
                    score2 = player.voice_score(audio2, sr, name)
                    if score2 > score:
                        audio, score = audio2, score2
                if conf.get("pitch", True):
                    audio, _ = player.match_pitch(audio, sr, name)
            pieces.append(srv.even_pauses(audio, sr, cap=pause_cap(plang), gap=conf.get("gap") or 0.0,
                                          lead=srv.lead_ok(part)))
            mx.clear_cache()
        audio = np.concatenate(pieces)
        if conf.get("gap"):
            audio = audio[: len(audio) - int(sr * conf["gap"])]
        fd, wav = tempfile.mkstemp(suffix=".wav")
        os.close(fd)
        try:
            with wave.open(wav, "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(sr)
                w.writeframes((np.clip(audio, -1, 1) * 32767).astype(np.int16).tobytes())
            if abs(rate - 1.0) > 1e-6:  # speed only, pitch kept (ffmpeg atempo), as the render script does
                fast = wav + ".rate.wav"
                subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", wav, "-filter:a", f"atempo={rate}", fast],
                               check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                os.replace(fast, wav)
            subprocess.run(["afconvert", "-f", "m4af", "-d", "aac", wav, out], check=True,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        finally:
            os.remove(wav)
        return len(audio) / sr / rate

    warm = tempfile.mkstemp(suffix=".m4a")[1]
    try:
        render("Hello.", "ryan", "english", warm)
    finally:
        os.remove(warm)
    proto.write(json.dumps({"ready": True, "refs": ref_prints(srv)}) + "\n")

    for line in sys.stdin:
        req = json.loads(line)
        try:
            secs = render(req["text"], req["voice"], req["lang"], req["out"], float(req.get("rate", 1.0)))
            proto.write(json.dumps({"id": req["id"], "ok": True, "seconds": round(secs, 2)}) + "\n")
        except Exception as e:  # noqa: BLE001 - report the type only, never the text
            proto.write(json.dumps({"id": req["id"], "ok": False, "error": type(e).__name__}) + "\n")


if __name__ == "__main__":
    main()
