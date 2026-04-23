from pathlib import Path

FIXTURES = Path(__file__).resolve().parents[2] / "tests" / "fixtures"
SGT_SYX = FIXTURES / "QY70_SGT.syx"


def _upload(client, path=SGT_SYX):
    with open(path, "rb") as f:
        r = client.post("/api/devices", files={"file": (path.name, f, "application/octet-stream")})
    assert r.status_code == 200
    return r.json()["id"]


def test_diff_identical_devices(client):
    id_a = _upload(client)
    id_b = _upload(client)
    r = client.post("/api/diff", json={"id_a": id_a, "id_b": id_b})
    assert r.status_code == 200
    assert r.json()["changes"] == []


def test_diff_after_patch(client):
    id_a = _upload(client)
    id_b = _upload(client)
    client.patch(f"/api/devices/{id_b}/field", json={"path": "system.master_volume", "value": 50})
    r = client.post("/api/diff", json={"id_a": id_a, "id_b": id_b})
    assert r.status_code == 200
    paths = [c["path"] for c in r.json()["changes"]]
    assert any("master_volume" in p for p in paths)


def test_diff_device_not_found_404(client):
    r = client.post("/api/diff", json={"id_a": "nope", "id_b": "nope"})
    assert r.status_code == 404
