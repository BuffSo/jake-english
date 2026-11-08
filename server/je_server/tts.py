"""Ryan, Jake and Sohee voices through a worker process on the Mac's existing TTS setup (ADR-0009).

One worker, one queue: urgent jobs (Ryan's live feedback) go before prepared ones (model audio for
later lines). Sounds are cached by sha256(voice|lang|rate|text), with Korean keys also carrying how they were
made (`MADE`) and every key the fingerprint of the voice's reference recordings the worker reports when it starts
(`Voice.refs`), so the same line is made once and a new recording makes new sounds.
Sounds played as they are made once (Jake, Ryan's fixed phrases, Sohee) can be heard back with whisper and made
again when their last word is missing.
"""
from __future__ import annotations

import asyncio
import hashlib
import itertools
import json
import logging
import os
import re
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Literal

from .audio import with_rate

WORKER = Path(__file__).with_name("tts_worker.py")
RATES = (0.6, 0.8, 1.0)
# Speaking rate baked into each sound, kept in pitch, by voice and language. Ryan's Korean (greeting,
# feedback) at 1x sounded drawn out on the phone (2026-11-05); the reply reader plays Korean at 1.3x since
# the user found 1x too slow (2026-11-03). After trying it on the phone the user set Jake's Korean (the
# recommended situation) to 1.1x and kept Ryan at 1.3x (2026-11-05). Later that day the user found Ryan's 1.3x
# a bit fast and set him to 1.2x. After the new pause handling Jake was tried at 1x and set back to 1.1x. On
# 2026-11-06 the user asked for Jake 0.1x slower than that: 1x. English model lines stay at 1x: they are what the
# learner copies.
SPEAK_RATE = {
    ("ryan", "korean"): 1.2,
    ("ryan", "english"): 1.0,
    ("jake", "korean"): 1.0,
    ("jake", "english"): 1.0,
    ("sohee", "korean"): 1.0,  # Sohee's interpretation (2026-11-06): 1x until the user hears it on the phone
}
# The name the worker gets, when it is not the server's own. The voice setup makes a name it does not know in its
# default voice, without an error, and its plain "sohee" is another model that would load a second one into memory:
# Sohee is the cloned voice, on the same model as Ryan and Jake (spec korean-translation 「제약」).
WORKER_VOICE = {"sohee": "sohee_clone"}


# Korean sounds are made differently since 2026-11-05: pauses inside a sentence are cut short
# (`tts_worker.pause_cap`) and Jake and the fixed phrases are heard back. The mark keeps older Korean files from
# being served. English model lines did not change and keep their keys.
MADE = {"korean": "2", "english": ""}
END_RETRIES = 2  # takes made again when the last word is missing; the last take is kept after that
WHISPER_LANG = {"korean": "ko", "english": "en"}

log = logging.getLogger("je_server")
Hear = Callable[[Path, str], Awaitable[str]]


class VoiceError(Exception):
    pass


def audio_key(voice: str, lang: str, text: str, ref: str = "") -> str:
    """The rate is in the key, so a sound made before a rate change is never served for the new rate; so is `ref`,
    the reference recordings' fingerprint, so a sound in an old recording's voice is not served after a new one
    (todo voice-reference-in-sound-key). Without a fingerprint the key is as it was before it came in."""
    made = f"{MADE[lang]}|" if MADE[lang] else ""
    ref = f"{ref}|" if ref else ""
    return hashlib.sha256(f"{voice}|{lang}|{SPEAK_RATE[voice, lang]}|{made}{ref}{text}".encode()).hexdigest()


def ends_right(text: str, heard: str) -> bool:
    """Whether the sound got to the end: the transcript ends with the text's last word, spaces and punctuation
    aside. 2026-11-05 the voice model swallowed the last sound of 「…연습하고 싶어.」 and whisper heard 「싶다」."""
    last = re.findall(r"\w+", text.lower())
    return bool(last) and re.sub(r"\W", "", heard.lower()).endswith(last[-1])


class Voice:
    start_timeout = 300  # seconds for the worker to load the model and say it is ready

    def __init__(self, python: str, module: str, audio_dir: Path, worker: Path = WORKER, hear: Hear | None = None):
        self.python, self.module, self.worker = python, module, worker
        self.hear = hear  # (sound file, whisper language) -> transcript, for check=True
        self.audio_dir = audio_dir
        self.tmp_dir = audio_dir / ".tmp"
        self.proc: asyncio.subprocess.Process | None = None
        self.queue: asyncio.PriorityQueue = asyncio.PriorityQueue()
        self.inflight: dict[str, asyncio.Future] = {}
        self.seq = itertools.count()
        self.ids = itertools.count(1)
        self.consumer: asyncio.Task | None = None
        self.rating: dict[str, asyncio.Future] = {}
        # the reference recordings' fingerprints by worker voice and language, from the worker's {"ready": true}
        # (`tts_worker.ref_prints`); read again whenever a worker starts, so a new recording counts after a restart
        self.refs: dict[str, dict[str, str]] = {}

    def path(self, key: str) -> Path:
        return self.audio_dir / f"{key}.m4a"

    def key(self, voice: str, lang: str, text: str) -> str:
        """The sound's key in the voice as the worker has it now: `audio_key` with its reference fingerprint."""
        return audio_key(voice, lang, text, self.refs.get(WORKER_VOICE.get(voice, voice), {}).get(lang, ""))

    async def start(self) -> None:
        self.audio_dir.mkdir(parents=True, exist_ok=True)
        self.tmp_dir.mkdir(exist_ok=True)
        await self._spawn()
        self.consumer = asyncio.create_task(self._consume())

    async def _spawn(self) -> None:
        self.proc = await asyncio.create_subprocess_exec(
            self.python, "-I", str(self.worker), self.module,
            stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL,
            limit=1 << 20)
        try:
            line = await asyncio.wait_for(self.proc.stdout.readline(), timeout=self.start_timeout)
            ready = json.loads(line) if line else {}
            if not ready.get("ready"):
                raise VoiceError("voice worker did not start")
            self.refs = ready.get("refs") or {}
        except BaseException:
            # a half-started worker must not stay: the next job would read its late {"ready": true} as the
            # answer, and every answer after that would belong to the job before (PR #12 review)
            if self.proc.returncode is None:
                self.proc.kill()
            await self.proc.wait()
            self.proc = None
            raise

    async def say(self, text: str, voice: Literal["ryan", "jake", "sohee"], lang: Literal["english", "korean"],
                  urgent: bool, rank: int = 0, check: bool = False) -> str:
        """rank orders prepared jobs (the line number), so the next line's sound is not stuck behind later lines;
        Sohee's sounds made ahead pass a rank above every line number (`engine.SOHEE_RANK`) to come after them.
        check hears the sound back and makes it again when its last word is missing; it adds a transcription
        (about 0.4 s), so Ryan's live feedback does not use it."""
        key = self.key(voice, lang, text)
        if self.path(key).exists():
            return key
        fut = self.inflight.get(key)
        if fut is None:
            fut = asyncio.get_running_loop().create_future()
            self.inflight[key] = fut
        # an urgent ask for a queued prepared job queues it again in front; the consumer skips duplicates
        self.queue.put_nowait((0 if urgent else 1, 0 if urgent else rank, next(self.seq), key, text, voice, lang,
                               check))
        await asyncio.shield(fut)
        return key

    async def _consume(self) -> None:
        while True:
            _, _, _, key, text, voice, lang, check = await self.queue.get()
            fut = self.inflight.get(key)
            if fut is None or fut.done():
                continue
            try:
                await self._make(key, text, voice, lang, check)
                fut.set_result(key)
            except Exception as e:  # noqa: BLE001 - every failure reaches the waiting caller
                fut.set_exception(e if isinstance(e, VoiceError) else VoiceError(type(e).__name__))
            finally:
                self.inflight.pop(key, None)

    async def _make(self, key: str, text: str, voice: str, lang: str, check: bool = False) -> None:
        tmp = self.tmp_dir / f"{key}.m4a"
        checking = check and self.hear is not None
        for take in range(1 + (END_RETRIES if checking else 0)):
            await self._render(tmp, text, voice, lang)
            if not checking or await self._ends_right(tmp, text, lang):
                break
            log.info("voice end missing: take %d of %d", take + 1, 1 + END_RETRIES)
        os.replace(tmp, self.path(key))

    async def _ends_right(self, sound: Path, text: str, lang: str) -> bool:
        try:
            return ends_right(text, await self.hear(sound, WHISPER_LANG[lang]))
        except Exception as e:  # noqa: BLE001 - cannot hear it now: keep the sound rather than lose it
            log.info("voice end check failed: %s", type(e).__name__)
            return True

    async def _render(self, tmp: Path, text: str, voice: str, lang: str) -> None:
        if self.proc is None or self.proc.returncode is not None:
            await self._spawn()
        req = {"id": next(self.ids), "text": text, "voice": WORKER_VOICE.get(voice, voice), "lang": lang, "rate": SPEAK_RATE[voice, lang],
               "out": str(tmp)}
        self.proc.stdin.write((json.dumps(req, ensure_ascii=False) + "\n").encode())
        await self.proc.stdin.drain()
        line = await self.proc.stdout.readline()
        if not line:
            await self.proc.wait()
            self.proc = None
            raise VoiceError("voice worker died")
        resp = json.loads(line)
        if not resp.get("ok"):
            raise VoiceError(resp.get("error", "voice worker failed"))

    async def rate_file(self, key: str, rate: float) -> Path:
        """A 0.6x/0.8x copy, made once. Requests for the same copy at the same time share one ffmpeg run
        (PR #12 review: they shared one temp file and the second os.replace failed)."""
        if rate not in RATES:
            raise ValueError("rate")
        if rate == 1.0:
            return self.path(key)
        out = self.audio_dir / f"{key}@{rate}.m4a"
        if out.exists():
            return out
        job = self.rating.get(out.name)
        if job is None:
            job = asyncio.ensure_future(self._make_rate(key, rate, out))
            self.rating[out.name] = job
            job.add_done_callback(lambda _: self.rating.pop(out.name, None))
        await asyncio.shield(job)
        return out

    async def _make_rate(self, key: str, rate: float, out: Path) -> None:
        tmp = self.tmp_dir / f"{out.stem}-{next(self.ids)}.m4a"
        await with_rate(self.path(key), rate, tmp)
        os.replace(tmp, out)

    async def stop(self) -> None:
        if self.consumer:
            self.consumer.cancel()
        if self.proc and self.proc.returncode is None:
            self.proc.stdin.close()
            try:
                await asyncio.wait_for(self.proc.wait(), timeout=5)
            except asyncio.TimeoutError:
                self.proc.kill()
