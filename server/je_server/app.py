"""FastAPI app. Every route sits behind the token check (REVIEW.md 「맥 서버 보안」)."""
from __future__ import annotations

import json
import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request
from fastapi import Path as PathParam
from fastapi import Query
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from typing import Literal

from pydantic import BaseModel, Field

from .auth import token_checker
from .claude import ClaudeUnavailable
from .config import Settings
from .engine import Engine, NotFound, TooLong

log = logging.getLogger("je_server")
MAX_UPLOAD = 5 * 1024 * 1024
ASSETS = {"ryan-front.png", "ryan-listening.png"}
ID = r"^[0-9a-f]{12}$"
KEY = r"^[0-9a-f]{64}$"


@dataclass
class Services:
    engine: Engine
    voice: Any
    whisper: Any

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
    from .claude import Claude
    from .store import Store
    from .tts import Voice

    store = Store(settings.data_dir)
    voice = Voice(settings.tts_python, settings.tts_module, store.audio_dir)
    whisper = Whisper(settings.whisper_exe, settings.whisper_model, settings.whisper_port)
    claude = Claude(anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key, max_retries=2, timeout=60))
    return Services(engine=Engine(store, claude, voice, whisper), voice=voice, whisper=whisper)


class ApiError(Exception):
    def __init__(self, status: int, code: str, say: dict | None = None):
        self.status, self.code, self.say = status, code, say


class NewRoleplay(BaseModel):
    situation: str = Field(min_length=1, max_length=300)


async def read_body(request: Request) -> bytes:
    if int(request.headers.get("content-length") or 0) > MAX_UPLOAD:
        raise ApiError(413, "too_long")
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

    @router.get("/health")
    def health() -> dict:
        return {"ok": True}

    @router.get("/home")
    def home() -> dict:
        e = engine()
        return {"lines": {n: e.said(n).model_dump() for n in ("greeting", "ask_mode", "ask_situation", "ask_recommend")},
                "images": {"front": "/assets/ryan-front.png", "listening": "/assets/ryan-listening.png"}}

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
        if not services.voice.path(key).is_file():
            raise ApiError(404, "not_found")
        return FileResponse(await services.voice.rate_file(key, rate), media_type="audio/mp4")

    @router.post("/transcribe")
    async def transcribe(request: Request) -> dict:
        body = await read_body(request)
        try:
            return {"text": await engine().transcribe(body)}
        except TooLong:
            raise ApiError(413, "too_long", engine().said("too_long").model_dump()) from None

    @router.post("/recommend")
    async def recommend() -> dict:
        try:
            return (await engine().recommend()).model_dump()
        except ClaudeUnavailable:
            raise claude_down() from None

    @router.post("/roleplays")
    async def create(body: NewRoleplay) -> dict:
        try:
            return (await engine().create(body.situation.strip())).model_dump(mode="json")
        except ClaudeUnavailable:
            raise claude_down() from None

    @router.get("/roleplays/{rp_id}/lines/{idx}")
    async def line(rp_id: str = PathParam(pattern=ID), idx: int = PathParam(ge=0)) -> dict:
        try:
            return (await engine().line(rp_id, idx)).model_dump(mode="json")
        except NotFound:
            raise ApiError(404, "not_found") from None
        except ClaudeUnavailable:
            raise claude_down() from None

    @router.get("/roleplays/{rp_id}/lines/{idx}/three")
    async def three(rp_id: str = PathParam(pattern=ID), idx: int = PathParam(ge=0)) -> dict:
        try:
            return (await engine().three(rp_id, idx)).model_dump(mode="json")
        except NotFound:
            raise ApiError(404, "not_found") from None
        except ClaudeUnavailable:
            raise claude_down() from None

    @router.post("/roleplays/{rp_id}/lines/{idx}/attempts")
    async def attempt(request: Request, rp_id: str = PathParam(pattern=ID), idx: int = PathParam(ge=0),
                      mode: Literal["turn", "retry"] = Query("turn")):
        body = await read_body(request)
        try:
            engine().user_line(rp_id, idx)
        except NotFound:
            raise ApiError(404, "not_found") from None

        async def lines():
            async for ev in engine().attempt(rp_id, idx, body, mode):
                yield json.dumps(ev, ensure_ascii=False) + "\n"

        return StreamingResponse(lines(), media_type="application/x-ndjson")

    @router.get("/roleplays/{rp_id}/summary")
    def summary(rp_id: str = PathParam(pattern=ID)) -> dict:
        try:
            return engine().summary(rp_id)
        except NotFound:
            raise ApiError(404, "not_found") from None

    app.include_router(router)
    return app
