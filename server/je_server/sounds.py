"""The sound explanation list (spec 「소리 설명 목록」). Ryan only rewords these; he never invents one.

The texts in data/sounds.json are a draft until a person reviews them.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Sound:
    a: str  # CMUdict phoneme (stress removed)
    b: str
    name: str
    explain: str


SOUNDS: list[Sound] = [Sound(**s) for s in json.loads(
    (Path(__file__).with_name("data") / "sounds.json").read_text(encoding="utf-8"))]
LISTED_PHONES = {p for s in SOUNDS for p in (s.a, s.b)}


def find(a: str, b: str) -> Sound | None:
    return next((s for s in SOUNDS if {s.a, s.b} == {a, b}), None)
