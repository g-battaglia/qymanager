"""Groove Template: 16-step timing/velocity/gate offsets."""

from dataclasses import dataclass, field


@dataclass
class GrooveStep:
    timing_offset: int = 100
    velocity_scale: int = 100
    gate_scale: int = 100

    def validate(self) -> list[str]:
        errors: list[str] = []
        for name, val in [
            ("timing_offset", self.timing_offset),
            ("velocity_scale", self.velocity_scale),
            ("gate_scale", self.gate_scale),
        ]:
            if not 0 <= val <= 200:
                errors.append(f"{name} must be 0-200, got {val}")
        return errors


@dataclass
class GrooveTemplate:
    index: int = 0
    name: str = ""
    steps: list[GrooveStep] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.steps:
            object.__setattr__(self, "steps", [GrooveStep() for _ in range(16)])

    def validate(self) -> list[str]:
        errors: list[str] = []
        if len(self.steps) != 16:
            errors.append(f"must have exactly 16 steps, got {len(self.steps)}")
        for i, step in enumerate(self.steps):
            errs = step.validate()
            errors.extend(f"step[{i}]: {e}" for e in errs)
        return errors
