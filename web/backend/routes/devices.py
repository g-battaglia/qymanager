from __future__ import annotations

from pathlib import Path
from tempfile import NamedTemporaryFile

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import Response

from qymanager.converters.lossy_policy import LossyPolicy, apply_policy
from qymanager.editor.ops import set_field
from qymanager.formats.io import load_device, save_device
from qymanager.model import DeviceModel
from qymanager.model.serialization import udm_to_dict

from ..schemas import (
    DeviceResponse,
    ExportRequest,
    FieldPatch,
    FieldPatchResponse,
    OkResponse,
    UploadResponse,
    ValidateResponse,
)
from ..session import get_session

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

    did = get_session().create(device, filename=file.filename)
    return UploadResponse(id=did, device=udm_to_dict(device))


@router.get("/devices/{did}", response_model=DeviceResponse)
def get_device(did: str) -> DeviceResponse:
    device = get_session().get(did)
    if device is None:
        raise HTTPException(404, "Device not found")
    return DeviceResponse(device=udm_to_dict(device))


@router.post("/devices/{did}/merge-capture", response_model=DeviceResponse)
async def merge_capture(did: str, file: UploadFile = File(...)) -> DeviceResponse:
    """Enrich an uploaded QY70 bulk with an XG capture (.json or .syx).

    The capture carries the real voice assignments that the bulk dump does
    not — Bank MSB/LSB/Program, Volume, Pan, Reverb/Chorus sends — either as
    SysEx XG Parameter Change messages or as channel events (`Bn 00 MSB`,
    `Bn 20 LSB`, `Cn PROG`, …). After merging, the session holds an updated
    Device with populated `multi_part` voices and the combined raw bytes,
    so `GET /devices/{did}` and `syx-analysis` see the enriched device.
    """
    import json

    from qymanager.formats.xg_bulk import parse_xg_bulk_to_udm

    sess = get_session()
    device = sess.get(did)
    if device is None:
        raise HTTPException(404, "Device not found")

    blob = await file.read()
    if len(blob) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "Capture too large (max 5 MB)")

    suffix = Path(file.filename or "capture.bin").suffix.lower()
    if suffix == ".json":
        try:
            entries = json.loads(blob)
        except json.JSONDecodeError as exc:
            raise HTTPException(400, f"Invalid JSON: {exc}") from exc
        if not isinstance(entries, list):
            raise HTTPException(400, "Capture JSON must be a list of {t,data}")
        raw = bytearray()
        for entry in entries:
            hx = entry.get("data", "") if isinstance(entry, dict) else ""
            if not hx:
                continue
            try:
                raw.extend(bytes.fromhex(hx))
            except ValueError:
                continue
        capture_bytes = bytes(raw)
    else:
        capture_bytes = blob

    if not capture_bytes:
        raise HTTPException(400, "Capture contained no usable bytes")

    try:
        enriched = parse_xg_bulk_to_udm(capture_bytes, base_device=device)
    except ValueError as exc:
        raise HTTPException(400, f"Capture not recognized: {exc}") from exc

    sess.update(did, enriched)
    return DeviceResponse(device=udm_to_dict(enriched))


@router.patch("/devices/{did}/field", response_model=FieldPatchResponse)
def patch_device_field(did: str, patch: FieldPatch) -> FieldPatchResponse:
    sess = get_session()
    device = sess.get(did)
    if device is None:
        raise HTTPException(404, "Device not found")
    try:
        set_field(device, patch.path, patch.value)
    except (ValueError, KeyError) as e:
        return FieldPatchResponse(device=udm_to_dict(device), errors=[str(e)])
    return FieldPatchResponse(device=udm_to_dict(device))


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

    warning_strings: list[str] = []
    try:
        if req.target_model:
            target = DeviceModel(req.target_model.lower())
            policy = LossyPolicy(keep=req.keep, drop=req.drop)
            converted, warnings = apply_policy(device, policy, target_model=target)
            save_device(converted, out_path)
            warning_strings = [f"{w.path}: {w.reason}" for w in warnings]
        else:
            save_device(device, out_path)
        data = out_path.read_bytes()
    except Exception as e:
        raise HTTPException(500, f"Export failed: {e}") from e
    finally:
        out_path.unlink(missing_ok=True)

    media_types = {
        "syx": "application/octet-stream",
        "q7p": "application/octet-stream",
        "mid": "audio/midi",
    }
    headers = {"X-Warnings": "|".join(warning_strings)} if warning_strings else {}
    return Response(content=data, media_type=media_types[fmt], headers=headers)


@router.delete("/devices/{did}", response_model=OkResponse)
def delete_device(did: str) -> OkResponse:
    if not get_session().delete(did):
        raise HTTPException(404, "Device not found")
    return OkResponse()
