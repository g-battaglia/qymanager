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
    def test_pattern_tempo_is_extracted(self, qy70_sysex_data):
        # `parse_syx_to_udm` now delegates tempo extraction to
        # SyxAnalyzer. The fixture SGT pattern runs at 151 BPM; any
        # plausible musical tempo (30..300) is acceptable here. The
        # old stub returned 120.0 unconditionally, which was a bug.
        device = parse_syx_to_udm(qy70_sysex_data)
        bpm = device.patterns[0].tempo_bpm
        assert 30.0 <= bpm <= 300.0
        assert bpm != 120.0, "tempo should come from the bulk header, not a hardcoded default"

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

    def test_section_map_covers_qy70_layout(self, qy70_sysex_data):
        # Session 33a enum extension: UDM now carries INTRO/FILL_AB/
        # FILL_BA/ENDING alongside the QY700 MAIN/FILL set. Sections
        # 0-5 on a QY70 bulk are preserved verbatim instead of being
        # dropped.
        device = parse_syx_to_udm(qy70_sysex_data)
        section_names = set(device.patterns[0].sections.keys())
        qy70_ok = {
            SectionName.INTRO,
            SectionName.MAIN_A,
            SectionName.MAIN_B,
            SectionName.FILL_AB,
            SectionName.FILL_BA,
            SectionName.ENDING,
        }
        assert section_names.issubset(qy70_ok)

    def test_section_has_8_tracks(self, qy70_sysex_data):
        device = parse_syx_to_udm(qy70_sysex_data)
        for sec in device.patterns[0].sections.values():
            assert len(sec.tracks) == 8
            for trk in sec.tracks:
                assert isinstance(trk, PatternTrack)

    def test_track_voice_populated_when_db_match(self, qy70_sysex_data):
        # Session 33a: when the SyxAnalyzer resolves a track's voice
        # via the 23-signature DB (confidence 1.0), the Voice is
        # populated with the real Bank MSB/LSB/Program. Tracks without
        # a DB match fall back to the zero-Voice default.
        device = parse_syx_to_udm(qy70_sysex_data)
        any_populated = False
        for sec in device.patterns[0].sections.values():
            for trk in sec.tracks:
                assert isinstance(trk.voice, Voice)
                if trk.voice.bank_msb or trk.voice.bank_lsb or trk.voice.program:
                    any_populated = True
        # The SGT fixture is in the DB, so at least one track must
        # surface real voice data.
        assert any_populated


class TestParseSyxValidation:
    def test_udm_validation_passes(self, qy70_sysex_data):
        device = parse_syx_to_udm(qy70_sysex_data)
        errors = device.validate()
        assert errors == [], f"Validation errors: {errors}"
