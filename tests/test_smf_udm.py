"""Tests for SMF ↔ UDM Device (F1 P1.3)."""

import io

import mido
import pytest

from qymanager.formats.smf import emit_udm_to_smf, parse_smf_to_udm
from qymanager.model import (
    Device,
    DeviceModel,
    EventKind,
    MidiEvent,
    Song,
    SongTrack,
    SongTrackKind,
    TimeSig,
)


@pytest.fixture
def tiny_smf_bytes():
    mid = mido.MidiFile(type=1, ticks_per_beat=480)
    conductor = mido.MidiTrack()
    conductor.append(mido.MetaMessage("set_tempo", tempo=500000, time=0))  # 120 BPM
    conductor.append(mido.MetaMessage("time_signature", numerator=4, denominator=4, time=0))
    conductor.append(mido.MetaMessage("track_name", name="HELLO", time=0))
    mid.tracks.append(conductor)

    track = mido.MidiTrack()
    track.append(mido.Message("program_change", channel=0, program=24, time=0))
    track.append(mido.Message("note_on", channel=0, note=60, velocity=100, time=0))
    track.append(mido.Message("note_off", channel=0, note=60, velocity=64, time=480))
    track.append(mido.Message("control_change", channel=0, control=7, value=100, time=0))
    mid.tracks.append(track)

    buf = io.BytesIO()
    mid.save(file=buf)
    return buf.getvalue()


class TestParseSmfBasic:
    def test_returns_device(self, tiny_smf_bytes):
        device = parse_smf_to_udm(tiny_smf_bytes)
        assert isinstance(device, Device)

    def test_default_model_qy70(self, tiny_smf_bytes):
        device = parse_smf_to_udm(tiny_smf_bytes)
        assert device.model == DeviceModel.QY70

    def test_override_model(self, tiny_smf_bytes):
        device = parse_smf_to_udm(tiny_smf_bytes, device_model=DeviceModel.QY700)
        assert device.model == DeviceModel.QY700

    def test_source_format_smf(self, tiny_smf_bytes):
        device = parse_smf_to_udm(tiny_smf_bytes)
        assert device.source_format == "smf"

    def test_raw_passthrough(self, tiny_smf_bytes):
        device = parse_smf_to_udm(tiny_smf_bytes)
        assert device._raw_passthrough == tiny_smf_bytes


class TestParseSmfSong:
    def test_one_song(self, tiny_smf_bytes):
        device = parse_smf_to_udm(tiny_smf_bytes)
        assert len(device.songs) == 1

    def test_tempo_extracted(self, tiny_smf_bytes):
        device = parse_smf_to_udm(tiny_smf_bytes)
        assert device.songs[0].tempo_bpm == 120.0

    def test_time_sig_extracted(self, tiny_smf_bytes):
        device = parse_smf_to_udm(tiny_smf_bytes)
        ts = device.songs[0].time_sig
        assert ts.numerator == 4 and ts.denominator == 4

    def test_song_name(self, tiny_smf_bytes):
        device = parse_smf_to_udm(tiny_smf_bytes)
        assert device.songs[0].name == "HELLO"


class TestParseSmfEvents:
    def test_track_count(self, tiny_smf_bytes):
        device = parse_smf_to_udm(tiny_smf_bytes)
        assert len(device.songs[0].tracks) == 1

    def test_event_kinds(self, tiny_smf_bytes):
        device = parse_smf_to_udm(tiny_smf_bytes)
        kinds = [e.kind for e in device.songs[0].tracks[0].events]
        assert EventKind.PROG_CHANGE in kinds
        assert EventKind.NOTE_ON in kinds
        assert EventKind.NOTE_OFF in kinds
        assert EventKind.CC in kinds

    def test_note_on_data(self, tiny_smf_bytes):
        device = parse_smf_to_udm(tiny_smf_bytes)
        note_on = next(
            e for e in device.songs[0].tracks[0].events if e.kind == EventKind.NOTE_ON
        )
        assert note_on.data1 == 60
        assert note_on.data2 == 100
        assert note_on.tick == 0

    def test_note_off_tick(self, tiny_smf_bytes):
        device = parse_smf_to_udm(tiny_smf_bytes)
        note_off = next(
            e for e in device.songs[0].tracks[0].events if e.kind == EventKind.NOTE_OFF
        )
        assert note_off.tick == 480


class TestZeroVelocityNoteOn:
    def test_converted_to_note_off(self):
        mid = mido.MidiFile(type=1, ticks_per_beat=480)
        conductor = mido.MidiTrack()
        mid.tracks.append(conductor)
        track = mido.MidiTrack()
        track.append(mido.Message("note_on", channel=0, note=60, velocity=100, time=0))
        track.append(mido.Message("note_on", channel=0, note=60, velocity=0, time=240))
        mid.tracks.append(track)
        buf = io.BytesIO()
        mid.save(file=buf)

        device = parse_smf_to_udm(buf.getvalue())
        kinds = [e.kind for e in device.songs[0].tracks[0].events]
        assert kinds == [EventKind.NOTE_ON, EventKind.NOTE_OFF]


class TestEmitSmf:
    def _make_device(self):
        events = [
            MidiEvent(tick=0, channel=0, kind=EventKind.PROG_CHANGE, data1=24),
            MidiEvent(tick=0, channel=0, kind=EventKind.NOTE_ON, data1=60, data2=100),
            MidiEvent(tick=480, channel=0, kind=EventKind.NOTE_OFF, data1=60, data2=64),
        ]
        song = Song(
            name="OUT",
            tempo_bpm=100.0,
            time_sig=TimeSig(3, 4),
            tracks=[SongTrack(index=0, kind=SongTrackKind.SEQ, events=events)],
        )
        return Device(model=DeviceModel.QY70, songs=[song])

    def test_returns_bytes(self):
        device = self._make_device()
        data = emit_udm_to_smf(device)
        assert isinstance(data, bytes) and data[:4] == b"MThd"

    def test_no_songs_raises(self):
        device = Device(model=DeviceModel.QY70, songs=[])
        with pytest.raises(ValueError, match="no songs"):
            emit_udm_to_smf(device)

    def test_emit_then_parse_preserves_tempo(self):
        device = self._make_device()
        data = emit_udm_to_smf(device)
        device2 = parse_smf_to_udm(data)
        assert device2.songs[0].tempo_bpm == 100.0

    def test_emit_then_parse_preserves_time_sig(self):
        device = self._make_device()
        data = emit_udm_to_smf(device)
        device2 = parse_smf_to_udm(data)
        assert device2.songs[0].time_sig.numerator == 3
        assert device2.songs[0].time_sig.denominator == 4

    def test_emit_then_parse_preserves_notes(self):
        device = self._make_device()
        data = emit_udm_to_smf(device)
        device2 = parse_smf_to_udm(data)
        events = device2.songs[0].tracks[0].events
        note_on = [e for e in events if e.kind == EventKind.NOTE_ON]
        note_off = [e for e in events if e.kind == EventKind.NOTE_OFF]
        assert len(note_on) == 1 and note_on[0].data1 == 60 and note_on[0].data2 == 100
        assert len(note_off) == 1 and note_off[0].tick == 480
