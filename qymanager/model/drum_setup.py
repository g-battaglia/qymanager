"""Drum Setup: per-note parameters."""

from dataclasses import dataclass, field

from qymanager.model.types import NoteOffMode


@dataclass
class DrumNote:
    pitch_coarse: int = 0
    pitch_fine: int = 0
    level: int = 100
    pan: int = 64
    reverb_send: int = 0
    chorus_send: int = 0
    variation_send: int = 0
    filter_cutoff: int = 0
    filter_resonance: int = 0
    eg_attack: int = 0
    eg_decay1: int = 0
    eg_decay2: int = 0
    alt_group: int = 0
    note_off_mode: NoteOffMode = NoteOffMode.STANDARD

    def validate(self) -> list[str]:
        errors: list[str] = []
        for name, val, lo, hi in [
            ("pitch_coarse", self.pitch_coarse, -64, 63),
            ("pitch_fine", self.pitch_fine, -64, 63),
            ("level", self.level, 0, 127),
            ("pan", self.pan, 0, 127),
            ("reverb_send", self.reverb_send, 0, 127),
            ("chorus_send", self.chorus_send, 0, 127),
            ("variation_send", self.variation_send, 0, 127),
            ("filter_cutoff", self.filter_cutoff, -64, 63),
            ("filter_resonance", self.filter_resonance, -64, 63),
            ("eg_attack", self.eg_attack, -64, 63),
            ("eg_decay1", self.eg_decay1, -64, 63),
            ("eg_decay2", self.eg_decay2, -64, 63),
            ("alt_group", self.alt_group, 0, 127),
        ]:
            if not lo <= val <= hi:
                errors.append(f"{name} must be {lo}-{hi}, got {val}")
        return errors


@dataclass
class DrumSetup:
    kit_index: int = 0
    notes: dict[int, DrumNote] = field(default_factory=dict)

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not 0 <= self.kit_index <= 1:
            errors.append(f"kit_index must be 0-1, got {self.kit_index}")
        for note_num, note in self.notes.items():
            if not 13 <= note_num <= 84:
                errors.append(f"note key must be 13-84, got {note_num}")
            errors.extend(note.validate())
        return errors
