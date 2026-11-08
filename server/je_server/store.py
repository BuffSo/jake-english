"""Records on the Mac, outside the repository (spec 「녹음과 기록」). Recordings are never deleted here."""
from __future__ import annotations

import json
import logging
import os
import re
import secrets
import tempfile
from pathlib import Path

from . import topics
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
        """The saved sentences. An unreadable file or entry is skipped, like an unreadable roleplay in `all`: one bad
        record must not take the whole list down (todo 01). The text is not logged."""
        items, ok = self._read_saved()
        if not ok:
            log.warning("unreadable saved sentences skipped")
        return items

    def save_saved(self, items: list[Saved]) -> None:
        """Writes the list. A file that could not be read whole is first kept as saved.broken.json (then
        saved.broken.2.json and so on, never over an earlier copy), so what was in it can still be put back by hand
        (final review: a second breakage used to be lost). The copies stay in the app data folder until removed."""
        path = self.root / "saved.json"
        if path.exists() and not self._read_saved()[1]:
            n = 1
            while (broken := self.root / ("saved.broken.json" if n == 1 else f"saved.broken.{n}.json")).exists():
                n += 1
            path.replace(broken)
            log.warning("kept unreadable saved sentences as %s", broken.name)
        self._write(path, json.dumps([s.model_dump() for s in items], ensure_ascii=False, indent=1))

    def _read_saved(self) -> tuple[list[Saved], bool]:
        """The entries that could be read, and whether the whole file could."""
        path = self.root / "saved.json"
        if not path.exists():
            return [], True
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except ValueError:
            return [], False
        if not isinstance(raw, list):
            return [], False
        items, ok = [], True
        for entry in raw:
            try:
                items.append(Saved.model_validate(entry))
            except ValueError:
                ok = False
        return items, ok

    # --- Ryan's shadowing tip: the day it was last said and which comes next (spec ryan-shadowing-tip 4) ----------

    def load_tip(self) -> tuple[str | None, int]:
        """The day (YYYY-MM-DD) the tip was last said and the turn of the next one. A missing or unreadable file reads
        as never said, from the first one: the first screen must not fail over it."""
        path = self.root / "tip.json"
        if not path.exists():
            return None, 0
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            day, nxt = raw["day"], raw["next"]
            if not isinstance(day, str) or not isinstance(nxt, int) or isinstance(nxt, bool) or nxt < 0:
                raise ValueError
        except (ValueError, TypeError, KeyError):
            log.warning("unreadable tip.json: starting the tips over")
            return None, 0
        return day, nxt

    def save_tip(self, day: str, next_: int) -> None:
        self._write(self.root / "tip.json", json.dumps({"day": day, "next": next_}))

    # --- free talk: the turn of Ryan's next first question (spec free-talk-design 2) ---------------------------------

    def load_talk(self) -> int:
        """The turn of the next first question. A missing or unreadable file reads as the first one."""
        path = self.root / "talk.json"
        if not path.exists():
            return 0
        try:
            nxt = json.loads(path.read_text(encoding="utf-8"))["next"]
            if not isinstance(nxt, int) or isinstance(nxt, bool) or nxt < 0:
                raise ValueError
        except (ValueError, TypeError, KeyError):
            log.warning("unreadable talk.json: starting the first questions over")
            return 0
        return nxt

    def save_talk(self, next_: int) -> None:
        self._write(self.root / "talk.json", json.dumps({"next": next_}))

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

    def recent_situations(self, n: int = 10, topic: str = topics.OTHER) -> list[str]:
        """The topic's latest situations, for Jake to avoid. A roleplay from before topics counts as 「그 밖의 상황」."""
        found = [(rp.created, rp.situation) for rp in self.all() if rp.kind != "talk" and (rp.topic or topics.OTHER) == topic]
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

    def play_path(self, rp_id: str, idx: int, n: int) -> Path:
        """The play copy of a recording, beside it (spec play-button-feedback 4). Not `{idx}-{n}.m4a`, so it is never
        taken for a try. Creates no folder."""
        return self._dir(rp_id) / "rec" / f"{idx}-{n}.play.m4a"

    def rec_path(self, rp_id: str, idx: int, n: int) -> Path:
        d = self._dir(rp_id) / "rec"
        d.mkdir(parents=True, exist_ok=True)
        return d / f"{idx}-{n}.m4a"
