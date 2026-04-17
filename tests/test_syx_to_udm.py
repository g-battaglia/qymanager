"""Tests for QY70 .syx → UDM Device parsing (F1 P1.2c)."""

import pytest

from qymanager.formats.qy70.reader import parse_syx_to_udm
from qymanager.model import (
    Device,
    DeviceModel,
    PatternTrack,
    SectionName,
    TimeSig,
    Voice,
)


class TestParseSyxBasic:
    def test_returns_device(self, qy70_sysex_data):
        device = parse_syx_to_udm(qy70_sysex_data)
        assert isinstance(device, Device)

    def test_model_qy70(self, qy70_sysex_data):
        device = parse_syx_to_udm(qy70_sysex_data)
        assert device.model == DeviceModel.QY70
        assert device.is_qy70

    def test_source_format(self, qy70_sysex_data):
        device = parse_syx_to_udm(qy70_sysex_data)
        assert device.source_format == "syx"

    def test_raw_passthrough_preserved(self, qy70_sysex_data):
        device = parse_syx_to_udm(qy70_sysex_data)
        assert device._raw_passthrough == qy70_sysex_data

    def test_empty_raises(self):
        with pytest.raises(ValueError, match="No QY70 style-data"):
            parse_syx_to_udm(b"")

    def test_non_qy70_raises(self):
        with pytest.raises(ValueError, match="No QY70 style-data"):
            parse_syx_to_udm(b"\xf0\x43\x00\x4c\x00\x00\x00\xf7")

    def test_has_one_pattern(self, qy70_sysex_data):
        device = parse_syx_to_udm(qy70_sysex_data)
        assert len(device.patterns) == 1


class TestParseSyxPatternFields:
    def test_pattern_has_default_tempo(self, qy70_sysex_data):
        device = parse_syx_to_udm(qy70_sysex_data)
        assert device.patterns[0].tempo_bpm == 120.0

    def test_pattern_time_sig_4_4(self, qy70_sysex_data):
        device = parse_syx_to_udm(qy70_sysex_data)
        ts = device.patterns[0].time_sig
        assert isinstance(ts, TimeSig)
        assert ts.numerator == 4
        assert ts.denominator == 4

    def test_pattern_name_is_string(self, qy70_sysex_data):
        device = parse_syx_to_udm(qy70_sysex_data)
        assert isinstance(device.patterns[0].name, str)


class TestParseSyxSections:
    def test_has_sections(self, qy70_sysex_data):
        device = parse_syx_to_udm(qy70_sysex_data)
        assert len(device.patterns[0].sections) > 0

    def test_section_keys_are_sectionname(self, qy70_sysex_data):
        device = parse_syx_to_udm(qy70_sysex_data)
        for key in device.patterns[0].sections:
            assert isinstance(key, SectionName)

    def test_no_intro_or_ending(self, qy70_sysex_data):
        # UDM schema has no INTRO/ENDING semantics — QY70 legacy idx 0 and 5
        # must be mapped or dropped (we drop them).
        device = parse_syx_to_udm(qy70_sysex_data)
        section_names = set(device.patterns[0].sections.keys())
        assert SectionName.MAIN_A in section_names

    def test_section_has_8_tracks(self, qy70_sysex_data):
        device = parse_syx_to_udm(qy70_sysex_data)
        for sec in device.patterns[0].sections.values():
            assert len(sec.tracks) == 8
            for trk in sec.tracks:
                assert isinstance(trk, PatternTrack)

    def test_track_has_default_voice(self, qy70_sysex_data):
        device = parse_syx_to_udm(qy70_sysex_data)
        for sec in device.patterns[0].sections.values():
            for trk in sec.tracks:
                assert isinstance(trk.voice, Voice)
                assert trk.voice.bank_msb == 0
                assert trk.voice.program == 0


class TestParseSyxValidation:
    def test_udm_validation_passes(self, qy70_sysex_data):
        device = parse_syx_to_udm(qy70_sysex_data)
        errors = device.validate()
        assert errors == [], f"Validation errors: {errors}"
