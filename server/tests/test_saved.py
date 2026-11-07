"""Saved sentences (spec review-practice 5, 6; ADR-0011). The fake script's lines are made up (tests/fakes.py)."""
import pytest

from je_server.engine import NotFound

pytestmark = pytest.mark.anyio


async def test_save_and_list_newest_first(engine):
    rp = await engine.create("길 묻기")
    await engine.set_saved(rp.id, 1, True)
    await engine.set_saved(rp.id, 2, True)
    items = engine.saved()
    assert [(i["idx"], i["speaker"], i["text"]) for i in items] == [
        (2, "ryan", "How do I get there?"), (1, "user", "It's right over there.")]
    assert items[0]["title_ko"] == rp.frame.title_ko and items[0]["rp_id"] == rp.id
    assert items[1]["key"] == "it's right over there"


async def test_save_twice_keeps_one(engine):
    rp = await engine.create("길 묻기")
    other = await engine.copy(rp.id)
    assert await engine.set_saved(rp.id, 1, True) == {"key": "it's right over there", "on": True}
    await engine.set_saved(rp.id, 1, True)
    await engine.set_saved(other.id, 1, True)
    assert [i["rp_id"] for i in engine.saved()] == [rp.id]


async def test_unsave_removes_by_sentence(engine):
    rp = await engine.create("길 묻기")
    other = await engine.copy(rp.id)
    await engine.set_saved(rp.id, 1, True)
    assert await engine.set_saved(other.id, 1, False) == {"key": "it's right over there", "on": False}
    assert engine.saved() == []


async def test_saved_survives_restart(engine, engine_factory):
    rp = await engine.create("길 묻기")
    await engine.set_saved(rp.id, 3, True)
    assert [i["idx"] for i in engine_factory().saved()] == [3]


async def test_saved_list_finds_moved_line(engine):
    rp = await engine.create("길 묻기")
    await engine.set_saved(rp.id, 3, True)  # "Go straight and turn left."
    moved = engine.store.load(rp.id)
    moved.lines[3].text, moved.lines[5].text = moved.lines[5].text, moved.lines[3].text
    engine.store.save(moved)
    [item] = engine.saved()
    assert item["idx"] == 5 and item["text"] == "Go straight and turn left."


async def test_saved_list_skips_lost_line(engine):
    rp = await engine.create("길 묻기")
    await engine.set_saved(rp.id, 3, True)
    lost = engine.store.load(rp.id)
    lost.lines[3].text = "Turn right at the bank."
    engine.store.save(lost)
    assert engine.saved() == []
    assert [s.key for s in engine.store.load_saved()] == ["go straight and turn left"]


async def test_save_unknown_line_is_not_found(engine):
    rp = await engine.create("길 묻기")
    with pytest.raises(NotFound):
        await engine.set_saved("000000000000", 1, True)
    with pytest.raises(NotFound):
        await engine.set_saved(rp.id, 99, True)
    assert engine.store.load_saved() == []


async def test_resave_after_line_lost(engine):
    """A saved line that no longer resolves must not block saving the sentence again (PR #27 review)."""
    rp = await engine.create("길 묻기")
    await engine.set_saved(rp.id, 3, True)  # "Go straight and turn left."
    lost = engine.store.load(rp.id)
    lost.lines[3].text = "Turn right at the bank."
    engine.store.save(lost)
    other = await engine.create("길 묻기")
    await engine.set_saved(other.id, 3, True)
    [item] = engine.saved()
    assert (item["rp_id"], item["idx"]) == (other.id, 3)
    assert len(engine.store.load_saved()) == 1


# todo 01-2: one unreadable record must not take the whole list down (`Store.all` already skips such a file)
async def test_saved_list_skips_an_unreadable_roleplay(engine):
    rp = await engine.create("길 묻기")
    other = await engine.create("카페 주문")
    await engine.set_saved(rp.id, 1, True)
    await engine.set_saved(other.id, 2, True)
    (engine.store._dir(other.id) / "roleplay.json").write_text("{ not json", encoding="utf-8")
    assert [i["rp_id"] for i in engine.saved()] == [rp.id]


async def test_saved_list_skips_an_unreadable_saved_file(engine):
    (engine.store.root / "saved.json").write_text("{ not json", encoding="utf-8")
    assert engine.saved() == []


async def test_saved_list_skips_an_unreadable_entry(engine):
    rp = await engine.create("길 묻기")
    await engine.set_saved(rp.id, 1, True)
    path = engine.store.root / "saved.json"
    path.write_text(path.read_text(encoding="utf-8").replace("[", '[{"key": 3},', 1), encoding="utf-8")
    assert [i["idx"] for i in engine.saved()] == [1]


async def test_saving_over_an_unreadable_saved_file_keeps_a_copy(engine):
    rp = await engine.create("길 묻기")
    (engine.store.root / "saved.json").write_text("{ not json", encoding="utf-8")
    await engine.set_saved(rp.id, 1, True)
    assert [i["idx"] for i in engine.saved()] == [1]
    assert (engine.store.root / "saved.broken.json").read_text(encoding="utf-8") == "{ not json"
