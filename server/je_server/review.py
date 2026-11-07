"""Reading past records for 「다시 연습」 (spec 2026-11-07-review-practice, ADR-0011). Pure functions over
`Roleplay` records; nothing here calls Claude."""
from __future__ import annotations

import re

_PIECE = re.compile(r"[a-z0-9']+")


def sentence_key(text: str) -> str:
    """The same sentence, case and punctuation aside (speaking spec 「지난 녹음과 비교」). The app has the same rule
    (`app/src/flow/review.ts`); contract/sentence-keys.json keeps the two in step."""
    return " ".join(_PIECE.findall(text.lower().replace("’", "'")))
