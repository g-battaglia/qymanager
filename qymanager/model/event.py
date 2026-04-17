"""MIDI event in UDM."""

from dataclasses import dataclass
from typing import Optional

from qymanager.model.types import EventKind


@dataclass(frozen=True)
class MidiEvent:
    tick: int = 0
    channel: int = 0
    kind: EventKind = EventKind.NOTE_ON
    data1: int = 0
    data2: int = 0
    nrpn_msb: Optional[int] = None
    nrpn_lsb: Optional[int] = None
    sysex_data: Optional[bytes] = None

    def __post_init__(self) -> None:
        if self.tick < 0:
            raise ValueError(f"tick must be >= 0, got {self.tick}")
        if not 0 <= self.channel <= 15:
            raise ValueError(f"channel must be 0-15, got {self.channel}")
        if not 0 <= self.data1 <= 127:
            raise ValueError(f"data1 must be 0-127, got {self.data1}")
        if not 0 <= self.data2 <= 127:
            raise ValueError(f"data2 must be 0-127, got {self.data2}")

    @property
    def is_note(self) -> bool:
        return self.kind in (EventKind.NOTE_ON, EventKind.NOTE_OFF)

    @property
    def note(self) -> int:
        return self.data1

    @property
    def velocity(self) -> int:
        return self.data2
