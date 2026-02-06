"""
MIDI event and phrase data models.
"""

from dataclasses import dataclass, field
from enum import IntEnum
from typing import List, Optional


class EventType(IntEnum):
    """MIDI event types."""

    NOTE_OFF = 0x80
    NOTE_ON = 0x90
    POLY_PRESSURE = 0xA0
    CONTROL_CHANGE = 0xB0
    PROGRAM_CHANGE = 0xC0
    CHANNEL_PRESSURE = 0xD0
    PITCH_BEND = 0xE0
    SYSEX = 0xF0
    META = 0xFF


@dataclass
class MidiEvent:
    """
    A single MIDI event.

    Attributes:
        delta_time: Time since previous event in ticks
        event_type: Type of MIDI event
        channel: MIDI channel (0-15 for channel messages)
        data1: First data byte (note number, CC number, etc.)
        data2: Second data byte (velocity, CC value, etc.)
        data: Raw data for SysEx/Meta events
    """

    delta_time: int
    event_type: EventType
    channel: int = 0
    data1: int = 0
    data2: int = 0
    data: Optional[bytes] = None

    @property
    def is_note_on(self) -> bool:
        """Check if this is a note-on event with velocity > 0."""
        return self.event_type == EventType.NOTE_ON and self.data2 > 0

    @property
    def is_note_off(self) -> bool:
        """Check if this is a note-off event (or note-on with velocity 0)."""
        return self.event_type == EventType.NOTE_OFF or (
            self.event_type == EventType.NOTE_ON and self.data2 == 0
        )

    @property
    def note(self) -> int:
        """Get note number for note events."""
        return self.data1

    @property
    def velocity(self) -> int:
        """Get velocity for note events."""
        return self.data2

    def to_bytes(self) -> bytes:
        """
        Convert event to raw MIDI bytes (without delta time).

        Returns:
            MIDI event bytes
        """
        status = self.event_type | (self.channel & 0x0F)

        if self.event_type in (EventType.PROGRAM_CHANGE, EventType.CHANNEL_PRESSURE):
            return bytes([status, self.data1])
        elif self.event_type == EventType.SYSEX:
            return self.data or bytes([0xF0, 0xF7])
        else:
            return bytes([status, self.data1, self.data2])

    @classmethod
    def note_on(cls, channel: int, note: int, velocity: int, delta_time: int = 0) -> "MidiEvent":
        """Create a note-on event."""
        return cls(
            delta_time=delta_time,
            event_type=EventType.NOTE_ON,
            channel=channel,
            data1=note,
            data2=velocity,
        )

    @classmethod
    def note_off(
        cls, channel: int, note: int, velocity: int = 0, delta_time: int = 0
    ) -> "MidiEvent":
        """Create a note-off event."""
        return cls(
            delta_time=delta_time,
            event_type=EventType.NOTE_OFF,
            channel=channel,
            data1=note,
            data2=velocity,
        )

    @classmethod
    def control_change(cls, channel: int, cc: int, value: int, delta_time: int = 0) -> "MidiEvent":
        """Create a control change event."""
        return cls(
            delta_time=delta_time,
            event_type=EventType.CONTROL_CHANGE,
            channel=channel,
            data1=cc,
            data2=value,
        )

    @classmethod
    def program_change(cls, channel: int, program: int, delta_time: int = 0) -> "MidiEvent":
        """Create a program change event."""
        return cls(
            delta_time=delta_time,
            event_type=EventType.PROGRAM_CHANGE,
            channel=channel,
            data1=program,
            data2=0,
        )


@dataclass
class Phrase:
    """
    A phrase containing a sequence of MIDI events.

    In QY devices, phrases are reusable building blocks that can be
    assigned to tracks within pattern sections.

    Attributes:
        id: Phrase identifier
        name: Optional phrase name
        length_ticks: Total length in MIDI ticks
        events: List of MIDI events
        loop: Whether the phrase should loop
    """

    id: int = 0
    name: str = ""
    length_ticks: int = 0
    events: List[MidiEvent] = field(default_factory=list)
    loop: bool = False

    @property
    def note_count(self) -> int:
        """Count note-on events in phrase."""
        return sum(1 for e in self.events if e.is_note_on)

    @property
    def duration_ticks(self) -> int:
        """Calculate actual duration from events."""
        if not self.events:
            return 0
        return sum(e.delta_time for e in self.events)

    def get_notes(self) -> List[MidiEvent]:
        """Get all note-on events."""
        return [e for e in self.events if e.is_note_on]

    def transpose(self, semitones: int) -> "Phrase":
        """
        Create a transposed copy of this phrase.

        Args:
            semitones: Number of semitones to transpose (positive = up)

        Returns:
            New transposed phrase
        """
        new_events = []
        for event in self.events:
            if event.event_type in (EventType.NOTE_ON, EventType.NOTE_OFF):
                new_note = max(0, min(127, event.data1 + semitones))
                new_event = MidiEvent(
                    delta_time=event.delta_time,
                    event_type=event.event_type,
                    channel=event.channel,
                    data1=new_note,
                    data2=event.data2,
                )
                new_events.append(new_event)
            else:
                new_events.append(event)

        return Phrase(
            id=self.id,
            name=self.name,
            length_ticks=self.length_ticks,
            events=new_events,
            loop=self.loop,
        )

    def scale_velocity(self, factor: float) -> "Phrase":
        """
        Create a velocity-scaled copy of this phrase.

        Args:
            factor: Velocity multiplier (0.0-2.0 typically)

        Returns:
            New phrase with scaled velocities
        """
        new_events = []
        for event in self.events:
            if event.event_type == EventType.NOTE_ON and event.data2 > 0:
                new_velocity = max(1, min(127, int(event.data2 * factor)))
                new_event = MidiEvent(
                    delta_time=event.delta_time,
                    event_type=event.event_type,
                    channel=event.channel,
                    data1=event.data1,
                    data2=new_velocity,
                )
                new_events.append(new_event)
            else:
                new_events.append(event)

        return Phrase(
            id=self.id,
            name=self.name,
            length_ticks=self.length_ticks,
            events=new_events,
            loop=self.loop,
        )
