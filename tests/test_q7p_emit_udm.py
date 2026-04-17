"""Tests for UDM Device → Q7P emit + roundtrip (F1 P1.2b)."""

import struct

import pytest

from qymanager.formats.qy700.reader import parse_q7p_to_udm
from qymanager.formats.qy700.writer import emit_udm_to_q7p
from qymanager.model import (
    Device,
    DeviceModel,
    Pattern,
    PatternTrack,
    Section,
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
    buf[0x18A] = 0x1C  # 4/4
    name_bytes = name[:10].encode("ascii").ljust(10, b" ")
    buf[0x876 : 0x876 + 10] = name_bytes
    for i in range(0x9C0, min(0xA90, size)):
        buf[i] = 0xFE
    for i in range(0xB10, size):
        buf[i] = 0xF8
    return buf


@pytest.fixture
def q7p_synthetic():
    return bytes(_make_q7p(tempo_bpm_x10=960, name="HELLO     "))


class TestEmitUdmBasic:
    def test_emit_returns_bytes(self, q7p_synthetic):
        device = parse_q7p_to_udm(q7p_synthetic)
        data = emit_udm_to_q7p(device)
        assert isinstance(data, bytes)

    def test_emit_preserves_size(self, q7p_synthetic):
        device = parse_q7p_to_udm(q7p_synthetic)
        data = emit_udm_to_q7p(device)
        assert len(data) == len(q7p_synthetic)

    def test_emit_keeps_header(self, q7p_synthetic):
        device = parse_q7p_to_udm(q7p_synthetic)
        data = emit_udm_to_q7p(device)
        assert data[:16] == b"YQ7PAT     V1.00"

    def test_emit_no_patterns_raises(self):
        device = Device(model=DeviceModel.QY700, patterns=[])
        with pytest.raises(ValueError, match="no patterns"):
            emit_udm_to_q7p(device)

    def test_emit_no_raw_passthrough_creates_minimal(self):
        pattern = Pattern(
            index=3,
            name="SCRATCH",
            tempo_bpm=100.0,
            time_sig=TimeSig(4, 4),
            sections={SectionName.MAIN_A: Section(name=SectionName.MAIN_A, tracks=[])},
        )
        device = Device(model=DeviceModel.QY700, patterns=[pattern])
        data = emit_udm_to_q7p(device)
        assert len(data) == 3072
        assert data[:16] == b"YQ7PAT     V1.00"
        assert data[0x10] == 3


class TestEmitUpdatesFields:
    def test_tempo_updated(self, q7p_synthetic):
        device = parse_q7p_to_udm(q7p_synthetic)
        device.patterns[0].tempo_bpm = 140.0
        data = emit_udm_to_q7p(device)
        raw = struct.unpack(">H", data[0x188:0x18A])[0]
        assert raw == 1400

    def test_name_updated(self, q7p_synthetic):
        device = parse_q7p_to_udm(q7p_synthetic)
        device.patterns[0].name = "NEWNAME"
        data = emit_udm_to_q7p(device)
        assert data[0x876:0x880].rstrip(b" ") == b"NEWNAME"

    def test_time_sig_updated(self, q7p_synthetic):
        device = parse_q7p_to_udm(q7p_synthetic)
        object.__setattr__(device.patterns[0], "time_sig", TimeSig(3, 4))
        data = emit_udm_to_q7p(device)
        assert data[0x18A] == 0x14

    def test_track_volume_updated(self, q7p_synthetic):
        device = parse_q7p_to_udm(q7p_synthetic)
        for sec in device.patterns[0].sections.values():
            sec.tracks[0].volume = 77
            break
        data = emit_udm_to_q7p(device)
        assert data[0x226] == 77

    def test_track_voice_updated(self, q7p_synthetic):
        device = parse_q7p_to_udm(q7p_synthetic)
        for sec in device.patterns[0].sections.values():
            sec.tracks[2].voice = Voice(bank_msb=0, bank_lsb=0, program=24)
            break
        data = emit_udm_to_q7p(device)
        assert data[0x1F6 + 2] == 24


class TestRoundtripFromFixture:
    def test_emit_parse_preserves_name(self, q7p_data):
        device = parse_q7p_to_udm(q7p_data)
        emitted = emit_udm_to_q7p(device)
        device2 = parse_q7p_to_udm(emitted)
        assert device2.patterns[0].name == device.patterns[0].name

    def test_emit_parse_preserves_tempo(self, q7p_data):
        device = parse_q7p_to_udm(q7p_data)
        emitted = emit_udm_to_q7p(device)
        device2 = parse_q7p_to_udm(emitted)
        assert device2.patterns[0].tempo_bpm == device.patterns[0].tempo_bpm

    def test_emit_parse_preserves_time_sig(self, q7p_data):
        device = parse_q7p_to_udm(q7p_data)
        emitted = emit_udm_to_q7p(device)
        device2 = parse_q7p_to_udm(emitted)
        assert device2.patterns[0].time_sig == device.patterns[0].time_sig

    def test_emit_parse_preserves_section_keys(self, q7p_data):
        device = parse_q7p_to_udm(q7p_data)
        emitted = emit_udm_to_q7p(device)
        device2 = parse_q7p_to_udm(emitted)
        assert set(device2.patterns[0].sections.keys()) == set(
            device.patterns[0].sections.keys()
        )

    def test_emit_parse_preserves_track_voices(self, q7p_data):
        device = parse_q7p_to_udm(q7p_data)
        emitted = emit_udm_to_q7p(device)
        device2 = parse_q7p_to_udm(emitted)
        first_name = next(iter(device.patterns[0].sections))
        tracks1 = device.patterns[0].sections[first_name].tracks
        tracks2 = device2.patterns[0].sections[first_name].tracks
        assert len(tracks1) == len(tracks2)
        for a, b in zip(tracks1, tracks2):
            assert a.voice.bank_msb == b.voice.bank_msb
            assert a.voice.bank_lsb == b.voice.bank_lsb
            assert a.voice.program == b.voice.program

    def test_emit_parse_preserves_track_volumes(self, q7p_data):
        device = parse_q7p_to_udm(q7p_data)
        emitted = emit_udm_to_q7p(device)
        device2 = parse_q7p_to_udm(emitted)
        first_name = next(iter(device.patterns[0].sections))
        tracks1 = device.patterns[0].sections[first_name].tracks
        tracks2 = device2.patterns[0].sections[first_name].tracks
        for a, b in zip(tracks1, tracks2):
            assert a.volume == b.volume
            assert a.pan == b.pan
            assert a.reverb_send == b.reverb_send
            assert a.chorus_send == b.chorus_send

    def test_byte_identical_no_edits(self, q7p_data):
        device = parse_q7p_to_udm(q7p_data)
        emitted = emit_udm_to_q7p(device)
        assert len(emitted) == len(q7p_data)
        assert emitted[:16] == q7p_data[:16]
