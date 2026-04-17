"""UDM field-path → XG Parameter Change address lookup.

Each UDM path (e.g. "system.master_volume", "multi_part[3].volume",
"effects.reverb.return_level", "drum_setup[0].notes[36].level") maps
to a tuple (AH, AM, AL) that identifies a Yamaha XG Parameter Change.

Templates use the placeholders:

- `{part}`   — 0..31 for Multi Part address slots (AM)
- `{kit}`    — 0 or 1 for Drum Setup 1/2 (selects AH 0x30 or 0x31)
- `{note}`   — 13..84 MIDI note number for per-drum parameters (AM)

Source of authority: wiki/xg-parameters.md, midi_tools/xg_param.py.
"""

from __future__ import annotations

import re
from typing import Optional

AH_SYSTEM = 0x00
AH_EFFECT = 0x02
AH_MULTI_PART = 0x08
AH_DRUM_BASE = 0x30  # Drum Setup 1 = 0x30, Drum Setup 2 = 0x31


# Fixed-path (non-indexed) addresses
_FIXED: dict[str, tuple[int, int, int]] = {
    "system.master_tune": (AH_SYSTEM, 0x00, 0x00),  # 4 nibbles: 00..03
    "system.master_volume": (AH_SYSTEM, 0x00, 0x04),
    "system.transpose": (AH_SYSTEM, 0x00, 0x06),
    "effects.reverb.type_code": (AH_EFFECT, 0x01, 0x00),
    "effects.reverb.return_level": (AH_EFFECT, 0x01, 0x0C),
    "effects.reverb.pan": (AH_EFFECT, 0x01, 0x0D),
    "effects.chorus.type_code": (AH_EFFECT, 0x01, 0x20),
    "effects.chorus.return_level": (AH_EFFECT, 0x01, 0x2C),
    "effects.chorus.pan": (AH_EFFECT, 0x01, 0x2D),
    "effects.chorus.send_to_reverb": (AH_EFFECT, 0x01, 0x2E),
    "effects.variation.type_code": (AH_EFFECT, 0x01, 0x40),
    "effects.variation.return_level": (AH_EFFECT, 0x01, 0x56),
    "effects.variation.pan": (AH_EFFECT, 0x01, 0x57),
    "effects.variation.send_to_reverb": (AH_EFFECT, 0x01, 0x58),
    "effects.variation.send_to_chorus": (AH_EFFECT, 0x01, 0x59),
    "effects.variation.connection": (AH_EFFECT, 0x01, 0x5A),  # 0 system / 1 insertion
}


_MULTI_PART_AL: dict[str, int] = {
    "voice.bank_msb": 0x01,
    "voice.bank_lsb": 0x02,
    "voice.program": 0x03,
    "rx_channel": 0x04,
    "mono_poly": 0x05,
    "key_on_assign": 0x06,
    "same_note_number_key": 0x07,
    "part_mode": 0x08,
    "note_shift": 0x09,
    "detune": 0x0A,
    "volume": 0x0B,
    "velocity_sense_depth": 0x0C,
    "velocity_sense_offset": 0x0D,
    "pan": 0x0E,
    "note_limit_low": 0x0F,
    "note_limit_high": 0x10,
    "dry_level": 0x11,
    "chorus_send": 0x12,
    "reverb_send": 0x13,
    "variation_send": 0x14,
    "cutoff": 0x15,
    "resonance": 0x16,
    "eg_attack": 0x17,
    "eg_decay": 0x18,
    "eg_release": 0x19,
    "bend_pitch": 0x23,
}


_DRUM_NOTE_AL: dict[str, int] = {
    "pitch_coarse": 0x00,
    "pitch_fine": 0x01,
    "level": 0x02,
    "alt_group": 0x03,
    "pan": 0x04,
    "reverb_send": 0x05,
    "chorus_send": 0x06,
    "variation_send": 0x07,
    "key_assign": 0x08,
    "note_off_mode": 0x09,  # Rx Note Off / 0 = disabled
    "filter_cutoff": 0x14,
    "filter_resonance": 0x15,
    "eg_attack": 0x16,
    "eg_decay1": 0x17,
    "eg_decay2": 0x18,
}


_RX_MULTI = re.compile(r"^multi_part\[(\d+)\]\.(.+)$")
_RX_DRUM = re.compile(r"^drum_setup\[(\d+)\]\.notes\[(\d+)\]\.(.+)$")


def resolve_address(path: str) -> Optional[tuple[int, int, int]]:
    """Translate a UDM path into an XG (AH, AM, AL) address.

    Returns None if the path is not mapped. Unknown multi-part fields or
    drum-note fields also return None.
    """
    if path in _FIXED:
        return _FIXED[path]

    m = _RX_MULTI.match(path)
    if m is not None:
        idx = int(m.group(1))
        suffix = m.group(2)
        al = _MULTI_PART_AL.get(suffix)
        if al is None or not 0 <= idx <= 31:
            return None
        return (AH_MULTI_PART, idx, al)

    m = _RX_DRUM.match(path)
    if m is not None:
        kit = int(m.group(1))
        note = int(m.group(2))
        suffix = m.group(3)
        al = _DRUM_NOTE_AL.get(suffix)
        if al is None or kit not in (0, 1) or not 0 <= note <= 127:
            return None
        return (AH_DRUM_BASE + kit, note, al)

    return None


def build_xg_parameter_change(
    ah: int,
    am: int,
    al: int,
    value: int,
    *,
    device: int = 0,
) -> bytes:
    """Encode a single XG Parameter Change SysEx message.

    Wire format:
        F0 43 1n 4C ah am al dd F7
    where n = device (0..15) and dd is the 7-bit value.
    """
    if not 0 <= device <= 15:
        raise ValueError(f"device must be 0-15, got {device}")
    if not 0 <= value <= 127:
        raise ValueError(f"value must be 0-127, got {value}")
    return bytes([0xF0, 0x43, 0x10 | device, 0x4C, ah & 0x7F, am & 0x7F, al & 0x7F, value & 0x7F, 0xF7])
