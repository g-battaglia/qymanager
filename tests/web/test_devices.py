import json
from pathlib import Path

FIXTURES = Path(__file__).resolve().parents[2] / "tests" / "fixtures"
SGT_SYX = FIXTURES / "QY70_SGT.syx"
T01_Q7P = FIXTURES / "T01.Q7P"
CAPTURES_DIR = Path(__file__).resolve().parents[2] / "data" / "captures_2026_04_23"
AMB01_BULK = CAPTURES_DIR / "AMB01_bulk_20260423_113016.syx"
AMB01_LOAD = CAPTURES_DIR / "AMB01_load_20260423_113116.json"


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


def test_merge_capture_populates_voices(client):
    if not AMB01_BULK.exists() or not AMB01_LOAD.exists():
        import pytest
        pytest.skip("AMB01 capture dataset not present")

    with open(AMB01_BULK, "rb") as f:
        r = client.post("/api/devices", files={"file": (AMB01_BULK.name, f)})
    assert r.status_code == 200
    did = r.json()["id"]

    # Bulk alone leaves multi_part voices at zeros.
    before = client.get(f"/api/devices/{did}").json()["device"]
    active_before = [
        p for p in before["multi_part"]
        if p["voice"]["bank_msb"] or p["voice"]["bank_lsb"] or p["voice"]["program"]
    ]
    assert len(active_before) == 0

    # Merge the capture JSON.
    with open(AMB01_LOAD, "rb") as f:
        r = client.post(
            f"/api/devices/{did}/merge-capture",
            files={"file": (AMB01_LOAD.name, f, "application/json")},
        )
    assert r.status_code == 200
    after = r.json()["device"]

    # Source format must remain "syx" (merge updates, not replaces).
    assert after["source_format"] == "syx"
    populated = {
        p["rx_channel"] + 1: p["voice"]
        for p in after["multi_part"]
        if p["voice"]["bank_msb"] or p["voice"]["bank_lsb"] or p["voice"]["program"]
    }
    # AMB#01 INDEX.md ground truth: ch9 drum25, ch12 PickBass/34, ch15 TremStr 0/40/44.
    assert populated[9] == {"bank_msb": 127, "bank_lsb": 0, "program": 25}
    assert populated[12] == {"bank_msb": 0, "bank_lsb": 0, "program": 34}
    assert populated[15] == {"bank_msb": 0, "bank_lsb": 40, "program": 44}


def test_merge_capture_raw_syx_accepted(client):
    """Accepts a raw `.syx` XG capture in addition to capture JSON."""
    if not AMB01_BULK.exists() or not AMB01_LOAD.exists():
        import pytest
        pytest.skip("AMB01 capture dataset not present")

    # Build raw XG .syx bytes from the JSON capture by flattening entries.
    entries = json.loads(AMB01_LOAD.read_text())
    raw = b"".join(bytes.fromhex(e["data"]) for e in entries if e.get("data"))

    with open(AMB01_BULK, "rb") as f:
        r = client.post("/api/devices", files={"file": (AMB01_BULK.name, f)})
    did = r.json()["id"]

    r = client.post(
        f"/api/devices/{did}/merge-capture",
        files={"file": ("capture.syx", raw, "application/octet-stream")},
    )
    assert r.status_code == 200
    after = r.json()["device"]
    populated = {
        p["rx_channel"] + 1: p["voice"]["program"]
        for p in after["multi_part"]
        if p["voice"]["bank_msb"] or p["voice"]["bank_lsb"] or p["voice"]["program"]
    }
    assert populated.get(9) == 25
    assert populated.get(12) == 34
    assert populated.get(15) == 44


def test_merge_capture_device_not_found(client):
    r = client.post(
        "/api/devices/does-not-exist/merge-capture",
        files={"file": ("x.json", b"[]", "application/json")},
    )
    assert r.status_code == 404


def test_merge_capture_invalid_json(client):
    did = _upload_sgx(client)
    r = client.post(
        f"/api/devices/{did}/merge-capture",
        files={"file": ("bad.json", b"{not valid json", "application/json")},
    )
    assert r.status_code == 400
