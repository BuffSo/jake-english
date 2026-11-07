"""Wait until the server can bind its address, before anything is loaded (ADR-0012).

launchd starts the server at login, and Tailscale may not have put the Mac's address on yet
(ADR-0007: the server binds only that address). uvicorn binds after the app's startup, so without
this wait whisper and the voice worker would load, the bind would fail, and launchd would start it
all again every 10 seconds. The same wait covers a worktree server still holding the port
(DEVENV guide 「카드가 서버를 시험할 때」). Any other bind error is left to uvicorn to report.

A well-formed JE_HOST that is wrong (a mistyped digit) fails the same way as Tailscale not up yet,
so the wait gives up after LIMIT with an error: launchd's last exit code and the log then show it,
and launchd starts the cheap wait again (PR #26 review).
"""
from __future__ import annotations

import errno
import logging
import socket
import time
from collections.abc import Callable

log = logging.getLogger("je_server")
STEP = 2.0
LIMIT = 300.0
WAIT_ON = {errno.EADDRNOTAVAIL: "address not on this Mac yet", errno.EADDRINUSE: "port in use"}


def _bind_error(host: str, port: int) -> int | None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)  # as uvicorn binds
        try:
            s.bind((host, port))
        except OSError as e:
            return e.errno if e.errno in WAIT_ON else None
    return None


def wait_for_address(host: str, port: int, sleep: Callable[[float], None] = time.sleep,
                     limit: float = LIMIT) -> None:
    code = _bind_error(host, port)
    if code is None:
        return
    log.info("waiting to bind JE_HOST:JE_PORT (%s)", WAIT_ON[code])
    started = time.monotonic()
    for _ in range(round(limit / STEP)):
        sleep(STEP)
        code = _bind_error(host, port)
        if code is None:
            log.info("JE_HOST:JE_PORT free after %.0fs", time.monotonic() - started)
            return
    raise SystemExit(f"could not bind JE_HOST:JE_PORT for {limit:.0f}s ({WAIT_ON[code]}); "
                     "check JE_HOST in server/.env and that Tailscale is on")
