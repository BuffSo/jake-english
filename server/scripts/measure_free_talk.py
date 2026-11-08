"""Measure one free-talk exchange on the Mac, stage by stage: from the recording to Ryan's first English sound.

Real Claude API (a few cents), the Mac's whisper model on its own port and a voice worker writing into a temporary
folder, so no sound is served from the cache. Prints times and word counts only: no transcript, no reply text.

    uv run python scripts/measure_free_talk.py a.m4a b.m4a [--runs 3] [--port 8792]

For each recording and run:
  prep      the m4a to 16 kHz WAV and the loudness check (as `Engine._attempt`)
  en, auto  whisper forced to English, then auto-detected (the second one tells Korean apart)
  per model the reply streamed: first text, first sentence cut (`SentenceBuffer`), whole reply
  voice     Ryan's English: the first sentence alone, and the whole reply made in one take
Then two ways to Ryan's first sound, without the phone's part:
  whole     transcription + whole reply + the whole reply's voice (wait for everything, then speak)
  first     transcription + first sentence + its voice (speak each sentence as it is cut)
"""
from __future__ import annotations

import argparse
import asyncio
import json
import shutil
import statistics
import tempfile
import time
from pathlib import Path

import anthropic

from je_server import audio
from je_server.asr import Whisper
from je_server.claude import HAIKU, SONNET, Claude
from je_server.config import load_settings
from je_server.sentences import SentenceBuffer
from je_server.tts import Voice

# A first draft for timing only; the real prompt comes with the spec.
SYSTEM = """\
You are Ryan, a friendly English conversation partner for a Korean adult learning to speak English.
Chat casually in English about the learner's everyday life.
Reply in two or three short sentences: first a short reaction of a few words, then one simple follow-up question.
Use everyday words. No lists, no quotation marks, no emojis.
"""
OPENER = "Hi! What did you do today?"
MODELS = {"sonnet": SONNET, "haiku": HAIKU}
PRICE = {"claude-sonnet-5-5": (2.0, 10.0), "claude-haiku-5-5": (0.10, 0.50)}  # $ per million tokens in/out


def med(xs: list[float]) -> str:
    return f"{statistics.median(xs):.2f}s ({min(xs):.2f}–{max(xs):.2f})" if xs else "-"


async def reply(client, model: dict, heard: str) -> dict:
    kw = Claude(client)._request(model, {})
    if not kw.get("output_config"):
        kw.pop("output_config", None)
    t0 = time.perf_counter()
    first_text = first_sentence = None
    buf, sentences, text = SentenceBuffer(), [], ""
    body = json.dumps({"라이언이 먼저 한 말": OPENER, "학습자가 한 말": heard}, ensure_ascii=False)
    async with client.messages.stream(**kw, max_tokens=300, system=SYSTEM,
                                      messages=[{"role": "user", "content": body}]) as stream:
        async for delta in stream.text_stream:
            first_text = first_text or time.perf_counter() - t0
            text += delta
            got = buf.feed(delta)
            if got and first_sentence is None:
                first_sentence = time.perf_counter() - t0
            sentences += got
        final = await stream.get_final_message()
    whole = time.perf_counter() - t0
    sentences += buf.flush()
    first_sentence = first_sentence or whole
    u = final.usage
    price = PRICE[kw["model"]]
    return {"first_text": first_text or whole, "first_sentence": first_sentence, "whole": whole,
            "sentences": sentences, "text": text.strip(),
            "cost": u.input_tokens * price[0] / 1e6 + u.output_tokens * price[1] / 1e6}


async def fresh(voice: Voice, text: str) -> float:
    """Ryan's English sound made now: a sound with the same text made earlier in the run is deleted first, so the
    cache never answers (replies often begin alike)."""
    voice.path(voice.key("ryan", "english", text)).unlink(missing_ok=True)
    t = time.perf_counter()
    await voice.say(text, "ryan", "english", urgent=True)
    return time.perf_counter() - t


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("recordings", nargs="+", type=Path)
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--port", type=int, default=8792)
    args = ap.parse_args()
    s = load_settings()
    client = anthropic.AsyncAnthropic(api_key=s.anthropic_api_key, max_retries=1, timeout=30)
    work = Path(tempfile.mkdtemp(prefix="measure-free-talk-"))
    whisper = Whisper(s.whisper_exe, s.whisper_model, args.port)
    voice = Voice(s.tts_python, s.tts_module, work / "audio")
    t = time.perf_counter()
    await whisper.start()
    await voice.start()
    print(f"started whisper and voice worker in {time.perf_counter() - t:.1f}s")
    rows: dict[str, list[float]] = {}
    words: dict[str, list[int]] = {}
    cost = 0.0
    same: list[bool] = []  # auto-detected English gave the same text as forced English

    def add(k: str, v: float) -> None:
        rows.setdefault(k, []).append(v)

    try:
        for n in range(args.runs):
            for rec in args.recordings:
                wav = work / f"{rec.stem}.wav"
                t = time.perf_counter()
                await audio.to_wav16k(rec, wav)
                await audio.has_speech(wav)
                prep = time.perf_counter() - t
                t = time.perf_counter()
                heard = await whisper.transcribe(wav, "en")
                en = time.perf_counter() - t
                t = time.perf_counter()
                auto_text, lang = await whisper.transcribe_auto(wav)
                auto = time.perf_counter() - t
                t = time.perf_counter()
                await whisper.transcribe(wav, "auto")
                add("whisper auto (json, no language)", time.perf_counter() - t)
                t = time.perf_counter()
                await asyncio.gather(whisper.transcribe(wav, "en"), whisper.transcribe_auto(wav))
                add("whisper en + auto at once", time.perf_counter() - t)
                same.append(lang != "english" or auto_text == heard)
                wav.unlink()
                add("prep", prep)
                add("whisper en", en)
                add("whisper auto", auto)
                print(f"run {n + 1} {rec.name}: prep {prep:.2f} en {en:.2f} auto {auto:.2f} (detected {lang})")
                if lang == "korean":
                    continue  # a Korean question: Ryan's help, not a reply; transcription only here
                for name, model in MODELS.items():
                    r = await reply(client, model, heard)
                    cost += r["cost"]
                    first = r["sentences"][0] if r["sentences"] else r["text"]
                    v_first = await fresh(voice, first)
                    v_whole = await fresh(voice, r["text"])
                    trans = prep + en + auto
                    add(f"{name} first text", r["first_text"])
                    add(f"{name} first sentence", r["first_sentence"])
                    add(f"{name} whole reply", r["whole"])
                    add(f"{name} voice first sentence", v_first)
                    add(f"{name} voice whole reply", v_whole)
                    add(f"{name} → first sound, whole", trans + r["whole"] + v_whole)
                    add(f"{name} → first sound, first", trans + r["first_sentence"] + v_first)
                    words.setdefault(f"{name} words first", []).append(len(first.split()))
                    words.setdefault(f"{name} words whole", []).append(len(r["text"].split()))
                    print(f"  {name}: first text {r['first_text']:.2f} first sentence {r['first_sentence']:.2f} "
                          f"whole {r['whole']:.2f} | voice first {v_first:.2f} ({len(first.split())} words) "
                          f"whole {v_whole:.2f} ({len(r['text'].split())} words, {len(r['sentences'])} sentences)")
        print("\nmedian (min–max):")
        for k, v in rows.items():
            print(f"  {k}: {med(v)}")
        for k, v in words.items():
            print(f"  {k}: median {statistics.median(v)} ({min(v)}–{max(v)})")
        print(f"auto text same as en when English detected: {sum(same)}/{len(same)}")
        print(f"claude cost: ${cost:.4f}")
    finally:
        await voice.stop()
        await whisper.stop()
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    asyncio.run(main())
