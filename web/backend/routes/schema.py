from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from qymanager.editor.schema import (
    Enum,
    Range,
    _DRUM_NOTE_SPECS,
    _FIXED_SPECS,
    _MULTI_PART_SPECS,
)

router = APIRouter(tags=["schema"])


class SchemaEntry(BaseModel):
    path: str
    kind: str
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
