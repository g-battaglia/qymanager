"""Tests for the MIDI capture quantizer and D0/E0 encoder."""

import json
import os
import struct
import tempfile

import pytest

from midi_tools.quantizer import (
    QuantizedNote,
    QuantizedPattern,
    QuantizedTrack,
    quantize_capture,
)
from midi_tools.capture_to_q7p import (
    encode_phrase_events,
    write_smf,
    write_q7p_metadata,
    _encode_delta,
    _tick_to_gate,
)


@pytest.fixture
def sgt_capture_path():
    """Path to SGT capture fixture."""
    path = os.path.join(os.path.dirname(__file__), "..",
                        "midi_tools", "captured", "sgt_full_capture.json")
    if not os.path.exists(path):
        pytest.skip("SGT capture file not found")
    return path


class TestQuantizer:
    """Tests for quantize_capture()."""

    def test_basic_quantize(self, sgt_capture_path):
        """Quantize SGT capture with default settings."""
        pattern = quantize_capture(sgt_capture_path)
        assert pattern.bpm == 151
        assert pattern.ppqn == 480
        assert pattern.time_sig == (4, 4)
        assert pattern.bar_count > 0
        assert len(pattern.active_tracks) >= 4

    def test_forced_bar_count(self, sgt_capture_path):
        """Force specific bar count."""
        pattern = quantize_capture(sgt_capture_path, bar_count=6)
        assert pattern.bar_count == 6
        # All notes should be in bars 0-5
        for track in pattern.active_tracks:
            for note in track.notes:
                assert note.bar < 6

    def test_bpm_override(self, sgt_capture_path):
        """Override BPM from capture metadata."""
        pattern = quantize_capture(sgt_capture_path, bpm=120)
        assert pattern.bpm == 120

    def test_drum_detection(self, sgt_capture_path):
        """Channels 9 and 10 should be detected as drums."""
        pattern = quantize_capture(sgt_capture_path, bar_count=1)
        for track in pattern.active_tracks:
            if track.channel in (9, 10):
                assert track.is_drum
            else:
                assert not track.is_drum

    def test_note_on_off_pairing(self, sgt_capture_path):
        """All quantized notes should have positive duration."""
        pattern = quantize_capture(sgt_capture_path, bar_count=2)
        for track in pattern.active_tracks:
            for note in track.notes:
                assert note.tick_dur > 0
                assert note.velocity > 0
                assert 0 <= note.note <= 127

    def test_bar_ticks(self, sgt_capture_path):
        """Bar ticks calculation should be correct."""
        pattern = quantize_capture(sgt_capture_path)
        # 4/4 time at 480 PPQN: 4 beats × 480 = 1920 ticks per bar
        assert pattern.bar_ticks == 1920

    def test_notes_sorted(self, sgt_capture_path):
        """Notes should be sorted by bar, then tick, then note."""
        pattern = quantize_capture(sgt_capture_path, bar_count=4)
        for track in pattern.active_tracks:
            for i in range(1, len(track.notes)):
                prev = track.notes[i - 1]
                curr = track.notes[i]
                assert (curr.bar, curr.tick_on, curr.note) >= (prev.bar, prev.tick_on, prev.note)


class TestDeltaEncoding:
    """Tests for D0/E0 delta time encoding."""

    def test_small_delta(self):
        """Delta ≤ 127 should use A0."""
        buf = bytearray()
        _encode_delta(buf, 120)
        assert buf == bytearray([0xA0, 120])

    def test_medium_delta(self):
        """Delta 128-255 should use A1."""
        buf = bytearray()
        _encode_delta(buf, 240)
        assert buf == bytearray([0xA1, 240 - 128])

    def test_large_delta(self):
        """Delta > 1023 should emit multiple commands."""
        buf = bytearray()
        _encode_delta(buf, 1920)  # 1 bar at 480 PPQN
        # Should emit A7 7F (1023) + remaining
        total = 0
        i = 0
        while i < len(buf):
            step = buf[i] - 0xA0
            val = buf[i + 1]
            total += step * 128 + val
            i += 2
        assert total == 1920

    def test_zero_delta(self):
        """Zero delta should produce no output."""
        buf = bytearray()
        _encode_delta(buf, 0)
        assert len(buf) == 0


class TestGateEncoding:
    """Tests for gate time encoding."""

    def test_gate_range(self):
        """Gate should be in 0-127 range."""
        for dur in [0, 30, 60, 120, 240, 480, 960, 1920]:
            gate = _tick_to_gate(dur)
            assert 0 <= gate <= 127

    def test_gate_minimum(self):
        """Very short notes should have gate >= 1."""
        assert _tick_to_gate(1) >= 1
        assert _tick_to_gate(0) >= 1


class TestPhraseEncoder:
    """Tests for D0/E0 phrase encoding (verified from DECAY.Q7P format)."""

    def test_d0_format_vel_note_gate(self, sgt_capture_path):
        """D0 encoding: [D0][vel][note][gate] (4 bytes, DECAY-verified)."""
        pattern = quantize_capture(sgt_capture_path, bar_count=1)
        rhy1 = pattern.tracks.get(0)
        if rhy1 is None:
            pytest.skip("No RHY1 track in capture")

        data = encode_phrase_events(rhy1, pattern)
        assert data[:2] == b"\xF0\x00"
        assert data[-1] == 0xF2

        # Walk the stream: for each D0 event, byte+2 must match a track note
        track_notes = {n.note for n in rhy1.notes}
        i = 2
        d0_found = 0
        while i < len(data) - 1:
            cmd = data[i]
            if cmd == 0xD0 and i + 3 < len(data):
                vel = data[i+1]
                note = data[i+2]
                gate = data[i+3]
                assert note in track_notes, (
                    f"D0 at offset {i}: note=0x{note:02x} not in track notes"
                )
                assert 0 <= vel <= 0x7F
                assert 1 <= gate <= 0x7F
                d0_found += 1
                i += 4
            elif 0xA0 <= cmd <= 0xAF:
                i += 2
            elif cmd == 0xF2:
                break
            else:
                i += 1
        assert d0_found == len(rhy1.notes)

    def test_e0_format_gate_param_note_vel(self, sgt_capture_path):
        """E0 encoding: [E0][gate][param][note][vel] (5 bytes, DECAY-verified)."""
        pattern = quantize_capture(sgt_capture_path, bar_count=1)
        # Find first melody track
        melody = next((t for t in pattern.active_tracks if not t.is_drum), None)
        if melody is None:
            pytest.skip("No melody track in capture")

        data = encode_phrase_events(melody, pattern)
        assert data[:2] == b"\xF0\x00"
        assert data[-1] == 0xF2

        track_notes = {n.note for n in melody.notes}
        i = 2
        e0_found = 0
        while i < len(data) - 1:
            cmd = data[i]
            if cmd == 0xE0 and i + 4 < len(data):
                gate = data[i+1]
                param = data[i+2]
                note = data[i+3]
                vel = data[i+4]
                assert note in track_notes
                assert 0 <= vel <= 0x7F
                assert 1 <= gate <= 0x7F
                e0_found += 1
                i += 5
            elif 0xA0 <= cmd <= 0xAF:
                i += 2
            elif cmd == 0xF2:
                break
            else:
                i += 1
        assert e0_found == len(melody.notes)

    def test_encode_melody_track(self, sgt_capture_path):
        """Encode melody track produces valid E0 commands."""
        pattern = quantize_capture(sgt_capture_path, bar_count=1)
        # CHD1 is track 3 (melody)
        chd1 = pattern.tracks.get(3)
        if chd1 is None:
            pytest.skip("No CHD1 track in capture")

        data = encode_phrase_events(chd1, pattern)
        assert data[:2] == b"\xF0\x00"
        assert data[-1] == 0xF2
        assert 0xE0 in data

    def test_round_trip_note_count(self, sgt_capture_path):
        """Encoded phrase should have same note count when parsed back."""
        from qymanager.formats.qy700.phrase_parser import QY700PhraseParser

        pattern = quantize_capture(sgt_capture_path, bar_count=1)
        for track in pattern.active_tracks:
            data = encode_phrase_events(track, pattern)

            # Parse back with phrase parser
            # Wrap in minimal format for parser
            events = []
            i = 0
            while i < len(data):
                cmd = data[i]
                if cmd in (0xD0, 0xE0) and i + 3 < len(data):
                    events.append(data[i + 1])  # note
                    i += 4
                elif 0xA0 <= cmd <= 0xA7 and i + 1 < len(data):
                    i += 2
                elif cmd == 0xF2:
                    break
                else:
                    i += 1

            assert len(events) == len(track.notes), (
                f"Track {track.name}: encoded {len(events)} notes, "
                f"expected {len(track.notes)}"
            )


class TestEndToEndRoundtrip:
    """Full pipeline: capture → quantize → Q7P 5120 → parse → verify notes."""

    def test_roundtrip_note_count(self, sgt_capture_path):
        """Notes encoded into Q7P 5120-byte file must decode back identically."""
        from midi_tools.build_q7p_5120 import build_5120_q7p
        from midi_tools.q7p_to_midi import (
            find_phrase_blocks,
            parse_phrase_events,
        )

        pattern = quantize_capture(sgt_capture_path, bar_count=4)
        scaffold = os.path.join(os.path.dirname(__file__), "..",
                                "data", "q7p", "DECAY.Q7P")
        if not os.path.exists(scaffold):
            pytest.skip("DECAY.Q7P scaffold not available")

        q7p_data = build_5120_q7p(pattern, scaffold)
        assert len(q7p_data) == 5120

        # Parse phrase blocks back from the Q7P data
        blocks = find_phrase_blocks(q7p_data)
        expected_names = {t.name for t in pattern.active_tracks}
        decoded_names = {name for _, name in blocks if name in expected_names}
        assert decoded_names == expected_names, (
            f"Decoded phrases {decoded_names} != expected {expected_names}"
        )

        # Count notes per phrase
        expected = {t.name: len(t.notes) for t in pattern.active_tracks}
        for offset, name in blocks:
            if name not in expected:
                continue
            phrase = parse_phrase_events(q7p_data, offset, channel=0)
            assert len(phrase.events) == expected[name], (
                f"Track {name}: {len(phrase.events)} decoded vs "
                f"{expected[name]} expected"
            )


class TestSMFWriter:
    """Tests for Standard MIDI File output."""

    def test_write_smf(self, sgt_capture_path):
        """Write and verify SMF file."""
        import mido

        pattern = quantize_capture(sgt_capture_path, bar_count=4)

        with tempfile.NamedTemporaryFile(suffix=".mid", delete=False) as f:
            smf_path = f.name

        try:
            write_smf(pattern, smf_path)

            mid = mido.MidiFile(smf_path)
            assert mid.type == 1
            assert mid.ticks_per_beat == 480
            assert len(mid.tracks) == len(pattern.active_tracks) + 1  # +1 for tempo

            # Verify total note count
            total_notes = sum(
                1 for track in mid.tracks
                for msg in track
                if msg.type == "note_on" and msg.velocity > 0
            )
            expected_notes = sum(len(t.notes) for t in pattern.active_tracks)
            assert total_notes == expected_notes
        finally:
            os.unlink(smf_path)


class TestQ7PMetadata:
    """Tests for Q7P metadata writing."""

    def test_write_metadata(self, sgt_capture_path):
        """Write Q7P with correct metadata."""
        pattern = quantize_capture(sgt_capture_path, bar_count=4)

        data = write_q7p_metadata(pattern)
        assert len(data) == 3072
        assert data[:16] == b"YQ7PAT     V1.00"

        # Check tempo
        tempo = struct.unpack(">H", data[0x188:0x18A])[0] / 10
        assert tempo == 151.0

        # Check name
        name = data[0x876:0x880].decode("ascii").strip()
        assert len(name) > 0
