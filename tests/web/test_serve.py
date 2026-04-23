from pathlib import Path

from fastapi.testclient import TestClient

from web.backend.app import create_app


def test_serve_static_mount_with_temp_dir(tmp_path: Path):
    (tmp_path / "index.html").write_text("<!doctype html><html><body>ok</body></html>")
    app = create_app(frontend_dir=tmp_path)
    client = TestClient(app)
    r = client.get("/")
    assert r.status_code == 200
    assert "ok" in r.text


def test_serve_api_routes_available():
    app = create_app()
    client = TestClient(app)
    r = client.get("/api/schema")
    assert r.status_code == 200
