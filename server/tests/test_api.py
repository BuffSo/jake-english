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
    for path in ["/home", "/assets/ryan-front.png", "/audio/" + "a" * 64, "/roleplays/000000000000/lines/0"]:
        assert c.get(path).status_code == 401
    assert c.post("/roleplays", json={"situation": "x"}).status_code == 401


def test_home_lists_fixed_lines(client):
    j = client.get("/home").json()
    assert set(j["lines"]) == {"greeting", "ask_mode", "ask_situation", "ask_recommend"}
    assert all(len(v["audio"]) == 64 for v in j["lines"].values())
    assert j["images"] == {"front": "/assets/ryan-front.png", "listening": "/assets/ryan-listening.png"}


def test_assets_served_from_assets_dir(client, settings):
    settings.assets_dir.mkdir(parents=True)
    (settings.assets_dir / "ryan-front.png").write_bytes(b"png")
    r = client.get("/assets/ryan-front.png")
    assert r.status_code == 200 and r.content == b"png"


def test_create_roleplay_and_get_lines(client):
    rp = client.post("/roleplays", json={"situation": "길 묻기"}).json()
    assert rp["lines"][0]["speaker"] == "ryan"
    line = client.get(f"/roleplays/{rp['id']}/lines/1").json()
    assert line["three"]["words"] and len(line["audio"]) == 64
    audio = client.get(f"/audio/{line['audio']}?rate=0.8")
    assert audio.status_code == 200 and audio.headers["content-type"] == "audio/mp4"
    assert client.get(f"/roleplays/{rp['id']}/lines/0/three").json()["words"]


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
    j = client.post("/recommend").json()
    assert j["text"].endswith("싶어.") and len(j["audio"]) == 64
