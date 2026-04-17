"""Phrase: reusable musical building block."""

from dataclasses import dataclass, field

from qymanager.model.types import PhraseCategory, PhraseType, TimeSig
from qymanager.model.event import MidiEvent


@dataclass
class Phrase:
    index: int = 0
    name: str = ""
    category: PhraseCategory = PhraseCategory.DA
    beats: int = 4
    time_sig: TimeSig = None  # type: ignore[assignment]
    events: list[MidiEvent] = field(default_factory=list)
    phrase_type: PhraseType = PhraseType.BYPASS

    def __post_init__(self) -> None:
        if self.time_sig is None:
            object.__setattr__(self, "time_sig", TimeSig())

    @property
    def note_count(self) -> int:
        from qymanager.model.types import EventKind

        return sum(1 for e in self.events if e.kind == EventKind.NOTE_ON)

    def validate(self) -> list[str]:
        errors: list[str] = []
        if self.beats < 1 or self.beats > 16:
            errors.append(f"beats must be 1-16, got {self.beats}")
        return errors
