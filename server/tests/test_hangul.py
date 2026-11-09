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
    ("think", "싱크"), ("fish", "피시"), ("TV", "티비"),
])
def test_reading(word, hangul):
    assert reading(word) == hangul


def test_a_word_not_in_the_dictionary_has_no_reading():
    assert reading("qzxv") is None


def test_the_english_word_that_opens_a_korean_sentence_is_written_in_hangul():
    assert for_korean_voice("go는 지금 일에 써요.") == "고는 지금 일에 써요."
    # each Korean sentence is made on its own (`tts_worker.split_parts`), so a later sentence opens the same way
    assert for_korean_voice("어제 일이라 went를 써요. go는 지금 일에 써요.") == "어제 일이라 went를 써요. 고는 지금 일에 써요."
    assert for_korean_voice("좋아요!\ndo는 빼도 돼요.") == "좋아요!\n두는 빼도 돼요."


def test_the_whole_english_run_before_the_korean_is_written_in_hangul():
    assert for_korean_voice("go to는 장소 앞에 써요.") == "고 투는 장소 앞에 써요."
    assert for_korean_voice("I'm은 I am을 줄인 말이에요.") == "아임은 I am을 줄인 말이에요."
    assert for_korean_voice("Went 대신 go를 써요.") == "웬트 대신 go를 써요."


def test_english_inside_a_sentence_is_left_as_it_is():
    # after a Korean word the voice read them right (「그리고 go는」, 「과거형 went를」, 「stop이 step처럼」)
    text = "그리고 go는 맞지 않아요. 과거형 went를 써요. stop이 step처럼 들렸어요."
    assert for_korean_voice(text) == "그리고 go는 맞지 않아요. 과거형 went를 써요. 스탑이 step처럼 들렸어요."


def test_an_english_sentence_is_left_for_the_english_voice():
    # the voice module reads a sentence without Hangul in English
    assert for_korean_voice("I went to the park. 이렇게 말해요.") == "I went to the park. 이렇게 말해요."
    assert for_korean_voice("Have a nice day!") == "Have a nice day!"


def test_a_word_not_in_the_dictionary_stays_and_the_rest_is_read():
    assert for_korean_voice("qzxv는 없는 낱말이에요.") == "qzxv는 없는 낱말이에요."
    assert for_korean_voice("go qzxv는 없어요.") == "고 qzxv는 없어요."


def test_korean_without_english_is_unchanged():
    text = "좋아요, 잘했어요. 3번 문장을 다시 해 볼까요?"
    assert for_korean_voice(text) == text
