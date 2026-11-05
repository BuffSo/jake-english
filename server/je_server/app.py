"""FastAPI app. All routes sit behind the token check."""
from __future__ import annotations

from dataclasses import dataclass

from fastapi import APIRouter, Depends, FastAPI

from .auth import token_checker
from .config import Settings


@dataclass
class Services:
    """Filled in by later tasks (engine, voice, whisper)."""


def create_app(settings: Settings, services: Services | None = None) -> FastAPI:
    app = FastAPI(title="jake-english server", docs_url=None, redoc_url=None, openapi_url=None)
    router = APIRouter(dependencies=[Depends(token_checker(settings.token))])

    @router.get("/health")
    def health() -> dict:
        return {"ok": True}

    app.include_router(router)
    return app
