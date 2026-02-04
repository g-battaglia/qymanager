"""
QY70 Pattern decoder.

Decodes the phrase and section data from QY70 SysEx bulk dumps
into the common Pattern model.

Based on reverse engineering of QY70 SysEx data structure:
- AL 0x00-0x07: Section phrase data (Intro, MainA, MainB, FillAB, FillBA, Ending, + 2 extra)
- AL 0x08-0x2F: Track data blocks (organized by section)
- AL 0x7F: Style header/configuration
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from qyconv.models.pattern import Pattern, PatternSettings
from qyconv.models.section import Section, SectionType
from qyconv.models.track import Track, TrackSettings
from qyconv.models.phrase import Phrase, MidiEvent, EventType


@dataclass
class QY70SectionData:
    """Raw section data extracted from SysEx."""

    index: int
    phrase_data: bytes
    track_blocks: List[bytes]


class QY70PatternDecoder:
    """
    Decoder for QY70 pattern data.

    Converts decoded SysEx data into Pattern objects with
    full phrase and track information.
    """

    # Section mapping (AL values to SectionType)
    SECTION_MAP = {
        0x00: SectionType.INTRO,
        0x01: SectionType.MAIN_A,
        0x02: SectionType.MAIN_B,
        0x03: SectionType.FILL_AB,
        0x04: SectionType.FILL_BA,
        0x05: SectionType.ENDING,
    }

    # Track block offset: each section has tracks at AL = section_base + (section_index * 8)
    # Section 0 tracks at 0x00-0x07
    # Section 1 tracks at 0x08-0x0F
    # etc.

    def __init__(self):
        self.section_data: Dict[int, bytes] = {}
        self.header_data: bytes = b""

    def decode(self, section_data: Dict[int, bytes]) -> Pattern:
        """
        Decode QY70 section data into a Pattern.

        Args:
            section_data: Dict mapping AL index to decoded data bytes

        Returns:
            Decoded Pattern object
        """
        self.section_data = section_data
        self.header_data = section_data.get(0x7F, b"")

        pattern = Pattern()
        pattern.source_format = "qy70"

        # Decode header
        self._decode_header(pattern)

        # Decode each section
        for al_index, section_type in self.SECTION_MAP.items():
            section = self._decode_section(al_index, section_type)
            pattern.sections[section_type] = section

        return pattern

    def _decode_header(self, pattern: Pattern) -> None:
        """Decode style header/configuration data."""
        if len(self.header_data) < 16:
            return

        # The header structure is complex and partially understood
        # Key fields based on analysis:

        # Try to extract tempo (appears in header data)
        # Format is device-specific
        if len(self.header_data) >= 32:
            # Common tempo location patterns
            for offset in [0x0A, 0x0C, 0x10]:
                if offset + 1 < len(self.header_data):
                    potential_tempo = self.header_data[offset]
                    if 40 <= potential_tempo <= 240:
                        pattern.settings.tempo = potential_tempo
                        break

    def _decode_section(self, al_index: int, section_type: SectionType) -> Section:
        """
        Decode a single section.

        Args:
            al_index: AL byte value for this section's phrase data
            section_type: Type of section

        Returns:
            Decoded Section
        """
        section = Section(
            section_type=section_type,
            enabled=True,
            length_measures=4,  # Default
        )

        # Get phrase data for this section
        phrase_data = self.section_data.get(al_index, b"")

        # Decode tracks
        section.tracks = self._decode_tracks(al_index, phrase_data)

        # Try to determine section length from phrase data
        if phrase_data:
            section.length_measures = self._estimate_length(phrase_data)
            section._raw_data = phrase_data

        return section

    def _decode_tracks(self, section_al: int, phrase_data: bytes) -> List[Track]:
        """
        Decode track data for a section.

        Args:
            section_al: AL index for the section
            phrase_data: Raw phrase data

        Returns:
            List of 8 Track objects
        """
        tracks = []

        # Phrase data structure (based on analysis):
        # Each section's phrase data contains info for all 8 tracks
        # First bytes appear to be common header: 08 04 82 01 00 40 20 08 04 82 01 00 06 1C

        for track_num in range(8):
            track = Track(number=track_num + 1)

            # Extract track-specific data from phrase data
            if phrase_data and len(phrase_data) > 20:
                track = self._decode_single_track(track_num, phrase_data)
            else:
                # Empty track
                track.enabled = False

            tracks.append(track)

        return tracks

    def _decode_single_track(self, track_num: int, phrase_data: bytes) -> Track:
        """
        Decode a single track from phrase data.

        Args:
            track_num: Track number (0-7)
            phrase_data: Section phrase data

        Returns:
            Track object
        """
        track = Track(number=track_num + 1)

        # Track header appears at fixed offsets within phrase data
        # Based on analysis, data structure repeats patterns

        # The phrase data contains encoded MIDI events
        # We'll extract what we can, but full decoding requires
        # understanding the proprietary compression

        # For now, mark track as enabled if we have phrase data
        track.enabled = len(phrase_data) > 20

        # Default settings based on track type
        if track_num < 2:
            # Rhythm tracks
            track.settings.channel = 10
            track.settings.program = 0
        elif track_num == 2:
            # Bass
            track.settings.channel = 9
            track.settings.program = 33
        else:
            # Chord tracks
            track.settings.channel = track_num + 8
            track.settings.program = 0

        return track

    def _estimate_length(self, phrase_data: bytes) -> int:
        """
        Estimate section length in measures from phrase data.

        Args:
            phrase_data: Raw phrase data

        Returns:
            Estimated length in measures
        """
        # Length might be encoded in header bytes
        # Common lengths: 1, 2, 4, 8 measures

        if len(phrase_data) < 256:
            return 1
        elif len(phrase_data) < 512:
            return 2
        elif len(phrase_data) < 1024:
            return 4
        else:
            return 8

    def extract_phrases(self, section_al: int) -> List[Phrase]:
        """
        Extract phrase objects from section data.

        Args:
            section_al: Section AL index

        Returns:
            List of Phrase objects
        """
        phrases = []
        phrase_data = self.section_data.get(section_al, b"")

        if not phrase_data:
            return phrases

        # Parse the phrase data format
        # This is a simplified parser that creates basic phrase structures
        # Full implementation would decode the MIDI events

        # Create a single phrase with the raw data
        phrase = Phrase(
            id=section_al,
            name=f"Section_{section_al:02X}",
            length_ticks=1920,  # Default 1 bar at 480 PPQN
        )

        # TODO: Decode MIDI events from phrase_data
        # The data appears to be a proprietary format

        phrases.append(phrase)
        return phrases


def decode_qy70_pattern(section_data: Dict[int, bytes]) -> Pattern:
    """
    Convenience function to decode QY70 pattern data.

    Args:
        section_data: Dict mapping AL index to decoded data

    Returns:
        Decoded Pattern
    """
    decoder = QY70PatternDecoder()
    return decoder.decode(section_data)
