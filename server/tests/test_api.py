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


def test_home_lists_fixed_lines(client):
    j = client.get("/home").json()
    assert set(j["lines"]) == {"greeting", "ask_mode", "ask_situation", "ask_recommend"}
    assert all(len(v["audio"]) == 64 for v in j["lines"].values())
    assert j["images"] == {
        "front": "/assets/ryan-front.png",
        "listening": "/assets/ryan-listening.png",
        "jake": "/assets/jake-front.png",
        "thinking": {
            "jake": ["/assets/jake-thinking-1.png", "/assets/jake-thinking-2.png"],
            "ryan": ["/assets/ryan-thinking-1.png", "/assets/ryan-thinking-2.png"],
        },
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
    assert line["three"]["words"] and len(line["audio"]) == 64
    assert line["progress"] == {"no": 1, "total": 3}
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
    assert j["text"].endswith("어때요?") and len(j["audio"]) == 64


def test_recommend_route_takes_turned_down(client, fake_claude):
    skip = ["카페에서 주문하는 상황으로 연습해 보면 어때요?"]
    assert client.post("/recommend", json={"skip": skip}).status_code == 200
    assert [a for n, a in fake_claude.calls if n == "recommend"][-1] == ([], skip)
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
    assert r.status_code == 200 and r.headers["content-type"] == "audio/mp4" and r.content == speech_bytes


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
