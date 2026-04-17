"""Unified UDM file I/O: auto-detect format on load, dispatch on emit.

Extension-based dispatch:

| Extension | Parser                    | Emitter                  |
|-----------|---------------------------|--------------------------|
| `.q7p`    | `parse_q7p_to_udm`        | `emit_udm_to_q7p`        |
| `.syx`    | XG bulk first, then sparse| `emit_udm_to_syx` (bulk) |
| `.blk`    | same as `.syx`            | `emit_udm_to_syx`        |
| `.mid`    | `parse_smf_to_udm`        | `emit_udm_to_smf`        |

For `.syx`, `parse_xg_bulk_to_udm` is tried first; if no XG Parameter
Change messages are present, we fall back to `parse_syx_to_udm` (QY70
sparse pattern dump). This matches reality where both kinds of .syx
exist in the wild.
"""

from __future__ import annotations

from pathlib import Path
from typing import Union

from qymanager.formats.qy70.reader import parse_syx_to_udm
from qymanager.formats.qy70.writer import emit_udm_to_syx
from qymanager.formats.qy700.reader import parse_q7p_to_udm
from qymanager.formats.qy700.writer import emit_udm_to_q7p
from qymanager.formats.smf import emit_udm_to_smf, parse_smf_to_udm
from qymanager.formats.xg_bulk import emit_udm_to_xg_bulk, parse_xg_bulk_to_udm
from qymanager.model import Device, DeviceModel


def load_device(
    path: Union[str, Path],
    *,
    device_model: DeviceModel = DeviceModel.QY70,
) -> Device:
    """Parse a file into a UDM Device, auto-detecting format by extension."""
    p = Path(path)
    ext = p.suffix.lower()
    data = p.read_bytes()

    if ext == ".q7p":
        return parse_q7p_to_udm(data)
    if ext in (".syx", ".blk"):
        try:
            return parse_xg_bulk_to_udm(data, device_model=device_model)
        except ValueError:
            return parse_syx_to_udm(data)
    if ext == ".mid":
        return parse_smf_to_udm(data, device_model=device_model)
    raise ValueError(f"Unsupported file extension: {ext} (path={path})")


def save_device(device: Device, path: Union[str, Path]) -> bytes:
    """Emit the UDM Device to `path` using the emitter matched to its extension."""
    p = Path(path)
    ext = p.suffix.lower()

    if ext == ".q7p":
        data = emit_udm_to_q7p(device)
    elif ext in (".syx", ".blk"):
        if device.source_format == "xg-bulk":
            data = emit_udm_to_xg_bulk(device)
        else:
            data = emit_udm_to_syx(device)
    elif ext == ".mid":
        data = emit_udm_to_smf(device)
    else:
        raise ValueError(f"Unsupported file extension: {ext} (path={path})")

    p.write_bytes(data)
    return data
