"""Fingered Zone for chord detection."""

from dataclasses import dataclass


@dataclass
class FingeredZone:
    low_note: int = 0
    high_note: int = 60

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not 0 <= self.low_note <= 127:
            errors.append(f"low_note must be 0-127, got {self.low_note}")
        if not 0 <= self.high_note <= 127:
            errors.append(f"high_note must be 0-127, got {self.high_note}")
        if self.low_note > self.high_note:
            errors.append(f"low_note ({self.low_note}) > high_note ({self.high_note})")
        return errors
