"""Get/set UDM fields by path.

Works hand-in-hand with `schema.validate` and `address_map.resolve_address`.
Auto-creates `MultiPart` slots and `DrumSetup` kits/notes when writing a
path that doesn't yet exist.
"""

from __future__ import annotations

import re
from dataclasses import replace
from typing import Any, Optional

from qymanager.editor.schema import validate
from qymanager.model import (
    Device,
    DrumNote,
    DrumSetup,
    MultiPart,
    VariationBlock,
    Voice,
)


_RX_MULTI = re.compile(r"^multi_part\[(\d+)\]\.(.+)$")
_RX_DRUM = re.compile(r"^drum_setup\[(\d+)\]\.notes\[(\d+)\]\.(.+)$")


def _ensure_part(device: Device, index: int) -> MultiPart:
    while len(device.multi_part) <= index:
        device.multi_part.append(
            MultiPart(
                part_index=len(device.multi_part),
                rx_channel=len(device.multi_part),
                voice=Voice(),
            )
        )
    return device.multi_part[index]


def _ensure_kit(device: Device, kit_index: int) -> DrumSetup:
    while len(device.drum_setup) <= kit_index:
        device.drum_setup.append(DrumSetup(kit_index=len(device.drum_setup)))
    return device.drum_setup[kit_index]


def _ensure_note(kit: DrumSetup, note: int) -> DrumNote:
    if note not in kit.notes:
        kit.notes[note] = DrumNote()
    return kit.notes[note]


def _ensure_variation(device: Device) -> VariationBlock:
    if device.effects.variation is None:
        device.effects.variation = VariationBlock()
    return device.effects.variation


def get_field(device: Device, path: str) -> Any:
    """Read a UDM field by dotted path. Returns None for missing slots."""
    if path.startswith("system."):
        return getattr(device.system, path[len("system.") :], None)
    if path.startswith("effects.reverb."):
        return getattr(device.effects.reverb, path[len("effects.reverb.") :], None)
    if path.startswith("effects.chorus."):
        return getattr(device.effects.chorus, path[len("effects.chorus.") :], None)
    if path.startswith("effects.variation."):
        if device.effects.variation is None:
            return None
        return getattr(
            device.effects.variation, path[len("effects.variation.") :], None
        )

    m = _RX_MULTI.match(path)
    if m is not None:
        idx = int(m.group(1))
        if idx >= len(device.multi_part):
            return None
        return _traverse(device.multi_part[idx], m.group(2))

    m = _RX_DRUM.match(path)
    if m is not None:
        kit = int(m.group(1))
        note = int(m.group(2))
        if kit >= len(device.drum_setup):
            return None
        drum = device.drum_setup[kit]
        if note not in drum.notes:
            return None
        return getattr(drum.notes[note], m.group(3), None)

    return None


def set_field(device: Device, path: str, value: Any) -> Any:
    """Validate `value`, coerce, and write it into the Device at `path`.

    Auto-creates missing Multi Part / Drum Setup / VariationBlock slots.
    Returns the UDM-coerced value that was stored.
    """
    coerced = validate(path, value)

    if path.startswith("system."):
        attr = path[len("system.") :]
        setattr(device.system, attr, coerced)
        return coerced
    if path.startswith("effects.reverb."):
        attr = path[len("effects.reverb.") :]
        setattr(device.effects.reverb, attr, coerced)
        return coerced
    if path.startswith("effects.chorus."):
        attr = path[len("effects.chorus.") :]
        setattr(device.effects.chorus, attr, coerced)
        return coerced
    if path.startswith("effects.variation."):
        block = _ensure_variation(device)
        attr = path[len("effects.variation.") :]
        setattr(block, attr, coerced)
        return coerced

    m = _RX_MULTI.match(path)
    if m is not None:
        idx = int(m.group(1))
        part = _ensure_part(device, idx)
        _set_nested(part, m.group(2), coerced)
        return coerced

    m = _RX_DRUM.match(path)
    if m is not None:
        kit_idx = int(m.group(1))
        note_num = int(m.group(2))
        kit = _ensure_kit(device, kit_idx)
        note = _ensure_note(kit, note_num)
        setattr(note, m.group(3), coerced)
        return coerced

    raise ValueError(f"cannot set unknown UDM path: {path}")


def _traverse(obj: Any, dotted: str) -> Any:
    for part in dotted.split("."):
        if obj is None:
            return None
        obj = getattr(obj, part, None)
    return obj


def _set_nested(obj: Any, dotted: str, value: Any) -> None:
    parts = dotted.split(".")
    if len(parts) == 1:
        setattr(obj, parts[0], value)
        return
    # nested dataclass (e.g. voice.bank_msb). Handle frozen Voice specially.
    head, rest = parts[0], parts[1:]
    inner = getattr(obj, head)
    if isinstance(inner, Voice):
        kwargs = {rest[0]: value}
        setattr(obj, head, replace(inner, **kwargs))
        return
    _set_nested(inner, ".".join(rest), value)


def apply_edits(device: Device, edits: dict[str, Any]) -> list[str]:
    """Apply a batch of path→value edits. Returns a list of per-field errors.

    Fields that validate + apply cleanly are silently committed. Any
    failure is recorded and that edit is skipped (other edits continue).
    """
    errors: list[str] = []
    for path, value in edits.items():
        try:
            set_field(device, path, value)
        except (ValueError, KeyError, AttributeError) as exc:
            errors.append(f"{path}: {exc}")
    return errors


def make_xg_messages(
    device: Device,
    edits: dict[str, Any],
    *,
    device_number: int = 0,
) -> list[tuple[str, bytes]]:
    """Translate a batch of edits into XG SysEx Parameter Change bytes.

    Each edit is validated, encoded to its 7-bit XG byte, and packed as
    `F0 43 1n 4C ah am al dd F7`. Returns [(path, sysex_bytes), ...]
    in the input order. Edits without an address mapping are skipped.
    """
    from qymanager.editor.address_map import build_xg_parameter_change, resolve_address
    from qymanager.editor.schema import encode_xg

    _ = device  # reserved for future per-device dialect adjustments
    out: list[tuple[str, bytes]] = []
    for path, raw_value in edits.items():
        addr = resolve_address(path)
        if addr is None:
            continue
        ah, am, al = addr
        byte_val = encode_xg(path, raw_value)
        msg = build_xg_parameter_change(ah, am, al, byte_val, device=device_number)
        out.append((path, msg))
        # Detune is a 2-byte parameter: AL=0x09 (MSB) + AL=0x0A (LSB).
        # Emit a second message for the LSB byte (always 0 for single-byte edits).
        if ah == 0x08 and al == 0x09:
            msg2 = build_xg_parameter_change(ah, am, 0x0A, 0, device=device_number)
            out.append((path + ".__lsb", msg2))
    return out
