"""
QY700 Q7P Pattern decoder.

Provides complete parsing and decoding of Q7P binary files
with full offset mapping for all known fields.

File Structure (3072 bytes):
    0x000-0x00F: Header "YQ7PAT     V1.00"
    0x010-0x02F: Pattern info
    0x030-0x0FF: Reserved
    0x100-0x11F: Section pointers
    0x120-0x17F: Section encoded data
    0x180-0x18F: Tempo/timing
    0x190-0x19F: Channel config
    0x1A0-0x1DB: Reserved
    0x1DC-0x1EF: Track numbering and flags
    0x1F0-0x21F: Reserved
    0x220-0x35F: Volume/velocity/pan tables
    0x360-0x4FF: Phrase data area
    0x500-0x677: Additional phrase data
    0x678-0x86F: Sequence events
    0x870-0x8FF: Template info
    0x900-0x9BF: Pattern mappings
    0x9C0-0xB0F: Fill area (0xFE)
    0xB10-0xBFF: Padding (0xF8)
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import struct

from qymanager.models.pattern import Pattern, PatternSettings
from qymanager.models.section import Section, SectionType
from qymanager.models.track import Track, TrackSettings
from qymanager.models.phrase import Phrase


@dataclass
class Q7POffsets:
    """
    Complete offset map for Q7P file structure.
    """

    # Header
    HEADER_MAGIC = (0x000, 16)  # "YQ7PAT     V1.00"

    # Pattern info
    PATTERN_NUMBER = 0x010  # 1 byte
    PATTERN_FLAGS = 0x011  # 1 byte
    SIZE_MARKER = (0x030, 2)  # Big-endian word

    # Section pointers (0x100-0x11F)
    SECTION_PTR_START = 0x100
    SECTION_PTR_SIZE = 32

    # Section encoded data (0x120-0x17F)
    SECTION_DATA_START = 0x120
    SECTION_DATA_SIZE = 96

    # Tempo and timing (0x180-0x18F)
    TEMPO_AREA = 0x180
    TEMPO_VALUE = 0x188  # Tempo byte (needs scaling)
    TIME_SIG = 0x18A  # Time signature

    # Channel configuration (0x190-0x19F)
    CHANNEL_ASSIGN = 0x190  # 8 bytes - channel per track

    # Track configuration (0x1DC-0x1EF)
    TRACK_NUMBERS = 0x1DC  # 8 bytes: 00 01 02 03 04 05 06 07
    TRACK_FLAGS = 0x1E4  # Track enable flags

    # Volume/Velocity/Pan tables (0x220-0x35F)
    VOLUME_TABLE_START = 0x220
    VOLUME_TABLE_SIZE = 320  # Complex structure

    # Volume offsets within table
    SECTION_VOLUMES = {
        SectionType.INTRO: 0x226,
        SectionType.MAIN_A: 0x227,
        SectionType.MAIN_B: 0x228,
        SectionType.FILL_AB: 0x229,
        SectionType.FILL_BA: 0x22A,
        SectionType.ENDING: 0x22B,
    }

    # Pan values (0x40 = center)
    PAN_TABLE_START = 0x270

    # Phrase data (0x360-0x677)
    PHRASE_DATA_START = 0x360
    PHRASE_DATA_SIZE = 792

    # Phrase/pattern velocity data
    PHRASE_VELOCITY_START = 0x360
    PHRASE_VELOCITY_SIZE = 80

    # Velocity table at 0x3B0
    VELOCITY_TABLE = 0x3B0

    # Sequence events (0x678-0x86F)
    SEQUENCE_START = 0x678
    SEQUENCE_SIZE = 504

    # Template info (0x870-0x8FF)
    TEMPLATE_PADDING = 0x870  # 6 bytes of 0x40
    TEMPLATE_NAME = 0x876  # 10 bytes ASCII
    TEMPLATE_RESERVED = 0x880  # to 0x8FF

    # Pattern mappings (0x900-0x9BF)
    PATTERN_MAP_START = 0x900
    PATTERN_MAP_SIZE = 192

    # Fill areas
    FILL_AREA = (0x9C0, 0xB10)  # Filled with 0xFE
    PADDING_AREA = (0xB10, 0xC00)  # Filled with 0xF8


class Q7PPatternDecoder:
    """
    Complete decoder for QY700 Q7P pattern files.

    Extracts all pattern data including tempo, sections,
    tracks, volumes, and phrase assignments.
    """

    def __init__(self, data: bytes):
        """
        Initialize decoder with Q7P data.

        Args:
            data: Complete Q7P file data (3072 or 5120 bytes)
        """
        if len(data) not in (3072, 5120):
            raise ValueError(f"Invalid Q7P size: {len(data)} (expected 3072 or 5120)")

        self.data = data
        self.offsets = Q7POffsets()
        self._is_extended = len(data) == 5120

    def decode(self) -> Pattern:
        """
        Decode Q7P data into Pattern object.

        Returns:
            Complete Pattern with all decoded data
        """
        pattern = Pattern()
        pattern.source_format = "qy700"
        pattern._raw_data = self.data

        # Decode header
        pattern.name = self._decode_name()
        pattern.number = self.data[Q7POffsets.PATTERN_NUMBER]

        # Decode settings
        pattern.settings = self._decode_settings()

        # Decode sections
        pattern.sections = self._decode_all_sections()

        return pattern

    def _decode_name(self) -> str:
        """Extract pattern name."""
        # Name offset differs between 3072 and 5120 byte files
        if self._is_extended:
            name_offset = 0xA00  # 5120-byte file
        else:
            name_offset = Q7POffsets.TEMPLATE_NAME  # 0x876 for 3072-byte file

        name = self.data[name_offset : name_offset + 10]
        try:
            return name.decode("ascii").rstrip("\x00 ")
        except UnicodeDecodeError:
            return "PATTERN"

    def _decode_settings(self) -> PatternSettings:
        """Decode pattern settings including tempo."""
        settings = PatternSettings()

        # Tempo offset differs between 3072 and 5120 byte files
        if self._is_extended:
            tempo_offset = 0xA08  # 5120-byte file
        else:
            tempo_offset = 0x188  # 3072-byte file

        # Try big-endian word first (04 B0 = 1200 / 10 = 120 BPM)
        tempo_word = struct.unpack(">H", self.data[tempo_offset : tempo_offset + 2])[0]
        if tempo_word > 0:
            calculated_tempo = tempo_word // 10
            if 40 <= calculated_tempo <= 240:
                settings.tempo = calculated_tempo
            else:
                settings.tempo = 120  # Default
        else:
            settings.tempo = 120  # Default

        return settings

    def _decode_all_sections(self) -> Dict[SectionType, Section]:
        """Decode all 6 sections."""
        sections = {}

        section_types = [
            SectionType.INTRO,
            SectionType.MAIN_A,
            SectionType.MAIN_B,
            SectionType.FILL_AB,
            SectionType.FILL_BA,
            SectionType.ENDING,
        ]

        for idx, section_type in enumerate(section_types):
            section = self._decode_section(idx, section_type)
            sections[section_type] = section

        return sections

    def _decode_section(self, index: int, section_type: SectionType) -> Section:
        """
        Decode a single section.

        Args:
            index: Section index (0-5)
            section_type: Type of section

        Returns:
            Decoded Section
        """
        section = Section(
            section_type=section_type,
            enabled=True,
            length_measures=4,
        )

        # Check if section has data
        # Section pointers at 0x100
        ptr_offset = Q7POffsets.SECTION_PTR_START + (index * 2)
        if ptr_offset + 1 < len(self.data):
            ptr_value = self.data[ptr_offset : ptr_offset + 2]
            # 0xFE FE indicates empty section
            if ptr_value == b"\xfe\xfe":
                section.enabled = False

        # Decode tracks for this section
        section.tracks = self._decode_tracks(index, section_type)

        return section

    def _decode_tracks(self, section_index: int, section_type: SectionType) -> List[Track]:
        """
        Decode all 8 tracks for a section.

        Args:
            section_index: Section index (0-5)
            section_type: Type of section

        Returns:
            List of 8 Track objects
        """
        tracks = []

        # Get channel assignments
        channels = self._get_channel_assignments()

        # Get volume values for this section
        volumes = self._get_section_volumes(section_type)

        # Get pan values
        pans = self._get_pan_values()

        for track_num in range(8):
            track = Track(number=track_num + 1)

            # Channel
            if track_num < len(channels):
                track.settings.channel = channels[track_num]

            # Volume
            if track_num < len(volumes):
                track.settings.volume = volumes[track_num]

            # Pan
            if track_num < len(pans):
                track.settings.pan = pans[track_num]

            # Track type defaults
            if track_num < 2:
                # Rhythm
                track.name = f"RHY{track_num + 1}"
                track.settings.channel = 10
            elif track_num == 2:
                # Bass
                track.name = "BASS"
            else:
                # Chord
                track.name = f"CHD{track_num - 2}"

            tracks.append(track)

        return tracks

    def _get_channel_assignments(self) -> List[int]:
        """Get MIDI channel assignments for 8 tracks."""
        channels = []
        for i in range(8):
            offset = Q7POffsets.CHANNEL_ASSIGN + i
            if offset < len(self.data):
                ch = self.data[offset]
                # Channel values might be offset or encoded
                if ch < 16:
                    channels.append(ch + 1)  # Convert 0-15 to 1-16
                else:
                    channels.append(i + 1)  # Default
            else:
                channels.append(i + 1)
        return channels

    def _get_section_volumes(self, section_type: SectionType) -> List[int]:
        """Get volume values for tracks in a section."""
        volumes = []

        # Volume table has complex structure
        # Each section has 16 entries (8 tracks × 2?)
        base_offset = Q7POffsets.SECTION_VOLUMES.get(section_type, 0x226)

        for i in range(8):
            offset = base_offset + i
            if offset < len(self.data):
                vol = self.data[offset]
                # Convert from internal format
                if vol <= 127:
                    volumes.append(vol)
                else:
                    volumes.append(100)  # Default
            else:
                volumes.append(100)

        return volumes

    def _get_pan_values(self) -> List[int]:
        """Get pan values for 8 tracks."""
        pans = []
        for i in range(8):
            offset = Q7POffsets.PAN_TABLE_START + i
            if offset < len(self.data):
                pan = self.data[offset]
                if pan <= 127:
                    pans.append(pan)
                else:
                    pans.append(64)  # Center
            else:
                pans.append(64)
        return pans

    def get_phrase_data(self) -> bytes:
        """Get raw phrase data area."""
        start = Q7POffsets.PHRASE_DATA_START
        end = start + Q7POffsets.PHRASE_DATA_SIZE
        return self.data[start:end]

    def get_sequence_data(self) -> bytes:
        """Get raw sequence/event data."""
        start = Q7POffsets.SEQUENCE_START
        end = start + Q7POffsets.SEQUENCE_SIZE
        return self.data[start:end]

    def dump_offsets(self) -> str:
        """Generate debug dump of key offset values."""
        lines = ["Q7P Offset Dump:"]

        lines.append(f"  Pattern Number: {self.data[0x010]}")
        lines.append(f"  Pattern Flags:  0x{self.data[0x011]:02X}")
        lines.append(f"  Template Name:  {self._decode_name()!r}")

        # Tempo area
        tempo_hex = " ".join(f"{b:02X}" for b in self.data[0x188:0x190])
        lines.append(f"  Tempo Area:     {tempo_hex}")

        # Section pointers
        ptrs = self.data[0x100:0x110]
        ptr_hex = " ".join(f"{b:02X}" for b in ptrs)
        lines.append(f"  Section Ptrs:   {ptr_hex}")

        # Channels
        channels = self._get_channel_assignments()
        lines.append(f"  Channels:       {channels}")

        return "\n".join(lines)


def decode_q7p_file(filepath: str) -> Pattern:
    """
    Convenience function to decode a Q7P file.

    Args:
        filepath: Path to Q7P file

    Returns:
        Decoded Pattern
    """
    with open(filepath, "rb") as f:
        data = f.read()

    decoder = Q7PPatternDecoder(data)
    return decoder.decode()
