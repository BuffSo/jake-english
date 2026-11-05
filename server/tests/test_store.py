import pytest

from je_server.models import Frame, Roleplay, ScriptLine
from je_server.store import Store


def rp(store, situation="길 묻기", created="2026-11-05T10:00:00"):
    return Roleplay(id=store.new_id(), created=created, situation=situation,
                    frame=Frame(title_ko="t", user_role_ko="u", ryan_role_ko="r", place_ko="p", goal_ko="g"),
                    lines=[ScriptLine(idx=0, speaker="ryan", text="Hi.")])


def test_save_and_load_round_trip(tmp_path):
    s = Store(tmp_path)
    r = rp(s)
    s.save(r)
    assert s.load(r.id) == r


def test_ids_are_12_hex():
    import re
    assert re.fullmatch(r"[0-9a-f]{12}", Store.new_id())


def test_load_rejects_bad_or_missing_ids(tmp_path):
    s = Store(tmp_path)
    for bad in ["../etc", "0" * 12, "ZZZZZZZZZZZZ", ""]:
        with pytest.raises(KeyError):
            s.load(bad)


def test_recent_situations_newest_first(tmp_path):
    s = Store(tmp_path)
    s.save(rp(s, "첫째", "2026-11-05T09:00:00"))
    s.save(rp(s, "둘째", "2026-11-05T10:00:00"))
    assert s.recent_situations() == ["둘째", "첫째"]


def test_rec_path_is_inside_the_roleplay(tmp_path):
    s = Store(tmp_path)
    r = rp(s)
    s.save(r)
    p = s.rec_path(r.id, 3, 1)
    assert p.parent.exists() and p.name == "3-1.m4a" and r.id in str(p)
