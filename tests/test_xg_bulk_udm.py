"""Tests for XG bulk parser ↔ UDM Device (F2)."""

import pytest

from qymanager.formats.xg_bulk import emit_udm_to_xg_bulk, parse_xg_bulk_to_udm
from qymanager.model import Device, DeviceModel


def _xg(ah: int, am: int, al: int, *data: int, device: int = 0) -> bytes:
    payload = bytes(data)
    return bytes([0xF0, 0x43, 0x10 | device, 0x4C, ah, am, al]) + payload + b"\xF7"


def _bulk(*messages: bytes) -> bytes:
    return b"".join(messages)


class TestParseXgBulkBasic:
    def test_returns_device(self):
        blob = _bulk(_xg(0x00, 0x00, 0x04, 100))
        device = parse_xg_bulk_to_udm(blob)
        assert isinstance(device, Device)

    def test_default_model(self):
        blob = _bulk(_xg(0x00, 0x00, 0x04, 100))
        device = parse_xg_bulk_to_udm(blob)
        assert device.model == DeviceModel.QY70

    def test_custom_model(self):
        blob = _bulk(_xg(0x00, 0x00, 0x04, 100))
        device = parse_xg_bulk_to_udm(blob, device_model=DeviceModel.QY700)
        assert device.model == DeviceModel.QY700

    def test_source_format(self):
        blob = _bulk(_xg(0x00, 0x00, 0x04, 100))
        device = parse_xg_bulk_to_udm(blob)
        assert device.source_format == "xg-bulk"

    def test_raw_passthrough(self):
        blob = _bulk(_xg(0x00, 0x00, 0x04, 100))
        device = parse_xg_bulk_to_udm(blob)
        assert device._raw_passthrough == blob

    def test_empty_stream_raises(self):
        with pytest.raises(ValueError, match="No XG Parameter"):
            parse_xg_bulk_to_udm(b"")


class TestApplySystem:
    def test_master_volume(self):
        blob = _bulk(_xg(0x00, 0x00, 0x04, 77))
        device = parse_xg_bulk_to_udm(blob)
        assert device.system.master_volume == 77

    def test_transpose(self):
        blob = _bulk(_xg(0x00, 0x00, 0x06, 60))  # 60 - 64 = -4
        device = parse_xg_bulk_to_udm(blob)
        assert device.system.transpose == -4

    def test_master_tune_centred(self):
        # 0x0400 is the XG centre = 0 cents
        blob = _bulk(
            _xg(0x00, 0x00, 0x00, 0x00),
            _xg(0x00, 0x00, 0x01, 0x04),
            _xg(0x00, 0x00, 0x02, 0x00),
            _xg(0x00, 0x00, 0x03, 0x00),
        )
        device = parse_xg_bulk_to_udm(blob)
        assert device.system.master_tune == 0

    def test_master_tune_positive(self):
        # 0x0450 = 0x0400 + 80 → +4 cents (≈0.05 cents per step)
        blob = _bulk(
            _xg(0x00, 0x00, 0x00, 0x00),
            _xg(0x00, 0x00, 0x01, 0x04),
            _xg(0x00, 0x00, 0x02, 0x05),
            _xg(0x00, 0x00, 0x03, 0x00),
        )
        device = parse_xg_bulk_to_udm(blob)
        assert device.system.master_tune == 4

    def test_master_tune_negative(self):
        # 0x03B0 = 0x0400 - 80 → -4 cents
        blob = _bulk(
            _xg(0x00, 0x00, 0x00, 0x00),
            _xg(0x00, 0x00, 0x01, 0x03),
            _xg(0x00, 0x00, 0x02, 0x0B),
            _xg(0x00, 0x00, 0x03, 0x00),
        )
        device = parse_xg_bulk_to_udm(blob)
        assert device.system.master_tune == -4

    def test_master_attenuator(self):
        blob = _bulk(_xg(0x00, 0x00, 0x05, 25))
        device = parse_xg_bulk_to_udm(blob)
        assert device.system.master_attenuator == 25


class TestApplyEffects:
    def test_reverb_type(self):
        blob = _bulk(_xg(0x02, 0x01, 0x00, 5))
        device = parse_xg_bulk_to_udm(blob)
        assert device.effects.reverb.type_code == 5

    def test_reverb_return_level(self):
        blob = _bulk(_xg(0x02, 0x01, 0x0C, 80))
        device = parse_xg_bulk_to_udm(blob)
        assert device.effects.reverb.return_level == 80

    def test_chorus_type(self):
        blob = _bulk(_xg(0x02, 0x01, 0x20, 4))
        device = parse_xg_bulk_to_udm(blob)
        assert device.effects.chorus.type_code == 4

    def test_variation_type(self):
        blob = _bulk(_xg(0x02, 0x01, 0x40, 12))
        device = parse_xg_bulk_to_udm(blob)
        assert device.effects.variation is not None
        assert device.effects.variation.type_code == 12


class TestApplyMultiPart:
    def test_autogrow_parts(self):
        blob = _bulk(_xg(0x08, 0x03, 0x01, 64))  # Part 3 Bank MSB
        device = parse_xg_bulk_to_udm(blob)
        assert len(device.multi_part) >= 4

    def test_bank_msb_lsb_program(self):
        blob = _bulk(
            _xg(0x08, 0x00, 0x01, 127),  # Bank MSB
            _xg(0x08, 0x00, 0x02, 0),    # Bank LSB
            _xg(0x08, 0x00, 0x03, 24),   # Program
        )
        device = parse_xg_bulk_to_udm(blob)
        p0 = device.multi_part[0]
        assert p0.voice.bank_msb == 127
        assert p0.voice.bank_lsb == 0
        assert p0.voice.program == 24

    def test_volume_pan_sends(self):
        blob = _bulk(
            _xg(0x08, 0x05, 0x0B, 110),  # Volume
            _xg(0x08, 0x05, 0x0E, 40),   # Pan
            _xg(0x08, 0x05, 0x13, 50),   # Reverb Send
            _xg(0x08, 0x05, 0x12, 30),   # Chorus Send
        )
        device = parse_xg_bulk_to_udm(blob)
        p5 = device.multi_part[5]
        assert p5.volume == 110
        assert p5.pan == 40
        assert p5.reverb_send == 50
        assert p5.chorus_send == 30


class TestAdditive:
    def test_base_device_preserved(self):
        base = parse_xg_bulk_to_udm(_bulk(_xg(0x08, 0x00, 0x03, 7)))
        later = parse_xg_bulk_to_udm(_bulk(_xg(0x08, 0x00, 0x0B, 99)), base_device=base)
        assert later.multi_part[0].voice.program == 7
        assert later.multi_part[0].volume == 99


class TestEmitXgBulk:
    def test_emit_byte_identical(self):
        blob = _bulk(
            _xg(0x08, 0x00, 0x01, 0),
            _xg(0x08, 0x00, 0x03, 24),
            _xg(0x02, 0x01, 0x00, 5),
        )
        device = parse_xg_bulk_to_udm(blob)
        assert emit_udm_to_xg_bulk(device) == blob

    def test_emit_without_raw_raises(self):
        device = Device(model=DeviceModel.QY70)
        with pytest.raises(ValueError, match="raw_passthrough"):
            emit_udm_to_xg_bulk(device)


class TestValidation:
    def test_device_validates(self):
        blob = _bulk(
            _xg(0x00, 0x00, 0x04, 100),
            _xg(0x08, 0x01, 0x01, 0),
            _xg(0x08, 0x01, 0x0B, 100),
        )
        device = parse_xg_bulk_to_udm(blob)
        errors = device.validate()
        assert errors == [], f"Validation errors: {errors}"
