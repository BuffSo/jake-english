import re

import pytest

from je_server.hangul import for_korean_voice, reading

# 2026-11-09 Ryan's Korean voice read a short English word that opened a Korean sentence as another word (「go는」
# came out like 「조우는」 in every take); after a Korean word, or written in Hangul, it was read right. So the
# English words that open a Korean sentence go to the voice in Hangul.


@pytest.mark.parametrize("word, hangul", [
    ("go", "고"), ("went", "웬트"), ("do", "두"), ("get", "겟"), ("it", "잇"), ("stop", "스탑"), ("step", "스텝"),
    ("I", "아이"), ("to", "투"), ("eat", "이트"), ("the", "더"), ("am", "앰"), ("have", "해브"), ("been", "빈"),
    ("play", "플레이"), ("street", "스트리트"), ("next", "넥스트"),  # clusters
    ("quick", "퀵"), ("question", "퀘스천"), ("sweet", "스위트"), ("word", "워드"),  # w after a consonant
    ("music", "뮤직"), ("few", "퓨"), ("yesterday", "예스터데이"),  # y
    ("time", "타임"), ("OK", "오케이"), ("Jake", "제이크"), ("page", "페이지"),  # two-part vowels
    ("hello", "헐로"), ("really", "릴리"), ("always", "올웨이즈"), ("world", "월드"),  # l
    ("every", "에버리"), ("park", "파크"),  # r
    ("think", "싱크"), ("fish", "피시"), ("TV", "티비"), ("duwe", "두"),  # a w with no vowel after it
    ("singing", "싱잉"), ("singer", "싱어"), ("longer", "롱거"),  # ng before a vowel (PR #77 review: KeyError)
    ("there", "데어"), ("here", "히어"), ("sure", "슈어"), ("more", "모어"), ("car", "카"), ("star", "스타"),
])  # a final r: 어 after most vowels (PR #77 review: there came out 데, another word), none after a (car 카)
def test_reading(word, hangul):
    assert reading(word) == hangul


def test_every_dictionary_word_has_a_hangul_reading():
    # an error here would come out of `tts.audio_key` and stop the sound of the reply (PR #77 review: 「singing은」)
    from je_server import cmu
    from je_server.hangul import hangul

    bad = [w for w, prons in cmu._dict().items() if not re.fullmatch(r"[가-힣]+", hangul(prons[0]))]
    assert bad == []


def test_a_word_not_in_the_dictionary_has_no_reading():
    assert reading("qzxv") is None


def test_the_short_english_word_that_opens_a_korean_sentence_is_written_in_hangul():
    assert for_korean_voice("go는 지금 일에 써요.") == "고는 지금 일에 써요."
    # each Korean sentence is made on its own (`tts_worker.split_parts`), so a later sentence opens the same way
    assert for_korean_voice("어제 일이라 went를 써요. go는 지금 일에 써요.") == "어제 일이라 went를 써요. 고는 지금 일에 써요."
    assert for_korean_voice("좋아요!\ndo는 빼도 돼요.") == "좋아요!\n두는 빼도 돼요."
    assert for_korean_voice("  or는 둘 중 하나예요.") == "  오어는 둘 중 하나예요."
    assert for_korean_voice("OK, 다시 해 볼까요?") == "오케이, 다시 해 볼까요?"  # a comma after it (final review)
    assert for_korean_voice("I’m은 줄인 말이에요.") == "아임은 줄인 말이에요."  # a curly apostrophe


def test_the_leading_short_words_of_an_english_run_are_written_in_hangul():
    assert for_korean_voice("go to는 장소 앞에 써요.") == "고 투는 장소 앞에 써요."
    assert for_korean_voice("I'm은 I am을 줄인 말이에요.") == "아임은 I am을 줄인 말이에요."
    assert for_korean_voice("I went는 과거예요.") == "아이 went는 과거예요."  # up to the first longer word


def test_a_longer_opening_word_is_left_to_the_voice():
    # the voice read them right opening a sentence (went, stop 4/4; right, very, think, fan 3/3), and the rules
    # can read worse than the model (coffee would be 카피, which is copy) (final review)
    for text in ("went는 과거형이에요.", "stop이 step처럼 들렸어요.", "coffee가 copy처럼 들렸어요.",
                 "singing은 노래하는 거예요."):
        assert for_korean_voice(text) == text


def test_a_two_letter_abbreviation_is_read_by_its_letters():
    # 「AI가」 read as a word would be 아이가 (a child), and 「IT」 잇 (final review)
    assert for_korean_voice("AI가 답을 써요.") == "에이아이가 답을 써요."
    assert for_korean_voice("IT 회사예요.") == "아이티 회사예요."
    assert for_korean_voice("TV는 꺼 주세요.") == "티브이는 꺼 주세요."


def test_english_inside_a_sentence_is_left_as_it_is():
    # after a Korean word the voice read them right (「그리고 go는」, 「과거형 went를」, 「stop이 step처럼」)
    text = "그리고 go는 맞지 않아요. 과거형 went를 써요. 여기서 do는 빼요."
    assert for_korean_voice(text) == text


def test_an_english_sentence_is_left_for_the_english_voice():
    # the voice module reads a sentence without Hangul in English
    assert for_korean_voice("I went to the park. 이렇게 말해요.") == "I went to the park. 이렇게 말해요."
    assert for_korean_voice("Go on! 이렇게 말해요.") == "Go on! 이렇게 말해요."
    assert for_korean_voice("Have a nice day!") == "Have a nice day!"


def test_a_word_not_in_the_dictionary_stays_and_the_rest_is_read():
    assert for_korean_voice("qz는 없는 낱말이에요.") == "qz는 없는 낱말이에요."
    assert for_korean_voice("go qz는 없어요.") == "고 qz는 없어요."


def test_korean_without_english_is_unchanged():
    text = "좋아요, 잘했어요. 3번 문장을 다시 해 볼까요?"
    assert for_korean_voice(text) == text
