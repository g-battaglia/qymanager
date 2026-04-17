"""Tests for UDM Device → .syx emit + roundtrip (F1 P1.2d)."""

import pytest

from qymanager.formats.qy70.reader import parse_syx_to_udm
from qymanager.formats.qy70.writer import emit_udm_to_syx
from qymanager.model import Device, DeviceModel, Pattern


class TestEmitSyxFromPassthrough:
    def test_returns_bytes(self, qy70_sysex_data):
        device = parse_syx_to_udm(qy70_sysex_data)
        data = emit_udm_to_syx(device)
        assert isinstance(data, bytes)

    def test_byte_identical_roundtrip(self, qy70_sysex_data):
        device = parse_syx_to_udm(qy70_sysex_data)
        data = emit_udm_to_syx(device)
        assert data == qy70_sysex_data


class TestEmitSyxGuards:
    def test_non_qy70_raises(self):
        device = Device(model=DeviceModel.QY700, patterns=[Pattern()])
        with pytest.raises(ValueError, match="requires QY70"):
            emit_udm_to_syx(device)

    def test_no_raw_raises_not_implemented(self):
        device = Device(model=DeviceModel.QY70, patterns=[Pattern()])
        with pytest.raises(NotImplementedError, match="dense bitstream"):
            emit_udm_to_syx(device)


class TestRoundtripParseEmitParse:
    def test_parse_emit_parse_equivalent(self, qy70_sysex_data):
        d1 = parse_syx_to_udm(qy70_sysex_data)
        emitted = emit_udm_to_syx(d1)
        d2 = parse_syx_to_udm(emitted)
        assert d1.model == d2.model
        assert len(d1.patterns) == len(d2.patterns)
        assert d1.patterns[0].name == d2.patterns[0].name
        assert d1.patterns[0].tempo_bpm == d2.patterns[0].tempo_bpm
        assert set(d1.patterns[0].sections.keys()) == set(
            d2.patterns[0].sections.keys()
        )
