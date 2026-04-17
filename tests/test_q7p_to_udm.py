"""Tests for Q7P → UDM Device parsing (F1 P1.2a)."""

import struct
import pytest

from qymanager.formats.qy700.reader import parse_q7p_to_udm
from qymanager.model import (
    Device,
    DeviceModel,
    PatternTrack,
    SectionName,
    TimeSig,
    Voice,
)


def _make_q7p(
    size: int = 3072,
    pattern_number: int = 1,
    tempo_bpm_x10: int = 1200,
    name: str = "TEST      ",
) -> bytearray:
    buf = bytearray(size)
    buf[0:16] = b"YQ7PAT     V1.00"
    buf[0x10] = pattern_number
    struct.pack_into(">H", buf, 0x30, 0x0990)
    struct.pack_into(">H", buf, 0x188, tempo_bpm_x10)
    name_bytes = name[:10].encode("ascii").ljust(10, b" ")
    buf[0x876 : 0x876 + 10] = name_bytes
    for i in range(0x9C0, min(0xA90, size)):
        buf[i] = 0xFE
    for i in range(0xB10, size):
        buf[i] = 0xF8
    return buf


@pytest.fixture
def q7p_t01(q7p_data):
    return q7p_data


@pytest.fixture
def q7p_synthetic():
    return bytes(_make_q7p(tempo_bpm_x10=960, name="HELLO     "))


class TestParseQ7pToUdmBasic:
    def test_returns_device(self, q7p_synthetic):
        device = parse_q7p_to_udm(q7p_synthetic)
        assert isinstance(device, Device)

    def test_device_model_qy700(self, q7p_synthetic):
        device = parse_q7p_to_udm(q7p_synthetic)
        assert device.model == DeviceModel.QY700
        assert device.is_qy700

    def test_source_format(self, q7p_synthetic):
        device = parse_q7p_to_udm(q7p_synthetic)
        assert device.source_format == "q7p"

    def test_raw_passthrough(self, q7p_synthetic):
        device = parse_q7p_to_udm(q7p_synthetic)
        assert device._raw_passthrough == q7p_synthetic

    def test_raw_passthrough_byte_identical_fixture(self, q7p_t01):
        device = parse_q7p_to_udm(q7p_t01)
        assert device._raw_passthrough == q7p_t01

    def test_invalid_header_raises(self):
        with pytest.raises(ValueError, match="Invalid Q7P header"):
            parse_q7p_to_udm(b"WRONGHEADER1234" + bytes(3056))

    def test_too_short_raises(self):
        with pytest.raises(ValueError, match="Invalid Q7P header"):
            parse_q7p_to_udm(b"YQ7PAT     V1.0")

    def test_has_one_pattern(self, q7p_synthetic):
        device = parse_q7p_to_udm(q7p_synthetic)
        assert len(device.patterns) == 1


class TestParseQ7pPatternFields:
    def test_pattern_name(self, q7p_synthetic):
        device = parse_q7p_to_udm(q7p_synthetic)
        assert device.patterns[0].name == "HELLO"

    def test_pattern_index(self, q7p_synthetic):
        device = parse_q7p_to_udm(q7p_synthetic)
        assert device.patterns[0].index == 1

    def test_tempo(self, q7p_synthetic):
        device = parse_q7p_to_udm(q7p_synthetic)
        assert device.patterns[0].tempo_bpm == 96.0

    def test_time_sig_default(self, q7p_synthetic):
        device = parse_q7p_to_udm(q7p_synthetic)
        ts = device.patterns[0].time_sig
        assert isinstance(ts, TimeSig)
        assert ts.numerator == 4
        assert ts.denominator == 4


class TestParseQ7pSections:
    def test_has_enabled_sections(self, q7p_synthetic):
        device = parse_q7p_to_udm(q7p_synthetic)
        pat = device.patterns[0]
        assert len(pat.sections) > 0

    def test_section_names_are_sectionname(self, q7p_synthetic):
        device = parse_q7p_to_udm(q7p_synthetic)
        for key in device.patterns[0].sections:
            assert isinstance(key, SectionName)

    def test_section_has_tracks(self, q7p_synthetic):
        device = parse_q7p_to_udm(q7p_synthetic)
        for sec in device.patterns[0].sections.values():
            assert len(sec.tracks) > 0
            for trk in sec.tracks:
                assert isinstance(trk, PatternTrack)

    def test_track_has_voice(self, q7p_synthetic):
        device = parse_q7p_to_udm(q7p_synthetic)
        for sec in device.patterns[0].sections.values():
            for trk in sec.tracks:
                assert isinstance(trk.voice, Voice)


class TestParseQ7pFixture:
    def test_t01_pattern_name(self, q7p_t01):
        device = parse_q7p_to_udm(q7p_t01)
        assert isinstance(device.patterns[0].name, str)

    def test_t01_tempo_reasonable(self, q7p_t01):
        device = parse_q7p_to_udm(q7p_t01)
        tempo = device.patterns[0].tempo_bpm
        assert 30.0 <= tempo <= 300.0

    def test_t01_track_channels_in_range(self, q7p_t01):
        device = parse_q7p_to_udm(q7p_t01)
        for sec in device.patterns[0].sections.values():
            for trk in sec.tracks:
                assert 0 <= trk.midi_channel <= 15

    def test_t01_track_volumes_in_range(self, q7p_t01):
        device = parse_q7p_to_udm(q7p_t01)
        for sec in device.patterns[0].sections.values():
            for trk in sec.tracks:
                assert 0 <= trk.volume <= 127

    def test_t01_track_pans_in_range(self, q7p_t01):
        device = parse_q7p_to_udm(q7p_t01)
        for sec in device.patterns[0].sections.values():
            for trk in sec.tracks:
                assert 0 <= trk.pan <= 127

    def test_t01_validation_passes(self, q7p_t01):
        device = parse_q7p_to_udm(q7p_t01)
        errors = device.validate()
        assert errors == [], f"Validation errors: {errors}"


class TestParseQ7pEmptyTemplate:
    def test_txx_roundtrip(self, q7p_empty_file):
        if not q7p_empty_file.exists():
            pytest.skip("TXX.Q7P not found")
        with open(q7p_empty_file, "rb") as f:
            data = f.read()
        device = parse_q7p_to_udm(data)
        assert device._raw_passthrough == data
        assert device.model == DeviceModel.QY700
