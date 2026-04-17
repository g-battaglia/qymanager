"""Tests for editor ops: get/set UDM fields and XG-message synthesis (F3)."""

import pytest

from qymanager.editor.ops import apply_edits, get_field, make_xg_messages, set_field
from qymanager.model import Device, DeviceModel


def _fresh_device() -> Device:
    return Device(model=DeviceModel.QY70)


class TestGetField:
    def test_system_default(self):
        device = _fresh_device()
        assert get_field(device, "system.master_volume") == 100

    def test_missing_part_slot(self):
        device = _fresh_device()
        assert get_field(device, "multi_part[5].volume") is None

    def test_missing_drum_kit(self):
        device = _fresh_device()
        assert get_field(device, "drum_setup[0].notes[36].level") is None

    def test_variation_none(self):
        device = _fresh_device()
        assert get_field(device, "effects.variation.type_code") is None


class TestSetField:
    def test_system_writes(self):
        device = _fresh_device()
        set_field(device, "system.master_volume", 77)
        assert device.system.master_volume == 77

    def test_transpose_signed_stored(self):
        device = _fresh_device()
        set_field(device, "system.transpose", -5)
        assert device.system.transpose == -5

    def test_autogrow_part(self):
        device = _fresh_device()
        set_field(device, "multi_part[3].volume", 110)
        assert len(device.multi_part) >= 4
        assert device.multi_part[3].volume == 110

    def test_voice_bank_via_replace(self):
        device = _fresh_device()
        set_field(device, "multi_part[0].voice.bank_msb", 127)
        set_field(device, "multi_part[0].voice.program", 24)
        assert device.multi_part[0].voice.bank_msb == 127
        assert device.multi_part[0].voice.program == 24

    def test_autocreate_variation(self):
        device = _fresh_device()
        assert device.effects.variation is None
        set_field(device, "effects.variation.type_code", 12)
        assert device.effects.variation is not None
        assert device.effects.variation.type_code == 12

    def test_autogrow_drum(self):
        device = _fresh_device()
        set_field(device, "drum_setup[0].notes[36].level", 100)
        assert 36 in device.drum_setup[0].notes
        assert device.drum_setup[0].notes[36].level == 100

    def test_range_rejected(self):
        device = _fresh_device()
        with pytest.raises(ValueError):
            set_field(device, "system.master_volume", 200)


class TestApplyEdits:
    def test_batch_success(self):
        device = _fresh_device()
        errors = apply_edits(
            device,
            {
                "system.master_volume": 110,
                "effects.reverb.type_code": 5,
                "multi_part[0].volume": 90,
            },
        )
        assert errors == []
        assert device.system.master_volume == 110
        assert device.effects.reverb.type_code == 5
        assert device.multi_part[0].volume == 90

    def test_partial_failure(self):
        device = _fresh_device()
        errors = apply_edits(
            device,
            {
                "system.master_volume": 110,
                "system.master_volume_BAD": 1,  # unknown path
                "system.transpose": 500,  # out of range
            },
        )
        assert len(errors) == 2
        assert device.system.master_volume == 110  # good edit still applied


class TestMakeXgMessages:
    def test_emits_sysex_for_mapped(self):
        device = _fresh_device()
        out = make_xg_messages(
            device,
            {
                "system.master_volume": 77,
                "effects.reverb.type_code": 3,
            },
        )
        assert len(out) == 2
        for _path, msg in out:
            assert msg[0] == 0xF0 and msg[-1] == 0xF7

    def test_unmapped_path_skipped(self):
        device = _fresh_device()
        out = make_xg_messages(device, {"unknown.field": 5})
        assert out == []

    def test_transpose_encoded_with_offset(self):
        device = _fresh_device()
        out = make_xg_messages(device, {"system.transpose": -4})
        assert len(out) == 1
        _path, msg = out[0]
        assert msg[7] == 60  # -4 + 64
