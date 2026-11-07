"""Records on the Mac, outside the repository (spec 「녹음과 기록」). Recordings are never deleted here."""
from __future__ import annotations

import json
import logging
import os
import re
import secrets
import tempfile
from pathlib import Path

from .models import Roleplay, Saved

ID = re.compile(r"^[0-9a-f]{12}$")
log = logging.getLogger("je_server")


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

    @staticmethod
    def _write(path: Path, text: str) -> None:
        """Written whole or not at all: a temporary file in the same folder, then replaced."""
        fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".json")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp, path)

    def save(self, rp: Roleplay) -> None:
        d = self._dir(rp.id)
        d.mkdir(exist_ok=True)
        self._write(d / "roleplay.json", rp.model_dump_json(indent=1))

    # --- saved sentences (ADR-0011): one file for all of them ----------------------------------------------------

    def load_saved(self) -> list[Saved]:
        path = self.root / "saved.json"
        if not path.exists():
            return []
        return [Saved.model_validate(s) for s in json.loads(path.read_text(encoding="utf-8"))]

    def save_saved(self, items: list[Saved]) -> None:
        self._write(self.root / "saved.json", json.dumps([s.model_dump() for s in items], ensure_ascii=False, indent=1))

    def load(self, rp_id: str) -> Roleplay:
        path = self._dir(rp_id) / "roleplay.json"
        if not path.exists():
            raise KeyError(rp_id)
        return Roleplay.model_validate_json(path.read_text(encoding="utf-8"))

    def all(self) -> list[Roleplay]:
        """Every roleplay on the Mac, for 「다시 연습」 (ADR-0011). A file that cannot be read is skipped."""
        found = []
        for d in self.roleplays.iterdir():
            if ID.match(d.name) and (d / "roleplay.json").exists():
                try:
                    found.append(Roleplay.model_validate_json((d / "roleplay.json").read_text(encoding="utf-8")))
                except ValueError:
                    log.warning("unreadable roleplay %s", d.name)
        return found

    def recent_situations(self, n: int = 10, topic: str = "other") -> list[str]:
        """The topic's latest situations, for Jake to avoid. A roleplay from before topics counts as "other"."""
        found = [(rp.created, rp.situation) for rp in self.all() if (rp.topic or "other") == topic]
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
