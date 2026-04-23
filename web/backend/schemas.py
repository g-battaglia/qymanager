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
    format: str
    target_model: str | None = None
    keep: list[str] = Field(default_factory=list)
    drop: list[str] = Field(default_factory=list)


class OkResponse(BaseModel):
    ok: bool = True
