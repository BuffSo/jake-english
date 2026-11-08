"""Cut streamed text into sentences for the voice, so the first sentence plays while the rest arrives."""
from __future__ import annotations

import re

END = re.compile(r"(?<=[.?!])\s+")


class NewSentence(str):
    """Text that starts a new sentence for the voice where `SentenceBuffer` would not cut: after 「…」 or a mark inside
    a closing bracket or quote (PR #44 review). The text shown is the same."""


class SentenceBuffer:
    def __init__(self):
        self.buf = ""

    def feed(self, delta: str) -> list[str]:
        self.buf += delta
        parts = END.split(self.buf)
        self.buf = parts.pop()
        return [p.strip() for p in parts if p.strip()]

    def flush(self) -> list[str]:
        rest, self.buf = self.buf.strip(), ""
        return [rest] if rest else []
