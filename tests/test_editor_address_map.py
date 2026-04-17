"""Tests for UDM path → XG (AH, AM, AL) address resolution (F3)."""

import pytest

from qymanager.editor.address_map import (
    build_xg_parameter_change,
    resolve_address,
)


class TestFixedPaths:
    def test_master_volume(self):
        assert resolve_address("system.master_volume") == (0x00, 0x00, 0x04)

    def test_transpose(self):
        assert resolve_address("system.transpose") == (0x00, 0x00, 0x06)

    def test_reverb_type(self):
        assert resolve_address("effects.reverb.type_code") == (0x02, 0x01, 0x00)

    def test_chorus_return(self):
        assert resolve_address("effects.chorus.return_level") == (0x02, 0x01, 0x2C)

    def test_variation_type(self):
        assert resolve_address("effects.variation.type_code") == (0x02, 0x01, 0x40)


class TestMultiPart:
    def test_part0_volume(self):
        assert resolve_address("multi_part[0].volume") == (0x08, 0x00, 0x0B)

    def test_part15_bank_msb(self):
        assert resolve_address("multi_part[15].voice.bank_msb") == (0x08, 0x0F, 0x01)

    def test_part15_program(self):
        assert resolve_address("multi_part[15].voice.program") == (0x08, 0x0F, 0x03)

    def test_unknown_part_field(self):
        assert resolve_address("multi_part[0].made_up_field") is None

    def test_index_out_of_range(self):
        assert resolve_address("multi_part[32].volume") is None

    def test_reverb_send(self):
        assert resolve_address("multi_part[5].reverb_send") == (0x08, 0x05, 0x13)

    def test_chorus_send(self):
        assert resolve_address("multi_part[5].chorus_send") == (0x08, 0x05, 0x12)


class TestDrumSetup:
    def test_kit0_note36_level(self):
        assert resolve_address("drum_setup[0].notes[36].level") == (0x30, 0x24, 0x02)

    def test_kit1_note38_pan(self):
        assert resolve_address("drum_setup[1].notes[38].pan") == (0x31, 0x26, 0x04)

    def test_invalid_kit(self):
        assert resolve_address("drum_setup[2].notes[36].level") is None


class TestUnknownPaths:
    def test_unknown_returns_none(self):
        assert resolve_address("foo.bar") is None


class TestBuildXgMessage:
    def test_returns_sysex(self):
        msg = build_xg_parameter_change(0x00, 0x00, 0x04, 100)
        assert msg[0] == 0xF0 and msg[-1] == 0xF7

    def test_yamaha_xg_header(self):
        msg = build_xg_parameter_change(0x00, 0x00, 0x04, 100)
        assert msg[1] == 0x43
        assert msg[3] == 0x4C

    def test_device_number(self):
        msg = build_xg_parameter_change(0x00, 0x00, 0x04, 100, device=3)
        assert msg[2] == 0x13

    def test_data_byte(self):
        msg = build_xg_parameter_change(0x00, 0x00, 0x04, 77)
        assert msg[7] == 77

    def test_rejects_out_of_range_value(self):
        with pytest.raises(ValueError, match="value"):
            build_xg_parameter_change(0x00, 0x00, 0x04, 200)

    def test_rejects_out_of_range_device(self):
        with pytest.raises(ValueError, match="device"):
            build_xg_parameter_change(0x00, 0x00, 0x04, 50, device=16)
