"""Multi Part parameters."""

from dataclasses import dataclass

from qymanager.model.types import MonoPoly, KeyOnAssign
from qymanager.model.voice import Voice


@dataclass
class MultiPart:
    part_index: int = 0
    rx_channel: int = 0
    voice: Voice = None  # type: ignore[assignment]
    volume: int = 100
    pan: int = 64
    reverb_send: int = 40
    chorus_send: int = 0
    variation_send: int = 0
    cutoff: int = 0
    resonance: int = 0
    eg_attack: int = 0
    eg_decay: int = 0
    eg_release: int = 0
    mono_poly: MonoPoly = MonoPoly.POLY
    key_on_assign: KeyOnAssign = KeyOnAssign.MULTI
    dry_level: int = 0x40
    bend_pitch: int = 2

    def __post_init__(self) -> None:
        if self.voice is None:
            object.__setattr__(self, "voice", Voice())

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not 0 <= self.part_index <= 31:
            errors.append(f"part_index must be 0-31, got {self.part_index}")
        if not 0 <= self.rx_channel <= 16:
            errors.append(f"rx_channel must be 0-16, got {self.rx_channel}")
        for name, val, lo, hi in [
            ("volume", self.volume, 0, 127),
            ("pan", self.pan, 0, 127),
            ("reverb_send", self.reverb_send, 0, 127),
            ("chorus_send", self.chorus_send, 0, 127),
            ("variation_send", self.variation_send, 0, 127),
            ("dry_level", self.dry_level, 0, 127),
            ("bend_pitch", self.bend_pitch, 0, 24),
        ]:
            if not lo <= val <= hi:
                errors.append(f"{name} must be {lo}-{hi}, got {val}")
        for name, val in [("cutoff", self.cutoff), ("resonance", self.resonance)]:
            if not -64 <= val <= 63:
                errors.append(f"{name} must be -64..+63, got {val}")
        return errors
