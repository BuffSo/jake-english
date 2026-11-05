"""CMUdict lookups (word stress and phonemes)."""
from __future__ import annotations

import re
from functools import lru_cache


@lru_cache(maxsize=1)
def _dict() -> dict[str, list[list[str]]]:
    import cmudict

    return cmudict.dict()


def key(word: str) -> str:
    w = word.lower().replace("’", "'")
    return re.sub(r"^[^a-z0-9']+|[^a-z0-9']+$", "", w)


def prons(word: str) -> list[list[str]]:
    return _dict().get(key(word), [])


def _is_vowel(phone: str) -> bool:
    return phone[-1].isdigit()


def vowel_count(pron: list[str]) -> int:
    return sum(1 for p in pron if _is_vowel(p))


def primary_index(pron: list[str]) -> int | None:
    vowels = [p for p in pron if _is_vowel(p)]
    for i, p in enumerate(vowels):
        if p.endswith("1"):
            return i
    return None


def strip_stress(pron: list[str]) -> list[str]:
    return [p.rstrip("012") for p in pron]
