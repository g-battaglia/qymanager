"""Section and PatternTrack in a pattern."""

from dataclasses import dataclass, field

from qymanager.model.types import SectionName, TransposeRule
from qymanager.model.voice import Voice


@dataclass
class PatternTrack:
    phrase_ref: int = 0
    midi_channel: int = 0
    voice: Voice = None  # type: ignore[assignment]
    transpose_rule: TransposeRule = TransposeRule.BYPASS
    mute: bool = False
    pan: int = 64
    volume: int = 100
    reverb_send: int = 0
    chorus_send: int = 0

    def __post_init__(self) -> None:
        if self.voice is None:
            object.__setattr__(self, "voice", Voice())

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not 0 <= self.midi_channel <= 15:
            errors.append(f"midi_channel must be 0-15, got {self.midi_channel}")
        if not 0 <= self.pan <= 127:
            errors.append(f"pan must be 0-127, got {self.pan}")
        if not 0 <= self.volume <= 127:
            errors.append(f"volume must be 0-127, got {self.volume}")
        return errors


@dataclass
class Section:
    name: SectionName = SectionName.MAIN_A
    tracks: list[PatternTrack] = field(default_factory=list)
    enabled: bool = True

    def validate(self) -> list[str]:
        errors: list[str] = []
        for i, t in enumerate(self.tracks):
            errs = t.validate()
            errors.extend(f"track[{i}]: {e}" for e in errs)
        return errors
