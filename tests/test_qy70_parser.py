"""Tests for QY70 SysEx parser."""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from qymanager.formats.qy70.sysex_parser import SysExParser, MessageType


class TestSysExParser:
    """Test cases for QY70 SysEx parser."""

    def test_parse_init_message(self):
        """Test parsing init/parameter change message."""
        # F0 43 10 5F 00 00 00 01 F7
        data = bytes([0xF0, 0x43, 0x10, 0x5F, 0x00, 0x00, 0x00, 0x01, 0xF7])

        parser = SysExParser()
        messages = parser.parse_bytes(data)

        assert len(messages) == 1
        msg = messages[0]
        assert msg.message_type == MessageType.PARAMETER_CHANGE
        assert msg.device_number == 0
        assert msg.address == (0x00, 0x00, 0x00)

    def test_parse_bulk_dump(self):
        """Test parsing a minimal bulk dump message."""
        # Create a minimal bulk dump
        # F0 43 00 5F BH BL AH AM AL [data] CS F7
        data = bytearray(
            [
                0xF0,
                0x43,
                0x00,
                0x5F,  # Header
                0x00,
                0x08,  # Byte count (8 bytes)
                0x02,
                0x7E,
                0x00,  # Address (style data, section 0)
            ]
        )
        # Add 8 bytes of encoded data
        data.extend([0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07])
        # Add checksum (calculated over address + data)
        checksum_data = bytes(data[6:])  # AH AM AL + data
        cs = (128 - (sum(checksum_data) & 0x7F)) & 0x7F
        data.append(cs)
        data.append(0xF7)

        parser = SysExParser()
        messages = parser.parse_bytes(bytes(data))

        assert len(messages) == 1
        msg = messages[0]
        assert msg.message_type == MessageType.BULK_DUMP
        assert msg.is_bulk_dump
        assert msg.address == (0x02, 0x7E, 0x00)
        assert msg.is_style_data

    def test_parse_multiple_messages(self):
        """Test parsing file with multiple SysEx messages."""
        # Two simple messages
        msg1 = bytes([0xF0, 0x43, 0x10, 0x5F, 0x00, 0x00, 0x00, 0x01, 0xF7])
        msg2 = bytes([0xF0, 0x43, 0x10, 0x5F, 0x00, 0x00, 0x01, 0x02, 0xF7])

        parser = SysExParser()
        messages = parser.parse_bytes(msg1 + msg2)

        assert len(messages) == 2

    def test_invalid_message_skipped(self):
        """Test that non-Yamaha messages are skipped."""
        # Non-Yamaha message (Roland = 0x41)
        invalid = bytes([0xF0, 0x41, 0x10, 0x00, 0x00, 0xF7])
        valid = bytes([0xF0, 0x43, 0x10, 0x5F, 0x00, 0x00, 0x00, 0x01, 0xF7])

        parser = SysExParser()
        messages = parser.parse_bytes(invalid + valid)

        # Should only get the valid Yamaha message
        assert len(messages) == 1
        assert messages[0].message_type == MessageType.PARAMETER_CHANGE

    def test_get_style_messages(self):
        """Test filtering for style data messages."""
        parser = SysExParser()

        # Mock some messages
        from qymanager.formats.qy70.sysex_parser import SysExMessage

        parser.messages = [
            SysExMessage(MessageType.BULK_DUMP, 0, (0x02, 0x7E, 0x00), b"", b""),
            SysExMessage(MessageType.BULK_DUMP, 0, (0x02, 0x7E, 0x01), b"", b""),
            SysExMessage(MessageType.PARAMETER_CHANGE, 0, (0x00, 0x00, 0x00), b"", b""),
        ]

        style_msgs = parser.get_style_messages()
        assert len(style_msgs) == 2

        section_msgs = parser.get_messages_by_section(0x00)
        assert len(section_msgs) == 1


class TestSysExParserWithFile:
    """Test SysEx parser with real file."""

    def test_parse_qy70_file(self, qy70_sysex_file):
        """Test parsing real QY70 SysEx file."""
        if not qy70_sysex_file.exists():
            pytest.skip("Test file not found")

        parser = SysExParser()
        messages = parser.parse_file(str(qy70_sysex_file))

        # Should have multiple messages
        assert len(messages) > 0

        # First message is usually init
        assert messages[0].message_type in (MessageType.PARAMETER_CHANGE, MessageType.BULK_DUMP)

    def test_checksum_validation(self, qy70_sysex_file):
        """Test that checksums validate correctly."""
        if not qy70_sysex_file.exists():
            pytest.skip("Test file not found")

        parser = SysExParser()
        messages = parser.parse_file(str(qy70_sysex_file))

        bulk_dumps = [m for m in messages if m.is_bulk_dump]

        # All bulk dumps should have valid checksums
        for msg in bulk_dumps:
            assert msg.checksum_valid, f"Invalid checksum at address {msg.address}"

    def test_style_data_extraction(self, qy70_sysex_file):
        """Test extracting style data from file."""
        if not qy70_sysex_file.exists():
            pytest.skip("Test file not found")

        parser = SysExParser()
        parser.parse_file(str(qy70_sysex_file))

        style_messages = parser.get_style_messages()

        # Should have style data
        assert len(style_messages) > 0

        # All style messages should have decoded data
        for msg in style_messages:
            assert msg.decoded_data is not None
            assert len(msg.decoded_data) > 0
