from pathlib import Path

FIXTURES = Path(__file__).resolve().parents[2] / "tests" / "fixtures"
SGT_SYX = FIXTURES / "QY70_SGT.syx"
T01_Q7P = FIXTURES / "T01.Q7P"


def test_upload_syx_ok(client):
    with open(SGT_SYX, "rb") as f:
        r = client.post(
            "/api/devices", files={"file": ("QY70_SGT.syx", f, "application/octet-stream")}
        )
    assert r.status_code == 200
    data = r.json()
    assert "id" in data
    assert isinstance(data["device"], dict)
    assert data["device"]["model"].upper() in ("QY70", "QY700")


def test_upload_q7p_ok(client):
    with open(T01_Q7P, "rb") as f:
        r = client.post("/api/devices", files={"file": ("T01.Q7P", f, "application/octet-stream")})
    assert r.status_code == 200
    data = r.json()
    assert "id" in data
    assert isinstance(data["device"], dict)


def test_upload_invalid_fails_400(client):
    r = client.post(
        "/api/devices", files={"file": ("bad.bin", b"not a valid file", "application/octet-stream")}
    )
    assert r.status_code == 400


def test_upload_too_large_413(client):
    big = b"\x00" * (5 * 1024 * 1024 + 1)
    r = client.post("/api/devices", files={"file": ("big.syx", big, "application/octet-stream")})
    assert r.status_code == 413


def test_get_device_not_found_404(client):
    r = client.get("/api/devices/nonexistent")
    assert r.status_code == 404


def _upload_sgx(client):
    with open(SGT_SYX, "rb") as f:
        r = client.post(
            "/api/devices", files={"file": ("QY70_SGT.syx", f, "application/octet-stream")}
        )
    assert r.status_code == 200
    return r.json()["id"]


def test_patch_field_ok(client):
    did = _upload_sgx(client)
    r = client.patch(
        f"/api/devices/{did}/field",
        json={"path": "system.master_volume", "value": 100},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["errors"] == []
    device = data["device"]
    assert device["system"]["master_volume"] == 100


def test_patch_field_out_of_range(client):
    did = _upload_sgx(client)
    r = client.patch(
        f"/api/devices/{did}/field",
        json={"path": "system.master_volume", "value": 999},
    )
    assert r.status_code == 200
    data = r.json()
    assert len(data["errors"]) > 0


def test_validate_device(client):
    did = _upload_sgx(client)
    r = client.post(f"/api/devices/{did}/validate")
    assert r.status_code == 200
    assert "errors" in r.json()


def test_export_syx_roundtrip(client):
    did = _upload_sgx(client)
    r = client.post(
        f"/api/devices/{did}/export",
        json={"format": "syx"},
    )
    assert r.status_code == 200
    assert len(r.content) > 0
    assert r.headers["content-type"] == "application/octet-stream"


def test_export_convert_with_target(client):
    did = _upload_sgx(client)
    r = client.post(
        f"/api/devices/{did}/export",
        json={"format": "q7p", "target_model": "QY700"},
    )
    assert r.status_code == 200
    assert len(r.content) > 0


def test_delete_device(client):
    did = _upload_sgx(client)
    r = client.delete(f"/api/devices/{did}")
    assert r.status_code == 200
    r2 = client.get(f"/api/devices/{did}")
    assert r2.status_code == 404
