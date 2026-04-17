"""Utility flags (device-specific settings)."""

from dataclasses import dataclass


@dataclass
class UtilityFlags:
    click_on: bool = False
    click_in_measure: bool = True
    click_velocity: int = 100
    quantize_value: int = 0
    interval_time_ms: int = 0

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not 0 <= self.click_velocity <= 127:
            errors.append(f"click_velocity must be 0-127, got {self.click_velocity}")
        if not 0 <= self.interval_time_ms <= 500:
            errors.append(f"interval_time_ms must be 0-500, got {self.interval_time_ms}")
        return errors
