"""FastAPI app. Every route sits behind the token check (REVIEW.md 「맥 서버 보안」)."""
from __future__ import annotations

import json
import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request
from fastapi import Path as PathParam
from fastapi import Query
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse

from pydantic import BaseModel, Field, model_validator

from . import topics
from .hints import hide_unshown  # every answer with lines goes through it (spec free-talk-design 9)
from .auth import RequestGuard, token_checker
from .claude import ClaudeUnavailable
from .config import Settings
from .engine import Engine, NotFound, TooLong
from .asr import WhisperError
from .models import Mode
from .talk import CannotDrop, NoHint, Talks, TalkBusy, TalkEnded
from .tts import VoiceError

log = logging.getLogger("je_server")
MAX_UPLOAD = 5 * 1024 * 1024
# Thinking faces shown instead of a spinner while Claude works, two per person, cross-faded by the app
# (docs/superpowers/specs/2026-11-06-waiting-animation-design.md). Like Ryan's pictures they live only in the
# private assets folder.
THINKING = {who: [f"{who}-thinking-{n}.png" for n in (1, 2)] for who in ("jake", "ryan", "sohee")}
# jake-front.png: Jake's face while his suggested situation waits for 「이걸로 할게요」 or 「다른 걸로요」 (2026-11-06 user)
# Sohee's faces for the free talk (spec free-talk 2, 3): the face and the whisper face sit beside the thinking pair
# (the thinking pair comes from THINKING above).
ASSETS = {"ryan-front.png", "ryan-listening.png", "jake-front.png", "sohee-face.png", "sohee-whisper-face.png",
          *THINKING["jake"], *THINKING["ryan"], *THINKING["sohee"]}
ID = r"^[0-9a-f]{12}$"
KEY = r"^[0-9a-f]{64}$"


@dataclass
class Services:
    engine: Engine
    voice: Any
    whisper: Any
    talks: Talks | None = None

    def __post_init__(self) -> None:
        # one Talks for the whole app: its busy and ending guards are per instance (spec 2, 6)
        if self.talks is None:
            self.talks = Talks(self.engine)

    async def start(self) -> None:
        await self.whisper.start()
        await self.voice.start()
        await self.engine.warm()

    async def stop(self) -> None:
        await self.voice.stop()
        await self.whisper.stop()


def build_services(settings: Settings) -> Services:
    import anthropic

    from .asr import Whisper
    from .claude import QUICKS, TALKERS, WRITERS, Claude
    from .store import Store
    from .tts import Voice

    store = Store(settings.data_dir)
    whisper = Whisper(settings.whisper_exe, settings.whisper_model, settings.whisper_port)
    voice = Voice(settings.tts_python, settings.tts_module, store.audio_dir, hear=whisper.hear)
    writer, quick = WRITERS[settings.claude_writer], QUICKS[settings.claude_quick]
    recommender = QUICKS[settings.claude_recommend]
    talker, hinter = TALKERS[settings.claude_talk], QUICKS[settings.claude_hint]
    log.info("claude models: writer %s, quick %s, recommend %s, talk %s, hint %s", writer["model"], quick["model"],
             recommender["model"], talker["model"], hinter["model"])
    claude = Claude(anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key, max_retries=2, timeout=30),
                    writer=writer, quick=quick, recommender=recommender, talker=talker, hinter=hinter)
    return Services(engine=Engine(store, claude, voice, whisper), voice=voice, whisper=whisper)


class ApiError(Exception):
    def __init__(self, status: int, code: str, say: dict | None = None):
        self.status, self.code, self.say = status, code, say


TopicId = Literal[tuple(t.id for t in topics.TOPICS)]  # type: ignore[valid-type]


class NewRoleplay(BaseModel):
    """A situation the learner described or Jake suggested, or a line of the topic's list (spec situation-topics).
    Without a topic (an app from before topics) it is 「그 밖의 상황」."""

    situation: str | None = Field(None, min_length=1, max_length=300)
    pick: str | None = Field(None, max_length=40)
    topic: TopicId = topics.OTHER

    @model_validator(mode="after")
    def one_of(self) -> NewRoleplay:
        if (self.situation is None) == (self.pick is None):
            raise ValueError("give a situation or a pick")
        if self.pick is not None:
            try:
                topics.pick(self.topic, self.pick)
            except KeyError:
                raise ValueError("no such pick in the topic") from None
        return self


class SavedChange(BaseModel):
    rp_id: str = Field(pattern=ID)
    idx: int = Field(ge=0)
    on: bool


class Recommend(BaseModel):
    # Jake's suggestions turned down on the situation screen (「다른 걸로요」, 2026-11-06), so they do not come
    # back. Limited like the situation itself; the app keeps the last TURNED_DOWN_MAX.
    skip: list[Annotated[str, Field(max_length=300)]] = Field(default_factory=list, max_length=10)
    topic: TopicId = topics.OTHER


async def read_body(request: Request) -> bytes:
    """The declared size is checked by RequestGuard; this also stops an undeclared (chunked) body at the limit."""
    buf = bytearray()
    async for chunk in request.stream():
        buf += chunk
        if len(buf) > MAX_UPLOAD:
            raise ApiError(413, "too_long")
    return bytes(buf)


def create_app(settings: Settings, services: Services | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if services is not None:
            await services.start()
            log.info("ready")
        yield
        if services is not None:
            await services.stop()

    app = FastAPI(title="jake-english server", docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)
    app.add_middleware(RequestGuard, token=settings.token, max_body=MAX_UPLOAD)
    router = APIRouter(dependencies=[Depends(token_checker(settings.token))])

    @app.exception_handler(ApiError)
    async def api_error(_: Request, e: ApiError):
        return JSONResponse({"code": e.code, "say": e.say}, status_code=e.status)

    @app.exception_handler(HTTPException)
    async def http_error(_: Request, e: HTTPException):
        body = e.detail if isinstance(e.detail, dict) else {"code": "not_found" if e.status_code == 404 else "error",
                                                           "say": None}
        return JSONResponse(body, status_code=e.status_code)

    @app.exception_handler(RequestValidationError)
    async def bad_request(_: Request, e: RequestValidationError):
        return JSONResponse({"code": "bad_request", "say": None}, status_code=422)

    def engine() -> Engine:
        if services is None:
            raise ApiError(503, "not_ready")
        return services.engine

    def claude_down() -> ApiError:
        return ApiError(503, "claude_unavailable", engine().said("claude_down").model_dump())

    def talks() -> Talks:
        if services is None:
            raise ApiError(503, "not_ready")
        return services.talks

    @router.get("/health")
    def health() -> dict:
        return {"ok": True}

    @router.get("/home")
    def home(tip: bool = Query(False)) -> dict:
        e = engine()
        lines = ("greeting", "ask_mode", "ask_again", "ask_situation", "ask_recommend", "ask_topic", "ask_how",
                 "ask_pick", "ask_describe")
        # Ryan's shadowing tip, the day's first time the app asks for it (spec ryan-shadowing-tip 4). Only when asked:
        # a plain `curl /home` checking the server is up must not use up the day's line.
        said_tip = e.home_tip() if tip else None
        extra = {"tip": said_tip.model_dump()} if said_tip else {}
        return {"lines": {n: e.said(n).model_dump() for n in lines}, **extra, "topics": topics.public(),
                "images": {"front": "/assets/ryan-front.png", "listening": "/assets/ryan-listening.png",
                           "jake": "/assets/jake-front.png",
                           "thinking": {who: [f"/assets/{n}" for n in names] for who, names in THINKING.items()},
                           "sohee": {"face": "/assets/sohee-face.png", "whisper": "/assets/sohee-whisper-face.png"}}}

    @router.get("/assets/{name}")
    def asset(name: str):
        path = settings.assets_dir / name
        if name not in ASSETS or not path.is_file():
            raise ApiError(404, "not_found")
        return FileResponse(path, media_type="image/png")

    @router.get("/audio/{key}")
    async def sound(key: str = PathParam(pattern=KEY), rate: float = Query(1.0)):
        if rate not in (0.6, 0.8, 1.0):
            raise ApiError(422, "bad_request")
        voice = engine().voice  # through engine(): 503 not_ready when started without services (todo 11, 4번)
        if not voice.path(key).is_file():
            raise ApiError(404, "not_found")
        return FileResponse(await voice.rate_file(key, rate), media_type="audio/mp4")

    @router.post("/transcribe")
    async def transcribe(request: Request) -> dict:
        body = await read_body(request)
        try:
            return {"text": await engine().transcribe(body)}
        except TooLong:
            raise ApiError(413, "too_long", engine().said("too_long").model_dump()) from None

    @router.post("/recommend")
    async def recommend(body: Recommend | None = None) -> dict:
        try:
            body = body or Recommend()
            return (await engine().recommend(body.skip, body.topic)).model_dump()
        except ClaudeUnavailable:
            raise claude_down() from None

    @router.post("/roleplays")
    async def create(body: NewRoleplay) -> dict:
        try:
            if body.pick is not None:  # its script is in the repository: no Claude (spec fixed-list-scripts)
                rp = await engine().create_pick(body.topic, body.pick)
            else:
                rp = await engine().create(body.situation.strip(), body.topic)
            return hide_unshown(rp.model_dump(mode="json"))
        except ClaudeUnavailable:
            raise claude_down() from None

    @router.get("/roleplays/{rp_id}")
    def roleplay(rp_id: str = PathParam(pattern=ID)) -> dict:
        try:
            return hide_unshown(engine().load(rp_id).model_dump(mode="json"))
        except NotFound:
            raise ApiError(404, "not_found") from None

    @router.get("/past")
    def past() -> dict:
        return {"items": engine().past()}

    @router.get("/groups/{group}/latest")
    def latest(group: str = PathParam(pattern=ID)) -> dict:
        try:
            return hide_unshown(engine().latest(group))
        except NotFound:
            raise ApiError(404, "not_found") from None

    @router.get("/resume")
    def resume() -> dict:
        # the conversation to resume and where, or null (spec resume-roleplay 1, 2)
        return {"resume": hide_unshown(engine().resume())}

    @router.get("/saved")
    def saved() -> dict:
        return {"items": engine().saved()}

    @router.post("/saved")
    async def set_saved(body: SavedChange) -> dict:
        try:
            return await engine().set_saved(body.rp_id, body.idx, body.on)
        except NotFound:
            raise ApiError(404, "not_found") from None

    @router.post("/roleplays/{rp_id}/copy")
    async def copy(rp_id: str = PathParam(pattern=ID)) -> dict:
        try:
            return hide_unshown((await engine().copy(rp_id)).model_dump(mode="json"))
        except NotFound:
            raise ApiError(404, "not_found") from None

    @router.get("/roleplays/{rp_id}/lines/{idx}")
    async def line(rp_id: str = PathParam(pattern=ID), idx: int = PathParam(ge=0)) -> dict:
        try:
            line = await engine().line(rp_id, idx)  # waits for the model sound only (LINE_WAIT); notes come later
            return hide_unshown({**line.model_dump(mode="json"), "progress": engine().progress(rp_id, idx)})
        except NotFound:
            raise ApiError(404, "not_found") from None

    @router.get("/roleplays/{rp_id}/lines/{idx}/three")
    async def three(rp_id: str = PathParam(pattern=ID), idx: int = PathParam(ge=0)) -> dict:
        try:
            return (await engine().three(rp_id, idx)).model_dump(mode="json")
        except NotFound:
            raise ApiError(404, "not_found") from None
        except ClaudeUnavailable:
            raise claude_down() from None

    @router.get("/roleplays/{rp_id}/lines/{idx}/ko")
    async def ko(rp_id: str = PathParam(pattern=ID), idx: int = PathParam(ge=0)) -> dict:
        try:
            return {"text": await engine().ko(rp_id, idx)}
        except NotFound:
            raise ApiError(404, "not_found") from None
        except ClaudeUnavailable:
            raise claude_down() from None

    @router.get("/roleplays/{rp_id}/lines/{idx}/ko/audio")
    async def ko_audio(rp_id: str = PathParam(pattern=ID), idx: int = PathParam(ge=0)) -> dict:
        try:
            return {"audio": await engine().ko_audio(rp_id, idx)}
        except NotFound:
            raise ApiError(404, "not_found") from None
        except VoiceError:
            raise ApiError(503, "voice_unavailable") from None

    @router.post("/roleplays/{rp_id}/lines/{idx}/attempts")
    async def attempt(request: Request, rp_id: str = PathParam(pattern=ID), idx: int = PathParam(ge=0),
                      mode: Mode = Query("turn")):
        body = await read_body(request)
        try:
            engine().target_line(rp_id, idx, mode)
        except NotFound:
            raise ApiError(404, "not_found") from None

        async def lines():
            async for ev in engine().attempt(rp_id, idx, body, mode):
                yield json.dumps(ev, ensure_ascii=False) + "\n"

        return StreamingResponse(lines(), media_type="application/x-ndjson")

    @router.post("/roleplays/{rp_id}/lines/{idx}/skip")
    async def skip(rp_id: str = PathParam(pattern=ID), idx: int = PathParam(ge=0)) -> dict:
        # a line of mine skipped inside the roleplay: its place moves past it (spec resume-roleplay 3)
        try:
            return {"pos": await engine().skip(rp_id, idx)}
        except NotFound:
            raise ApiError(404, "not_found") from None

    @router.get("/roleplays/{rp_id}/lines/{idx}/attempts/{n}/recording")
    async def recording(rp_id: str = PathParam(pattern=ID), idx: int = PathParam(ge=0), n: int = PathParam(ge=1)):
        # found by a checked ID and two integers only, inside the roleplay's rec folder (REVIEW.md 「맥 서버 보안」);
        # its play copy, cut to the speech (spec play-button-feedback 4)
        try:
            return FileResponse(await engine().recording(rp_id, idx, n), media_type="audio/mp4")
        except NotFound:
            raise ApiError(404, "not_found") from None

    @router.get("/roleplays/{rp_id}/summary")
    def summary(rp_id: str = PathParam(pattern=ID)) -> dict:
        try:
            return hide_unshown(engine().summary(rp_id))
        except NotFound:
            raise ApiError(404, "not_found") from None

    # --- free talk (spec free-talk-design 2, 6, 7). Like every route, behind the token; the recording comes through
    # `read_body` (5 MB); ids are checked by `ID`, `heard` is a count 0..50 ---------------------------------------
    # 「↻ 다시 말하기」 drops my last turn by its line number, found only among the talk's lines
    # (docs/superpowers/specs/2026-11-09-talk-resay-design.md 3, 4)

    @router.post("/talks")
    async def create_talk() -> dict:
        return hide_unshown((await talks().create()).model_dump(mode="json"))  # a VoiceError is kept in `create`

    @router.post("/talks/{rp_id}/turns")
    async def talk_turn(request: Request, rp_id: str = PathParam(pattern=ID),
                        heard: int | None = Query(None, ge=0, le=50)):
        body = await read_body(request)
        try:
            talks().check_open(rp_id)  # before streaming, so a refusal is a status and not a line
        except NotFound:
            raise ApiError(404, "not_found") from None
        except TalkEnded:
            raise ApiError(409, "ended") from None
        except TalkBusy:
            raise ApiError(409, "busy") from None

        async def lines():
            try:
                async for ev in talks().turn(rp_id, body, heard):
                    yield json.dumps(ev, ensure_ascii=False) + "\n"
            except WhisperError:
                # whisper could not hear it: an error event the app shows, not a stream that breaks off
                yield json.dumps(engine().talk_error("no_speech"), ensure_ascii=False) + "\n"

        return StreamingResponse(lines(), media_type="application/x-ndjson")

    @router.post("/talks/{rp_id}/lines/{idx}/drop")
    async def drop_turn(rp_id: str = PathParam(pattern=ID), idx: int = PathParam(ge=0)) -> dict:
        # sent as 「↻ 다시 말하기」 is pressed, before the turn said again (spec talk-resay 3 「맥에 알리는 길」)
        try:
            await talks().drop(rp_id, idx)
        except NotFound:
            raise ApiError(404, "not_found") from None
        except TalkEnded:
            raise ApiError(409, "ended") from None
        except TalkBusy:
            raise ApiError(409, "busy") from None
        except CannotDrop as e:
            raise ApiError(409, e.code) from None
        return {"dropped": idx}

    @router.post("/talks/{rp_id}/end")
    async def end_talk(rp_id: str = PathParam(pattern=ID), heard: int | None = Query(None, ge=0, le=50)) -> dict:
        try:
            return hide_unshown(await talks().end(rp_id, heard))
        except NotFound:
            raise ApiError(404, "not_found") from None
        except TalkBusy:
            raise ApiError(409, "busy") from None
        except ClaudeUnavailable:
            raise claude_down() from None

    # Sohee chance on Ryan's reply at `idx` (spec free-talk-design 9), each step on its own route like `/ko` and
    # `/ko/audio`. A step asked before the one it follows is 409 `no_hint`; the first step's answer leaves the full
    # sentence out, which only 「전체 문장 보기」 (`/hint/full`) gives.

    @router.post("/talks/{rp_id}/lines/{idx}/hint")
    async def hint(rp_id: str = PathParam(pattern=ID), idx: int = PathParam(ge=0)) -> dict:
        try:
            h = await talks().hint(rp_id, idx)
        except NotFound:
            raise ApiError(404, "not_found") from None
        except ClaudeUnavailable:
            raise claude_down() from None
        return {"meaning_ko": h.meaning_ko, "starters": h.starters}

    @router.get("/talks/{rp_id}/lines/{idx}/hint/audio")
    async def hint_audio(rp_id: str = PathParam(pattern=ID), idx: int = PathParam(ge=0)) -> dict:
        try:
            return {"audio": await talks().hint_audio(rp_id, idx)}
        except NotFound:
            raise ApiError(404, "not_found") from None
        except NoHint:
            raise ApiError(409, "no_hint") from None
        except VoiceError:
            raise ApiError(503, "voice_unavailable") from None

    @router.post("/talks/{rp_id}/lines/{idx}/hint/full")
    async def hint_full(rp_id: str = PathParam(pattern=ID), idx: int = PathParam(ge=0)) -> dict:
        try:
            return await talks().show_full(rp_id, idx)
        except NotFound:
            raise ApiError(404, "not_found") from None
        except NoHint:
            raise ApiError(409, "no_hint") from None

    @router.get("/talks/{rp_id}/lines/{idx}/hint/sounds/{n}")
    async def hint_sound(rp_id: str = PathParam(pattern=ID), idx: int = PathParam(ge=0),
                         n: int = PathParam(ge=0, le=3)) -> dict:
        try:
            return {"audio": await talks().hint_sound(rp_id, idx, n)}
        except NotFound:
            raise ApiError(404, "not_found") from None
        except NoHint:
            raise ApiError(409, "no_hint") from None
        except VoiceError:
            raise ApiError(503, "voice_unavailable") from None

    @router.get("/talks/{rp_id}/lines/{idx}/hint/three")
    async def hint_three(rp_id: str = PathParam(pattern=ID), idx: int = PathParam(ge=0)) -> dict:
        try:
            return (await talks().hint_three(rp_id, idx)).model_dump(mode="json")
        except NotFound:
            raise ApiError(404, "not_found") from None
        except NoHint:
            raise ApiError(409, "no_hint") from None
        except ClaudeUnavailable:
            raise claude_down() from None

    app.include_router(router)
    return app
