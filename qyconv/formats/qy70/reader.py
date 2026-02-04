"""
QY70 SysEx file reader.

Reads .syx files containing QY70 style/pattern bulk dumps and
converts them to the common Pattern model.
"""

from pathlib import Path
from typing import Dict, List, Optional, Union

from qyconv.models.pattern import Pattern, PatternSettings
from qyconv.models.section import Section, SectionType
from qyconv.models.track import Track, TrackSettings
from qyconv.formats.qy70.sysex_parser import SysExParser, SysExMessage


class QY70Reader:
    """
    Reader for QY70 SysEx pattern files.

    Parses .syx files and constructs Pattern objects from the
    contained bulk dump data.

    Example:
        pattern = QY70Reader.read("style.syx")
        print(f"Pattern: {pattern.name}, Tempo: {pattern.tempo}")
    """

    # Section index to SectionType mapping
    SECTION_MAP = {
        0x00: SectionType.INTRO,
        0x01: SectionType.MAIN_A,
        0x02: SectionType.MAIN_B,
        0x03: SectionType.FILL_AB,
        0x04: SectionType.FILL_BA,
        0x05: SectionType.ENDING,
    }

    def __init__(self):
        self.parser = SysExParser()
        self._raw_messages: List[SysExMessage] = []
        self._section_data: Dict[int, bytearray] = {}

    @classmethod
    def read(cls, filepath: Union[str, Path]) -> Pattern:
        """
        Read a QY70 SysEx file and return a Pattern.

        Args:
            filepath: Path to .syx file

        Returns:
            Parsed Pattern object
        """
        reader = cls()
        return reader.parse_file(filepath)

    def parse_file(self, filepath: Union[str, Path]) -> Pattern:
        """
        Parse a SysEx file.

        Args:
            filepath: Path to .syx file

        Returns:
            Parsed Pattern object
        """
        filepath = Path(filepath)

        if not filepath.exists():
            raise FileNotFoundError(f"File not found: {filepath}")

        with open(filepath, "rb") as f:
            data = f.read()

        return self.parse_bytes(data)

    def parse_bytes(self, data: bytes) -> Pattern:
        """
        Parse SysEx data from bytes.

        Args:
            data: Raw SysEx file contents

        Returns:
            Parsed Pattern object
        """
        # Parse SysEx messages
        self._raw_messages = self.parser.parse_bytes(data)

        # Group messages by section
        self._organize_messages()

        # Build pattern from messages
        pattern = self._build_pattern()
        pattern.source_format = "qy70"
        pattern._raw_data = data

        return pattern

    def _organize_messages(self) -> None:
        """Organize messages by section index."""
        self._section_data = {}

        for msg in self._raw_messages:
            if msg.is_style_data and msg.decoded_data:
                section_idx = msg.address_low

                if section_idx not in self._section_data:
                    self._section_data[section_idx] = bytearray()

                self._section_data[section_idx].extend(msg.decoded_data)

    def _build_pattern(self) -> Pattern:
        """Build Pattern object from parsed data."""
        pattern = Pattern.create_empty()

        # Parse header/config section (0x7F)
        if 0x7F in self._section_data:
            self._parse_header(pattern, bytes(self._section_data[0x7F]))

        # Parse each section
        for section_idx, section_type in self.SECTION_MAP.items():
            section = self._parse_section(section_idx, section_type)
            if section:
                pattern.sections[section_type] = section

        return pattern

    def _parse_header(self, pattern: Pattern, data: bytes) -> None:
        """
        Parse pattern header/config data.

        Args:
            pattern: Pattern to update
            data: Decoded header data
        """
        if len(data) < 20:
            return

        # Extract tempo (typically at offset 0x0A-0x0B)
        # This needs reverse engineering of the exact format
        # For now, use defaults
        pattern.settings.tempo = 120

        # Name parsing would go here
        # pattern.name = data[offset:offset+10].decode('ascii', errors='replace')

    def _parse_section(self, section_idx: int, section_type: SectionType) -> Optional[Section]:
        """
        Parse a single section from bulk dump data.

        Args:
            section_idx: Section index (0x00-0x05)
            section_type: Type of section

        Returns:
            Parsed Section or None if no data
        """
        # Get data for this section
        data = self._section_data.get(section_idx)

        if not data:
            # Return empty section
            return Section.create_empty(section_type)

        section = Section(
            section_type=section_type,
            enabled=True,
            length_measures=4,  # Default, needs parsing
            tracks=[],
        )

        # Parse track data
        section.tracks = self._parse_tracks(bytes(data))
        section._raw_data = bytes(data)

        return section

    def _parse_tracks(self, data: bytes) -> List[Track]:
        """
        Parse track data from section dump.

        Args:
            data: Decoded section data

        Returns:
            List of 8 Track objects
        """
        tracks = []

        # Create 8 tracks with default settings
        # Actual parsing of track data would need more reverse engineering
        for i in range(8):
            track = Track(number=i + 1, enabled=True, settings=TrackSettings())
            tracks.append(track)

        return tracks

    @classmethod
    def can_read(cls, filepath: Union[str, Path]) -> bool:
        """
        Check if a file can be read as QY70 SysEx.

        Args:
            filepath: Path to check

        Returns:
            True if file appears to be valid QY70 SysEx
        """
        filepath = Path(filepath)

        if not filepath.exists():
            return False

        try:
            with open(filepath, "rb") as f:
                header = f.read(16)

            # Check for SysEx start and Yamaha ID
            if len(header) < 4:
                return False

            return (
                header[0] == 0xF0  # SysEx start
                and header[1] == 0x43  # Yamaha
                and header[3] == 0x5F  # QY70 model ID
            )
        except Exception:
            return False
