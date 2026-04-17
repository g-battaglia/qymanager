# W2 — Backend diff + schema endpoints

> **Obiettivo**: endpoint `POST /api/diff` (confronto 2 device) e `GET /api/schema` (spec
> campi per UI auto-form). L'export lossy è già in W1 via `target_model`; qui lo estendiamo
> con un endpoint separato `POST /api/convert` per simmetria con la UI.

## Route `routes/diff.py`

### Contratto

| Request | `POST /api/diff` |
|---------|------------------|
| Body    | `{id_a: str, id_b: str}` |
| Response | `{changes: [{path: str, a: Any, b: Any}]}` |

### Implementazione

```python
from __future__ import annotations
from typing import Any
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from qymanager.model.serialization import udm_to_dict
from ..session import get_session

router = APIRouter(tags=["diff"])


class DiffRequest(BaseModel):
    id_a: str
    id_b: str


class DiffChange(BaseModel):
    path: str
    a: Any
    b: Any


class DiffResponse(BaseModel):
    changes: list[DiffChange]


def _flatten(value: Any, prefix: str = "") -> dict[str, Any]:
    out: dict[str, Any] = {}
    if isinstance(value, dict):
        for k, v in value.items():
            out.update(_flatten(v, f"{prefix}.{k}" if prefix else k))
    elif isinstance(value, list):
        for i, v in enumerate(value):
            out.update(_flatten(v, f"{prefix}[{i}]"))
    else:
        out[prefix] = value
    return out


@router.post("/diff", response_model=DiffResponse)
def diff_devices(req: DiffRequest) -> DiffResponse:
    sess = get_session()
    da, db = sess.get(req.id_a), sess.get(req.id_b)
    if da is None or db is None:
        raise HTTPException(404, "Device not found")

    fa = _flatten(udm_to_dict(da))
    fb = _flatten(udm_to_dict(db))
    all_paths = sorted(set(fa) | set(fb))
    changes = [
        DiffChange(path=p, a=fa.get(p), b=fb.get(p))
        for p in all_paths if fa.get(p) != fb.get(p)
    ]
    return DiffResponse(changes=changes)
```

## Route `routes/schema.py`

### Contratto

| Request | `GET /api/schema` |
|---------|-------------------|
| Response | `{paths: [{path, kind: "range"\|"enum", lo?, hi?, options?}]}` |

### Implementazione

```python
from __future__ import annotations
from typing import Any
from fastapi import APIRouter
from pydantic import BaseModel

from qymanager.editor.schema import (
    _FIXED_SPECS,
    _MULTI_PART_SPECS,
    _DRUM_NOTE_SPECS,
    Range,
    Enum,
)

router = APIRouter(tags=["schema"])


class SchemaEntry(BaseModel):
    path: str
    kind: str  # "range" | "enum"
    lo: int | None = None
    hi: int | None = None
    options: list[str] | None = None


class SchemaResponse(BaseModel):
    paths: list[SchemaEntry]


def _spec_to_entry(path: str, spec: Any) -> SchemaEntry:
    if isinstance(spec, Range):
        return SchemaEntry(path=path, kind="range", lo=spec.lo, hi=spec.hi)
    if isinstance(spec, Enum):
        return SchemaEntry(path=path, kind="enum", options=list(spec.options))
    raise ValueError(f"Unknown spec type: {type(spec)}")


@router.get("/schema", response_model=SchemaResponse)
def get_schema() -> SchemaResponse:
    entries: list[SchemaEntry] = []
    for path, spec in _FIXED_SPECS.items():
        entries.append(_spec_to_entry(path, spec))
    for suffix, spec in _MULTI_PART_SPECS.items():
        entries.append(_spec_to_entry(f"multi_part[*].{suffix}", spec))
    for suffix, spec in _DRUM_NOTE_SPECS.items():
        entries.append(_spec_to_entry(f"drum_setup[*].notes[*].{suffix}", spec))
    return SchemaResponse(paths=entries)
```

**Nota**: se i nomi esatti delle mappe in `qymanager/editor/schema.py` sono diversi da
`_FIXED_SPECS` / `_MULTI_PART_SPECS` / `_DRUM_NOTE_SPECS`, adattare dopo ispezione del
modulo (leggere `qymanager/editor/schema.py` prima di scrivere il route).

## Wire-up in `app.py`

```python
from .routes import devices, diff, schema
# ...
app.include_router(devices.router, prefix="/api")
app.include_router(diff.router,    prefix="/api")
app.include_router(schema.router,  prefix="/api")
```

## Test

`tests/web/test_diff.py`:

1. `test_diff_identical_devices` — stesso file caricato 2 volte → `changes == []`
2. `test_diff_after_patch` — carica 2×, PATCH `master_volume` su uno, diff contiene path
3. `test_diff_device_not_found_404`

`tests/web/test_schema.py`:

1. `test_schema_returns_paths` — lista non vuota, contiene `system.master_volume` con kind=range
2. `test_schema_multi_part_has_pattern` — verifica che esista entry `multi_part[*].volume`

## Task granulari

1. Leggere `qymanager/editor/schema.py` e verificare nomi esatti delle mappe spec
2. Creare `web/backend/routes/diff.py` con `POST /diff`
3. Creare `web/backend/routes/schema.py` con `GET /schema`
4. Wire routers in `app.py`
5. `tests/web/test_diff.py` (3 test)
6. `tests/web/test_schema.py` (2 test)
7. Commit: `feat(web-backend): W2 — diff + schema endpoints`

## Verifica

```bash
uv run pytest tests/web/ -v
uv run ruff check web/backend tests/web
# Smoke:
uv run python -c "
from fastapi.testclient import TestClient
from web.backend.app import create_app
c = TestClient(create_app())
r = c.get('/api/schema')
print(r.status_code, len(r.json()['paths']))
"
```
