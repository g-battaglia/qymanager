"""
QY700 Q7P binary file parser.

Parses the binary structure of QY700 pattern (.Q7P) files.

Q7P File Structure (3072 bytes total):
    Offset  Size    Description
    0x000   16      Header "YQ7PAT     V1.00"
    0x010   32      Pattern info (number, flags)
    0x030   2       Size marker
    0x100   32      Track pointers
    0x120   96      Section data
    0x180   16      Tempo/timing
    0x190   8       Channel assignments
    0x220   160     Volume/velocity tables
    0x360   176     Phrase data
    0x678   64      Sequence events
    0x870   16      Template name
    0x900   128     Pattern mappings
    0x9C0   208     Fill bytes (0xFE)
    0xB10   240     Padding (0xF8)
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
import struct


@dataclass
class Q7PHeader:
    """
    Q7P file header structure.
    """

    magic: bytes  # "YQ7PAT     V1.00" (16 bytes)
    pattern_number: int  # Pattern slot number
    flags: int  # Various flags
    size_marker: int  # Data size indicator

    def is_valid(self) -> bool:
        """Check if header is valid."""
        return self.magic == b"YQ7PAT     V1.00"


@dataclass
class Q7PSection:
    """
    A section within a Q7P pattern.
    """

    index: int  # Section index (0-5)
    enabled: bool  # Whether section is active
    length_measures: int  # Length in measures
    data: bytes  # Raw section data
    track_data: List[bytes]  # Per-track data


@dataclass
class Q7PTrackData:
    """
    Track configuration data from Q7P.
    """

    channel: int
    volume: int
    pan: int
    program: int
    bank_msb: int
    bank_lsb: int
    enabled: bool


class Q7PParser:
    """
    Parser for QY700 Q7P binary files.

    Example:
        parser = Q7PParser()
        header, sections = parser.parse_file("pattern.Q7P")
    """

    # File structure constants
    FILE_SIZE = 3072
    HEADER_MAGIC = b"YQ7PAT     V1.00"
    HEADER_SIZE = 16

    # Offset table
    OFFSETS = {
        "header": 0x000,
        "pattern_info": 0x010,
        "size_marker": 0x030,
        "track_pointers": 0x100,
        "section_data": 0x120,
        "tempo": 0x180,
        "channels": 0x190,
        "track_numbers": 0x1DC,
        "volume_table": 0x220,
        "phrase_data": 0x360,
        "sequence_events": 0x678,
        "template_name": 0x870,
        "pattern_mappings": 0x900,
        "fill_area": 0x9C0,
        "padding_area": 0xB10,
    }

    def __init__(self):
        self.data: bytes = b""
        self.header: Optional[Q7PHeader] = None
        self.sections: List[Q7PSection] = []
        self._raw_sections: Dict[str, bytes] = {}

    def parse_file(self, filepath: str) -> Tuple[Q7PHeader, List[Q7PSection]]:
        """
        Parse a Q7P file.

        Args:
            filepath: Path to .Q7P file

        Returns:
            Tuple of (header, sections)
        """
        with open(filepath, "rb") as f:
            self.data = f.read()

        return self.parse_bytes(self.data)

    def parse_bytes(self, data: bytes) -> Tuple[Q7PHeader, List[Q7PSection]]:
        """
        Parse Q7P data from bytes.

        Args:
            data: Raw file contents

        Returns:
            Tuple of (header, sections)
        """
        self.data = data

        if len(data) != self.FILE_SIZE:
            raise ValueError(f"Invalid Q7P file size: {len(data)} (expected {self.FILE_SIZE})")

        # Parse header
        self.header = self._parse_header()

        if not self.header.is_valid():
            raise ValueError("Invalid Q7P header")

        # Extract raw sections
        self._extract_sections()

        # Parse section data
        self.sections = self._parse_sections()

        return self.header, self.sections

    def _parse_header(self) -> Q7PHeader:
        """Parse file header."""
        magic = self.data[0:16]

        # Pattern number at offset 0x10
        pattern_number = self.data[0x10]

        # Flags at offset 0x11
        flags = self.data[0x11]

        # Size marker at offset 0x30-0x31
        size_marker = struct.unpack(">H", self.data[0x30:0x32])[0]

        return Q7PHeader(
            magic=magic, pattern_number=pattern_number, flags=flags, size_marker=size_marker
        )

    def _extract_sections(self) -> None:
        """Extract raw data for each file section."""
        self._raw_sections = {}

        # Extract each named section
        offsets = list(self.OFFSETS.items())

        for i, (name, start) in enumerate(offsets):
            # End is start of next section or file end
            if i + 1 < len(offsets):
                end = offsets[i + 1][1]
            else:
                end = len(self.data)

            self._raw_sections[name] = self.data[start:end]

    def _parse_sections(self) -> List[Q7PSection]:
        """Parse pattern sections."""
        sections = []

        # QY700 has 6 main sections
        for idx in range(6):
            section = self._parse_single_section(idx)
            sections.append(section)

        return sections

    def _parse_single_section(self, index: int) -> Q7PSection:
        """
        Parse a single section.

        Args:
            index: Section index (0-5)

        Returns:
            Parsed Q7PSection
        """
        # Section data is interleaved in the file
        # This needs more reverse engineering to determine exact layout

        section = Q7PSection(
            index=index,
            enabled=True,
            length_measures=4,  # Default, needs parsing
            data=b"",
            track_data=[],
        )

        return section

    def get_tempo(self) -> int:
        """
        Extract tempo from parsed data.

        Returns:
            Tempo in BPM
        """
        if not self.data:
            return 120

        # Tempo appears to be stored at multiple locations
        # Most likely at offset 0x188-0x189
        tempo_data = self._raw_sections.get("tempo", b"")
        if len(tempo_data) >= 10:
            # Tempo value (needs verification)
            tempo = tempo_data[8] * 2  # Rough estimate
            if 40 <= tempo <= 240:
                return tempo

        return 120  # Default

    def get_template_name(self) -> str:
        """
        Extract template name from parsed data.

        Returns:
            Template name string
        """
        # Template name is at offset 0x876 (after 6 bytes of 0x40 padding)
        if len(self.data) >= 0x880:
            name = self.data[0x876:0x880]
            try:
                # Strip trailing nulls/spaces and decode
                return name.decode("ascii").rstrip("\x00 ")
            except UnicodeDecodeError:
                return ""
        return ""

    def get_track_volumes(self) -> List[int]:
        """
        Extract per-track volume values.

        Returns:
            List of 16 volume values
        """
        vol_data = self._raw_sections.get("volume_table", b"")
        if len(vol_data) >= 16:
            return list(vol_data[:16])
        return [100] * 16  # Defaults

    def get_channel_assignments(self) -> List[int]:
        """
        Extract channel assignments for tracks.

        Returns:
            List of channel numbers
        """
        ch_data = self._raw_sections.get("channels", b"")
        if len(ch_data) >= 8:
            return list(ch_data[:8])
        return [i + 1 for i in range(8)]  # Defaults

    def dump_structure(self) -> str:
        """
        Generate a text dump of file structure for debugging.

        Returns:
            Formatted structure description
        """
        lines = ["Q7P File Structure:"]
        lines.append(f"  File size: {len(self.data)} bytes")

        if self.header:
            lines.append(f"  Header valid: {self.header.is_valid()}")
            lines.append(f"  Pattern number: {self.header.pattern_number}")
            lines.append(f"  Size marker: 0x{self.header.size_marker:04X}")

        lines.append("")
        lines.append("  Sections:")
        for name, data in self._raw_sections.items():
            offset = self.OFFSETS.get(name, 0)
            lines.append(f"    {name:20} @ 0x{offset:03X}: {len(data):4d} bytes")

        return "\n".join(lines)


def parse_q7p_file(filepath: str) -> Tuple[Q7PHeader, List[Q7PSection]]:
    """
    Convenience function to parse a Q7P file.

    Args:
        filepath: Path to .Q7P file

    Returns:
        Tuple of (header, sections)
    """
    parser = Q7PParser()
    return parser.parse_file(filepath)
