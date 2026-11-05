"""Bearer token check. Every route goes through it (REVIEW.md 「맥 서버 보안」).

Two layers: `RequestGuard` runs before routing, so a request without the token, or one that declares a body
over the limit, is turned away before FastAPI reads the body (PR #12 review: a route with a JSON body was
read and parsed before the router's dependency ran). The router dependency stays as the second layer.
"""
from __future__ import annotations

import json
import secrets

from fastapi import HTTPException, Request


def _valid(header: str, expected: bytes) -> bool:
    scheme, _, given = header.partition(" ")
    return scheme.lower() == "bearer" and secrets.compare_digest(given.encode(), expected)


def token_checker(token: str):
    expected = token.encode()

    def require_token(request: Request) -> None:
        if not _valid(request.headers.get("authorization", ""), expected):
            raise HTTPException(status_code=401, detail={"code": "unauthorized", "say": None})

    return require_token


class RequestGuard:
    """ASGI middleware: token and declared body size, checked before the body is read."""

    def __init__(self, app, token: str, max_body: int):
        self.app, self.expected, self.max_body = app, token.encode(), max_body

    async def _reply(self, send, status: int, code: str) -> None:
        body = json.dumps({"code": code, "say": None}).encode()
        await send({"type": "http.response.start", "status": status,
                    "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode())]})
        await send({"type": "http.response.body", "body": body})

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        headers = {k.lower(): v for k, v in scope.get("headers", [])}
        if not _valid(headers.get(b"authorization", b"").decode("latin-1"), self.expected):
            return await self._reply(send, 401, "unauthorized")
        declared = headers.get(b"content-length")
        if declared is not None:
            try:
                size = int(declared)
            except ValueError:
                return await self._reply(send, 400, "bad_request")
            if size > self.max_body:
                return await self._reply(send, 413, "too_long")
        await self.app(scope, receive, send)
