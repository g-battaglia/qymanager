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
        DiffChange(path=p, a=fa.get(p), b=fb.get(p)) for p in all_paths if fa.get(p) != fb.get(p)
    ]
    return DiffResponse(changes=changes)
