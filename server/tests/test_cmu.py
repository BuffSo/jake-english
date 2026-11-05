from je_server import cmu


def test_record_has_noun_and_verb_stress():
    assert {cmu.primary_index(p) for p in cmu.prons("record")} >= {0, 1}


def test_lookup_ignores_case_and_punctuation():
    assert cmu.prons("Coffee.") == cmu.prons("coffee") != []


def test_unknown_word_is_empty():
    assert cmu.prons("namsan") == []


def test_primary_index_and_vowels():
    assert cmu.primary_index(["K", "AA1", "F", "IY0"]) == 0
    assert cmu.vowel_count(["K", "AA1", "F", "IY0"]) == 2
    assert cmu.strip_stress(["K", "AA1", "F", "IY0"]) == ["K", "AA", "F", "IY"]
