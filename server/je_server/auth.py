"""Bearer token check. Every route goes through it (REVIEW.md 「맥 서버 보안」)."""
from __future__ import annotations

import secrets

from fastapi import HTTPException, Request


def token_checker(token: str):
    expected = token.encode()

    def require_token(request: Request) -> None:
        header = request.headers.get("authorization", "")
        scheme, _, given = header.partition(" ")
        if scheme.lower() != "bearer" or not secrets.compare_digest(given.encode(), expected):
            raise HTTPException(status_code=401, detail={"code": "unauthorized", "say": None})

    return require_token
