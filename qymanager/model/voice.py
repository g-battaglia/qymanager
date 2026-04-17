"""Voice selection: Bank MSB + LSB + Program."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Voice:
    bank_msb: int = 0
    bank_lsb: int = 0
    program: int = 0

    def __post_init__(self) -> None:
        for name, val in [("bank_msb", self.bank_msb), ("bank_lsb", self.bank_lsb)]:
            if not 0 <= val <= 127:
                raise ValueError(f"{name} must be 0-127, got {val}")
        if not 0 <= self.program <= 127:
            raise ValueError(f"program must be 0-127, got {self.program}")

    @property
    def is_drum(self) -> bool:
        return self.bank_msb == 127
