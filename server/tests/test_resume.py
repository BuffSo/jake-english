"""Resuming the last conversation (spec docs/superpowers/specs/2026-11-08-resume-roleplay-design.md): a skip moves the
roleplay's place, and the Mac tells the app which conversation to resume and from where."""
import pytest

from je_server.engine import NotFound

pytestmark = pytest.mark.anyio


# --- a skipped line moves the place (spec 3) ---------------------------------------------------------------------


async def test_skip_moves_pos_past_my_line(engine_with_rp):
    engine, rp_id, user_idx = engine_with_rp
    assert await engine.skip(rp_id, user_idx) == user_idx + 1
    rp = engine.load(rp_id)
    assert rp.pos == user_idx + 1 and rp.attempts == {}  # no try, no recording


async def test_skip_never_moves_pos_back(engine_with_rp):
    engine, rp_id, _ = engine_with_rp
    mine = [l.idx for l in engine.load(rp_id).lines if l.speaker == "user"]
    await engine.skip(rp_id, mine[1])
    assert await engine.skip(rp_id, mine[0]) == mine[1] + 1
    assert await engine.skip(rp_id, mine[1]) == mine[1] + 1  # the same skip twice


async def test_skip_on_ryans_line_is_not_found(engine_with_rp):
    engine, rp_id, _ = engine_with_rp
    with pytest.raises(NotFound):
        await engine.skip(rp_id, 0)  # line 0 is Ryan's in the fake script
    with pytest.raises(NotFound):
        await engine.skip(rp_id, 99)


def test_skip_route(client):
    rp = client.post("/roleplays", json={"situation": "길 묻기"}).json()
    mine = next(l["idx"] for l in rp["lines"] if l["speaker"] == "user")
    assert client.post(f"/roleplays/{rp['id']}/lines/{mine}/skip").json() == {"pos": mine + 1}
    assert client.post(f"/roleplays/{rp['id']}/lines/0/skip").status_code == 404


# --- the conversation to resume (spec 1, 2) ----------------------------------------------------------------------


async def test_resume_after_a_followed_turn(engine_with_rp, speech_bytes, fake_whisper):
    engine, rp_id, user_idx = engine_with_rp
    fake_whisper.text = engine.load(rp_id).lines[user_idx].text
    [e async for e in engine.attempt(rp_id, user_idx, speech_bytes, "turn")]
    r = engine.resume()
    assert r["roleplay"]["id"] == rp_id and r["at"] == user_idx + 1
    assert [s["idx"] for s in r["said"]] == [user_idx] and r["progress"] == {"no": 2, "total": 3}
    assert r["ended"] is False


async def test_resume_skips_an_unreadable_record(engine_with_rp):
    engine, rp_id, _ = engine_with_rp
    bad = engine.store.roleplays / ("f" * 12)
    bad.mkdir()
    (bad / "roleplay.json").write_text("{", encoding="utf-8")
    assert engine.resume()["roleplay"]["id"] == rp_id


def test_resume_route(client):
    assert client.get("/resume").json() == {"resume": None}
    rp = client.post("/roleplays", json={"situation": "길 묻기"}).json()
    r = client.get("/resume").json()["resume"]
    assert r["roleplay"]["id"] == rp["id"] and r["at"] == 0 and r["said"] == [] and r["ended"] is False
