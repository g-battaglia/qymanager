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


class TestPhraseBlockLayout:
    """Tests that validate the phrase block header layout."""

    def test_decay_phrase_headers(self):
        """DECAY.Q7P phrase blocks must have 26-byte header with tempo at +0x18."""
        scaffold = os.path.join(os.path.dirname(__file__), "..",
                                "data", "q7p", "DECAY.Q7P")
        if not os.path.exists(scaffold):
            pytest.skip("DECAY.Q7P not available")
        from midi_tools.q7p_to_midi import find_phrase_blocks
        with open(scaffold, "rb") as f:
            data = f.read()
        blocks = find_phrase_blocks(data)
        assert len(blocks) >= 10
        for offset, _ in blocks:
            # Tempo is BE16 at +0x18
            tempo_raw = struct.unpack(">H", data[offset + 0x18:offset + 0x1A])[0]
            assert tempo_raw == 1200, f"DECAY tempo expected 1200 (120 BPM), got {tempo_raw}"
            # Event stream starts with F0 00 at +0x1A
            assert data[offset + 0x1A] == 0xF0
            assert data[offset + 0x1B] == 0x00


class TestDecayIdentityRoundtrip:
    """Validate walker/encoder against real DECAY.Q7P phrase events."""

    def test_decay_phrase_bytes_roundtrip(self):
        """Walking and re-emitting DECAY events must produce identical bytes."""
        scaffold = os.path.join(os.path.dirname(__file__), "..",
                                "data", "q7p", "DECAY.Q7P")
        if not os.path.exists(scaffold):
            pytest.skip("DECAY.Q7P not available")
        from midi_tools.q7p_to_midi import find_phrase_blocks
        with open(scaffold, "rb") as f:
            data = f.read()
        blocks = find_phrase_blocks(data)

        for offset, name in blocks:
            start = offset + 0x1A
            assert data[start] == 0xF0 and data[start + 1] == 0x00
            # Walk events and re-emit
            buf = bytearray(b"\xF0\x00")
            i = start + 2
            end = None
            while i < len(data):
                b = data[i]
                if b == 0xF2:
                    buf.append(0xF2)
                    end = i + 1
                    break
                elif 0xA0 <= b <= 0xAF:
                    buf.extend(data[i:i + 2])
                    i += 2
                elif b == 0xD0:
                    buf.extend(data[i:i + 4])
                    i += 4
                elif b == 0xE0:
                    buf.extend(data[i:i + 5])
                    i += 5
                else:
                    buf.append(b)
                    i += 1
            assert end is not None
            orig = data[start:end]
            assert bytes(buf) == orig, f"Phrase {name!r}: re-emit differs"


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

    def test_roundtrip_hardware_capture_s28(self):
        """Session 28 hardware-captured SGT produces valid Q7P 5120 (regression)."""
        cap = os.path.join(os.path.dirname(__file__), "..",
                           "midi_tools", "captured", "s28_sgt", "capture.json")
        scaffold = os.path.join(os.path.dirname(__file__), "..",
                                "data", "q7p", "DECAY.Q7P")
        if not os.path.exists(cap) or not os.path.exists(scaffold):
            pytest.skip("Hardware capture or scaffold not available")

        from midi_tools.build_q7p_5120 import build_5120_q7p, validate_q7p
        from midi_tools.q7p_to_midi import find_phrase_blocks

        pattern = quantize_capture(cap, bar_count=4)
        assert pattern.bpm == 151.0
        assert pattern.bar_count == 4

        total_notes = sum(len(t.notes) for t in pattern.tracks.values())
        assert total_notes == 208, f"Expected 208 notes, got {total_notes}"

        q7p = build_5120_q7p(pattern, scaffold)
        assert len(q7p) == 5120

        warnings = validate_q7p(q7p)
        assert len(warnings) == 0, f"Validator warnings: {warnings}"

        blocks = find_phrase_blocks(q7p)
        assert len(blocks) >= 6


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


class TestPatternNameDirectory:
    """Tests for the AH=0x05 pattern-name directory decoder (Session 28)."""

    @pytest.fixture
    def directory_path(self):
        path = os.path.join(os.path.dirname(__file__), "..",
                            "midi_tools", "captured", "s28_areas", "ah_0x05.syx")
        if not os.path.exists(path):
            pytest.skip("ah_0x05.syx capture not available")
        return path

    def test_parse_empty_directory(self, directory_path):
        """An all-empty capture must yield 20 slots of 8 asterisks."""
        from midi_tools.decode_pattern_names import parse_names
        with open(directory_path, "rb") as f:
            syx = f.read()
        slots = parse_names(syx)
        assert len(slots) == 20
        for slot in slots:
            assert slot["empty"] is True
            assert slot["name"] == "********"
            assert slot["meta_hex"] == "00" * 8

    def test_reject_non_qy70_sysex(self):
        """Invalid SysEx prefix must raise ValueError."""
        from midi_tools.decode_pattern_names import parse_names
        with pytest.raises(ValueError):
            parse_names(b"\xf0\x00\x00\x00" + b"\x00" * 330)

    def test_reject_bad_body_length(self):
        """Short body must raise ValueError."""
        from midi_tools.decode_pattern_names import parse_names
        short = bytes([0xF0, 0x43, 0x00, 0x5F, 0x02, 0x40, 0x05, 0x00, 0x00]) \
                + b"\x00" * 10 + bytes([0x00, 0xF7])
        with pytest.raises(ValueError):
            parse_names(short)

    def test_parse_synthetic_filled_slot(self):
        """Synthetic dump with one non-empty slot must be parsed correctly."""
        from midi_tools.decode_pattern_names import parse_names
        header = bytes([0xF0, 0x43, 0x00, 0x5F, 0x02, 0x40, 0x05, 0x00, 0x00])
        body = bytearray(b"\x2a" * 16 * 20)
        body[0:8] = b"MYSTYLE "
        body[8:16] = bytes([0x01, 0x02, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])
        syx = header + bytes(body) + bytes([0x00, 0xF7])
        slots = parse_names(syx)
        assert slots[0]["name"] == "MYSTYLE "
        assert slots[0]["empty"] is False
        assert slots[0]["meta_hex"] == "0102000000000000"
        for i in range(1, 20):
            assert slots[i]["empty"] is True
