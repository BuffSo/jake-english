from je_server.models import Syllable as S
from je_server.models import ThreeLine, Word
from je_server.threeline import check, degrade, korean_line, plain, refs, tidy


def coffee(stress_first=True, hi="카"):
    m1, m2 = ("s", "w") if stress_first else ("w", "s")
    return Word(syl=[S(en="cof", ko="카", m=m1, hi=hi if m1 == "s" else ""),
                     S(en="fee.", ko="피", m=m2, hi="피" if m2 == "s" else "")])


def line(*words, reading=""):
    return ThreeLine(words=list(words), reading=reading)


I = Word(syl=[S(en="I", ko="아이", m="n")])
LIKE = Word(syl=[S(en="like", ko="라익", m="n")])


def kinds(problems):
    return [p.kind for p in problems]


def test_good_line_has_no_problems():
    assert check("I like coffee.", line(I, LIKE, coffee(), reading="[[카-피]]")) == []


def test_stress_on_wrong_syllable():
    p = check("I like coffee.", line(I, LIKE, coffee(stress_first=False)))
    assert kinds(p) == ["stress"] and p[0].word == 2


def test_record_noun_and_verb_both_pass():
    noun = Word(syl=[S(en="re", ko="레", m="s", hi="레"), S(en="cord.", ko="커드", m="w")])
    verb = Word(syl=[S(en="re", ko="리", m="w"), S(en="cord.", ko="코드", m="s", hi="코")])
    assert check("record.", line(noun)) == []
    assert check("record.", line(verb)) == []


def test_highlight_must_be_one_hangul_in_ko():
    w = Word(syl=[S(en="ob", ko="압", m="s", hi="아브"), S(en="ject?", ko="젝트", m="w")])
    assert kinds(check("object?", line(w))) == ["hi"]
    missing = Word(syl=[S(en="ob", ko="압", m="s", hi="옵"), S(en="ject?", ko="젝트", m="w")])
    assert kinds(check("object?", line(missing))) == ["hi"]
    stray = Word(syl=[S(en="ob", ko="압", m="n", hi="압"), S(en="ject?", ko="젝트", m="w")])
    assert kinds(check("object?", line(stray))) == ["hi"]


def test_emphasis_and_unknown_words_skip_stress_check():
    namsan = Word(syl=[S(en="Nam", ko="남", m="n"), S(en="san", ko="산", m="s", hi="산")])
    did = Word(syl=[S(en="did", ko="딛", m="s", hi="딛")], emph=True)
    assert check("Namsan", line(namsan)) == []
    assert check("did", line(did)) == []


def test_syllable_count_mismatch_skips_stress_check():
    # every: CMU has 3 vowels (EH1 V ER0 IY0) and 2 (EH1 V R IY0); 4 syllables matches none
    w = Word(syl=[S(en="e", ko="에", m="n"), S(en="v", ko="브", m="n"),
                  S(en="e", ko="어", m="s", hi="어"), S(en="ry", ko="리", m="n")])
    assert check("every", line(w)) == []


def test_words_must_match_text():
    assert kinds(check("I like tea.", line(I, LIKE, coffee()))) == ["words"]


def test_words_problem_names_what_is_missing():
    # a model that runs two words into one sound dropped the small word between them; the retry must say which
    p = check("I like coffee.", line(I, coffee()))
    assert kinds(p) == ["words"] and "missing 'like' after 'i'" in p[0].detail


def test_words_problem_names_extra_and_changed_words():
    extra = check("I like coffee.", line(I, LIKE, LIKE, coffee()))[0].detail
    assert "extra 'like'" in extra
    changed = check("I like tea.", line(I, LIKE, coffee()))[0].detail
    assert "'coffee' should be 'tea'" in changed


def test_reading_ref_must_match_korean_syllables():
    p = check("I like coffee.", line(I, LIKE, coffee(), reading="[[카-페]] 말고"))
    assert kinds(p) == ["ref"]


def test_reading_ref_with_non_hangul_is_a_problem():
    assert kinds(check("I like coffee.", line(I, LIKE, coffee(), reading="[[ka-피]]"))) == ["ref"]


def test_ref_may_span_words_with_a_space():
    # the Korean line here is 「아이 라익 카피」
    assert check("I like coffee.", line(I, LIKE, coffee(), reading="[[라익 카-피]]")) == []


def test_ref_hyphens_need_not_follow_syllables():
    # the hyphens are not shown in the Korean line, so only its letters must agree
    assert check("I like coffee.", line(I, LIKE, coffee(), reading="[[카피]], [[아-이]]")) == []


def test_ref_may_point_at_one_letter_inside_a_syllable():
    assert check("I like coffee.", line(I, LIKE, coffee(), reading="[[이]]를 길게")) == []


def test_ref_letters_must_still_match():
    for bad in ("[[카 페]]", "[[아이카]]", "[[피카]]", "[[카--피]]", "[[카-피 ]]", "[[ 카피]]"):
        assert kinds(check("I like coffee.", line(I, LIKE, coffee(), reading=bad))) == ["ref"], bad


def test_refs_lists_bracket_contents():
    assert refs("앞을 세게, [[카-피]]. 뒤 [[피]]는 「약하게」") == ["카-피", "피"]


def test_degrade_removes_only_bad_marks():
    bad = line(I, LIKE, coffee(stress_first=False), reading="[[카-페]]")
    fixed = degrade("I like coffee.", bad, check("I like coffee.", bad))
    assert all(s.m != "s" for s in fixed.words[2].syl) and fixed.reading == ""
    assert fixed.words[0] == I
    assert check("I like coffee.", fixed) == []


def test_degrade_with_word_mismatch_falls_back_to_plain():
    bad = line(I, LIKE, coffee())
    fixed = degrade("I like tea.", bad, check("I like tea.", bad))
    assert fixed == plain("I like tea.")


def test_korean_line_joins_linked_words():
    cup = Word(syl=[S(en="cup", ko="커", m="n")], link=True)
    of = Word(syl=[S(en="of", ko="퍼", m="w")])
    assert korean_line(line(cup, of, coffee())) == "커퍼 카피"


def test_plain_line_passes():
    assert check("Where is it?", plain("Where is it?")) == []
    assert [w.syl[0].en for w in plain("Where is it?").words] == ["Where", "is", "it?"]


def test_tidy_puts_the_final_consonant_back():
    # the model gives the letter without its final consonant (ko 딛, hi 디): the one letter with that vowel is meant
    did = Word(syl=[S(en="did", ko="딛", m="s", hi="디")])
    spring = Word(syl=[S(en="spring.", ko="스프링", m="s", hi="리")])
    bill = Word(syl=[S(en="bill", ko="빌", m="s", hi="이")])  # the bare vowel, as the model also gave
    out = tidy(line(I, did, spring, bill, reading="[[딛]]"))
    assert out.words[1].syl[0].hi == "딛" and out.words[2].syl[0].hi == "링" and out.words[3].syl[0].hi == "빌"
    assert out.words[0] == I and out.reading == "[[딛]]"
    assert check("I did spring bill", out) == []


def test_tidy_leaves_what_it_cannot_tell():
    twice = Word(syl=[S(en="bilbil", ko="빌빌", m="s", hi="비")])  # two letters with that vowel
    other = Word(syl=[S(en="ob", ko="압", m="s", hi="옵"), S(en="ject?", ko="젝트", m="w")])  # no letter with it
    stray = Word(syl=[S(en="ob", ko="압", m="n", hi="아"), S(en="ject?", ko="젝트", m="w")])  # not a strong syllable
    # another first consonant than the bare vowel 「ㅇ」 is another letter, not one without its final consonant
    unlike = Word(syl=[S(en="stop", ko="스탑", m="s", hi="즈")])
    for w in (twice, other, stray, unlike):
        assert tidy(line(w)) == line(w)
        assert kinds(check(word_text_of(w), tidy(line(w)))) == ["hi"]


def word_text_of(w):
    return "".join(s.en for s in w.syl)
