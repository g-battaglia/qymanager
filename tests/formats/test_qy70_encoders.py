"""
Tests for QY70 encoders: sparse + dense-factory.

Validates:
- Sparse encoder 7/7 on known_pattern.syx ground truth
- Dense encoder 100% byte roundtrip on all SGT Section 0 tracks
"""

from collections import defaultdict
from pathlib import Path

import pytest

from qymanager.formats.qy70.encoder_sparse import (
    SparseEvent,
    encode_event as encode_sparse,
    decode_event as decode_sparse,
    encode_sparse_track,
)
from qymanager.formats.qy70.encoder_dense import (
    DenseEncoder,
    encode_event as encode_dense,
    decode_event as decode_dense,
)
from qymanager.formats.qy70.sysex_parser import SysExParser


FIXTURES = Path(__file__).parent.parent.parent / "tests" / "fixtures"
CAPTURED = Path(__file__).parent.parent.parent / "midi_tools" / "captured"
KNOWN = CAPTURED / "known_pattern.syx"
SGT = FIXTURES / "QY70_SGT.syx"

# Ground truth events for known_pattern.syx (proven 7/7 in Session 14)
KNOWN_EVENTS = [
    (36, 127, 412, 240),   # Kick1 beat 1
    (49, 127,  74, 240),   # Crash1 beat 1
    (44, 119,  30, 240),   # HHpedal beat 1
    (44,  95,  30, 720),   # HHpedal beat 2
    (38, 127, 200, 960),   # Snare1 beat 3
    (44,  95,  30, 960),   # HHpedal beat 3
    (44,  95,  30, 1440),  # HHpedal beat 4
]


class TestSparseEncoder:
    """Sparse R=9×(i+1) encoder tests."""

    def test_roundtrip_known_pattern(self):
        """Each known_pattern event roundtrip decoder(encoder(e)) == e."""
        for i, (note, vel, gate, tick) in enumerate(KNOWN_EVENTS):
            event = SparseEvent(note=note, velocity=vel, gate=gate, tick=tick)
            encoded = encode_sparse(event, segment_idx=i)
            decoded = decode_sparse(encoded, segment_idx=i)

            # Velocity quantization: vel_code rounding loss
            vel_code = max(0, min(15, round((127 - vel) / 8)))
            expected_vel = max(1, 127 - vel_code * 8)

            assert decoded["note"] == note, \
                f"Event {i}: note {note} → {decoded['note']}"
            assert decoded["velocity"] == expected_vel, \
                f"Event {i}: vel {vel}→{expected_vel} → {decoded['velocity']}"
            assert decoded["gate"] == gate, \
                f"Event {i}: gate {gate} → {decoded['gate']}"
            assert decoded["tick_in_bar"] == tick, \
                f"Event {i}: tick {tick} → {decoded['tick_in_bar']}"

    def test_track_build_byte_match(self):
        """encode_sparse_track produces bytes matching known_pattern.syx ±1 DC."""
        events = [SparseEvent(note=n, velocity=v, gate=g, tick=t)
                  for n, v, g, t in KNOWN_EVENTS]
        generated = encode_sparse_track(events, bars=1)

        if not KNOWN.exists():
            pytest.skip("known_pattern.syx fixture not available")

        parser = SysExParser()
        msgs = parser.parse_file(str(KNOWN))
        real_bytes = None
        for m in msgs:
            if m.is_style_data and m.address_low == 0:
                real_bytes = m.decoded_data
                break
        assert real_bytes is not None

        # Allow ≤2 byte differences (known DC delimiter variance)
        diffs = sum(1 for i in range(min(len(generated), len(real_bytes)))
                    if generated[i] != real_bytes[i])
        assert diffs <= 2, f"Too many byte diffs: {diffs}"


class TestDenseEncoder:
    """Dense-factory per-event R table tests."""

    @pytest.fixture
    def encoder(self):
        enc = DenseEncoder()
        enc.load_sgt_tables()
        return enc

    @pytest.fixture
    def sgt_tracks(self):
        """Parse SGT SysEx → dict[track_idx] = concat bytes for Section 0."""
        if not SGT.exists():
            pytest.skip("QY70_SGT.syx fixture not available")
        parser = SysExParser()
        msgs = parser.parse_file(str(SGT))
        tracks = defaultdict(bytes)
        for m in msgs:
            if m.is_style_data and m.decoded_data and 0 <= m.address_low <= 7:
                tracks[m.address_low] += m.decoded_data
        return dict(tracks)

    @pytest.mark.parametrize("track_idx,track_name", [
        (0, "RHY1"),
        (1, "RHY2"),
        (2, "PAD"),
        (3, "BASS"),
        (5, "CHD2"),
        (6, "PHR1"),
    ])
    def test_sgt_roundtrip_per_track(self, encoder, sgt_tracks, track_idx, track_name):
        """SGT Section 0 track should roundtrip 100% byte-exact."""
        if track_idx not in sgt_tracks:
            pytest.skip(f"Track {track_idx} ({track_name}) not in SGT")
        body = sgt_tracks[track_idx]
        result = encoder.roundtrip_test(body, track_name)
        assert result["percent"] == 100.0, \
            f"{track_name}: {result['matches']}/{result['total']} ({result['percent']}%)"

    def test_sgt_full_roundtrip_count(self, encoder, sgt_tracks):
        """Total SGT Section 0 roundtrip = 247/247 events."""
        names = {0: "RHY1", 1: "RHY2", 2: "PAD", 3: "BASS", 5: "CHD2", 6: "PHR1"}
        total_m = 0
        total_n = 0
        for trk, name in names.items():
            if trk in sgt_tracks:
                r = encoder.roundtrip_test(sgt_tracks[trk], name)
                total_m += r["matches"]
                total_n += r["total"]
        assert total_m == total_n, f"SGT full roundtrip: {total_m}/{total_n}"
        assert total_m == 247, f"Expected 247 events, got {total_m}"

    def test_encode_modify_decode(self, encoder):
        """Modify decoded event, re-encode, decode → expect change."""
        # Take a chunk from SGT PHR1 (N=32)
        sample_chunk = bytes.fromhex("174d870d010152")  # any valid 7-byte
        R = 2  # first R from PHR1 table
        original = decode_dense(sample_chunk, R)
        # Modify note
        modified = original
        modified.f0 = (modified.f0 & ~0x7F) | 60  # change note to 60
        encoded = encode_dense(modified, R)
        redecoded = decode_dense(encoded, R)
        assert redecoded.note == 60
