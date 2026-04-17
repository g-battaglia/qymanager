# W1 — Backend devices routes

> **Obiettivo**: FastAPI scaffold + 6 endpoint devices (upload/get/patch/delete/validate/export),
> completamente testati via `TestClient`.

## Dipendenze

Aggiungere a `pyproject.toml`:

```toml
[project.optional-dependencies]
web = [
    "fastapi>=0.110",
    "uvicorn[standard]>=0.27",
    "python-multipart>=0.0.9",  # per upload multipart
    "websockets>=12",
]
```

Sync: `uv sync --all-extras --group dev`

## Struttura

```
web/
├── __init__.py
└── backend/
    ├── __init__.py
    ├── app.py               # create_app(frontend_dir: Path | None = None)
    ├── session.py           # DeviceSession in-memory cache
    ├── schemas.py           # pydantic models
    └── routes/
        ├── __init__.py
        └── devices.py
```

### `web/backend/app.py`

```python
from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from .routes import devices


def create_app(frontend_dir: Path | None = None, dev: bool = False) -> FastAPI:
    app = FastAPI(title="QYConv", version="1.0.0")

    if dev:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["http://localhost:5173"],
            allow_methods=["*"],
            allow_headers=["*"],
        )

    app.include_router(devices.router, prefix="/api")

    if frontend_dir is not None and frontend_dir.exists():
        app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")

    return app
```

### `web/backend/session.py`

```python
from __future__ import annotations
from dataclasses import dataclass, field
from threading import RLock
from uuid import uuid4

from qymanager.model.device import Device


@dataclass
class DeviceSession:
    _devices: dict[str, Device] = field(default_factory=dict)
    _lock: RLock = field(default_factory=RLock)

    def create(self, device: Device) -> str:
        did = str(uuid4())
        with self._lock:
            self._devices[did] = device
        return did

    def get(self, did: str) -> Device | None:
        with self._lock:
            return self._devices.get(did)

    def update(self, did: str, device: Device) -> None:
        with self._lock:
            self._devices[did] = device

    def delete(self, did: str) -> bool:
        with self._lock:
            return self._devices.pop(did, None) is not None

    def list_ids(self) -> list[str]:
        with self._lock:
            return list(self._devices.keys())


_session = DeviceSession()


def get_session() -> DeviceSession:
    return _session
```

### `web/backend/schemas.py`

```python
from __future__ import annotations
from typing import Any
from pydantic import BaseModel, Field


class UploadResponse(BaseModel):
    id: str
    device: dict[str, Any]
    warnings: list[str] = Field(default_factory=list)


class DeviceResponse(BaseModel):
    device: dict[str, Any]
    warnings: list[str] = Field(default_factory=list)


class FieldPatch(BaseModel):
    path: str
    value: Any


class FieldPatchResponse(BaseModel):
    device: dict[str, Any]
    errors: list[str] = Field(default_factory=list)


class ValidateResponse(BaseModel):
    errors: list[str] = Field(default_factory=list)


class ExportRequest(BaseModel):
    format: str  # "syx" | "q7p" | "mid"
    target_model: str | None = None  # "QY70" | "QY700"
    keep: list[str] = Field(default_factory=list)
    drop: list[str] = Field(default_factory=list)


class OkResponse(BaseModel):
    ok: bool = True
```

### `web/backend/routes/devices.py`

```python
from __future__ import annotations
from pathlib import Path
from tempfile import NamedTemporaryFile

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import Response

from qymanager.formats.io import load_device, save_device
from qymanager.editor.ops import set_field
from qymanager.model.serialization import udm_to_dict
from qymanager.converters.udm_convert import convert_file

from ..session import get_session
from ..schemas import (
    UploadResponse, DeviceResponse, FieldPatch, FieldPatchResponse,
    ValidateResponse, ExportRequest, OkResponse,
)

router = APIRouter(tags=["devices"])
MAX_UPLOAD_BYTES = 5 * 1024 * 1024


@router.post("/devices", response_model=UploadResponse)
async def upload_device(file: UploadFile = File(...)) -> UploadResponse:
    data = await file.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "File too large (max 5 MB)")

    suffix = Path(file.filename or "upload.bin").suffix.lower() or ".bin"
    with NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(data)
        tmp_path = Path(tmp.name)

    try:
        device = load_device(tmp_path)
    except Exception as e:
        raise HTTPException(400, f"Cannot parse file: {e}") from e
    finally:
        tmp_path.unlink(missing_ok=True)

    did = get_session().create(device)
    return UploadResponse(id=did, device=udm_to_dict(device), warnings=[])


@router.get("/devices/{did}", response_model=DeviceResponse)
def get_device(did: str) -> DeviceResponse:
    device = get_session().get(did)
    if device is None:
        raise HTTPException(404, "Device not found")
    return DeviceResponse(device=udm_to_dict(device))


@router.patch("/devices/{did}/field", response_model=FieldPatchResponse)
def patch_device_field(did: str, patch: FieldPatch) -> FieldPatchResponse:
    sess = get_session()
    device = sess.get(did)
    if device is None:
        raise HTTPException(404, "Device not found")
    try:
        updated = set_field(device, patch.path, patch.value)
    except (ValueError, KeyError) as e:
        return FieldPatchResponse(device=udm_to_dict(device), errors=[str(e)])
    sess.update(did, updated)
    return FieldPatchResponse(device=udm_to_dict(updated))


@router.post("/devices/{did}/validate", response_model=ValidateResponse)
def validate_device(did: str) -> ValidateResponse:
    device = get_session().get(did)
    if device is None:
        raise HTTPException(404, "Device not found")
    errors = device.validate()
    return ValidateResponse(errors=errors)


@router.post("/devices/{did}/export")
def export_device(did: str, req: ExportRequest) -> Response:
    device = get_session().get(did)
    if device is None:
        raise HTTPException(404, "Device not found")

    fmt = req.format.lower()
    if fmt not in {"syx", "q7p", "mid"}:
        raise HTTPException(400, f"Unsupported format: {fmt}")

    with NamedTemporaryFile(suffix=f".{fmt}", delete=False) as out:
        out_path = Path(out.name)

    warnings: list[str] = []
    try:
        if req.target_model:
            warnings = convert_file(
                device=device,
                target_model=req.target_model,
                output_path=out_path,
                keep=req.keep,
                drop=req.drop,
            )
        else:
            save_device(device, out_path)
        data = out_path.read_bytes()
    except Exception as e:
        raise HTTPException(500, f"Export failed: {e}") from e
    finally:
        out_path.unlink(missing_ok=True)

    media_types = {"syx": "application/octet-stream",
                   "q7p": "application/octet-stream",
                   "mid": "audio/midi"}
    headers = {"X-Warnings": "|".join(warnings)} if warnings else {}
    return Response(content=data, media_type=media_types[fmt], headers=headers)


@router.delete("/devices/{did}", response_model=OkResponse)
def delete_device(did: str) -> OkResponse:
    if not get_session().delete(did):
        raise HTTPException(404, "Device not found")
    return OkResponse()
```

## Test

`tests/web/conftest.py`:

```python
import pytest
from fastapi.testclient import TestClient
from web.backend.app import create_app
from web.backend.session import get_session


@pytest.fixture(autouse=True)
def clean_session():
    get_session()._devices.clear()
    yield
    get_session()._devices.clear()


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app())
```

`tests/web/test_devices.py` — 6+ test:

1. `test_upload_syx_ok` — upload `.syx`, verifica `id` + device dict valido
2. `test_upload_q7p_ok` — upload `.q7p` da fixture
3. `test_upload_invalid_fails_400` — upload bytes random → 400
4. `test_upload_too_large_413` — upload > 5MB → 413
5. `test_get_device_not_found_404`
6. `test_patch_field_ok` — PATCH `system.master_volume = 100`, verifica persistenza
7. `test_patch_field_out_of_range` — PATCH con valore invalido → `errors` popolato, no crash
8. `test_validate_ok`
9. `test_export_syx_roundtrip` — export `.syx` → riapri → stesso device
10. `test_export_convert_qy70_to_qy700` — target_model switch + warnings
11. `test_delete_device`

Usa fixtures esistenti: `tests/fixtures/QY70_SGT.syx`, Q7P file se disponibili.

## Task granulari (vedi `PROGRESS.md`)

1. Aggiungere dep `web` in `pyproject.toml` + `uv sync`
2. Creare `web/__init__.py`, `web/backend/__init__.py`, `web/backend/app.py`
3. Creare `web/backend/session.py`
4. Creare `web/backend/schemas.py`
5. Creare `web/backend/routes/__init__.py` + `devices.py` con 6 endpoint
6. Creare `tests/web/__init__.py`, `conftest.py`, `test_devices.py` con 10+ test
7. Commit: `feat(web-backend): W1 — FastAPI devices routes with TestClient coverage`

## Verifica

```bash
uv run pytest tests/web/ -v
uv run ruff check web/backend tests/web
uv run black --check web/backend tests/web
# Smoke: uv run python -c "from web.backend.app import create_app; app = create_app(); print(app.routes)"
```
