"""Records on the Mac, outside the repository (spec 「녹음과 기록」). Recordings are never deleted here."""
from __future__ import annotations

import os
import re
import secrets
import tempfile
from pathlib import Path

from .models import Roleplay

ID = re.compile(r"^[0-9a-f]{12}$")


class Store:
    def __init__(self, root: Path):
        self.root = root
        self.roleplays = root / "roleplays"
        self.audio_dir = root / "audio"
        self.tmp_dir = root / "tmp"
        for d in (self.roleplays, self.audio_dir, self.tmp_dir):
            d.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def new_id() -> str:
        return secrets.token_hex(6)

    def _dir(self, rp_id: str) -> Path:
        if not ID.match(rp_id):
            raise KeyError(rp_id)
        return self.roleplays / rp_id

    def save(self, rp: Roleplay) -> None:
        d = self._dir(rp.id)
        d.mkdir(exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=d, suffix=".json")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(rp.model_dump_json(indent=1))
        os.replace(tmp, d / "roleplay.json")

    def load(self, rp_id: str) -> Roleplay:
        path = self._dir(rp_id) / "roleplay.json"
        if not path.exists():
            raise KeyError(rp_id)
        return Roleplay.model_validate_json(path.read_text(encoding="utf-8"))

    def recent_situations(self, n: int = 10) -> list[str]:
        found = []
        for d in self.roleplays.iterdir():
            if ID.match(d.name) and (d / "roleplay.json").exists():
                rp = Roleplay.model_validate_json((d / "roleplay.json").read_text(encoding="utf-8"))
                found.append((rp.created, rp.situation))
        return [s for _, s in sorted(found, reverse=True)[:n]]

    def next_rec(self, rp_id: str, idx: int) -> tuple[int, Path]:
        n = 1
        while self.rec_path(rp_id, idx, n).exists():
            n += 1
        return n, self.rec_path(rp_id, idx, n)

    def find_rec(self, rp_id: str, idx: int, n: int) -> Path | None:
        """An existing recording, for replay. Unlike rec_path it creates no folder; a bad ID finds nothing."""
        try:
            path = self._dir(rp_id) / "rec" / f"{idx}-{n}.m4a"
        except KeyError:
            return None
        return path if path.is_file() else None

    def rec_path(self, rp_id: str, idx: int, n: int) -> Path:
        d = self._dir(rp_id) / "rec"
        d.mkdir(parents=True, exist_ok=True)
        return d / f"{idx}-{n}.m4a"
