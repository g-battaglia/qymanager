"""Tests for editor field schema validation + XG encoding (F3)."""

import pytest

from qymanager.editor.schema import encode_xg, spec_for, validate


class TestSpecLookup:
    def test_fixed_path(self):
        assert spec_for("system.master_volume") is not None

    def test_multi_part_path(self):
        assert spec_for("multi_part[3].volume") is not None

    def test_drum_path(self):
        assert spec_for("drum_setup[0].notes[36].level") is not None

    def test_unknown_path(self):
        assert spec_for("nonsense.foo") is None


class TestValidateRanges:
    def test_master_volume_ok(self):
        assert validate("system.master_volume", 100) == 100

    def test_master_volume_too_high(self):
        with pytest.raises(ValueError):
            validate("system.master_volume", 200)

    def test_master_volume_negative(self):
        with pytest.raises(ValueError):
            validate("system.master_volume", -1)

    def test_transpose_signed(self):
        assert validate("system.transpose", -12) == -12
        assert validate("system.transpose", 24) == 24

    def test_transpose_out_of_range(self):
        with pytest.raises(ValueError):
            validate("system.transpose", 25)

    def test_reverb_type_code(self):
        assert validate("effects.reverb.type_code", 5) == 5

    def test_variation_type_code(self):
        assert validate("effects.variation.type_code", 42) == 42
        with pytest.raises(ValueError):
            validate("effects.variation.type_code", 43)


class TestValidateEnum:
    def test_string_input(self):
        assert validate("effects.variation.connection", "system") == "system"

    def test_int_input(self):
        assert validate("effects.variation.connection", 1) == 1

    def test_bad_string(self):
        with pytest.raises(ValueError):
            validate("effects.variation.connection", "bogus")

    def test_bad_int(self):
        with pytest.raises(ValueError):
            validate("effects.variation.connection", 5)


class TestEncodeXg:
    def test_master_volume_passthrough(self):
        assert encode_xg("system.master_volume", 100) == 100

    def test_transpose_offset(self):
        assert encode_xg("system.transpose", 0) == 64
        assert encode_xg("system.transpose", -4) == 60
        assert encode_xg("system.transpose", 12) == 76

    def test_cutoff_signed(self):
        assert encode_xg("multi_part[0].cutoff", 0) == 64
        assert encode_xg("multi_part[0].cutoff", -10) == 54

    def test_drum_pan_passthrough(self):
        assert encode_xg("drum_setup[0].notes[36].pan", 100) == 100

    def test_variation_connection_enum(self):
        assert encode_xg("effects.variation.connection", "system") == 0
        assert encode_xg("effects.variation.connection", "insertion") == 1

    def test_string_int_coercion(self):
        assert encode_xg("system.master_volume", "77") == 77

    def test_unknown_path(self):
        with pytest.raises(ValueError, match="unknown"):
            encode_xg("nonsense.foo", 0)


class TestBendPitch:
    def test_udm_zero_to_xg(self):
        assert encode_xg("multi_part[0].bend_pitch", 2) == 0x40

    def test_bend_max(self):
        assert encode_xg("multi_part[0].bend_pitch", 24) == 0x40 + 22

    def test_bend_out_of_range(self):
        with pytest.raises(ValueError):
            encode_xg("multi_part[0].bend_pitch", 25)
