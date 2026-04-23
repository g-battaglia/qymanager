def test_schema_returns_paths(client):
    r = client.get("/api/schema")
    assert r.status_code == 200
    data = r.json()
    assert len(data["paths"]) > 0
    mv = next(e for e in data["paths"] if e["path"] == "system.master_volume")
    assert mv["kind"] == "range"
    assert mv["lo"] == 0
    assert mv["hi"] == 127


def test_schema_multi_part_has_pattern(client):
    r = client.get("/api/schema")
    data = r.json()
    paths = [e["path"] for e in data["paths"]]
    assert any("multi_part[*]" in p for p in paths)
