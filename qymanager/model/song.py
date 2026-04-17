"""Song and SongTrack."""

from dataclasses import dataclass, field
from typing import Optional

from qymanager.model.types import SongTrackKind, TimeSig
from qymanager.model.event import MidiEvent


@dataclass
class SongTrack:
    index: int = 0
    kind: SongTrackKind = SongTrackKind.SEQ
    events: list[MidiEvent] = field(default_factory=list)
    midi_channel: Optional[int] = None
    mute: bool = False


@dataclass
class Song:
    index: int = 0
    name: str = ""
    tempo_bpm: float = 120.0
    time_sig: TimeSig = None  # type: ignore[assignment]
    tracks: list[SongTrack] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.time_sig is None:
            object.__setattr__(self, "time_sig", TimeSig())

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not 30.0 <= self.tempo_bpm <= 300.0:
            errors.append(f"tempo_bpm must be 30-300, got {self.tempo_bpm}")
        return errors
