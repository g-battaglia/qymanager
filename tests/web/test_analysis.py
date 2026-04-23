from fastapi.testclient import TestClient

from web.backend.app import create_app


def test_resolve_voice_piano():
    client = TestClient(create_app())
    r = client.post("/api/resolve-voice", json={
        "bank_msb": 0, "bank_lsb": 0, "program": 0, "channel": 1,
    })
    assert r.status_code == 200
    data = r.json()
    assert data["name"] == "Acoustic Grand Piano"
    assert data["category"] == "Piano"
    assert data["is_drum"] is False


def test_resolve_voice_drum():
    client = TestClient(create_app())
    r = client.post("/api/resolve-voice", json={
        "bank_msb": 127, "bank_lsb": 0, "program": 0, "channel": 10,
    })
    assert r.status_code == 200
    data = r.json()
    assert data["name"] == "Standard Kit"
    assert data["is_drum"] is True


def test_resolve_voice_sfx():
    client = TestClient(create_app())
    r = client.post("/api/resolve-voice", json={
        "bank_msb": 64, "bank_lsb": 0, "program": 0, "channel": 1,
    })
    assert r.status_code == 200
    data = r.json()
    assert data["is_sfx"] is True


def test_phrases_q7p():
    client = TestClient(create_app())
    with open("tests/fixtures/T01.Q7P", "rb") as f:
        r = client.post("/api/devices", files={"file": ("T01.Q7P", f)})
    did = r.json()["id"]

    r = client.get(f"/api/devices/{did}/phrases")
    assert r.status_code == 200
    data = r.json()
    assert data["source"] == "q7p"
    assert len(data["phrases"]) >= 1
    phrase = data["phrases"][0]
    assert phrase["note_count"] > 0
    assert len(phrase["events"]) > 0
    assert phrase["events"][0]["note_name"] is not None


def test_phrases_syx():
    client = TestClient(create_app())
    with open("tests/fixtures/QY70_SGT.syx", "rb") as f:
        r = client.post("/api/devices", files={"file": ("QY70_SGT.syx", f)})
    did = r.json()["id"]

    r = client.get(f"/api/devices/{did}/phrases")
    assert r.status_code == 200
    data = r.json()
    assert data["source"] == "syx"
    assert data["note"] is not None


def test_phrases_not_found():
    client = TestClient(create_app())
    r = client.get("/api/devices/nonexistent/phrases")
    assert r.status_code == 404


def test_syx_analysis_available_for_syx_upload():
    client = TestClient(create_app())
    with open("tests/fixtures/QY70_SGT.syx", "rb") as f:
        up = client.post("/api/devices", files={"file": ("QY70_SGT.syx", f)})
    assert up.status_code == 200
    did = up.json()["id"]

    r = client.get(f"/api/devices/{did}/syx-analysis")
    assert r.status_code == 200
    data = r.json()
    assert data["available"] is True
    assert data["source_format"] == "syx"
    assert data["filesize"] > 0
    assert data["section_total"] == 6
    assert data["track_total"] == 8
    assert isinstance(data["tracks"], list) and len(data["tracks"]) == 8
    qy70_labels = {"D1", "D2", "PC", "BA", "C1", "C2", "C3", "C4"}
    assert {t["name"] for t in data["tracks"]} == qy70_labels
    assert data["reverb"]["name"]
    assert data["chorus"]["name"]
    assert data["variation"]["name"]
    assert data["stats"]["total_messages"] > 0


def test_syx_analysis_voice_source_tag():
    client = TestClient(create_app())
    with open("tests/fixtures/QY70_SGT.syx", "rb") as f:
        up = client.post("/api/devices", files={"file": ("QY70_SGT.syx", f)})
    did = up.json()["id"]

    r = client.get(f"/api/devices/{did}/syx-analysis")
    data = r.json()
    active = [t for t in data["tracks"] if t["has_data"]]
    assert active, "fixture should expose at least one active track"
    for t in active:
        assert t["voice_source"] in {"db", "nn", "class", "xg"}
        assert t["voice_name"] != ""
        assert "(DB)" not in t["voice_name"]
        assert "(NN" not in t["voice_name"]
        assert "(class)" not in t["voice_name"]


def test_syx_analysis_pattern_name_from_filename():
    client = TestClient(create_app())
    with open("tests/fixtures/QY70_SGT.syx", "rb") as f:
        up = client.post(
            "/api/devices",
            files={"file": ("P -  Custom Demo - 20231101.syx", f)},
        )
    did = up.json()["id"]

    r = client.get(f"/api/devices/{did}/syx-analysis")
    assert r.json()["pattern_name"] == "Custom Demo"


def test_syx_analysis_unavailable_for_q7p():
    client = TestClient(create_app())
    with open("tests/fixtures/T01.Q7P", "rb") as f:
        up = client.post("/api/devices", files={"file": ("T01.Q7P", f)})
    did = up.json()["id"]

    r = client.get(f"/api/devices/{did}/syx-analysis")
    assert r.status_code == 200
    data = r.json()
    assert data["available"] is False
    assert data["source_format"] == "q7p"
    assert data["tracks"] == []


def test_syx_analysis_not_found():
    client = TestClient(create_app())
    r = client.get("/api/devices/nonexistent/syx-analysis")
    assert r.status_code == 404
