"""
QY70 SysEx file reader.

Reads .syx files containing QY70 style/pattern bulk dumps and
converts them to the common Pattern model (legacy) or the
Unified Data Model (UDM) Device via parse_syx_to_udm().
"""

from pathlib import Path
from typing import Dict, List, Optional, Union

from qymanager.models.pattern import Pattern, PatternSettings
from qymanager.models.section import Section, SectionType
from qymanager.models.track import Track, TrackSettings
from qymanager.formats.qy70.sysex_parser import SysExParser, SysExMessage

from qymanager.model import (
    Device,
    DeviceModel,
    Pattern as UdmPattern,
    PatternTrack,
    Section as UdmSection,
    SectionName,
    TimeSig,
    Voice,
)


class QY70Reader:
    """
    Reader for QY70 SysEx pattern files.

    Parses .syx files and constructs Pattern objects from the
    contained bulk dump data.

    AL addressing scheme (confirmed from QY70 SGT dump):
        AL = section_index * 8 + track_index
        Section 0 (Intro):   AL 0x00-0x07 (8 tracks)
        Section 1 (Main A):  AL 0x08-0x0F
        Section 2 (Main B):  AL 0x10-0x17
        Section 3 (Fill AB): AL 0x18-0x1F
        Section 4 (Fill BA): AL 0x20-0x27
        Section 5 (Ending):  AL 0x28-0x2F
        Header:              AL 0x7F

    Example:
        pattern = QY70Reader.read("style.syx")
        print(f"Pattern: {pattern.name}, Tempo: {pattern.tempo}")
    """

    # Section index to SectionType mapping (index 0-5, NOT AL address)
    SECTION_MAP = {
        0: SectionType.INTRO,
        1: SectionType.MAIN_A,
        2: SectionType.MAIN_B,
        3: SectionType.FILL_AB,
        4: SectionType.FILL_BA,
        5: SectionType.ENDING,
    }

    # Number of tracks per section
    TRACKS_PER_SECTION = 8

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

        Each section has 8 tracks stored at:
            AL = section_idx * 8 + track_idx  (track_idx 0-7)

        Args:
            section_idx: Section index (0-5)
            section_type: Type of section

        Returns:
            Parsed Section or None if no data
        """
        # Collect per-track data for this section using correct AL addressing
        track_data_map: Dict[int, bytes] = {}
        has_any_data = False

        for track_idx in range(self.TRACKS_PER_SECTION):
            al = section_idx * self.TRACKS_PER_SECTION + track_idx
            data = self._section_data.get(al)
            if data and len(data) > 0:
                track_data_map[track_idx] = bytes(data)
                has_any_data = True

        if not has_any_data:
            # Return empty section
            return Section.create_empty(section_type)

        section = Section(
            section_type=section_type,
            enabled=True,
            length_measures=4,  # Default, needs parsing
            tracks=[],
        )

        # Parse track data
        section.tracks = self._parse_tracks(track_data_map)

        # Store combined raw data for the section
        combined = bytearray()
        for track_idx in range(self.TRACKS_PER_SECTION):
            if track_idx in track_data_map:
                combined.extend(track_data_map[track_idx])
        section._raw_data = bytes(combined)

        return section

    def _parse_tracks(self, track_data_map: Dict[int, bytes]) -> List[Track]:
        """
        Parse track data from section dump.

        Args:
            track_data_map: Dict mapping track_idx (0-7) to decoded track data

        Returns:
            List of 8 Track objects
        """
        tracks = []

        # Create 8 tracks, using available data where present
        for i in range(self.TRACKS_PER_SECTION):
            has_data = i in track_data_map and len(track_data_map[i]) > 0
            track = Track(number=i + 1, enabled=has_data, settings=TrackSettings())
            if has_data:
                track._raw_data = track_data_map[i]
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


_QY70_SECTION_MAP: dict[int, SectionName] = {
    1: SectionName.MAIN_A,
    2: SectionName.MAIN_B,
    3: SectionName.FILL_AA,
    4: SectionName.FILL_BB,
}


def parse_syx_to_udm(data: bytes) -> Device:
    """Parse QY70 .syx bulk dump data into a UDM Device.

    Extracts section/track structure via SysExParser (AL = section*8 + track)
    and produces Device(model=QY70) with one Pattern containing up to 6
    sections × 8 tracks. Sparse data (no voice/volume/pan) → default values.
    Raw bytes preserved in Device._raw_passthrough for lossless roundtrip.

    Args:
        data: Raw .syx file contents.

    Returns:
        Device with model=QY70 containing one Pattern.

    Raises:
        ValueError: If data contains no valid QY70 bulk-dump messages.
    """
    parser = SysExParser()
    messages = parser.parse_bytes(data)

    style_messages = [
        m for m in messages if m.is_style_data and m.decoded_data is not None
    ]
    if not style_messages:
        raise ValueError("No QY70 style-data bulk-dump messages found")

    section_data: dict[int, bytearray] = {}
    for msg in style_messages:
        al = msg.address_low
        if al not in section_data:
            section_data[al] = bytearray()
        if msg.decoded_data is not None:
            section_data[al].extend(msg.decoded_data)

    pattern_name = ""
    if 0x7F in section_data:
        header_bytes = bytes(section_data[0x7F])
        for start in range(min(len(header_bytes), 32)):
            chunk = header_bytes[start : start + 10]
            if all(0x20 <= b < 0x7F for b in chunk) and len(chunk) == 10:
                pattern_name = chunk.decode("ascii").rstrip()
                break

    udm_pattern = UdmPattern(
        index=0,
        name=pattern_name[:10] if pattern_name else "",
        tempo_bpm=120.0,
        measures=4,
        time_sig=TimeSig(numerator=4, denominator=4),
    )

    seen_section_indices: set[int] = set()
    for al in section_data:
        if al == 0x7F:
            continue
        seen_section_indices.add(al // 8)

    for sec_idx in sorted(seen_section_indices):
        section_name = _QY70_SECTION_MAP.get(sec_idx)
        if section_name is None:
            continue

        udm_tracks: list[PatternTrack] = []
        for track_idx in range(8):
            al = sec_idx * 8 + track_idx
            has_data = al in section_data and len(section_data[al]) > 0
            default_channel = 9 if track_idx < 2 else max(0, track_idx)
            udm_tracks.append(
                PatternTrack(
                    midi_channel=min(15, default_channel),
                    voice=Voice(),
                    mute=not has_data,
                    volume=100,
                    pan=64,
                    reverb_send=40,
                    chorus_send=0,
                )
            )

        udm_pattern.sections[section_name] = UdmSection(
            name=section_name,
            tracks=udm_tracks,
            enabled=True,
        )

    device = Device(
        model=DeviceModel.QY70,
        patterns=[udm_pattern],
        source_format="syx",
        _raw_passthrough=data,
    )
    return device
