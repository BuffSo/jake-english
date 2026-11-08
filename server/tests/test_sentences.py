from je_server.sentences import SentenceBuffer, split


def test_sentences_split_after_punctuation_and_space():
    b = SentenceBuffer()
    assert b.feed("잘했어요. 다") == ["잘했어요."]
    assert b.feed("음은 R이에요! 그") == ["다음은 R이에요!"]
    assert b.feed("리고") == []
    assert b.flush() == ["그리고"]
    assert b.flush() == []


def test_quoted_english_period_does_not_split():
    b = SentenceBuffer()
    assert b.feed("'I'm here.'에서 here가 좋았어요. ") == ["'I'm here.'에서 here가 좋았어요."]


def test_split_cuts_like_the_buffer():
    # a free-talk reply's parts are cut where the voice cut it while it streamed (spec free-talk-design 2, 4)
    assert split("Sounds fun! I walk there too. Was it busy?") == ["Sounds fun!", "I walk there too.", "Was it busy?"]
    assert split("") == []
