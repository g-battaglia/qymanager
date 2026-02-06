"""
QY700 Q7P file reader.

Reads .Q7P binary files and converts them to the common Pattern model.
"""

from pathlib import Path
from typing import Optional, Union

from qymanager.models.pattern import Pattern, PatternSettings
from qymanager.models.section import Section, SectionType
from qymanager.models.track import Track, TrackSettings, create_default_tracks
from qymanager.formats.qy700.binary_parser import Q7PParser, Q7PHeader


class QY700Reader:
    """
    Reader for QY700 Q7P pattern files.

    Parses .Q7P binary files and constructs Pattern objects.

    Example:
        pattern = QY700Reader.read("pattern.Q7P")
        print(f"Pattern: {pattern.name}, Tempo: {pattern.tempo}")
    """

    # Q7P section index to SectionType mapping
    SECTION_MAP = {
        0: SectionType.INTRO,
        1: SectionType.MAIN_A,
        2: SectionType.MAIN_B,
        3: SectionType.FILL_AB,
        4: SectionType.FILL_BA,
        5: SectionType.ENDING,
    }

    def __init__(self):
        self.parser = Q7PParser()
        self._raw_data: bytes = b""

    @classmethod
    def read(cls, filepath: Union[str, Path]) -> Pattern:
        """
        Read a Q7P file and return a Pattern.

        Args:
            filepath: Path to .Q7P file

        Returns:
            Parsed Pattern object
        """
        reader = cls()
        return reader.parse_file(filepath)

    def parse_file(self, filepath: Union[str, Path]) -> Pattern:
        """
        Parse a Q7P file.

        Args:
            filepath: Path to .Q7P file

        Returns:
            Parsed Pattern object
        """
        filepath = Path(filepath)

        if not filepath.exists():
            raise FileNotFoundError(f"File not found: {filepath}")

        with open(filepath, "rb") as f:
            self._raw_data = f.read()

        return self.parse_bytes(self._raw_data)

    def parse_bytes(self, data: bytes) -> Pattern:
        """
        Parse Q7P data from bytes.

        Args:
            data: Raw Q7P file contents

        Returns:
            Parsed Pattern object
        """
        self._raw_data = data

        # Parse with binary parser
        header, sections = self.parser.parse_bytes(data)

        # Build pattern from parsed data
        pattern = self._build_pattern(header)
        pattern.source_format = "qy700"
        pattern._raw_data = data

        return pattern

    def _build_pattern(self, header: Q7PHeader) -> Pattern:
        """
        Build Pattern object from parsed data.

        Args:
            header: Parsed Q7P header

        Returns:
            Pattern object
        """
        pattern = Pattern()

        # Extract pattern name from template name area
        name = self.parser.get_template_name()
        if name:
            pattern.name = name.ljust(10)[:10]
        else:
            pattern.name = "PATTERN   "

        # Extract tempo
        pattern.settings.tempo = self.parser.get_tempo()

        # Pattern number
        pattern.number = header.pattern_number

        # Parse each section
        volumes = self.parser.get_track_volumes()
        channels = self.parser.get_channel_assignments()

        for idx, section_type in self.SECTION_MAP.items():
            section = self._build_section(idx, section_type, volumes, channels)
            pattern.sections[section_type] = section

        return pattern

    def _build_section(
        self, index: int, section_type: SectionType, volumes: list, channels: list
    ) -> Section:
        """
        Build a Section from parsed data.

        Args:
            index: Section index
            section_type: Type of section
            volumes: Volume values for tracks
            channels: Channel assignments

        Returns:
            Section object
        """
        section = Section(
            section_type=section_type,
            enabled=True,
            length_measures=4,  # Default
            tracks=[],
        )

        # Create 8 tracks
        for track_num in range(8):
            track = Track(
                number=track_num + 1,
                enabled=True,
                settings=TrackSettings(
                    channel=channels[track_num] if track_num < len(channels) else track_num + 1,
                    volume=volumes[track_num] if track_num < len(volumes) else 100,
                ),
            )
            section.tracks.append(track)

        return section

    @classmethod
    def can_read(cls, filepath: Union[str, Path]) -> bool:
        """
        Check if a file can be read as Q7P.

        Args:
            filepath: Path to check

        Returns:
            True if file appears to be valid Q7P
        """
        filepath = Path(filepath)

        if not filepath.exists():
            return False

        try:
            with open(filepath, "rb") as f:
                header = f.read(16)

            return header == b"YQ7PAT     V1.00"
        except Exception:
            return False

    @classmethod
    def get_file_info(cls, filepath: Union[str, Path]) -> dict:
        """
        Get basic information about a Q7P file without full parsing.

        Args:
            filepath: Path to .Q7P file

        Returns:
            Dictionary with file info
        """
        filepath = Path(filepath)

        with open(filepath, "rb") as f:
            data = f.read()

        info = {
            "valid": False,
            "size": len(data),
            "expected_size": 3072,
        }

        if len(data) >= 16:
            info["header"] = data[:16].decode("ascii", errors="replace")
            info["valid"] = data[:16] == b"YQ7PAT     V1.00"

        if len(data) >= 0x878:
            # Template name at offset 0x870
            name = data[0x870:0x87A]
            info["template_name"] = name.decode("ascii", errors="replace").rstrip()

        return info
