"""Print the stress test's tables from the values scripts/measure_stress.py kept (spec stress-log 「표 다시 내기」).

    cd server && uv run python scripts/stress_report.py [--since YYYY-MM-DD]

Reads JE_DATA_DIR like the server. Prints counts and ratios as Markdown, never heard words or lines, so the output can
go into docs/guide/PRONUNCIATION_녹음으로_강세평가_시험_20261105.md as it is.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from je_server.config import DEFAULT_DATA_DIR, REPO_DIR, SERVER_DIR, read_env_file  # noqa: E402
from je_server.stress_report import load, render  # noqa: E402


def env() -> dict[str, str]:
    return {**read_env_file(REPO_DIR / ".env"), **read_env_file(SERVER_DIR / ".env"), **os.environ}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Print the stress tables from the kept values.")
    parser.add_argument("--since", help="only recordings from this day on (YYYY-MM-DD)")
    args = parser.parse_args(argv)
    data_dir = Path(env().get("JE_DATA_DIR") or DEFAULT_DATA_DIR).expanduser()
    records, broken = load(data_dir, args.since)
    print(render(records, broken), end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
