"""The parts of the voice worker that run without the voice model (the worker runs under the TTS virtualenv)."""
from je_server import tts_worker


def test_sentences_are_made_one_by_one():
    # 2026-11-05: pauses inside a sentence are cut short, so each sentence is made on its own to keep the
    # pause between sentences
    assert tts_worker.sentences("역할극 끝! 수고했어요. 고칠 것이 남았던 대사를 다시 해 볼까요?") == [
        "역할극 끝!", "수고했어요.", "고칠 것이 남았던 대사를 다시 해 볼까요?"]
    assert tts_worker.sentences("Sure, go straight for two blocks.") == ["Sure, go straight for two blocks."]
    assert tts_worker.sentences("  ") == []


def test_korean_pauses_inside_a_sentence_are_short():
    # 2026-11-05: Jake paused 0.4 s after 「은행 창구에서」 and 0.3 s after 「외국인 고객이」; the user heard it as
    # broken up. English model lines keep the module's cap.
    assert tts_worker.pause_cap("korean") <= 0.15
    assert tts_worker.pause_cap("english") == 0.75


def test_only_korean_is_split_into_sentences():
    # final review: English model lines must stay as they were made (one piece, no 0.6 s gap at "Mr." or
    # between sentences), and their sound keys did not change
    chunks = [("Sure. What size would you like?", "english"), ("Ask Mr. Smith at 3 p.m. today.", "english"),
              ("좋아요. 다음으로 가요.", "korean")]
    assert tts_worker.split_parts(chunks) == [
        ("Sure. What size would you like?", "english"), ("Ask Mr. Smith at 3 p.m. today.", "english"),
        ("좋아요.", "korean"), ("다음으로 가요.", "korean")]


# --- the reference recordings' fingerprints (todo voice-reference-in-sound-key) ---------------------------------

def fake_module(ref_dir):
    """Stands in for the voice setup: the parts `ref_prints` reads (its `ref_name` falls back to the Korean one)."""
    import types

    voices = {"ryan": {"ref": {"korean": "ryan_ko", "english": "ryan_en"}},
              "jake": {"ref": {"korean": "jake_ko", "english": "jake_en"}},
              "sohee_clone": {"ref": {"korean": "sohee_ko"}},
              "builtin": {"speaker": "x"}}
    for conf in voices.values():
        for name in conf.get("ref", {}).values():
            (ref_dir / f"{name}.wav").write_bytes(f"sound of {name}".encode())
            (ref_dir / f"{name}.txt").write_text(f"words of {name}", encoding="utf-8")
    return types.SimpleNamespace(REF_DIR=str(ref_dir), voice_conf=lambda n: voices.get(n, voices["builtin"]),
                                 ref_name=lambda conf, lang: conf["ref"].get(lang) or conf["ref"]["korean"])


def test_ref_prints_are_the_same_for_the_same_recordings(tmp_path):
    srv = fake_module(tmp_path)
    prints = tts_worker.ref_prints(srv)
    assert set(prints) == {"ryan", "jake", "sohee_clone"}
    assert all(len(p) == 16 for v in prints.values() for p in v.values())
    assert tts_worker.ref_prints(srv) == prints  # a restart with the same recordings keeps every sound


def test_a_new_korean_recording_changes_only_korean_sounds(tmp_path):
    srv = fake_module(tmp_path)
    before = tts_worker.ref_prints(srv)
    (tmp_path / "ryan_ko.wav").write_bytes(b"a new recording")
    after = tts_worker.ref_prints(srv)
    # English sounds use the English recording only; Korean ones may read English words with it, so they carry both
    assert after["ryan"]["english"] == before["ryan"]["english"]
    assert after["ryan"]["korean"] != before["ryan"]["korean"]
    assert after["jake"] == before["jake"] and after["sohee_clone"] == before["sohee_clone"]


def test_a_new_english_recording_or_its_words_change_both(tmp_path):
    srv = fake_module(tmp_path)
    before = tts_worker.ref_prints(srv)
    (tmp_path / "jake_en.txt").write_text("other words", encoding="utf-8")
    after = tts_worker.ref_prints(srv)
    assert after["jake"]["english"] != before["jake"]["english"]
    assert after["jake"]["korean"] != before["jake"]["korean"]


def test_a_missing_recording_does_not_stop_the_worker(tmp_path):
    # the worker must still say it is ready: a voice without its recording fails on its own sounds only
    srv = fake_module(tmp_path)
    before = tts_worker.ref_prints(srv)
    (tmp_path / "sohee_ko.wav").unlink()
    after = tts_worker.ref_prints(srv)
    assert after["sohee_clone"]["korean"] != before["sohee_clone"]["korean"] and after["ryan"] == before["ryan"]
