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
    # Block 1: Voice, mode, mixer, LFO, EG (AL 0x00-0x28)
    "element_reserve": 0x00,
    "voice.bank_msb": 0x01,
    "voice.bank_lsb": 0x02,
    "voice.program": 0x03,
    "rx_channel": 0x04,
    "mono_poly": 0x05,
    "key_on_assign": 0x06,
    "part_mode": 0x07,
    "note_shift": 0x08,
    "detune": 0x09,
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
    "vibrato_rate": 0x15,
    "vibrato_depth": 0x16,
    "vibrato_delay": 0x17,
    "cutoff": 0x18,
    "resonance": 0x19,
    "eg_attack": 0x1A,
    "eg_decay": 0x1B,
    "eg_release": 0x1C,
    "mw_pitch_control": 0x1D,
    "mw_filter_control": 0x1E,
    "mw_amplitude_control": 0x1F,
    "mw_lfo_pitch_depth": 0x20,
    "mw_lfo_filter_depth": 0x21,
    "mw_lfo_amplitude_depth": 0x22,
    "bend_pitch": 0x23,
    "bend_filter_control": 0x24,
    "bend_amplitude_control": 0x25,
    "bend_lfo_pitch_depth": 0x26,
    "bend_lfo_filter_depth": 0x27,
    "bend_lfo_amplitude_depth": 0x28,
    # Block 2: Receive Switches (AL 0x30-0x40)
    "rx_pitch_bend": 0x30,
    "rx_channel_aftertouch": 0x31,
    "rx_program_change": 0x32,
    "rx_control_change": 0x33,
    "rx_poly_aftertouch": 0x34,
    "rx_note_messages": 0x35,
    "rx_rpn": 0x36,
    "rx_nrpn": 0x37,
    "rx_modulation": 0x38,
    "rx_volume": 0x39,
    "rx_pan": 0x3A,
    "rx_expression": 0x3B,
    "rx_hold_pedal": 0x3C,
    "rx_portamento": 0x3D,
    "rx_sostenuto": 0x3E,
    "rx_soft_pedal": 0x3F,
    "rx_bank_select": 0x40,
    # Block 3: Scale Tuning (AL 0x41-0x4C)
    "scale_tuning_c": 0x41,
    "scale_tuning_cs": 0x42,
    "scale_tuning_d": 0x43,
    "scale_tuning_ds": 0x44,
    "scale_tuning_e": 0x45,
    "scale_tuning_f": 0x46,
    "scale_tuning_fs": 0x47,
    "scale_tuning_g": 0x48,
    "scale_tuning_gs": 0x49,
    "scale_tuning_a": 0x4A,
    "scale_tuning_as": 0x4B,
    "scale_tuning_b": 0x4C,
    # Block 4: CAT Control (AL 0x4D-0x52)
    "cat_pitch_control": 0x4D,
    "cat_filter_control": 0x4E,
    "cat_amplitude_control": 0x4F,
    "cat_lfo_pitch_depth": 0x50,
    "cat_lfo_filter_depth": 0x51,
    "cat_lfo_amplitude_depth": 0x52,
    # Block 5: PAT Control (AL 0x53-0x58)
    "pat_pitch_control": 0x53,
    "pat_filter_control": 0x54,
    "pat_amplitude_control": 0x55,
    "pat_lfo_pitch_depth": 0x56,
    "pat_lfo_filter_depth": 0x57,
    "pat_lfo_amplitude_depth": 0x58,
    # Block 6: AC1/AC2 (AL 0x59-0x66)
    "ac1_cc_number": 0x59,
    "ac1_pitch_control": 0x5A,
    "ac1_filter_control": 0x5B,
    "ac1_amplitude_control": 0x5C,
    "ac1_lfo_pitch_depth": 0x5D,
    "ac1_lfo_filter_depth": 0x5E,
    "ac1_lfo_amplitude_depth": 0x5F,
    "ac2_cc_number": 0x60,
    "ac2_pitch_control": 0x61,
    "ac2_filter_control": 0x62,
    "ac2_amplitude_control": 0x63,
    "ac2_lfo_pitch_depth": 0x64,
    "ac2_lfo_filter_depth": 0x65,
    "ac2_lfo_amplitude_depth": 0x66,
    # Block 7: Portamento & Pitch EG (AL 0x67-0x6E)
    "portamento_switch": 0x67,
    "portamento_time": 0x68,
    "pitch_eg_initial_level": 0x69,
    "pitch_eg_attack_time": 0x6A,
    "pitch_eg_release_level": 0x6B,
    "pitch_eg_release_time": 0x6C,
    "velocity_limit_low": 0x6D,
    "velocity_limit_high": 0x6E,
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
    "filter_cutoff": 0x0B,
    "filter_resonance": 0x0C,
    "eg_attack": 0x0D,
    "eg_decay1": 0x0E,
    "eg_decay2": 0x0F,
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
