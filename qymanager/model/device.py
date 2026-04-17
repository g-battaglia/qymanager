"""Device: top-level UDM container."""

from dataclasses import dataclass, field
from typing import Optional

from qymanager.model.types import DeviceModel
from qymanager.model.system import System
from qymanager.model.multi_part import MultiPart
from qymanager.model.drum_setup import DrumSetup
from qymanager.model.effects import Effects
from qymanager.model.pattern import Pattern
from qymanager.model.phrase import Phrase
from qymanager.model.song import Song
from qymanager.model.groove import GrooveTemplate
from qymanager.model.fingered_zone import FingeredZone
from qymanager.model.utility import UtilityFlags


@dataclass
class Device:
    model: DeviceModel = DeviceModel.QY70
    udm_version: str = "1.0"
    system: System = field(default_factory=System)
    multi_part: list[MultiPart] = field(default_factory=list)
    drum_setup: list[DrumSetup] = field(default_factory=list)
    effects: Effects = field(default_factory=Effects)
    songs: list[Song] = field(default_factory=list)
    patterns: list[Pattern] = field(default_factory=list)
    phrases_user: list[Phrase] = field(default_factory=list)
    groove_templates: list[GrooveTemplate] = field(default_factory=list)
    fingered_zone: FingeredZone = field(default_factory=FingeredZone)
    utility: UtilityFlags = field(default_factory=UtilityFlags)
    source_format: Optional[str] = None
    _raw_passthrough: Optional[bytes] = field(default=None, repr=False)

    def validate(self) -> list[str]:
        errors: list[str] = []
        errors.extend(self.system.validate())
        for i, part in enumerate(self.multi_part):
            errs = part.validate()
            errors.extend(f"multi_part[{i}]: {e}" for e in errs)
        for i, ds in enumerate(self.drum_setup):
            errs = ds.validate()
            errors.extend(f"drum_setup[{i}]: {e}" for e in errs)
        errors.extend(self.effects.validate())
        for i, pat in enumerate(self.patterns):
            errs = pat.validate()
            errors.extend(f"patterns[{i}]: {e}" for e in errs)
        for i, song in enumerate(self.songs):
            errs = song.validate()
            errors.extend(f"songs[{i}]: {e}" for e in errs)
        for i, phrase in enumerate(self.phrases_user):
            errs = phrase.validate()
            errors.extend(f"phrases_user[{i}]: {e}" for e in errs)
        for i, gt in enumerate(self.groove_templates):
            errs = gt.validate()
            errors.extend(f"groove_templates[{i}]: {e}" for e in errs)
        errors.extend(self.fingered_zone.validate())
        errors.extend(self.utility.validate())
        return errors

    @property
    def is_qy70(self) -> bool:
        return self.model == DeviceModel.QY70

    @property
    def is_qy700(self) -> bool:
        return self.model == DeviceModel.QY700

    @property
    def max_parts(self) -> int:
        return 16 if self.is_qy70 else 32

    @property
    def max_sections(self) -> int:
        return 6 if self.is_qy70 else 8
