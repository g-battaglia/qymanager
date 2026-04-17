"""Effects: Reverb, Chorus, Variation."""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ReverbBlock:
    type_code: int = 0
    return_level: int = 40
    params: dict[int, int] = field(default_factory=dict)

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not 0 <= self.type_code <= 10:
            errors.append(f"reverb type_code must be 0-10, got {self.type_code}")
        if not 0 <= self.return_level <= 127:
            errors.append(f"return_level must be 0-127, got {self.return_level}")
        return errors


@dataclass
class ChorusBlock:
    type_code: int = 0
    return_level: int = 40
    params: dict[int, int] = field(default_factory=dict)

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not 0 <= self.type_code <= 10:
            errors.append(f"chorus type_code must be 0-10, got {self.type_code}")
        if not 0 <= self.return_level <= 127:
            errors.append(f"return_level must be 0-127, got {self.return_level}")
        return errors


@dataclass
class VariationBlock:
    type_code: int = 0
    connection: str = "system"
    return_level: int = 40
    params: dict[int, int] = field(default_factory=dict)

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not 0 <= self.type_code <= 42:
            errors.append(f"variation type_code must be 0-42, got {self.type_code}")
        if self.connection not in ("system", "insertion"):
            errors.append(f"connection must be system/insertion, got {self.connection}")
        if not 0 <= self.return_level <= 127:
            errors.append(f"return_level must be 0-127, got {self.return_level}")
        return errors


@dataclass
class Effects:
    reverb: ReverbBlock = field(default_factory=ReverbBlock)
    chorus: ChorusBlock = field(default_factory=ChorusBlock)
    variation: Optional[VariationBlock] = None

    def validate(self) -> list[str]:
        errors: list[str] = []
        errors.extend(self.reverb.validate())
        errors.extend(self.chorus.validate())
        if self.variation is not None:
            errors.extend(self.variation.validate())
        return errors
