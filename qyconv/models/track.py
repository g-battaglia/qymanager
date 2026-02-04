"""
Track data model for QY patterns.
"""

from dataclasses import dataclass, field
from typing import List, Optional
from qyconv.models.phrase import Phrase


@dataclass
class TrackSettings:
    """
    Track parameter settings.

    These settings control how the track sounds and responds
    to chord changes in the accompaniment system.
    """

    # MIDI channel (1-16)
    channel: int = 1

    # Program selection
    program: int = 0  # Program change 0-127
    bank_msb: int = 0  # Bank select MSB (CC#0)
    bank_lsb: int = 0  # Bank select LSB (CC#32)

    # Volume and expression
    volume: int = 100  # Volume (CC#7), 0-127
    pan: int = 64  # Pan (CC#10), 0-127 (64=center)
    expression: int = 127  # Expression (CC#11), 0-127

    # Effects sends
    reverb_send: int = 40  # Reverb send level (CC#91)
    chorus_send: int = 0  # Chorus send level (CC#93)

    # Note parameters
    note_shift: int = 0  # Transpose in semitones (-24 to +24)
    velocity_offset: int = 0  # Velocity adjustment (-64 to +63)
    gate_time: int = 100  # Gate time percentage (1-200%)

    # Chord/accompaniment settings
    chord_mode: int = 0  # How track responds to chord changes
    ntt: int = 0  # Note Transposition Table type
    ntr: int = 0  # Note Transposition Rule
    high_key: int = 127  # Highest playable note
    low_key: int = 0  # Lowest playable note


@dataclass
class Track:
    """
    A single track within a pattern section.

    QY patterns have 8 tracks per section:
    - Track 1-2: Rhythm (drums)
    - Track 3: Bass
    - Track 4-8: Chord accompaniment

    Attributes:
        number: Track number (1-8)
        name: Optional track name
        enabled: Whether track is active
        mute: Whether track is muted
        settings: Track parameter settings
        phrase_refs: List of phrase references
        phrases: Inline phrase data (if not using references)
    """

    number: int = 1
    name: str = ""
    enabled: bool = True
    mute: bool = False
    settings: TrackSettings = field(default_factory=TrackSettings)
    phrase_refs: List[int] = field(default_factory=list)
    phrases: List[Phrase] = field(default_factory=list)

    # Raw data storage for round-trip conversion
    _raw_data: Optional[bytes] = field(default=None, repr=False)

    @property
    def is_rhythm(self) -> bool:
        """Check if this is a rhythm (drum) track."""
        return self.number in (1, 2)

    @property
    def is_bass(self) -> bool:
        """Check if this is the bass track."""
        return self.number == 3

    @property
    def is_chord(self) -> bool:
        """Check if this is a chord accompaniment track."""
        return self.number >= 4

    @property
    def has_data(self) -> bool:
        """Check if track has any musical data."""
        return bool(self.phrase_refs or self.phrases)

    def get_default_channel(self) -> int:
        """
        Get the default MIDI channel for this track type.

        Returns:
            Default channel number (1-16)
        """
        if self.number == 1:
            return 10  # Drums on channel 10
        elif self.number == 2:
            return 10  # Percussion also on channel 10
        else:
            return self.number + 7  # Tracks 3-8 on channels 10-15... or custom

    @classmethod
    def create_rhythm_track(cls, number: int = 1) -> "Track":
        """Create a rhythm track with drum defaults."""
        settings = TrackSettings(
            channel=10,
            program=0,  # Standard Kit
            bank_msb=127,
            bank_lsb=0,
            chord_mode=0,  # Drums don't follow chords
        )
        return cls(number=number, name="RHYTHM", settings=settings)

    @classmethod
    def create_bass_track(cls) -> "Track":
        """Create a bass track with typical defaults."""
        settings = TrackSettings(
            channel=9,
            program=33,  # Finger Bass
            bank_msb=0,
            bank_lsb=0,
            chord_mode=1,  # Follow chord root
        )
        return cls(number=3, name="BASS", settings=settings)

    @classmethod
    def create_chord_track(cls, number: int) -> "Track":
        """Create a chord accompaniment track."""
        if not 4 <= number <= 8:
            raise ValueError(f"Chord track number must be 4-8, got {number}")

        settings = TrackSettings(
            channel=number + 6,  # Channels 10-14
            program=0,  # Piano default
            bank_msb=0,
            bank_lsb=0,
            chord_mode=2,  # Full chord following
        )
        return cls(number=number, name=f"CHORD{number - 3}", settings=settings)


def create_default_tracks() -> List[Track]:
    """
    Create default set of 8 tracks for a pattern section.

    Returns:
        List of 8 Track objects with standard configuration
    """
    return [
        Track.create_rhythm_track(1),
        Track.create_rhythm_track(2),
        Track.create_bass_track(),
        Track.create_chord_track(4),
        Track.create_chord_track(5),
        Track.create_chord_track(6),
        Track.create_chord_track(7),
        Track.create_chord_track(8),
    ]
