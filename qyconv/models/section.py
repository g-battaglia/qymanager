"""
Section data model for QY patterns.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional
from qyconv.models.track import Track, create_default_tracks


class SectionType(Enum):
    """
    Pattern section types.

    QY devices organize patterns into sections that serve different
    musical purposes during accompaniment playback.
    """

    INTRO = "intro"
    MAIN_A = "main_a"
    MAIN_B = "main_b"
    FILL_AB = "fill_ab"  # Fill from A to B
    FILL_BA = "fill_ba"  # Fill from B to A
    ENDING = "ending"

    # Extended sections (QY700 specific)
    MAIN_C = "main_c"
    MAIN_D = "main_d"
    INTRO_2 = "intro_2"
    ENDING_2 = "ending_2"
    BREAK = "break"

    @classmethod
    def from_index(cls, index: int) -> "SectionType":
        """
        Get section type from numeric index.

        Args:
            index: Section index (0-5 for QY70, 0-10 for QY700)

        Returns:
            Corresponding SectionType
        """
        mapping = [
            cls.INTRO,
            cls.MAIN_A,
            cls.MAIN_B,
            cls.FILL_AB,
            cls.FILL_BA,
            cls.ENDING,
            cls.MAIN_C,
            cls.MAIN_D,
            cls.INTRO_2,
            cls.ENDING_2,
            cls.BREAK,
        ]
        if 0 <= index < len(mapping):
            return mapping[index]
        raise ValueError(f"Invalid section index: {index}")

    def to_index(self) -> int:
        """Get numeric index for this section type."""
        mapping = {
            self.INTRO: 0,
            self.MAIN_A: 1,
            self.MAIN_B: 2,
            self.FILL_AB: 3,
            self.FILL_BA: 4,
            self.ENDING: 5,
            self.MAIN_C: 6,
            self.MAIN_D: 7,
            self.INTRO_2: 8,
            self.ENDING_2: 9,
            self.BREAK: 10,
        }
        return mapping[self]

    @property
    def is_main(self) -> bool:
        """Check if this is a main section."""
        return self in (self.MAIN_A, self.MAIN_B, self.MAIN_C, self.MAIN_D)

    @property
    def is_fill(self) -> bool:
        """Check if this is a fill section."""
        return self in (self.FILL_AB, self.FILL_BA)

    @property
    def display_name(self) -> str:
        """Get human-readable section name."""
        names = {
            self.INTRO: "Intro",
            self.MAIN_A: "Main A",
            self.MAIN_B: "Main B",
            self.FILL_AB: "Fill A→B",
            self.FILL_BA: "Fill B→A",
            self.ENDING: "Ending",
            self.MAIN_C: "Main C",
            self.MAIN_D: "Main D",
            self.INTRO_2: "Intro 2",
            self.ENDING_2: "Ending 2",
            self.BREAK: "Break",
        }
        return names[self]


@dataclass
class Section:
    """
    A pattern section containing tracks and timing information.

    Each section represents a distinct part of a musical pattern
    (intro, main, fill, ending) that can be triggered during
    accompaniment playback.

    Attributes:
        section_type: Type of section (intro, main, etc.)
        enabled: Whether section is active
        length_measures: Length in measures
        time_numerator: Time signature numerator (beats per measure)
        time_denominator: Time signature denominator (beat unit)
        tracks: List of 8 tracks
    """

    section_type: SectionType = SectionType.MAIN_A
    enabled: bool = True
    length_measures: int = 4
    time_numerator: int = 4
    time_denominator: int = 4
    tracks: List[Track] = field(default_factory=create_default_tracks)

    # Raw data for round-trip conversion
    _raw_data: Optional[bytes] = field(default=None, repr=False)

    @property
    def length_beats(self) -> int:
        """Get length in beats."""
        return self.length_measures * self.time_numerator

    @property
    def length_ticks(self) -> int:
        """
        Get length in MIDI ticks.

        Assumes 480 PPQN (ticks per quarter note).
        """
        ppqn = 480
        beats_per_measure = self.time_numerator
        ticks_per_beat = (ppqn * 4) // self.time_denominator
        return self.length_measures * beats_per_measure * ticks_per_beat

    @property
    def has_data(self) -> bool:
        """Check if any track has musical data."""
        return any(track.has_data for track in self.tracks)

    @property
    def active_tracks(self) -> List[Track]:
        """Get list of tracks that have data."""
        return [t for t in self.tracks if t.has_data and t.enabled]

    def get_track(self, number: int) -> Optional[Track]:
        """
        Get track by number (1-8).

        Args:
            number: Track number

        Returns:
            Track if found, None otherwise
        """
        for track in self.tracks:
            if track.number == number:
                return track
        return None

    @classmethod
    def create_empty(cls, section_type: SectionType, length_measures: int = 4) -> "Section":
        """
        Create an empty section with default tracks.

        Args:
            section_type: Type of section to create
            length_measures: Section length

        Returns:
            New Section instance
        """
        return cls(
            section_type=section_type,
            enabled=True,
            length_measures=length_measures,
            tracks=create_default_tracks(),
        )


def create_default_sections() -> List[Section]:
    """
    Create default set of 6 sections for a QY70-compatible pattern.

    Returns:
        List of Section objects for Intro, MainA/B, Fills, Ending
    """
    return [
        Section.create_empty(SectionType.INTRO, length_measures=2),
        Section.create_empty(SectionType.MAIN_A, length_measures=4),
        Section.create_empty(SectionType.MAIN_B, length_measures=4),
        Section.create_empty(SectionType.FILL_AB, length_measures=1),
        Section.create_empty(SectionType.FILL_BA, length_measures=1),
        Section.create_empty(SectionType.ENDING, length_measures=2),
    ]
