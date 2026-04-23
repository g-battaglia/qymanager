"""System parameters."""

from dataclasses import dataclass

from qymanager.model.types import MidiSync


@dataclass
class MidiFilters:
    note: bool = True
    cc: bool = True
    pb: bool = True
    sysex: bool = True
    program: bool = True
    aftertouch: bool = True


@dataclass
class System:
    master_tune: int = 0
    master_volume: int = 100
    master_attenuator: int = 0
    transpose: int = 0
    midi_sync: MidiSync = MidiSync.INTERNAL
    device_id: int = 0
    echo_back: bool = False
    local_on: bool = True

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not -100 <= self.master_tune <= 100:
            errors.append(f"master_tune must be -100..+100, got {self.master_tune}")
        if not 0 <= self.master_volume <= 127:
            errors.append(f"master_volume must be 0-127, got {self.master_volume}")
        if not 0 <= self.master_attenuator <= 127:
            errors.append(
                f"master_attenuator must be 0-127, got {self.master_attenuator}"
            )
        if not -24 <= self.transpose <= 24:
            errors.append(f"transpose must be -24..+24, got {self.transpose}")
        if not 0 <= self.device_id <= 15:
            errors.append(f"device_id must be 0-15, got {self.device_id}")
        return errors
