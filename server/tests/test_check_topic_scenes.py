"""scripts/check_topic_scenes.py: the flags it prints beside the real model's suggestions and scripts (spec
korea-english-topic 5). The model's own output is read by hand; these only point at lines to read first."""
import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "check_topic_scenes", Path(__file__).resolve().parent.parent / "scripts" / "check_topic_scenes.py")
cs = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cs)


def test_known_people_are_flagged():
    # the topic's partner is someone the learner has never met
    assert cs.known_people("회사 동료에게 영어로 인사하는 상황") and cs.known_people("my coworker asks")
    assert cs.known_people("외국인 친구와 카페에서 만나는 상황") and cs.known_people("a friend from work")
    assert not cs.known_people("처음 보는 외국인과 인사하는 상황") and not cs.known_people("Nice to meet you!")


def test_abroad_is_flagged():
    assert cs.abroad("뉴욕 지하철역에서 표를 사는 상황") and cs.abroad("at an airport in Tokyo")
    assert not cs.abroad("한강공원에서 달리다 인사하는 상황") and not cs.abroad("서울의 카페에서")


def test_hard_words_are_long_or_rare():
    # easy everyday words (the user, 2026-11-08): flag long words to read, not a verdict
    assert cs.hard_words("They're called the Pensive Bodhisattvas.") == ["bodhisattvas"]
    assert cs.hard_words("Vegetables and glass noodles. You'll love it!") == []
