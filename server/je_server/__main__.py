"""Run the server: uv run python -m je_server"""
import logging

import uvicorn

from .app import build_services, create_app
from .config import load_settings
from .listen import wait_for_address


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    settings = load_settings()
    # before whisper and the voice load: at login Tailscale may not be up yet (ADR-0011)
    wait_for_address(settings.host, settings.port)
    app = create_app(settings, build_services(settings))
    # access_log off: URLs carry no text, but keep the log to timings and counts
    uvicorn.run(app, host=settings.host, port=settings.port, access_log=False)


if __name__ == "__main__":
    main()
