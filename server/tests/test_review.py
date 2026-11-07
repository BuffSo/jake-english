import json
from pathlib import Path

from je_server.review import sentence_key

CONTRACT = Path(__file__).resolve().parents[2] / "contract"


def test_sentence_keys_match_contract():
    for text, key in json.loads((CONTRACT / "sentence-keys.json").read_text(encoding="utf-8")):
        assert sentence_key(text) == key, text
