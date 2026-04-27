"""Completeness + round-trip tests for Multi Part XG editor coverage.

Verifies that every MultiPart field has:
1. An entry in address_map
2. A validation spec in schema
3. Correct XG parse/emit round-trip
"""

import pytest

from qymanager.editor.address_map import (
    _MULTI_PART_AL,
    build_xg_parameter_change,
    resolve_address,
)
from qymanager.editor.ops import get_field, make_xg_messages, set_field
from qymanager.editor.schema import _MULTI_PART_SPECS, encode_xg, spec_for, validate
from qymanager.formats.xg_bulk import XGRawMessage, _apply_multi_part
from qymanager.model import Device, DeviceModel, MultiPart, Voice


def _fresh_device() -> Device:
    return Device(model=DeviceModel.QY70)


class TestFieldCoverage:
    def test_all_address_entries_have_schema(self):
        """Every field in address_map has a validation spec in schema."""
        missing = []
        for field_name in _MULTI_PART_AL:
            if spec_for(f"multi_part[0].{field_name}") is None:
                missing.append(field_name)
        assert missing == [], f"Fields in address_map without schema spec: {missing}"

    def test_all_schema_entries_have_address(self):
        """Every field in schema has an address_map entry."""
        missing = []
        for field_name in _MULTI_PART_SPECS:
            if field_name not in _MULTI_PART_AL:
                missing.append(field_name)
        assert missing == [], f"Fields in schema without address_map: {missing}"


class TestXgBulkParseRoundTrip:
    """Parse a synthetic XG message → verify UDM value."""

    def _make_msg(self, al: int, value: int, part: int = 0) -> XGRawMessage:
        return XGRawMessage(
            ah=0x08, am=part, al=al,
            data=bytes([value & 0x7F]),
            raw=build_xg_parameter_change(0x08, part, al, value & 0x7F),
        )

    def _parse(self, al: int, value: int, part: int = 0) -> MultiPart:
        device = _fresh_device()
        _apply_multi_part(device, self._make_msg(al, value, part))
        return device.multi_part[part]

    @pytest.mark.parametrize(
        "al, field, xg_val, expected_udm",
        [
            (0x00, "element_reserve", 4, 4),
            (0x07, "part_mode", 2, 2),
            (0x08, "note_shift", 0x3C, -4),  # 0x3C = 60 → 60-64 = -4
            (0x09, "detune", 0x30, -16),  # 0x30 = 48 → 48-64 = -16
            (0x0B, "volume", 100, 100),
            (0x0C, "velocity_sense_depth", 80, 80),
            (0x0D, "velocity_sense_offset", 50, 50),
            (0x0E, "pan", 32, 32),
            (0x0F, "note_limit_low", 24, 24),
            (0x10, "note_limit_high", 96, 96),
            (0x11, "dry_level", 127, 127),
            (0x12, "chorus_send", 40, 40),
            (0x13, "reverb_send", 60, 60),
            (0x14, "variation_send", 30, 30),
            (0x15, "vibrato_rate", 0x30, -16),
            (0x16, "vibrato_depth", 0x50, 16),
            (0x17, "vibrato_delay", 0x40, 0),
            (0x18, "cutoff", 0x30, -16),
            (0x19, "resonance", 0x50, 16),
            (0x1A, "eg_attack", 0x3A, -6),
            (0x1B, "eg_decay", 0x46, 6),
            (0x1C, "eg_release", 0x40, 0),
            (0x1D, "mw_pitch_control", 0x44, 4),
            (0x1E, "mw_filter_control", 0x30, -16),
            (0x1F, "mw_amplitude_control", 0x50, 16),
            (0x20, "mw_lfo_pitch_depth", 20, 20),
            (0x21, "mw_lfo_filter_depth", 5, 5),
            (0x22, "mw_lfo_amplitude_depth", 0, 0),
            (0x24, "bend_filter_control", 0x30, -16),
            (0x25, "bend_amplitude_control", 0x50, 16),
            (0x26, "bend_lfo_pitch_depth", 0x44, 4),
            (0x27, "bend_lfo_filter_depth", 0x3C, -4),
            (0x28, "bend_lfo_amplitude_depth", 0x40, 0),
            # Rx switches
            (0x30, "rx_pitch_bend", 0, False),
            (0x30, "rx_pitch_bend", 1, True),
            (0x40, "rx_bank_select", 0, False),
            # Scale tuning
            (0x41, "scale_tuning_c", 0x44, 4),
            (0x4C, "scale_tuning_b", 0x3C, -4),
            # CAT / PAT
            (0x4D, "cat_pitch_control", 0x44, 4),
            (0x53, "pat_pitch_control", 0x3C, -4),
            # AC1/AC2
            (0x59, "ac1_cc_number", 16, 16),
            (0x60, "ac2_cc_number", 17, 17),
            # Portamento & Pitch EG
            (0x67, "portamento_switch", 1, True),
            (0x68, "portamento_time", 64, 64),
            (0x69, "pitch_eg_initial_level", 0x30, -16),
            (0x6D, "velocity_limit_low", 10, 10),
            (0x6E, "velocity_limit_high", 100, 100),
        ],
    )
    def test_parse_xg_to_udm(self, al, field, xg_val, expected_udm):
        p = self._parse(al, xg_val)
        actual = getattr(p, field)
        assert actual == expected_udm, (
            f"AL=0x{al:02X} field={field}: XG {xg_val} → expected {expected_udm}, got {actual}"
        )


class TestEditorSetEmitRoundTrip:
    """set_field → make_xg_messages → parse back → same value."""

    @pytest.mark.parametrize(
        "field, value",
        [
            ("cutoff", -10),
            ("resonance", 15),
            ("eg_attack", -6),
            ("eg_decay", 6),
            ("eg_release", 0),
            ("vibrato_rate", -20),
            ("vibrato_depth", 10),
            ("vibrato_delay", -5),
            ("mw_pitch_control", 12),
            ("mw_filter_control", -30),
            ("mw_amplitude_control", 20),
            ("mw_lfo_pitch_depth", 50),
            ("mw_lfo_filter_depth", 10),
            ("bend_pitch", 12),
            ("bend_filter_control", -10),
            ("bend_amplitude_control", 5),
            ("bend_lfo_pitch_depth", -8),
            ("volume", 90),
            ("pan", 100),
            ("reverb_send", 60),
            ("chorus_send", 30),
            ("variation_send", 10),
            ("note_shift", -5),
            ("element_reserve", 8),
            ("part_mode", 2),
            ("velocity_sense_depth", 80),
            ("velocity_sense_offset", 50),
            ("note_limit_low", 24),
            ("note_limit_high", 96),
            ("portamento_time", 64),
            ("velocity_limit_low", 10),
            ("velocity_limit_high", 100),
        ],
    )
    def test_set_emit_parse_roundtrip(self, field, value):
        path = f"multi_part[0].{field}"
        device = _fresh_device()
        set_field(device, path, value)
        assert get_field(device, path) == value

        msgs = make_xg_messages(device, {path: value})
        assert len(msgs) >= 1
        _, sysex = msgs[0]
        assert sysex[0] == 0xF0 and sysex[-1] == 0xF7

        device2 = _fresh_device()
        xg_msg = XGRawMessage(
            ah=sysex[4], am=sysex[5], al=sysex[6],
            data=bytes([sysex[7]]),
            raw=sysex,
        )
        _apply_multi_part(device2, xg_msg)
        actual = getattr(device2.multi_part[0], field)
        assert actual == value, f"{field}: set {value} → emit → parse = {actual}"


class TestDetuneEmit:
    def test_detune_emits_two_messages(self):
        device = _fresh_device()
        msgs = make_xg_messages(device, {"multi_part[0].detune": 5})
        assert len(msgs) == 2
        _, msg1 = msgs[0]
        _, msg2 = msgs[1]
        assert msg1[6] == 0x09  # AL = detune MSB
        assert msg2[6] == 0x0A  # AL = detune LSB


class TestNewFieldSchemaValidation:
    @pytest.mark.parametrize(
        "field, good, bad_lo, bad_hi",
        [
            ("vibrato_rate", 0, -65, 64),
            ("mw_pitch_control", 0, -25, 25),
            ("mw_lfo_pitch_depth", 50, -1, 128),
            ("element_reserve", 16, -1, 33),
            ("part_mode", 2, -1, 4),
            ("velocity_limit_low", 64, 0, 128),
            ("velocity_limit_high", 64, 0, 128),
            ("ac1_cc_number", 50, -1, 96),
            ("portamento_time", 64, -1, 128),
        ],
    )
    def test_validate_ranges(self, field, good, bad_lo, bad_hi):
        path = f"multi_part[0].{field}"
        assert validate(path, good) == good
        with pytest.raises(ValueError):
            validate(path, bad_lo)
        with pytest.raises(ValueError):
            validate(path, bad_hi)

    def test_key_on_assign_enum(self):
        path = "multi_part[0].key_on_assign"
        assert validate(path, "single") == "single"
        assert validate(path, "multi") == "multi"
        assert validate(path, "inst") == "inst"
        with pytest.raises(ValueError):
            validate(path, "bogus")
