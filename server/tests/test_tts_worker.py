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
