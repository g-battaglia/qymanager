"""
QY70 SysEx file writer.

Writes Pattern objects to .syx files in QY70 bulk dump format.
"""

from pathlib import Path
from typing import List, Union

from qymanager.models.pattern import Pattern
from qymanager.models.section import Section, SectionType
from qymanager.utils.yamaha_7bit import encode_7bit
from qymanager.utils.checksum import calculate_yamaha_checksum


class QY70Writer:
    """
    Writer for QY70 SysEx pattern files.

    Converts Pattern objects to .syx format for loading into QY70.

    Example:
        pattern = Pattern.create_empty("MY STYLE")
        QY70Writer.write(pattern, "mystyle.syx")
    """

    # Constants
    YAMAHA_ID = 0x43
    QY70_MODEL_ID = 0x5F
    SYSEX_START = 0xF0
    SYSEX_END = 0xF7

    # SectionType to index mapping
    SECTION_INDEX = {
        SectionType.INTRO: 0x00,
        SectionType.MAIN_A: 0x01,
        SectionType.MAIN_B: 0x02,
        SectionType.FILL_AB: 0x03,
        SectionType.FILL_BA: 0x04,
        SectionType.ENDING: 0x05,
    }

    # Maximum payload size per message (before 7-bit encoding)
    MAX_PAYLOAD = 128

    def __init__(self, device_number: int = 0):
        """
        Initialize writer.

        Args:
            device_number: MIDI device number (0-15)
        """
        self.device_number = device_number & 0x0F

    @classmethod
    def write(cls, pattern: Pattern, filepath: Union[str, Path], device_number: int = 0) -> None:
        """
        Write a Pattern to a SysEx file.

        Args:
            pattern: Pattern to write
            filepath: Output file path
            device_number: MIDI device number (0-15)
        """
        writer = cls(device_number)
        data = writer.to_bytes(pattern)

        filepath = Path(filepath)
        filepath.parent.mkdir(parents=True, exist_ok=True)

        with open(filepath, "wb") as f:
            f.write(data)

    def to_bytes(self, pattern: Pattern) -> bytes:
        """
        Convert Pattern to SysEx bytes.

        Args:
            pattern: Pattern to convert

        Returns:
            Complete SysEx file data
        """
        messages = []

        # Write header/init message
        messages.append(self._create_init_message())

        # Write each section
        for section_type, section in pattern.sections.items():
            if section_type in self.SECTION_INDEX:
                section_msgs = self._write_section(section)
                messages.extend(section_msgs)

        # Write pattern config/header (section 0x7F)
        messages.extend(self._write_pattern_header(pattern))

        return b"".join(messages)

    def _create_init_message(self) -> bytes:
        """Create the initialization message."""
        # F0 43 10 5F 00 00 00 01 F7
        return bytes(
            [
                self.SYSEX_START,
                self.YAMAHA_ID,
                0x10 | self.device_number,  # Parameter change type
                self.QY70_MODEL_ID,
                0x00,
                0x00,
                0x00,  # Address
                0x01,  # Data
                self.SYSEX_END,
            ]
        )

    def _write_section(self, section: Section) -> List[bytes]:
        """
        Write a section as bulk dump messages.

        Args:
            section: Section to write

        Returns:
            List of SysEx messages
        """
        messages = []

        section_idx = self.SECTION_INDEX.get(section.section_type)
        if section_idx is None:
            return messages

        # Get or generate section data
        if section._raw_data:
            data = section._raw_data
        else:
            data = self._generate_section_data(section)

        # Split into chunks and create bulk dump messages
        chunks = self._split_data(data)

        for chunk in chunks:
            msg = self._create_bulk_dump(section_idx, chunk)
            messages.append(msg)

        return messages

    def _generate_section_data(self, section: Section) -> bytes:
        """
        Generate binary data for a section.

        Args:
            section: Section to encode

        Returns:
            Binary section data
        """
        # For now, generate minimal data
        # Full implementation would encode all tracks and phrases
        data = bytearray(128)  # Placeholder
        return bytes(data)

    def _write_pattern_header(self, pattern: Pattern) -> List[bytes]:
        """
        Write pattern header as section 0x7F.

        Args:
            pattern: Pattern with header info

        Returns:
            List of SysEx messages
        """
        messages = []

        # Generate header data
        if pattern._raw_header:
            data = pattern._raw_header
        else:
            data = self._generate_header_data(pattern)

        chunks = self._split_data(data)

        for chunk in chunks:
            msg = self._create_bulk_dump(0x7F, chunk)
            messages.append(msg)

        return messages

    def _generate_header_data(self, pattern: Pattern) -> bytes:
        """Generate header/config data for pattern."""
        data = bytearray(128)

        # Pattern name (padded to 10 chars)
        name = pattern.name[:10].upper().ljust(10)
        for i, char in enumerate(name):
            data[i] = ord(char)

        # Tempo (placeholder)
        data[0x0A] = pattern.settings.tempo >> 1
        data[0x0B] = (pattern.settings.tempo & 1) << 7

        return bytes(data)

    def _split_data(self, data: bytes) -> List[bytes]:
        """Split data into chunks for bulk dump messages."""
        chunks = []
        for i in range(0, len(data), self.MAX_PAYLOAD):
            chunks.append(data[i : i + self.MAX_PAYLOAD])
        return chunks

    def _create_bulk_dump(self, section_idx: int, data: bytes) -> bytes:
        """
        Create a bulk dump SysEx message.

        Format: F0 43 0n 5F BH BL AH AM AL [encoded data] CS F7

        Args:
            section_idx: Section/address low byte
            data: Raw data to encode

        Returns:
            Complete SysEx message
        """
        # Encode data as 7-bit
        encoded = encode_7bit(data)

        # Byte count (of encoded data)
        byte_count = len(encoded)
        bh = (byte_count >> 7) & 0x7F
        bl = byte_count & 0x7F

        # Address
        ah = 0x02  # Style data
        am = 0x7E  # User style memory
        al = section_idx

        # Build message without checksum
        msg = bytearray(
            [
                self.SYSEX_START,
                self.YAMAHA_ID,
                0x00 | self.device_number,  # Bulk dump type
                self.QY70_MODEL_ID,
                bh,
                bl,  # Byte count
                ah,
                am,
                al,  # Address
            ]
        )
        msg.extend(encoded)

        # Calculate checksum (over address + data)
        checksum_data = bytes([ah, am, al]) + encoded
        checksum = calculate_yamaha_checksum(checksum_data)
        msg.append(checksum)

        msg.append(self.SYSEX_END)

        return bytes(msg)
