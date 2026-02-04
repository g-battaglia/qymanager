"""
Pattern data model - the top-level container for QY pattern data.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from qyconv.models.section import Section, SectionType, create_default_sections
from qyconv.models.phrase import Phrase


@dataclass
class PatternSettings:
    """
    Global pattern settings.
    """

    # Tempo
    tempo: int = 120  # BPM (40-240)
    tempo_fine: int = 0  # Fine tempo adjustment

    # Playback
    volume: int = 100  # Master volume (0-127)

    # Chord detection
    chord_detect: bool = True  # Enable chord detection
    chord_root: int = 0  # Root note (0=C, 1=C#, etc.)
    chord_type: int = 0  # Chord type (0=major, etc.)

    # Sync
    sync_start: bool = False  # Wait for MIDI start
    sync_stop: bool = False  # Stop on MIDI stop


@dataclass
class Pattern:
    """
    Complete pattern data structure.

    A Pattern represents a complete style/pattern that can be loaded
    into QY70 or QY700. It contains multiple sections (Intro, Main,
    Fill, Ending) each with 8 tracks.

    Attributes:
        name: Pattern name (max 10 characters)
        number: Pattern number/slot
        sections: Dictionary of sections by type
        phrases: Shared phrase library
        settings: Global pattern settings
        source_format: Original file format ("qy70" or "qy700")
    """

    name: str = "NEW STYLE "
    number: int = 0
    sections: Dict[SectionType, Section] = field(default_factory=dict)
    phrases: List[Phrase] = field(default_factory=list)
    settings: PatternSettings = field(default_factory=PatternSettings)
    source_format: Optional[str] = None

    # Raw data for round-trip conversion
    _raw_header: Optional[bytes] = field(default=None, repr=False)
    _raw_data: Optional[bytes] = field(default=None, repr=False)

    def __post_init__(self):
        """Initialize default sections if empty."""
        if not self.sections:
            for section in create_default_sections():
                self.sections[section.section_type] = section

    @property
    def tempo(self) -> int:
        """Get pattern tempo in BPM."""
        return self.settings.tempo

    @tempo.setter
    def tempo(self, value: int) -> None:
        """Set pattern tempo."""
        self.settings.tempo = max(40, min(240, value))

    @property
    def has_intro(self) -> bool:
        """Check if pattern has an intro section with data."""
        intro = self.sections.get(SectionType.INTRO)
        return intro is not None and intro.has_data

    @property
    def has_ending(self) -> bool:
        """Check if pattern has an ending section with data."""
        ending = self.sections.get(SectionType.ENDING)
        return ending is not None and ending.has_data

    def get_section(self, section_type: SectionType) -> Optional[Section]:
        """Get a section by type."""
        return self.sections.get(section_type)

    def get_main_sections(self) -> List[Section]:
        """Get all main sections (A, B, C, D)."""
        main_types = [
            SectionType.MAIN_A,
            SectionType.MAIN_B,
            SectionType.MAIN_C,
            SectionType.MAIN_D,
        ]
        return [s for t in main_types if (s := self.sections.get(t)) is not None]

    def get_all_tracks(self) -> List:
        """
        Get all tracks from all sections.

        Returns:
            List of (section_type, track) tuples
        """
        result = []
        for section_type, section in self.sections.items():
            for track in section.tracks:
                result.append((section_type, track))
        return result

    def get_active_sections(self) -> List[Section]:
        """Get sections that have musical data."""
        return [s for s in self.sections.values() if s.has_data and s.enabled]

    def validate(self) -> List[str]:
        """
        Validate pattern data.

        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []

        # Name validation
        if len(self.name) > 10:
            errors.append(f"Pattern name too long: {len(self.name)} chars (max 10)")

        # Tempo validation
        if not 40 <= self.settings.tempo <= 240:
            errors.append(f"Invalid tempo: {self.settings.tempo} (must be 40-240)")

        # Section validation
        for section_type, section in self.sections.items():
            if len(section.tracks) != 8:
                errors.append(
                    f"Section {section_type.name} has {len(section.tracks)} tracks (need 8)"
                )

            if section.length_measures < 1:
                errors.append(
                    f"Section {section_type.name} has invalid length: {section.length_measures}"
                )

        return errors

    @classmethod
    def create_empty(cls, name: str = "NEW STYLE ", tempo: int = 120) -> "Pattern":
        """
        Create an empty pattern with default sections.

        Args:
            name: Pattern name
            tempo: Tempo in BPM

        Returns:
            New Pattern instance
        """
        pattern = cls(name=name.upper().ljust(10)[:10])
        pattern.settings.tempo = tempo
        return pattern

    def copy(self) -> "Pattern":
        """Create a deep copy of this pattern."""
        import copy

        return copy.deepcopy(self)

    def __repr__(self) -> str:
        active = len(self.get_active_sections())
        return f"Pattern(name={self.name!r}, tempo={self.tempo}, sections={active}/{len(self.sections)})"
