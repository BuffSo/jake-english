"""Run the server: uv run python -m je_server"""
import uvicorn

from .app import create_app
from .config import load_settings


def main() -> None:
    settings = load_settings()
    uvicorn.run(create_app(settings), host=settings.host, port=settings.port)


if __name__ == "__main__":
    main()
