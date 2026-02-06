"""
QY700 Q7P file writer.

Writes Pattern objects to .Q7P binary format for loading into QY700.
"""

from pathlib import Path
from typing import Optional, Union
import struct

from qymanager.models.pattern import Pattern
from qymanager.models.section import Section, SectionType


class QY700Writer:
    """
    Writer for QY700 Q7P pattern files.

    Converts Pattern objects to .Q7P binary format.

    Example:
        pattern = Pattern.create_empty("MY STYLE")
        QY700Writer.write(pattern, "mystyle.Q7P")
    """

    # File constants
    FILE_SIZE = 3072
    HEADER = b"YQ7PAT     V1.00"

    # SectionType to index mapping
    SECTION_INDEX = {
        SectionType.INTRO: 0,
        SectionType.MAIN_A: 1,
        SectionType.MAIN_B: 2,
        SectionType.FILL_AB: 3,
        SectionType.FILL_BA: 4,
        SectionType.ENDING: 5,
    }

    def __init__(self):
        self._buffer: bytearray = bytearray()

    @classmethod
    def write(cls, pattern: Pattern, filepath: Union[str, Path]) -> None:
        """
        Write a Pattern to a Q7P file.

        Args:
            pattern: Pattern to write
            filepath: Output file path
        """
        writer = cls()
        data = writer.to_bytes(pattern)

        filepath = Path(filepath)
        filepath.parent.mkdir(parents=True, exist_ok=True)

        with open(filepath, "wb") as f:
            f.write(data)

    @classmethod
    def write_using_template(
        cls, pattern: Pattern, template_path: Union[str, Path], output_path: Union[str, Path]
    ) -> None:
        """
        Write a Pattern using an existing Q7P file as template.

        This preserves unknown/unparsed data from the template
        while updating known fields from the Pattern.

        Args:
            pattern: Pattern with data to write
            template_path: Path to template Q7P file
            output_path: Output file path
        """
        # Read template
        with open(template_path, "rb") as f:
            template_data = f.read()

        if len(template_data) != cls.FILE_SIZE:
            raise ValueError(f"Invalid template size: {len(template_data)}")

        # Create writer and generate output
        writer = cls()
        data = writer.to_bytes_with_template(pattern, template_data)

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "wb") as f:
            f.write(data)

    def to_bytes(self, pattern: Pattern) -> bytes:
        """
        Convert Pattern to Q7P binary format.

        Args:
            pattern: Pattern to convert

        Returns:
            Complete Q7P file data (3072 bytes)
        """
        # Initialize buffer with zeros
        self._buffer = bytearray(self.FILE_SIZE)

        # Write header
        self._write_header(pattern)

        # Write pattern info
        self._write_pattern_info(pattern)

        # Write tempo/timing
        self._write_tempo(pattern)

        # Write channel assignments
        self._write_channels(pattern)

        # Write volume table
        self._write_volumes(pattern)

        # Write template name
        self._write_template_name(pattern)

        # Write section data
        self._write_sections(pattern)

        # Fill unused areas
        self._fill_unused_areas()

        return bytes(self._buffer)

    def to_bytes_with_template(self, pattern: Pattern, template: bytes) -> bytes:
        """
        Convert Pattern using template for unknown data.

        Args:
            pattern: Pattern to convert
            template: Template Q7P data

        Returns:
            Complete Q7P file data
        """
        # Start with template
        self._buffer = bytearray(template)

        # Update known fields
        self._write_pattern_info(pattern)
        self._write_tempo(pattern)
        self._write_template_name(pattern)

        return bytes(self._buffer)

    def _write_header(self, pattern: Pattern) -> None:
        """Write file header."""
        self._buffer[0:16] = self.HEADER

    def _write_pattern_info(self, pattern: Pattern) -> None:
        """Write pattern information at offset 0x10."""
        # Pattern number
        self._buffer[0x10] = pattern.number & 0xFF

        # Flags (0x02 seems common based on file analysis)
        self._buffer[0x11] = 0x02

        # Size marker at 0x30-0x31
        struct.pack_into(">H", self._buffer, 0x30, 0x0990)

    def _write_tempo(self, pattern: Pattern) -> None:
        """Write tempo data at offset 0x188."""
        tempo = pattern.settings.tempo

        # Tempo encoding (needs verification)
        self._buffer[0x188] = (tempo >> 1) & 0x7F
        self._buffer[0x189] = (tempo << 7) & 0x80

    def _write_channels(self, pattern: Pattern) -> None:
        """Write channel assignments at offset 0x190."""
        # Default channel assignment pattern
        for i in range(8):
            self._buffer[0x190 + i] = 0x03  # Default value from analysis

    def _write_volumes(self, pattern: Pattern) -> None:
        """Write volume table at offset 0x220."""
        offset = 0x220

        # Write default volumes (0x64 = 100)
        for section in pattern.sections.values():
            for track in section.tracks[:8]:
                self._buffer[offset] = track.settings.volume
                offset += 1
            break  # Only use first section's values for now

        # Fill remaining with defaults
        while offset < 0x360:
            self._buffer[offset] = 0x64
            offset += 1

    def _write_template_name(self, pattern: Pattern) -> None:
        """Write template name at offset 0x870."""
        name = pattern.name[:10].upper().ljust(10)
        name_bytes = name.encode("ascii", errors="replace")
        self._buffer[0x870 : 0x870 + len(name_bytes)] = name_bytes

    def _write_sections(self, pattern: Pattern) -> None:
        """Write section data."""
        # If pattern has raw data from original file, preserve it
        if pattern._raw_data and len(pattern._raw_data) == self.FILE_SIZE:
            # Copy section-related data
            # Offset 0x100 - 0x200: Track/section pointers
            self._buffer[0x100:0x200] = pattern._raw_data[0x100:0x200]

            # Offset 0x360 - 0x678: Phrase data
            self._buffer[0x360:0x678] = pattern._raw_data[0x360:0x678]

    def _fill_unused_areas(self) -> None:
        """Fill unused areas with appropriate values."""
        # Fill area 0x9C0-0xA90 with 0xFE
        for i in range(0x9C0, 0xA90):
            if i < len(self._buffer):
                self._buffer[i] = 0xFE

        # Fill area 0xB10-end with 0xF8
        for i in range(0xB10, self.FILE_SIZE):
            if i < len(self._buffer):
                self._buffer[i] = 0xF8

        # Fill some areas with 0x40 (common pattern)
        for offset in [0x270, 0x280, 0x290]:
            for i in range(16):
                if offset + i < len(self._buffer):
                    self._buffer[offset + i] = 0x40


def create_empty_q7p() -> bytes:
    """
    Create an empty Q7P file with valid structure.

    Returns:
        Empty Q7P file data (3072 bytes)
    """
    pattern = Pattern.create_empty()
    writer = QY700Writer()
    return writer.to_bytes(pattern)
