"""Pattern: sections, chord track, tempo, time sig."""

from dataclasses import dataclass, field
from typing import Optional

from qymanager.model.types import SectionName, TimeSig
from qymanager.model.section import Section

CHORD_ROOTS = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
CHORD_TYPES = [
    "MAJ",
    "MIN",
    "DIM",
    "AUG",
    "SUS2",
    "SUS4",
    "7",
    "M7",
    "m7",
    "mM7",
    "DIM7",
    "AUG7",
    "7sus4",
    "7sus2",
    "6",
    "m6",
    "ADD9",
    "mADD9",
    "9",
    "M9",
    "m9",
    "11",
    "M11",
    "m11",
    "13",
    "M13",
    "m13",
    "MAJ7(#11)",
]


@dataclass(frozen=True)
class ChordEntry:
    root: int = 0
    chord_type: int = 0
    on_bass: bool = False
    measure: int = 0
    beat: int = 0

    def __post_init__(self) -> None:
        if not 0 <= self.root <= 11:
            raise ValueError(f"root must be 0-11, got {self.root}")
        if not 0 <= self.chord_type <= 27:
            raise ValueError(f"chord_type must be 0-27, got {self.chord_type}")

    @property
    def root_name(self) -> str:
        return CHORD_ROOTS[self.root]

    @property
    def chord_type_name(self) -> str:
        return CHORD_TYPES[self.chord_type]


@dataclass
class ChordTrack:
    entries: list[ChordEntry] = field(default_factory=list)

    def validate(self) -> list[str]:
        errors: list[str] = []
        for i, entry in enumerate(self.entries):
            try:
                entry.__post_init__()
            except ValueError as e:
                errors.append(f"entry[{i}]: {e}")
        return errors


@dataclass
class Pattern:
    index: int = 0
    name: str = ""
    tempo_bpm: float = 120.0
    measures: int = 4
    time_sig: TimeSig = None  # type: ignore[assignment]
    sections: dict[SectionName, Section] = field(default_factory=dict)
    chord_track: ChordTrack = None  # type: ignore[assignment]
    groove_ref: Optional[int] = None

    def __post_init__(self) -> None:
        if self.time_sig is None:
            object.__setattr__(self, "time_sig", TimeSig())
        if self.chord_track is None:
            object.__setattr__(self, "chord_track", ChordTrack())

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not 30.0 <= self.tempo_bpm <= 300.0:
            errors.append(f"tempo_bpm must be 30-300, got {self.tempo_bpm}")
        if self.measures < 1:
            errors.append(f"measures must be >= 1, got {self.measures}")
        if len(self.name) > 10:
            errors.append(f"name too long: {len(self.name)} chars (max 10)")
        errors.extend(self.chord_track.validate())
        for key, section in self.sections.items():
            errs = section.validate()
            errors.extend(f"section[{key.value}]: {e}" for e in errs)
        return errors
