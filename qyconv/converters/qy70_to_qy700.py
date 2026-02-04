"""
QY70 to QY700 format converter.

Converts QY70 SysEx (.syx) patterns to QY700 Q7P (.Q7P) binary format.
Uses a template-based approach to preserve unknown structure areas.

The conversion process:
1. Parse QY70 SysEx bulk dump
2. Decode 7-bit encoded section data
3. Map sections (Intro, MainA/B, Fills, Ending) to Q7P offsets
4. Apply template for unknown areas
5. Write complete Q7P file
"""

from pathlib import Path
from typing import Dict, List, Optional, Union
import struct

from qyconv.models.pattern import Pattern, PatternSettings
from qyconv.models.section import Section, SectionType
from qyconv.formats.qy70.reader import QY70Reader
from qyconv.formats.qy70.sysex_parser import SysExParser


class QY70ToQY700Converter:
    """
    Converter from QY70 SysEx format to QY700 Q7P format.

    Uses a template-based approach where a valid Q7P file is used as
    the base, and only known fields are overwritten with converted data.

    Attributes:
        template_data: Q7P template file data (3072 bytes)
    """

    # Q7P file constants
    Q7P_SIZE = 3072
    Q7P_HEADER = b"YQ7PAT     V1.00"

    # Section type to Q7P section index
    SECTION_MAP = {
        SectionType.INTRO: 0,
        SectionType.MAIN_A: 1,
        SectionType.MAIN_B: 2,
        SectionType.FILL_AB: 3,
        SectionType.FILL_BA: 4,
        SectionType.ENDING: 5,
    }

    # Q7P offset map for writable fields
    class Offsets:
        HEADER = 0x000  # 16 bytes
        PATTERN_NUMBER = 0x010  # 1 byte
        PATTERN_FLAGS = 0x011  # 1 byte
        SIZE_MARKER = 0x030  # 2 bytes
        SECTION_PTRS = 0x100  # 32 bytes
        SECTION_DATA = 0x120  # 96 bytes
        TEMPO = 0x188  # 2 bytes (big-endian, /10 for BPM)
        CHANNELS = 0x190  # 8 bytes
        TRACK_NUMS = 0x1DC  # 8 bytes
        TRACK_FLAGS = 0x1E4  # 2 bytes
        VOLUME_TABLE = 0x220  # 80 bytes
        PAN_TABLE = 0x270  # 16 bytes
        PHRASE_DATA = 0x360  # Variable
        SEQUENCE_DATA = 0x678  # Variable
        TEMPLATE_NAME = 0x876  # 10 bytes
        FILL_AREA = 0x9C0  # Filled with 0xFE
        PAD_AREA = 0xB10  # Filled with 0xF8

    def __init__(self, template_path: Optional[Union[str, Path]] = None):
        """
        Initialize converter.

        Args:
            template_path: Path to Q7P template file.
                          If None, generates a minimal template.
        """
        if template_path:
            self.template_data = self._load_template(template_path)
        else:
            self.template_data = self._create_minimal_template()

        self._buffer: bytearray = bytearray()
        self._qy70_section_data: Dict[int, bytes] = {}

    def _load_template(self, path: Union[str, Path]) -> bytes:
        """Load Q7P template file."""
        path = Path(path)
        with open(path, "rb") as f:
            data = f.read()

        if len(data) != self.Q7P_SIZE:
            raise ValueError(f"Invalid template size: {len(data)} (expected {self.Q7P_SIZE})")

        if data[:16] != self.Q7P_HEADER:
            raise ValueError("Invalid Q7P header in template")

        return data

    def _create_minimal_template(self) -> bytes:
        """Create minimal valid Q7P template."""
        data = bytearray(self.Q7P_SIZE)

        # Header
        data[0:16] = self.Q7P_HEADER

        # Pattern info
        data[0x10] = 0x01  # Pattern number
        data[0x11] = 0x00  # Flags

        # Size marker
        struct.pack_into(">H", data, 0x30, 0x0990)

        # Section pointers (all empty)
        for i in range(0x100, 0x120, 2):
            data[i] = 0xFE
            data[i + 1] = 0xFE

        # Tempo (120 BPM = 1200 / 10)
        struct.pack_into(">H", data, 0x188, 1200)

        # Channels (all to default)
        for i in range(8):
            data[0x190 + i] = 0x03

        # Track numbers 0-7
        for i in range(8):
            data[0x1DC + i] = i

        # Track flags
        data[0x1E4] = 0x00
        data[0x1E5] = 0x1F

        # Volume table (100 = 0x64)
        for i in range(80):
            data[0x220 + i] = 0x64

        # Pan table (64 = center)
        for i in range(16):
            data[0x270 + i] = 0x40

        # Fill areas
        for i in range(0x9C0, 0xB10):
            data[i] = 0xFE
        for i in range(0xB10, 0xC00):
            data[i] = 0xF8

        # Template name
        data[0x876:0x880] = b"NEW STYLE "

        return bytes(data)

    def convert(self, source_path: Union[str, Path]) -> bytes:
        """
        Convert QY70 SysEx file to Q7P format.

        Args:
            source_path: Path to .syx file

        Returns:
            Complete Q7P file data (3072 bytes)
        """
        source_path = Path(source_path)

        # Parse QY70 SysEx
        with open(source_path, "rb") as f:
            syx_data = f.read()

        return self.convert_bytes(syx_data)

    def convert_bytes(self, syx_data: bytes) -> bytes:
        """
        Convert QY70 SysEx bytes to Q7P format.

        Args:
            syx_data: Raw SysEx file data

        Returns:
            Complete Q7P file data
        """
        # Parse SysEx
        parser = SysExParser()
        messages = parser.parse_bytes(syx_data)

        # Group decoded data by section (AL value)
        self._qy70_section_data = {}
        for msg in messages:
            if msg.is_style_data and msg.decoded_data:
                al = msg.address_low
                if al not in self._qy70_section_data:
                    self._qy70_section_data[al] = bytearray()
                self._qy70_section_data[al].extend(msg.decoded_data)

        # Start with template
        self._buffer = bytearray(self.template_data)

        # Extract pattern info from header section (0x7F)
        self._convert_header()

        # Convert sections
        self._convert_sections()

        # Update section pointers
        self._update_section_pointers()

        return bytes(self._buffer)

    def _convert_header(self) -> None:
        """Convert pattern header from QY70 section 0x7F."""
        header_data = self._qy70_section_data.get(0x7F, b"")

        if not header_data:
            return

        # Try to extract name from header
        # The name location in QY70 header needs verification
        # For now, use first 10 printable chars as possible name
        name_bytes = bytearray(10)
        name_idx = 0
        for byte in header_data[:64]:
            if 0x20 <= byte <= 0x7E:  # Printable ASCII
                name_bytes[name_idx] = byte
                name_idx += 1
                if name_idx >= 10:
                    break

        if name_idx > 0:
            # Pad with spaces
            while name_idx < 10:
                name_bytes[name_idx] = 0x20
                name_idx += 1
            self._buffer[self.Offsets.TEMPLATE_NAME : self.Offsets.TEMPLATE_NAME + 10] = name_bytes

        # Try to extract tempo from header
        # Common locations for tempo in QY70 header
        for offset in [0x0A, 0x0C, 0x10]:
            if offset < len(header_data):
                potential_tempo = header_data[offset]
                if 40 <= potential_tempo <= 240:
                    # Store as Q7P format (tempo * 10, big-endian)
                    tempo_value = potential_tempo * 10
                    struct.pack_into(">H", self._buffer, self.Offsets.TEMPO, tempo_value)
                    break

    def _convert_sections(self) -> None:
        """Convert section phrase data from QY70 format."""
        # QY70 sections 0x00-0x05 map to Q7P sections 0-5
        for qy70_al, section_type in [
            (0x00, SectionType.INTRO),
            (0x01, SectionType.MAIN_A),
            (0x02, SectionType.MAIN_B),
            (0x03, SectionType.FILL_AB),
            (0x04, SectionType.FILL_BA),
            (0x05, SectionType.ENDING),
        ]:
            section_data = self._qy70_section_data.get(qy70_al, b"")

            if section_data:
                self._convert_section_data(self.SECTION_MAP[section_type], section_data)

    def _convert_section_data(self, q7p_section_idx: int, data: bytes) -> None:
        """
        Convert single section's phrase data to Q7P format.

        The phrase data structure differs between QY70 and QY700.
        This method attempts to preserve as much musical content as possible.

        Args:
            q7p_section_idx: Target section index (0-5)
            data: Decoded QY70 section data
        """
        if not data:
            return

        # The section encoded area at 0x120 contains section configuration
        # Each section has ~16 bytes of config data
        config_offset = self.Offsets.SECTION_DATA + (q7p_section_idx * 16)

        # Write section config bytes (first 16 bytes of phrase data typically)
        config_bytes = data[:16] if len(data) >= 16 else data.ljust(16, b"\x00")

        if config_offset + 16 <= len(self._buffer):
            self._buffer[config_offset : config_offset + 16] = config_bytes[:16]

        # If there's phrase data, try to place it in phrase area (0x360)
        # This is a simplified approach - full conversion would need
        # to understand the phrase event format
        if len(data) > 16:
            phrase_start = self.Offsets.PHRASE_DATA
            # Calculate offset for this section's phrase data
            phrase_offset = phrase_start + (q7p_section_idx * 80)

            phrase_bytes = data[16:96]  # Limit to 80 bytes per section
            if phrase_offset + len(phrase_bytes) <= self.Offsets.SEQUENCE_DATA:
                self._buffer[phrase_offset : phrase_offset + len(phrase_bytes)] = phrase_bytes

    def _update_section_pointers(self) -> None:
        """Update section pointer table based on which sections have data."""
        ptr_offset = self.Offsets.SECTION_PTRS

        for section_type, idx in self.SECTION_MAP.items():
            qy70_al = section_type.to_index()  # 0-5 for the 6 section types

            if qy70_al in self._qy70_section_data and self._qy70_section_data[qy70_al]:
                # Section has data - set pointer
                # Pointer format based on template analysis
                self._buffer[ptr_offset + (idx * 2)] = 0x00
                self._buffer[ptr_offset + (idx * 2) + 1] = 0x20 + (idx * 9)
            else:
                # Section empty - mark as 0xFE FE
                self._buffer[ptr_offset + (idx * 2)] = 0xFE
                self._buffer[ptr_offset + (idx * 2) + 1] = 0xFE

    def convert_and_save(
        self, source_path: Union[str, Path], output_path: Union[str, Path]
    ) -> None:
        """
        Convert QY70 SysEx to Q7P and save to file.

        Args:
            source_path: Path to source .syx file
            output_path: Path for output .Q7P file
        """
        q7p_data = self.convert(source_path)

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "wb") as f:
            f.write(q7p_data)


def convert_qy70_to_qy700(
    source_path: Union[str, Path],
    output_path: Union[str, Path],
    template_path: Optional[Union[str, Path]] = None,
) -> None:
    """
    Convert QY70 SysEx file to QY700 Q7P format.

    Convenience function for simple conversion.

    Args:
        source_path: Path to source .syx file
        output_path: Path for output .Q7P file
        template_path: Optional path to Q7P template file

    Example:
        convert_qy70_to_qy700("style.syx", "pattern.Q7P")
    """
    converter = QY70ToQY700Converter(template_path)
    converter.convert_and_save(source_path, output_path)


def convert_pattern_to_q7p(
    pattern: Pattern, template_path: Optional[Union[str, Path]] = None
) -> bytes:
    """
    Convert Pattern object to Q7P bytes.

    Args:
        pattern: Pattern to convert
        template_path: Optional Q7P template file

    Returns:
        Q7P file data (3072 bytes)
    """
    converter = QY70ToQY700Converter(template_path)

    # Start with template
    buffer = bytearray(converter.template_data)

    # Write pattern name
    name = pattern.name[:10].upper().ljust(10)
    buffer[converter.Offsets.TEMPLATE_NAME : converter.Offsets.TEMPLATE_NAME + 10] = name.encode(
        "ascii", errors="replace"
    )

    # Write tempo
    tempo_value = pattern.settings.tempo * 10
    struct.pack_into(">H", buffer, converter.Offsets.TEMPO, tempo_value)

    # Write pattern number
    buffer[converter.Offsets.PATTERN_NUMBER] = pattern.number & 0xFF

    # Write volumes from tracks
    vol_offset = converter.Offsets.VOLUME_TABLE + 6  # Skip first 6 bytes
    for section_type in [
        SectionType.INTRO,
        SectionType.MAIN_A,
        SectionType.MAIN_B,
        SectionType.FILL_AB,
        SectionType.FILL_BA,
        SectionType.ENDING,
    ]:
        section = pattern.sections.get(section_type)
        if section:
            for track in section.tracks[:8]:
                if vol_offset < converter.Offsets.PAN_TABLE:
                    buffer[vol_offset] = min(127, track.settings.volume)
                    vol_offset += 1

    return bytes(buffer)
