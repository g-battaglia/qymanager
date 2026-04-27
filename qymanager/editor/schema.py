"""Per-field validation + value encoding for UDM editing.

Two responsibilities:

1. `validate(path, value)` — verify an edit against the field's allowed
   range/enum. Raises `ValueError` on invalid values; returns the
   coerced value on success (e.g. int for numeric fields).
2. `encode_xg(path, value)` — convert a UDM-semantic value (which may
   be signed, a bool, or an enum name) into the 7-bit byte that the XG
   Parameter Change data byte expects.

Source of authority for ranges: `qymanager.model` `.validate()` methods
and `wiki/xg-parameters.md` encoding tables.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Optional, Union


@dataclass(frozen=True)
class Range:
    lo: int
    hi: int
    offset: int = 0  # XG byte = udm_value + offset

    def check(self, value: int) -> None:
        if not self.lo <= value <= self.hi:
            raise ValueError(f"value must be {self.lo}..{self.hi}, got {value}")

    def to_xg(self, value: int) -> int:
        self.check(value)
        return value + self.offset


@dataclass(frozen=True)
class Enum:
    options: tuple[str, ...]

    def check(self, value: Union[str, int]) -> int:
        if isinstance(value, int):
            if not 0 <= value < len(self.options):
                raise ValueError(
                    f"value must be 0..{len(self.options) - 1}, got {value}"
                )
            return value
        try:
            return self.options.index(value)
        except ValueError:
            raise ValueError(
                f"value must be one of {self.options}, got {value!r}"
            ) from None

    def to_xg(self, value: Union[str, int]) -> int:
        return self.check(value)


Spec = Union[Range, Enum]


_MIDI_7BIT = Range(0, 127)
_MIDI_SIGNED = Range(-64, 63, offset=64)  # 0x00..0x7F with 0x40 center
_TRANSPOSE = Range(-24, 24, offset=64)
_TUNE = Range(-100, 100, offset=0)  # stored as 4-nibble, pre-encoded
_REVERB_TYPE = Range(0, 10)
_CHORUS_TYPE = Range(0, 10)
_VARIATION_TYPE = Range(0, 42)
_VARIATION_CONNECTION = Enum(("system", "insertion"))


_FIXED_SPECS: dict[str, Spec] = {
    "system.master_tune": _TUNE,
    "system.master_volume": _MIDI_7BIT,
    "system.transpose": _TRANSPOSE,
    "effects.reverb.type_code": _REVERB_TYPE,
    "effects.reverb.return_level": _MIDI_7BIT,
    "effects.reverb.pan": _MIDI_7BIT,
    "effects.chorus.type_code": _CHORUS_TYPE,
    "effects.chorus.return_level": _MIDI_7BIT,
    "effects.chorus.pan": _MIDI_7BIT,
    "effects.chorus.send_to_reverb": _MIDI_7BIT,
    "effects.variation.type_code": _VARIATION_TYPE,
    "effects.variation.return_level": _MIDI_7BIT,
    "effects.variation.pan": _MIDI_7BIT,
    "effects.variation.send_to_reverb": _MIDI_7BIT,
    "effects.variation.send_to_chorus": _MIDI_7BIT,
    "effects.variation.connection": _VARIATION_CONNECTION,
}


_BOOL_SWITCH = Range(0, 1)
_CC_NUMBER = Range(0, 95)

_MULTI_PART_SPECS: dict[str, Spec] = {
    # Block 1: Voice, mode, mixer, LFO, EG (AL 0x00-0x28)
    "element_reserve": Range(0, 32),
    "voice.bank_msb": _MIDI_7BIT,
    "voice.bank_lsb": _MIDI_7BIT,
    "voice.program": _MIDI_7BIT,
    "rx_channel": Range(0, 16),
    "mono_poly": Enum(("mono", "poly")),
    "key_on_assign": Enum(("single", "multi", "inst")),
    "part_mode": Range(0, 3),
    "note_shift": _TRANSPOSE,
    "detune": _MIDI_SIGNED,
    "volume": _MIDI_7BIT,
    "velocity_sense_depth": _MIDI_7BIT,
    "velocity_sense_offset": _MIDI_7BIT,
    "pan": _MIDI_7BIT,
    "note_limit_low": _MIDI_7BIT,
    "note_limit_high": _MIDI_7BIT,
    "dry_level": _MIDI_7BIT,
    "reverb_send": _MIDI_7BIT,
    "chorus_send": _MIDI_7BIT,
    "variation_send": _MIDI_7BIT,
    "vibrato_rate": _MIDI_SIGNED,
    "vibrato_depth": _MIDI_SIGNED,
    "vibrato_delay": _MIDI_SIGNED,
    "cutoff": _MIDI_SIGNED,
    "resonance": _MIDI_SIGNED,
    "eg_attack": _MIDI_SIGNED,
    "eg_decay": _MIDI_SIGNED,
    "eg_release": _MIDI_SIGNED,
    "mw_pitch_control": _TRANSPOSE,
    "mw_filter_control": _MIDI_SIGNED,
    "mw_amplitude_control": _MIDI_SIGNED,
    "mw_lfo_pitch_depth": _MIDI_7BIT,
    "mw_lfo_filter_depth": _MIDI_7BIT,
    "mw_lfo_amplitude_depth": _MIDI_7BIT,
    "bend_pitch": Range(0, 24, offset=-2 + 0x40),
    "bend_filter_control": _MIDI_SIGNED,
    "bend_amplitude_control": _MIDI_SIGNED,
    "bend_lfo_pitch_depth": _MIDI_SIGNED,
    "bend_lfo_filter_depth": _MIDI_SIGNED,
    "bend_lfo_amplitude_depth": _MIDI_SIGNED,
    # Block 2: Receive Switches (AL 0x30-0x40)
    "rx_pitch_bend": _BOOL_SWITCH,
    "rx_channel_aftertouch": _BOOL_SWITCH,
    "rx_program_change": _BOOL_SWITCH,
    "rx_control_change": _BOOL_SWITCH,
    "rx_poly_aftertouch": _BOOL_SWITCH,
    "rx_note_messages": _BOOL_SWITCH,
    "rx_rpn": _BOOL_SWITCH,
    "rx_nrpn": _BOOL_SWITCH,
    "rx_modulation": _BOOL_SWITCH,
    "rx_volume": _BOOL_SWITCH,
    "rx_pan": _BOOL_SWITCH,
    "rx_expression": _BOOL_SWITCH,
    "rx_hold_pedal": _BOOL_SWITCH,
    "rx_portamento": _BOOL_SWITCH,
    "rx_sostenuto": _BOOL_SWITCH,
    "rx_soft_pedal": _BOOL_SWITCH,
    "rx_bank_select": _BOOL_SWITCH,
    # Block 3: Scale Tuning (AL 0x41-0x4C)
    "scale_tuning_c": _MIDI_SIGNED,
    "scale_tuning_cs": _MIDI_SIGNED,
    "scale_tuning_d": _MIDI_SIGNED,
    "scale_tuning_ds": _MIDI_SIGNED,
    "scale_tuning_e": _MIDI_SIGNED,
    "scale_tuning_f": _MIDI_SIGNED,
    "scale_tuning_fs": _MIDI_SIGNED,
    "scale_tuning_g": _MIDI_SIGNED,
    "scale_tuning_gs": _MIDI_SIGNED,
    "scale_tuning_a": _MIDI_SIGNED,
    "scale_tuning_as": _MIDI_SIGNED,
    "scale_tuning_b": _MIDI_SIGNED,
    # Block 4: CAT Control (AL 0x4D-0x52)
    "cat_pitch_control": _TRANSPOSE,
    "cat_filter_control": _MIDI_SIGNED,
    "cat_amplitude_control": _MIDI_SIGNED,
    "cat_lfo_pitch_depth": _MIDI_7BIT,
    "cat_lfo_filter_depth": _MIDI_7BIT,
    "cat_lfo_amplitude_depth": _MIDI_7BIT,
    # Block 5: PAT Control (AL 0x53-0x58)
    "pat_pitch_control": _TRANSPOSE,
    "pat_filter_control": _MIDI_SIGNED,
    "pat_amplitude_control": _MIDI_SIGNED,
    "pat_lfo_pitch_depth": _MIDI_7BIT,
    "pat_lfo_filter_depth": _MIDI_7BIT,
    "pat_lfo_amplitude_depth": _MIDI_7BIT,
    # Block 6: AC1/AC2 (AL 0x59-0x66)
    "ac1_cc_number": _CC_NUMBER,
    "ac1_pitch_control": _TRANSPOSE,
    "ac1_filter_control": _MIDI_SIGNED,
    "ac1_amplitude_control": _MIDI_SIGNED,
    "ac1_lfo_pitch_depth": _MIDI_7BIT,
    "ac1_lfo_filter_depth": _MIDI_7BIT,
    "ac1_lfo_amplitude_depth": _MIDI_7BIT,
    "ac2_cc_number": _CC_NUMBER,
    "ac2_pitch_control": _TRANSPOSE,
    "ac2_filter_control": _MIDI_SIGNED,
    "ac2_amplitude_control": _MIDI_SIGNED,
    "ac2_lfo_pitch_depth": _MIDI_7BIT,
    "ac2_lfo_filter_depth": _MIDI_7BIT,
    "ac2_lfo_amplitude_depth": _MIDI_7BIT,
    # Block 7: Portamento & Pitch EG (AL 0x67-0x6E)
    "portamento_switch": _BOOL_SWITCH,
    "portamento_time": _MIDI_7BIT,
    "pitch_eg_initial_level": _MIDI_SIGNED,
    "pitch_eg_attack_time": _MIDI_SIGNED,
    "pitch_eg_release_level": _MIDI_SIGNED,
    "pitch_eg_release_time": _MIDI_SIGNED,
    "velocity_limit_low": Range(1, 127),
    "velocity_limit_high": Range(1, 127),
}


_DRUM_NOTE_SPECS: dict[str, Spec] = {
    "pitch_coarse": _MIDI_SIGNED,
    "pitch_fine": _MIDI_SIGNED,
    "level": _MIDI_7BIT,
    "pan": _MIDI_7BIT,
    "reverb_send": _MIDI_7BIT,
    "chorus_send": _MIDI_7BIT,
    "variation_send": _MIDI_7BIT,
    "filter_cutoff": _MIDI_SIGNED,
    "filter_resonance": _MIDI_SIGNED,
    "eg_attack": _MIDI_SIGNED,
    "eg_decay1": _MIDI_SIGNED,
    "eg_decay2": _MIDI_SIGNED,
    "alt_group": _MIDI_7BIT,
    "note_off_mode": Enum(("standard", "disabled")),
    "key_assign": Enum(("single", "multi")),
}


_RX_MULTI = re.compile(r"^multi_part\[(\d+)\]\.(.+)$")
_RX_DRUM = re.compile(r"^drum_setup\[(\d+)\]\.notes\[(\d+)\]\.(.+)$")


def spec_for(path: str) -> Optional[Spec]:
    """Return the validation spec for a UDM path, or None if unmapped."""
    if path in _FIXED_SPECS:
        return _FIXED_SPECS[path]
    m = _RX_MULTI.match(path)
    if m is not None:
        return _MULTI_PART_SPECS.get(m.group(2))
    m = _RX_DRUM.match(path)
    if m is not None:
        return _DRUM_NOTE_SPECS.get(m.group(3))
    return None


def validate(path: str, value: Any) -> Union[int, str]:
    """Validate `value` against the field spec at `path`.

    Returns the coerced UDM-semantic value (typically int, or str for
    enum inputs). Raises ValueError on unknown path or out-of-range.
    """
    spec = spec_for(path)
    if spec is None:
        raise ValueError(f"unknown UDM path: {path}")
    if isinstance(spec, Range):
        if isinstance(value, str):
            try:
                value = int(value, 0)
            except ValueError:
                raise ValueError(f"{path}: expected integer, got {value!r}") from None
        if not isinstance(value, int):
            raise ValueError(f"{path}: expected integer, got {type(value).__name__}")
        spec.check(value)
        return value
    # Enum
    if isinstance(value, (str, int)):
        spec.check(value)
        return value
    raise ValueError(f"{path}: expected enum member, got {type(value).__name__}")


def encode_xg(path: str, value: Any) -> int:
    """Convert a UDM value at `path` to the XG data byte (0..127)."""
    spec = spec_for(path)
    if spec is None:
        raise ValueError(f"unknown UDM path: {path}")
    if isinstance(spec, Range):
        if isinstance(value, str):
            value = int(value, 0)
        if not isinstance(value, int):
            raise ValueError(f"{path}: expected integer, got {type(value).__name__}")
        return spec.to_xg(value)
    return spec.to_xg(value)
