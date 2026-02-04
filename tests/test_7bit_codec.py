"""Tests for Yamaha 7-bit codec."""

import pytest
import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from qyconv.utils.yamaha_7bit import encode_7bit, decode_7bit


class TestYamaha7BitCodec:
    """Test cases for 7-bit encoding/decoding."""

    def test_decode_simple(self):
        """Test decoding a simple 8-byte block."""
        # Header byte 0x40 means bit 6 is set, so first data byte has high bit
        encoded = bytes([0x40, 0x00, 0x40, 0x20, 0x10, 0x08, 0x04, 0x02])
        decoded = decode_7bit(encoded)

        # First byte should have high bit set (0x00 | 0x80 = 0x80)
        assert decoded[0] == 0x80
        assert len(decoded) == 7

    def test_encode_simple(self):
        """Test encoding 7 bytes to 8."""
        raw = bytes([0x80, 0x40, 0x20, 0x10, 0x08, 0x04, 0x02])
        encoded = encode_7bit(raw)

        # Should produce 8 bytes
        assert len(encoded) == 8
        # First byte is header with bit 6 set (for 0x80)
        assert encoded[0] == 0x40
        # Second byte is 0x80 with high bit cleared = 0x00
        assert encoded[1] == 0x00

    def test_roundtrip(self):
        """Test that encode followed by decode returns original data."""
        original = bytes([0x00, 0x7F, 0x80, 0xFF, 0x55, 0xAA, 0x12])
        encoded = encode_7bit(original)
        decoded = decode_7bit(encoded)

        assert decoded == original

    def test_roundtrip_multiple_blocks(self):
        """Test roundtrip with multiple 7-byte blocks."""
        original = bytes(range(21))  # 3 blocks of 7 bytes
        encoded = encode_7bit(original)
        decoded = decode_7bit(encoded)

        assert decoded == original

    def test_decode_partial_block(self):
        """Test decoding with incomplete final block."""
        # 5 bytes: header + 4 data bytes
        encoded = bytes([0x40, 0x00, 0x40, 0x20, 0x10])
        decoded = decode_7bit(encoded)

        # Should decode 4 bytes (what we have after header)
        assert len(decoded) == 4

    def test_encode_partial_block(self):
        """Test encoding fewer than 7 bytes."""
        raw = bytes([0x80, 0x40, 0x20])  # Only 3 bytes
        encoded = encode_7bit(raw)

        # Should produce 4 bytes (1 header + 3 data)
        assert len(encoded) == 4

    def test_all_zeros(self):
        """Test with all-zero data."""
        original = bytes([0x00] * 7)
        encoded = encode_7bit(original)
        decoded = decode_7bit(encoded)

        assert decoded == original
        assert encoded[0] == 0x00  # Header should be 0

    def test_all_high_bits(self):
        """Test with all high bits set."""
        original = bytes([0x80] * 7)
        encoded = encode_7bit(original)

        # Header should have all 7 bits set
        assert encoded[0] == 0x7F
        # All data bytes should be 0
        assert all(b == 0 for b in encoded[1:])

        decoded = decode_7bit(encoded)
        assert decoded == original

    def test_mixed_data(self):
        """Test with varied data patterns."""
        patterns = [
            bytes([0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06]),
            bytes([0x7F, 0x7E, 0x7D, 0x7C, 0x7B, 0x7A, 0x79]),
            bytes([0x80, 0x81, 0x82, 0x83, 0x84, 0x85, 0x86]),
            bytes([0xFF, 0xFE, 0xFD, 0xFC, 0xFB, 0xFA, 0xF9]),
        ]

        for original in patterns:
            encoded = encode_7bit(original)
            decoded = decode_7bit(encoded)
            assert decoded == original, f"Failed for pattern: {original.hex()}"

    def test_empty_data(self):
        """Test with empty input."""
        assert decode_7bit(b"") == b""
        assert encode_7bit(b"") == b""

    def test_single_byte(self):
        """Test with single byte input."""
        original = bytes([0xAB])
        encoded = encode_7bit(original)
        decoded = decode_7bit(encoded)

        assert decoded == original


class TestYamaha7BitRealData:
    """Test with real QY70 data if available."""

    def test_decode_real_sysex_data(self, qy70_sysex_data):
        """Test decoding real SysEx bulk dump data."""
        # Find first bulk dump message
        # Format: F0 43 0n 5F BH BL AH AM AL [data] CS F7

        if len(qy70_sysex_data) < 20:
            pytest.skip("Test file too small")

        # Find first bulk dump (starts with F0 43 0x 5F)
        start = 0
        for i in range(len(qy70_sysex_data) - 10):
            if (
                qy70_sysex_data[i] == 0xF0
                and qy70_sysex_data[i + 1] == 0x43
                and qy70_sysex_data[i + 2] & 0xF0 == 0x00
                and qy70_sysex_data[i + 3] == 0x5F
            ):
                start = i
                break

        if start == 0:
            pytest.skip("No bulk dump found")

        # Find message end
        end = qy70_sysex_data.find(0xF7, start)
        if end < 0:
            pytest.skip("Invalid message")

        # Extract payload (between address and checksum)
        payload = qy70_sysex_data[start + 9 : end - 1]

        # Decode should not raise
        decoded = decode_7bit(payload)

        # Decoded length should be approximately 7/8 of encoded length
        expected_len = (len(payload) // 8) * 7
        assert abs(len(decoded) - expected_len) <= 7  # Allow partial block
