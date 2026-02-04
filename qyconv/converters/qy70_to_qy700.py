"""
QY70 to QY700 format converter.

Converts QY70 SysEx (.syx) patterns to QY700 Q7P (.Q7P) binary format.
Uses a template-based approach to preserve unknown structure areas.

IMPORTANT: This converter uses a known-good Q7P template (TXX.Q7P) as the base
and only modifies SAFE fields (tempo, name, volumes, pan). It does NOT modify
the critical section configuration area (0x120-0x180) to avoid corrupting
the file structure which could cause hardware issues.

The conversion process:
1. Parse QY70 SysEx bulk dump
2. Decode 7-bit encoded section data
3. Extract only safe values (tempo, volume, pan, name)
4. Apply to template without modifying critical structures
5. Write complete Q7P file
"""

import base64
import struct
import zlib
from pathlib import Path
from typing import Dict, List, Optional, Union

from qyconv.models.pattern import Pattern, PatternSettings
from qyconv.models.section import Section, SectionType
from qyconv.formats.qy70.reader import QY70Reader
from qyconv.formats.qy70.sysex_parser import SysExParser


# Embedded TXX.Q7P template (compressed with zlib, base64 encoded)
# This is a known-good empty Q7P file with correct structure
_EMBEDDED_TEMPLATE_B64 = (
    "eNqLDDQPcAxRAIEwQz0DA0YGNIAmwDmBYXgBBQZNBiMGawalf1jBB4bfQEUHWD4BGYwMjBAGEwMT"
    "hMHMwAxkfHQgHyhAAcsGGQYGHoiTmKFAgULAwMjEzMLKxs4gT2kgRQNBChJA9wW6eg00gC7P70Bd"
    "UM/gMKhBWqV9fWxJfX1cUniCob6Jrn+9d31JfVp9bH1edX50YWJGQnh6fUlmRXZFfVl9Vl5euGdk"
    "fnR8Tk5UenpeTVZEdkJidn19VrVLPQQYA4GJCXarJHzVfU18HYJdM5SU9BwcfI0l9fLy1CWBMkpK"
    "MqKpqfF5DhkZokqSksGZMC3x8fX19vbeQAw1H0gr1CsogNkKYAgTB6kAKQeilBSQenv7eAgfphci"
    "b2/PQC3jqAwcRsFgAYwMQlwcvIYODo4MbGa+WcA8zMDKwMDLytYs3CHcweDFoAAuWeodCJZPKQQA"
    "qeVdCoWgRb5ZSVWtvh5Iq2nUg2klEK2lowdOhB3tkMQor9SsqgYUlJUHKgcqaGmCiGtoqABLzfp6"
    "JSUVJSUgX01NWQ1oXL21sSlYXk8Los7OTtHOzs01SEpKWlJGur5eVRUiTqn7Ka0vmNEAesyHBrsG"
    "KYT4BvgoDHwDgHHAIcWAGRRn/4YFGOjU8GOEAQDr1a6U"
)


def _get_embedded_template() -> bytes:
    """Decompress and return the embedded Q7P template."""
    compressed = base64.b64decode(_EMBEDDED_TEMPLATE_B64)
    return zlib.decompress(compressed)


class QY70ToQY700Converter:
    """
    Converter from QY70 SysEx format to QY700 Q7P format.

    Uses a template-based approach where a valid Q7P file is used as
    the base, and only SAFE known fields are overwritten with converted data.

    SAFETY: This converter intentionally does NOT modify:
    - Section configuration area (0x120-0x180)
    - Section pointers beyond what the template has
    - Any unknown/undocumented areas

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

    # Q7P offset map for SAFE writable fields only
    class Offsets:
        HEADER = 0x000  # 16 bytes - DO NOT MODIFY
        PATTERN_NUMBER = 0x010  # 1 byte - safe to modify
        PATTERN_FLAGS = 0x011  # 1 byte - safe to modify
        SIZE_MARKER = 0x030  # 2 bytes - DO NOT MODIFY

        # DANGER ZONE - DO NOT MODIFY THESE AREAS:
        # SECTION_PTRS = 0x100  # 32 bytes - critical structure
        # SECTION_DATA = 0x120  # 96 bytes - critical structure
        # TEMPO_AREA = 0x180    # 8 bytes padding - must be spaces (0x20)

        TEMPO = 0x188  # 2 bytes (big-endian, /10 for BPM) - safe
        TIME_SIG = 0x18A  # 2 bytes - safe
        CHANNELS = 0x190  # 8 bytes - safe
        TRACK_NUMS = 0x1DC  # 8 bytes - safe
        TRACK_FLAGS = 0x1E4  # 2 bytes - safe

        # Volume/Pan tables - safe to modify
        VOLUME_TABLE = 0x226  # Volume data starts at 0x226
        REVERB_TABLE = 0x256  # Reverb send values
        PAN_TABLE = 0x276  # Pan data starts at 0x276
        CHORUS_TABLE = 0x296  # Chorus send values

        # Name - safe to modify
        TEMPLATE_NAME = 0x876  # 10 bytes

        # Fill areas - DO NOT MODIFY
        # FILL_AREA = 0x9C0  # Filled with 0xFE
        # PAD_AREA = 0xB10   # Filled with 0xF8

    def __init__(self, template_path: Optional[Union[str, Path]] = None):
        """
        Initialize converter.

        Args:
            template_path: Path to Q7P template file.
                          If None, uses embedded known-good template.
        """
        if template_path:
            self.template_data = self._load_template(template_path)
        else:
            # Use embedded template - this is a known-good Q7P structure
            self.template_data = _get_embedded_template()

        self._buffer: bytearray = bytearray()
        self._qy70_section_data: Dict[int, bytearray] = {}
        self._qy70_track_data: Dict[int, bytearray] = {}

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

        SAFETY: Only modifies known-safe fields in the template.
        Does NOT modify critical structure areas.

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
        self._qy70_track_data = {}

        for msg in messages:
            if msg.is_style_data and msg.decoded_data:
                al = msg.address_low
                if al == 0x7F:
                    # Header data
                    if al not in self._qy70_section_data:
                        self._qy70_section_data[al] = bytearray()
                    self._qy70_section_data[al].extend(msg.decoded_data)
                elif 0x00 <= al <= 0x05:
                    # Section phrase data
                    if al not in self._qy70_section_data:
                        self._qy70_section_data[al] = bytearray()
                    self._qy70_section_data[al].extend(msg.decoded_data)
                elif 0x08 <= al <= 0x37:
                    # Track data: AL = 0x08 + (section * 8) + track
                    if al not in self._qy70_track_data:
                        self._qy70_track_data[al] = bytearray()
                    self._qy70_track_data[al].extend(msg.decoded_data)

        # Start with template - this has correct structure
        self._buffer = bytearray(self.template_data)

        # Only modify SAFE fields:
        self._extract_and_apply_name()
        self._extract_and_apply_tempo()
        self._extract_and_apply_volumes()
        self._extract_and_apply_pans()

        return bytes(self._buffer)

    def _extract_and_apply_name(self) -> None:
        """Extract name from QY70 header and apply to Q7P (SAFE)."""
        header_data = self._qy70_section_data.get(0x7F, b"")

        if not header_data:
            return

        # Extract first 10 printable chars as name
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

    def _extract_and_apply_tempo(self) -> None:
        """Extract tempo from QY70 header and apply to Q7P (SAFE)."""
        header_data = self._qy70_section_data.get(0x7F, b"")

        if not header_data:
            return

        # Try to extract tempo from common locations in QY70 header
        for offset in [0x0A, 0x0C, 0x10]:
            if offset < len(header_data):
                potential_tempo = header_data[offset]
                if 40 <= potential_tempo <= 240:
                    # Store as Q7P format (tempo * 10, big-endian)
                    tempo_value = potential_tempo * 10
                    struct.pack_into(">H", self._buffer, self.Offsets.TEMPO, tempo_value)
                    break

    def _extract_and_apply_volumes(self) -> None:
        """Extract volumes from QY70 track data and apply to Q7P (SAFE)."""
        # QY70 track data structure (after 7-bit decode):
        # Offset 24: volume value
        # Track AL = 0x08 + (section_idx * 8) + track_num

        for section_idx in range(6):  # 6 sections
            for track_num in range(8):  # 8 tracks
                al = 0x08 + (section_idx * 8) + track_num
                track_data = self._qy70_track_data.get(al, b"")

                if len(track_data) > 24:
                    volume = track_data[24] & 0x7F
                    if 0 < volume <= 127:
                        # Q7P volume offset: 0x226 + (section * 8) + track
                        vol_offset = self.Offsets.VOLUME_TABLE + (section_idx * 8) + track_num
                        if vol_offset < self.Offsets.REVERB_TABLE:
                            self._buffer[vol_offset] = volume

    def _extract_and_apply_pans(self) -> None:
        """Extract pan values from QY70 track data and apply to Q7P (SAFE)."""
        # QY70 track data structure (after 7-bit decode):
        # Offset 21: pan flag (0x41 = valid, 0x00 = use default)
        # Offset 22: pan value (0-127, 64=center)

        for section_idx in range(6):
            for track_num in range(8):
                al = 0x08 + (section_idx * 8) + track_num
                track_data = self._qy70_track_data.get(al, b"")

                if len(track_data) > 22:
                    pan_flag = track_data[21]
                    if pan_flag == 0x41:  # Pan value is valid
                        pan = track_data[22] & 0x7F
                        # Q7P pan offset: 0x276 + (section * 8) + track
                        pan_offset = self.Offsets.PAN_TABLE + (section_idx * 8) + track_num
                        if pan_offset < self.Offsets.CHORUS_TABLE:
                            self._buffer[pan_offset] = pan

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

    # Write pattern name (SAFE)
    name = pattern.name[:10].upper().ljust(10)
    buffer[converter.Offsets.TEMPLATE_NAME : converter.Offsets.TEMPLATE_NAME + 10] = name.encode(
        "ascii", errors="replace"
    )

    # Write tempo (SAFE)
    tempo_value = int(pattern.settings.tempo * 10)
    struct.pack_into(">H", buffer, converter.Offsets.TEMPO, tempo_value)

    # Write pattern number (SAFE)
    buffer[converter.Offsets.PATTERN_NUMBER] = pattern.number & 0xFF

    # Write volumes from tracks (SAFE)
    for section_idx, section_type in enumerate(
        [
            SectionType.INTRO,
            SectionType.MAIN_A,
            SectionType.MAIN_B,
            SectionType.FILL_AB,
            SectionType.FILL_BA,
            SectionType.ENDING,
        ]
    ):
        section = pattern.sections.get(section_type)
        if section:
            for track_num, track in enumerate(section.tracks[:8]):
                vol_offset = converter.Offsets.VOLUME_TABLE + (section_idx * 8) + track_num
                if vol_offset < converter.Offsets.REVERB_TABLE:
                    buffer[vol_offset] = min(127, track.settings.volume)

    return bytes(buffer)
