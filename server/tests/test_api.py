import json

from je_server.app import MAX_UPLOAD
from je_server.phrases import PHRASES, TALK_OPENERS, TALK_PHRASES


def test_unknown_roleplay_is_404(client):
    r = client.get("/roleplays/000000000000/lines/0")
    assert r.status_code == 404 and r.json()["code"] == "not_found"


def test_bad_ids_rejected(client):
    assert client.get("/roleplays/..%2Fx/lines/0").status_code in (404, 422)
    assert client.get("/audio/" + "g" * 64).status_code in (404, 422)
    assert client.get("/assets/secret.png").status_code == 404
    assert client.get("/audio/" + "a" * 64 + "?rate=2.0").status_code == 422


def test_routes_need_token(settings, engine, fake_voice, fake_whisper):
    from fastapi.testclient import TestClient

    from je_server.app import Services, create_app

    c = TestClient(create_app(settings, Services(engine=engine, voice=fake_voice, whisper=fake_whisper)))
    for path in ["/home", "/assets/ryan-front.png", "/audio/" + "a" * 64, "/roleplays/000000000000/lines/0",
                 "/roleplays/000000000000/lines/0/ko", "/roleplays/000000000000/lines/0/ko/audio"]:
        assert c.get(path).status_code == 401
    assert c.post("/roleplays", json={"situation": "x"}).status_code == 401
    for path in ["/talks", "/talks/000000000000/turns", "/talks/000000000000/end"]:
        assert c.post(path).status_code == 401


def test_home_lists_fixed_lines(client):
    j = client.get("/home").json()
    assert set(j["lines"]) == {"greeting", "ask_mode", "ask_again", "ask_situation", "ask_recommend", "ask_topic",
                               "ask_how", "ask_pick", "ask_describe"}
    assert all(len(v["audio"]) == 64 for v in j["lines"].values())
    assert j["images"] == {
        "front": "/assets/ryan-front.png",
        "listening": "/assets/ryan-listening.png",
        "jake": "/assets/jake-front.png",
        "thinking": {
            "jake": ["/assets/jake-thinking-1.png", "/assets/jake-thinking-2.png"],
            "ryan": ["/assets/ryan-thinking-1.png", "/assets/ryan-thinking-2.png"],
            "sohee": ["/assets/sohee-thinking-1.png", "/assets/sohee-thinking-2.png"],
        },
        "sohee": {"face": "/assets/sohee-face.png", "whisper": "/assets/sohee-whisper-face.png"},
    }


def test_thinking_faces_served(client, settings):
    settings.assets_dir.mkdir(parents=True)
    names = ["jake-thinking-1.png", "jake-thinking-2.png", "ryan-thinking-1.png", "ryan-thinking-2.png"]
    for n in names + ["ryan-face-v3.png"]:
        (settings.assets_dir / n).write_bytes(b"png")
    for n in names:
        r = client.get(f"/assets/{n}")
        assert r.status_code == 200 and r.content == b"png"
    assert client.get("/assets/ryan-face-v3.png").status_code == 404  # on disk but not listed


def test_home_lists_sohees_pictures(client):
    # Sohee's faces for the free talk (spec free-talk 2, 3): thinking pair plus the face and whisper face
    images = client.get("/home").json()["images"]
    assert images["thinking"]["sohee"] == ["/assets/sohee-thinking-1.png", "/assets/sohee-thinking-2.png"]
    assert images["sohee"] == {"face": "/assets/sohee-face.png", "whisper": "/assets/sohee-whisper-face.png"}


def test_sohee_pictures_are_served(client, settings):
    # made-up bytes in the test assets folder; the real pictures never go into the repo
    settings.assets_dir.mkdir(parents=True)
    names = ["sohee-thinking-1.png", "sohee-thinking-2.png", "sohee-face.png", "sohee-whisper-face.png"]
    for n in names + ["sohee-front.png"]:
        (settings.assets_dir / n).write_bytes(b"png")
    for n in names:
        r = client.get(f"/assets/{n}")
        assert r.status_code == 200 and r.content == b"png"
    assert client.get("/assets/sohee-front.png").status_code == 404  # on disk but not listed


def test_jake_front_served(client, settings):
    # Jake's own face while he waits for 「이걸로 할게요」 or 「다른 걸로요」 (2026-11-06 user, after the phone test)
    settings.assets_dir.mkdir(parents=True)
    (settings.assets_dir / "jake-front.png").write_bytes(b"png")
    r = client.get("/assets/jake-front.png")
    assert r.status_code == 200 and r.content == b"png"


def test_assets_served_from_assets_dir(client, settings):
    settings.assets_dir.mkdir(parents=True)
    (settings.assets_dir / "ryan-front.png").write_bytes(b"png")
    r = client.get("/assets/ryan-front.png")
    assert r.status_code == 200 and r.content == b"png"


def test_create_roleplay_and_get_lines(client):
    rp = client.post("/roleplays", json={"situation": "길 묻기"}).json()
    assert rp["lines"][0]["speaker"] == "ryan"
    line = client.get(f"/roleplays/{rp['id']}/lines/1").json()
    assert len(line["audio"]) == 64  # the learner's notes may still be on their way (spec dont-wait-for-line-notes)
    assert client.get(f"/roleplays/{rp['id']}/lines/1/three").json()["words"]
    assert line["progress"] == {"no": 1, "total": 3}
    audio = client.get(f"/audio/{line['audio']}?rate=0.8")
    assert audio.status_code == 200 and audio.headers["content-type"] == "audio/mp4"
    assert client.get(f"/roleplays/{rp['id']}/lines/0/three").json()["words"]


def test_learner_line_comes_while_claude_is_down(client, fake_claude):
    # spec dont-wait-for-line-notes 1: notes that cannot be made no longer stop the line; only the notes say so
    from je_server.claude import ClaudeUnavailable

    async def down(text, context):
        raise ClaudeUnavailable("fake")

    fake_claude.annotate = down  # before the roleplay, so its notes fail in the background too
    rp = client.post("/roleplays", json={"situation": "길 묻기"}).json()
    line = client.get(f"/roleplays/{rp['id']}/lines/1")
    assert line.status_code == 200 and len(line.json()["audio"]) == 64
    three = client.get(f"/roleplays/{rp['id']}/lines/1/three")
    assert three.status_code == 503 and three.json()["code"] == "claude_unavailable"


def test_create_roleplay_claude_down_is_503(client, fake_claude):
    fake_claude.fail_next = True
    r = client.post("/roleplays", json={"situation": "길 묻기"})
    assert r.status_code == 503 and r.json()["code"] == "claude_unavailable" and len(r.json()["say"]["audio"]) == 64


def test_situation_length_limited(client):
    assert client.post("/roleplays", json={"situation": "가" * 301}).status_code == 422
    assert client.post("/roleplays", json={"situation": ""}).status_code == 422


def test_upload_size_limited(client):
    r = client.post("/transcribe", content=b"0" * (5 * 1024 * 1024 + 1))
    assert r.status_code == 413 and r.json()["code"] == "too_long"


def test_recommend_route(client):
    from je_server.claude import JAKE_ENDINGS

    j = client.post("/recommend").json()
    assert j["text"].endswith(tuple(e for e, _ in JAKE_ENDINGS)) and len(j["audio"]) == 64


def test_recommend_route_takes_turned_down(client, fake_claude):
    skip = ["카페에서 주문하는 상황으로 연습해 보면 어때요?"]
    assert client.post("/recommend", json={"skip": skip}).status_code == 200
    assert [a for n, a in fake_claude.calls if n == "recommend"][-1] == ([], skip, "other")
    assert client.post("/recommend", json={}).status_code == 200  # what the app sent before 2026-11-06
    # the list and each item are limited (REVIEW.md 「맥 서버 보안」: no upload without a size limit)
    for bad in (["x"] * 11, ["x" * 301], "x"):
        r = client.post("/recommend", json={"skip": bad})
        assert r.status_code == 422 and r.json()["code"] == "bad_request"


def _app(settings, engine, fake_voice, fake_whisper):
    from je_server.app import Services, create_app

    return create_app(settings, Services(engine=engine, voice=fake_voice, whisper=fake_whisper))


def test_unauthenticated_body_is_not_read(settings, engine, fake_voice, fake_whisper):
    # PR #12 review: FastAPI read and parsed the /roleplays JSON body before the router's token check
    from fastapi.testclient import TestClient

    sent = []

    def body():
        for i in range(4):
            sent.append(i)
            yield b" " * 1024

    r = TestClient(_app(settings, engine, fake_voice, fake_whisper)).post(
        "/roleplays", content=body(), headers={"Content-Type": "application/json"})
    assert r.status_code == 401 and len(sent) <= 1


def test_declared_body_over_limit_is_rejected_before_reading(client):
    r = client.post("/roleplays", content=b"{}", headers={"Content-Type": "application/json",
                                                           "Content-Length": str(5 * 1024 * 1024 + 1)})
    assert r.status_code == 413 and r.json()["code"] == "too_long"


def test_bad_content_length_is_400(client):
    r = client.post("/roleplays", content=b"{}", headers={"Content-Type": "application/json",
                                                           "Content-Length": "abc"})
    assert r.status_code == 400


def test_attempt_route_modes(client, speech_bytes):
    rp = client.post("/roleplays", json={"situation": "길 묻기"}).json()
    client.get(f"/roleplays/{rp['id']}/lines/0")
    ok = client.post(f"/roleplays/{rp['id']}/lines/0/attempts?mode=shadow", content=speech_bytes)
    assert ok.status_code == 200 and ok.text.strip().splitlines()
    assert client.post(f"/roleplays/{rp['id']}/lines/1/attempts?mode=shadow", content=speech_bytes).status_code == 404
    assert client.post(f"/roleplays/{rp['id']}/lines/1/attempts?mode=bogus", content=speech_bytes).status_code == 422


def test_recording_is_served_after_an_attempt(client, speech_bytes):
    rp = client.post("/roleplays", json={"situation": "길 묻기"}).json()
    client.get(f"/roleplays/{rp['id']}/lines/1")
    client.post(f"/roleplays/{rp['id']}/lines/1/attempts?mode=turn", content=speech_bytes)
    r = client.get(f"/roleplays/{rp['id']}/lines/1/attempts/1/recording")
    # the play copy, moov first (spec play-button-feedback 4); a whole tone keeps its length
    assert r.status_code == 200 and r.headers["content-type"] == "audio/mp4"
    assert r.content != speech_bytes and r.content[4:8] == b"ftyp"
    assert r.content.index(b"moov") < r.content.index(b"mdat")


def test_recording_missing_is_404_and_creates_nothing(client, settings):
    rp = client.post("/roleplays", json={"situation": "길 묻기"}).json()
    assert client.get(f"/roleplays/{rp['id']}/lines/1/attempts/9/recording").status_code == 404
    assert client.get("/roleplays/000000000000/lines/1/attempts/1/recording").status_code == 404
    assert client.get(f"/roleplays/{rp['id']}/lines/1/attempts/0/recording").status_code == 422
    assert client.get("/roleplays/..%2Fx/lines/1/attempts/1/recording").status_code in (404, 422)
    assert not (settings.data_dir / "roleplays" / rp["id"] / "rec").exists()


def test_recording_needs_token(settings, engine, fake_voice, fake_whisper):
    from fastapi.testclient import TestClient

    from je_server.app import Services, create_app

    c = TestClient(create_app(settings, Services(engine=engine, voice=fake_voice, whisper=fake_whisper)))
    assert c.get("/roleplays/000000000000/lines/1/attempts/1/recording").status_code == 401


def test_audio_without_services_is_not_ready(settings, auth):
    from fastapi.testclient import TestClient

    from je_server.app import create_app

    c = TestClient(create_app(settings, None), headers=auth)
    r = c.get("/audio/" + "a" * 64)
    assert r.status_code == 503 and r.json()["code"] == "not_ready"


def test_copy_route(client):
    rp = client.post("/roleplays", json={"situation": "길 묻기"}).json()
    new = client.post(f"/roleplays/{rp['id']}/copy").json()
    assert new["id"] != rp["id"] and [l["text"] for l in new["lines"]] == [l["text"] for l in rp["lines"]]
    assert client.post("/roleplays/000000000000/copy").status_code == 404


def test_sohee_interpretation_text_then_sound(client):
    rp = client.post("/roleplays", json={"situation": "길 묻기"}).json()
    base = f"/roleplays/{rp['id']}/lines/0"
    assert client.get(f"{base}/ko/audio").status_code == 404  # no Korean yet
    r = client.get(f"{base}/ko")
    assert r.status_code == 200 and r.json() == {"text": "소희: " + rp["lines"][0]["text"]}
    audio = client.get(f"{base}/ko/audio").json()["audio"]
    assert len(audio) == 64 and client.get(f"/audio/{audio}").status_code == 200
    assert client.get(f"/roleplays/{rp['id']}/lines/99/ko").status_code == 404


def test_sohee_interpretation_failures(client, fake_claude, fake_voice):
    rp = client.post("/roleplays", json={"situation": "길 묻기"}).json()
    fake_claude.fail_next = True
    r = client.get(f"/roleplays/{rp['id']}/lines/1/ko")
    assert r.status_code == 503 and r.json()["code"] == "claude_unavailable"
    fake_voice.fail_text = client.get(f"/roleplays/{rp['id']}/lines/1/ko").json()["text"]
    r = client.get(f"/roleplays/{rp['id']}/lines/1/ko/audio")
    assert r.status_code == 503 and r.json()["code"] == "voice_unavailable"


def test_past_and_latest_routes(client, speech_bytes):
    rp = client.post("/roleplays", json={"situation": "길 묻기"}).json()
    assert client.get("/past").json() == {"items": []}
    client.get(f"/roleplays/{rp['id']}/lines/1")
    client.post(f"/roleplays/{rp['id']}/lines/1/attempts", content=speech_bytes,
                headers={"Content-Type": "audio/mp4"}).read()
    [item] = client.get("/past").json()["items"]
    assert item["group"] == rp["id"] and set(item) == {"group", "title_ko", "first", "latest"}
    j = client.get(f"/groups/{rp['id']}/latest").json()
    assert j["roleplay"]["id"] == rp["id"] and len(j["summary"]["lines"]) == 7


def test_get_roleplay_route(client):
    rp = client.post("/roleplays", json={"situation": "길 묻기"}).json()
    j = client.get(f"/roleplays/{rp['id']}").json()
    assert j["id"] == rp["id"] and j["origin"] is None and len(j["lines"]) == 7


def test_latest_unknown_or_unspoken_is_404(client):
    rp = client.post("/roleplays", json={"situation": "길 묻기"}).json()
    assert client.get(f"/groups/{rp['id']}/latest").status_code == 404
    assert client.get("/groups/000000000000/latest").status_code == 404
    assert client.get("/roleplays/000000000000").status_code == 404


def test_bad_group_id_rejected(client):
    assert client.get("/groups/..%2Fx/latest").status_code in (404, 422)
    assert client.get("/groups/ABCDEFABCDEF/latest").status_code in (404, 422)


def test_new_routes_need_token(settings, engine, fake_voice, fake_whisper):
    from fastapi.testclient import TestClient

    from je_server.app import Services, create_app

    c = TestClient(create_app(settings, Services(engine=engine, voice=fake_voice, whisper=fake_whisper)))
    for path in ["/past", "/groups/000000000000/latest", "/roleplays/000000000000"]:
        assert c.get(path).status_code == 401


def test_saved_routes(client):
    rp = client.post("/roleplays", json={"situation": "길 묻기"}).json()
    r = client.post("/saved", json={"rp_id": rp["id"], "idx": 1, "on": True})
    assert r.status_code == 200 and r.json()["on"] is True
    [item] = client.get("/saved").json()["items"]
    assert set(item) == {"key", "rp_id", "idx", "speaker", "text", "title_ko", "at"}
    client.post("/saved", json={"rp_id": rp["id"], "idx": 1, "on": False})
    assert client.get("/saved").json() == {"items": []}
    assert client.post("/saved", json={"rp_id": "000000000000", "idx": 1, "on": True}).status_code == 404


def test_saved_bad_body_rejected(client):
    for body in [{"rp_id": "../x", "idx": 1, "on": True}, {"rp_id": "000000000000", "idx": -1, "on": True},
                 {"rp_id": "000000000000", "idx": 1}]:
        assert client.post("/saved", json=body).status_code == 422


def test_saved_routes_need_token(settings, engine, fake_voice, fake_whisper):
    from fastapi.testclient import TestClient

    from je_server.app import Services, create_app

    c = TestClient(create_app(settings, Services(engine=engine, voice=fake_voice, whisper=fake_whisper)))
    assert c.get("/saved").status_code == 401
    assert c.post("/saved", json={"rp_id": "000000000000", "idx": 1, "on": True}).status_code == 401


# --- situation topics (spec situation-topics) --------------------------------------------------------------------

def test_home_lists_topics(client):
    topics = client.get("/home").json()["topics"]
    assert [t["id"] for t in topics] == ["tourist", "usa", "other"]
    # every line of the first topic's list, ids only (its count grew from 3 to 6 on 2026-11-08)
    from je_server.topics import get

    assert [p["id"] for p in topics[0]["picks"]] == [p.id for p in get("tourist").picks]
    assert all(set(p) == {"id", "title_ko"} for p in topics[0]["picks"])


def test_create_from_a_pick(client, fake_claude):
    # spec fixed-list-scripts 2: the repository's script, no Claude call for it; a second pick is the next run
    from je_server.topics import pick

    rp = client.post("/roleplays", json={"topic": "usa", "pick": "u-hotel-checkin"}).json()
    assert (rp["topic"], rp["pick"], rp["origin"]) == ("usa", "u-hotel-checkin", None)
    assert rp["frame"]["title_ko"] == "뉴욕 호텔 체크인"
    assert [(l["speaker"], l["text"]) for l in rp["lines"]] == list(pick("usa", "u-hotel-checkin").script)
    assert not any(n == "make_script" for n, _ in fake_claude.calls)
    again = client.post("/roleplays", json={"topic": "usa", "pick": "u-hotel-checkin"}).json()
    assert again["origin"] == rp["id"]


def test_create_without_topic_is_other(client):
    # what the app sent before topics (2026-11-07)
    assert client.post("/roleplays", json={"situation": "길 묻기"}).json()["topic"] == "other"


def test_create_rejects_bad_topic_or_pick(client, fake_claude):
    for body in ({"topic": "nope", "situation": "x"}, {"topic": "usa", "pick": "t-tmoney"},
                 {"topic": "usa", "pick": "u-none"}, {"topic": "usa"},
                 {"topic": "usa", "situation": "x", "pick": "u-hotel-checkin"}, {"topic": "usa", "pick": "u" * 41}):
        r = client.post("/roleplays", json=body)
        assert r.status_code == 422 and r.json()["code"] == "bad_request", body
    assert not [c for c in fake_claude.calls if c[0] == "make_script"]


def test_recommend_route_takes_the_topic(client, fake_claude):
    assert client.post("/recommend", json={"skip": [], "topic": "tourist"}).status_code == 200
    assert [a for n, a in fake_claude.calls if n == "recommend"][-1] == ([], [], "tourist")
    r = client.post("/recommend", json={"topic": "nope"})
    assert r.status_code == 422 and r.json()["code"] == "bad_request"


def test_home_without_asking_neither_gives_nor_uses_the_tip(client):
    # spec ryan-shadowing-tip 4: a card's `curl /home` must not use up the day's line
    from je_server.phrases import TIPS

    assert "tip" not in client.get("/home").json()
    assert client.get("/home", params={"tip": 1}).json()["tip"]["text"] == TIPS[0]


def test_home_gives_the_tip_once_when_asked(client):
    from je_server.phrases import TIPS

    first = client.get("/home", params={"tip": 1}).json()
    assert first["tip"]["text"] == TIPS[0] and len(first["tip"]["audio"]) == 64
    assert "tip" not in client.get("/home", params={"tip": 1}).json()
    assert "tip" not in first["lines"]


def test_home_still_answers_when_the_tip_file_cannot_be_read(client, tmp_path):
    # final review: the first screen is the way into the app; a tip.json the Mac cannot read or write (here a
    # folder in its place, like a full or read-only disk) must not turn /home into a 500
    (tmp_path / "data" / "tip.json").mkdir()
    r = client.get("/home", params={"tip": 1})
    assert r.status_code == 200 and "tip" not in r.json() and "greeting" in r.json()["lines"]


# --- free talk routes (spec free-talk-design 2, 6, 7) ------------------------------------------------------------

def talk_events(r) -> list[dict]:
    return [json.loads(l) for l in r.text.splitlines() if l]


def fix_item(idx: int) -> dict:
    # `said` is what the fake whisper hears for turn `idx`; the fix keeps its words (fixes.check)
    return {"idx": idx, "said": "I go to the park yesterday.", "fixed": "I went to the park yesterday.",
            "why_ko": "지난 일이라 go를 went로 바꿔요.", "sound": {"heard": "", "meant": "", "say_ko": ""}}


def talked(client, fake_whisper, speech_bytes) -> str:
    fake_whisper.text = "I go to the park yesterday."
    rp = client.post("/talks").json()
    client.post(f"/talks/{rp['id']}/turns", content=speech_bytes)
    return rp["id"]


def test_talk_routes_need_token(settings, engine, fake_voice, fake_whisper):
    from fastapi.testclient import TestClient

    from je_server.app import Services, create_app

    c = TestClient(create_app(settings, Services(engine=engine, voice=fake_voice, whisper=fake_whisper)))
    for path in ["/talks", "/talks/000000000000/turns", "/talks/000000000000/end"]:
        assert c.post(path).status_code == 401


def test_create_talk_route(client):
    rp = client.post("/talks").json()
    assert rp["kind"] == "talk" and rp["lines"][0]["parts"][0]["text"] == TALK_OPENERS[0]


def test_turn_route_streams_ndjson(client, speech_bytes):
    rp = client.post("/talks").json()
    r = client.post(f"/talks/{rp['id']}/turns", content=speech_bytes)
    assert r.status_code == 200 and r.headers["content-type"].startswith("application/x-ndjson")
    ev = talk_events(r)
    assert ev[0]["type"] == "heard" and ev[-1]["type"] == "done" and "reply" in [e["type"] for e in ev]


def test_turn_route_refuses_a_big_upload(client):
    rp = client.post("/talks").json()
    r = client.post(f"/talks/{rp['id']}/turns", content=b"x" * (MAX_UPLOAD + 1))
    assert r.status_code == 413


def test_turn_route_on_unknown_or_roleplay_is_404(client, speech_bytes):
    assert client.post("/talks/000000000000/turns", content=speech_bytes).status_code == 404
    roleplay = client.post("/roleplays", json={"situation": "길 묻기"}).json()
    assert client.post(f"/talks/{roleplay['id']}/turns", content=speech_bytes).status_code == 404
    assert client.post(f"/talks/{roleplay['id']}/end").status_code == 404
    assert client.post("/talks/..%2Fx/turns", content=speech_bytes).status_code in (404, 422)


def test_turn_after_end_is_409(client, fake_claude, fake_whisper, speech_bytes):
    rp_id = talked(client, fake_whisper, speech_bytes)
    fake_claude.fix_items = [fix_item(1)]
    assert client.post(f"/talks/{rp_id}/end").status_code == 200
    r = client.post(f"/talks/{rp_id}/turns", content=speech_bytes)
    assert r.status_code == 409 and r.json()["code"] == "ended"


def test_heard_must_be_a_small_count(client, speech_bytes):
    rp_id = client.post("/talks").json()["id"]
    for heard in (-1, 51):
        assert client.post(f"/talks/{rp_id}/turns?heard={heard}", content=speech_bytes).status_code == 422
        assert client.post(f"/talks/{rp_id}/end?heard={heard}").status_code == 422


def test_a_whisper_failure_in_a_turn_is_an_error_event(client, fake_whisper, speech_bytes):
    rp_id = client.post("/talks").json()["id"]
    fake_whisper.fail_lang = "en"
    r = client.post(f"/talks/{rp_id}/turns", content=speech_bytes)
    assert r.status_code == 200
    [ev] = talk_events(r)
    assert ev["type"] == "error" and ev["code"] == "no_speech" and ev["say"]["text"] == TALK_PHRASES["no_speech"]
    fake_whisper.fail_lang = None
    assert talk_events(client.post(f"/talks/{rp_id}/turns", content=speech_bytes))[-1]["type"] == "done"  # not stuck


def test_end_route_returns_items(client, fake_claude, fake_whisper, speech_bytes):
    rp_id = talked(client, fake_whisper, speech_bytes)
    fake_claude.fix_items = [fix_item(1)]
    j = client.post(f"/talks/{rp_id}/end").json()
    assert j["items"][0]["line"]["kind"] == "fix" and j["items"][0]["rec"] == {"rp_id": rp_id, "idx": 1, "n": 1}
    assert j["say"] is None


def test_end_route_when_claude_is_down_is_503(client, fake_claude, fake_whisper, speech_bytes):
    rp_id = talked(client, fake_whisper, speech_bytes)
    fake_claude.fail_next = True
    r = client.post(f"/talks/{rp_id}/end")
    assert r.status_code == 503 and r.json()["code"] == "claude_unavailable"
    assert r.json()["say"]["text"] == PHRASES["claude_down"]


def test_a_fix_line_is_practised_on_the_attempt_route(client, fake_claude, fake_whisper, speech_bytes):
    rp_id = talked(client, fake_whisper, speech_bytes)
    fake_claude.fix_items = [fix_item(1)]
    fix_idx = client.post(f"/talks/{rp_id}/end").json()["items"][0]["line"]["idx"]
    r = client.post(f"/roleplays/{rp_id}/lines/{fix_idx}/attempts?mode=practice", content=speech_bytes)
    assert talk_events(r)[0]["type"] == "heard"
    rp = client.get(f"/roleplays/{rp_id}").json()
    assert [a["mode"] for a in rp["attempts"][str(fix_idx)]] == ["practice"]


def test_a_saved_fix_is_listed_as_free_talk(client, fake_claude, fake_whisper, speech_bytes):
    rp_id = talked(client, fake_whisper, speech_bytes)
    fake_claude.fix_items = [fix_item(1)]
    fix_idx = client.post(f"/talks/{rp_id}/end").json()["items"][0]["line"]["idx"]
    assert client.post("/saved", json={"rp_id": rp_id, "idx": fix_idx, "on": True}).status_code == 200
    [item] = client.get("/saved").json()["items"]
    assert item["title_ko"] == "자유 대화" and item["speaker"] == "user" and item["idx"] == fix_idx


# --- Sohee chance routes (spec free-talk-design 9) -----------------------------------------------------------------

def hint_base(client, speech_bytes) -> str:
    """The hint routes of Ryan's reply (line 2) after my first turn."""
    rp = client.post("/talks").json()
    client.post(f"/talks/{rp['id']}/turns", content=speech_bytes)
    return f"/talks/{rp['id']}/lines/2/hint"


def test_hint_answer_leaves_out_the_full_sentence(client, fake_claude, speech_bytes):
    base = hint_base(client, speech_bytes)
    r = client.post(base)
    h = fake_claude.hint_value
    assert r.status_code == 200 and r.json() == {"meaning_ko": h.meaning_ko, "starters": h.starters}
    assert h.full not in r.text
    assert client.post(base).json() == r.json() and len(fake_claude.hint_calls) == 1


def test_hint_routes_give_sohees_sound_the_full_sentence_and_ryans_sounds(client, fake_claude, fake_voice,
                                                                          speech_bytes):
    from je_server.phrases import SOHEE_PHRASES

    base = hint_base(client, speech_bytes)
    client.post(base)
    h = fake_claude.hint_value
    audio = client.get(f"{base}/audio").json()["audio"]
    assert audio == fake_voice.key("sohee", "korean", f"{h.meaning_ko} {SOHEE_PHRASES['hint_start']}")
    assert client.get(f"/audio/{audio}").status_code == 200
    assert client.get(f"{base}/sounds/0").json() == {"audio": fake_voice.key("ryan", "english", h.starters[0])}
    full = client.post(f"{base}/full").json()
    phrase = SOHEE_PHRASES["hint_full"]
    assert full == {"text": h.full, "say": {"text": phrase, "audio": fake_voice.key("sohee", "korean", phrase)}}
    n = len(h.starters)
    assert client.get(f"{base}/sounds/{n}").json() == {"audio": fake_voice.key("ryan", "english", h.full)}
    three = client.get(f"{base}/three").json()
    assert set(three) == {"words", "reading"}


def test_hint_steps_out_of_order_are_409(client, fake_claude, speech_bytes):
    base = hint_base(client, speech_bytes)
    for r in (client.post(f"{base}/full"), client.get(f"{base}/audio"), client.get(f"{base}/sounds/0"),
              client.get(f"{base}/three")):
        assert r.status_code == 409 and r.json() == {"code": "no_hint", "say": None}
    client.post(base)
    n = len(fake_claude.hint_value.starters)
    for r in (client.get(f"{base}/sounds/{n}"), client.get(f"{base}/three")):  # before 「전체 문장 보기」
        assert r.status_code == 409 and r.json()["code"] == "no_hint"


def test_hint_on_a_wrong_line_or_a_roleplay_is_404(client, fake_claude, speech_bytes):
    base = hint_base(client, speech_bytes)
    rp_id = base.split("/")[2]
    assert client.post(f"/talks/{rp_id}/lines/1/hint").status_code == 404  # my turn
    assert client.post(f"/talks/{rp_id}/lines/9/hint").status_code == 404
    assert client.post("/talks/000000000000/lines/0/hint").status_code == 404
    roleplay = client.post("/roleplays", json={"situation": "길 묻기"}).json()
    assert client.post(f"/talks/{roleplay['id']}/lines/0/hint").status_code == 404
    client.post(base)
    client.post(f"{base}/full")
    n = len(fake_claude.hint_value.starters)
    assert n < 3 and client.get(f"{base}/sounds/{n + 1}").status_code == 404
    assert fake_claude.hint_calls and len(fake_claude.hint_calls) == 1


def test_hint_paths_are_checked(client, speech_bytes):
    base = hint_base(client, speech_bytes)
    rp_id = base.split("/")[2]
    assert client.post(f"/talks/{rp_id}/lines/-1/hint").status_code == 422
    assert client.get(f"{base}/sounds/4").status_code == 422
    assert client.get(f"{base}/sounds/-1").status_code == 422
    assert client.post("/talks/..%2Fx/lines/0/hint").status_code in (404, 422)


def test_hint_when_claude_is_down_is_503(client, fake_claude, speech_bytes):
    base = hint_base(client, speech_bytes)
    fake_claude.fail_next = True
    r = client.post(base)
    assert r.status_code == 503 and r.json()["code"] == "claude_unavailable"
    assert r.json()["say"]["text"] == PHRASES["claude_down"]


def test_hint_sound_failure_is_503(client, fake_claude, fake_voice, speech_bytes):
    from je_server.phrases import SOHEE_PHRASES

    base = hint_base(client, speech_bytes)
    client.post(base)
    h = fake_claude.hint_value
    fake_voice.fail_text = f"{h.meaning_ko} {SOHEE_PHRASES['hint_start']}"
    r = client.get(f"{base}/audio")
    assert r.status_code == 503 and r.json()["code"] == "voice_unavailable"
    fake_voice.fail_text = h.starters[0]
    assert client.get(f"{base}/sounds/0").status_code == 503


def test_hint_routes_need_token(settings, engine, fake_voice, fake_whisper):
    from fastapi.testclient import TestClient

    from je_server.app import Services, create_app

    c = TestClient(create_app(settings, Services(engine=engine, voice=fake_voice, whisper=fake_whisper)))
    base = "/talks/000000000000/lines/0/hint"
    assert c.post(base).status_code == 401 and c.post(f"{base}/full").status_code == 401
    for path in (f"{base}/audio", f"{base}/sounds/0", f"{base}/three"):
        assert c.get(path).status_code == 401


def test_end_route_counts_sohee_chances(client, fake_claude, speech_bytes):
    base = hint_base(client, speech_bytes)
    client.post(base)
    client.post(f"{base}/full")
    j = client.post(f"/talks/{base.split('/')[2]}/end").json()
    assert j["sohee"] == 2 and j["items"] == []
