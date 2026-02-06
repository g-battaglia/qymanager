"""
QY700 Phrase Data Parser.

Parses the proprietary MIDI event format used in Q7P files.
This format is shared between QY70 SysEx and QY700 Q7P files.

MIDI Event Format (Yamaha QY series):
    D0 nn vv xx = Drum note on (note, velocity, next-byte)
    E0 nn vv xx = Melody note on (note, velocity, next-byte)
    C1 nn pp    = Note on alternate encoding (note, param)
    A0-A7 dd    = Delta time (step type, duration)
    BE xx       = Note off / reset
    BC xx       = Control change
    F0 00       = Start of MIDI data marker
    F2          = End of phrase marker
    0x40        = Padding byte

5120-byte Q7P Phrase Block Structure:
    Offset 0-11:   Name (ASCII, space padded)
    Offset 12-13:  0x03 0x1C (marker)
    Offset 14-17:  0x00 0x00 0x00 0x7F (note range)
    Offset 18-19:  0x00 0x07 (track flags)
    Offset 20-23:  0x90 0x00 0x00 0x00 (MIDI setup)
    Offset 24-25:  Tempo * 10 (big-endian, e.g., 0x04B0 = 120 BPM)
    Offset 26-27:  0xF0 0x00 (start MIDI marker)
    Offset 28+:    MIDI events
    F2:            End of phrase
    0x40 padding:  Fill to next block boundary
"""

from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Union
from enum import Enum


class MidiEventType(Enum):
    """MIDI event types in Yamaha QY format."""

    DRUM_NOTE = 0xD0
    MELODY_NOTE = 0xE0
    ALT_NOTE = 0xC1
    DELTA_A0 = 0xA0
    DELTA_A1 = 0xA1
    DELTA_A2 = 0xA2
    DELTA_A3 = 0xA3
    DELTA_A4 = 0xA4
    DELTA_A5 = 0xA5
    DELTA_A6 = 0xA6
    DELTA_A7 = 0xA7
    NOTE_OFF = 0xBE
    CONTROL = 0xBC
    START_MARKER = 0xF0
    END_MARKER = 0xF2
    PADDING = 0x40


@dataclass
class MidiEvent:
    """A single MIDI event."""

    event_type: str
    note: int = 0
    velocity: int = 0
    delta: int = 0
    param: int = 0
    raw_bytes: bytes = field(default_factory=bytes)

    def __repr__(self) -> str:
        if self.event_type == "drum":
            return f"DrumNote({self.note}, vel={self.velocity})"
        elif self.event_type == "note":
            return f"NoteOn({self.note}, vel={self.velocity})"
        elif self.event_type == "alt_note":
            return f"AltNote({self.note}, param={self.param})"
        elif self.event_type == "delta":
            return f"Delta(step={self.param}, val={self.delta})"
        elif self.event_type == "off":
            return f"NoteOff({self.param})"
        elif self.event_type == "ctrl":
            return f"Control({self.param})"
        elif self.event_type == "end":
            return "End"
        return f"Event({self.event_type})"


@dataclass
class PhraseBlock:
    """A phrase block from 5120-byte Q7P file."""

    name: str
    offset: int
    midi_offset: int
    tempo: int
    note_range: Tuple[int, int]
    events: List[MidiEvent] = field(default_factory=list)
    raw_data: bytes = field(default_factory=bytes)

    @property
    def note_count(self) -> int:
        """Count of note events."""
        return sum(1 for e in self.events if e.event_type in ("drum", "note", "alt_note"))

    @property
    def duration_ticks(self) -> int:
        """Estimated duration in ticks."""
        return sum(e.delta for e in self.events if e.event_type == "delta")


class QY700PhraseParser:
    """
    Parser for QY700 phrase data.

    Handles both:
    - 5120-byte Q7P files with inline phrase blocks
    - 3072-byte Q7P files with phrase/sequence areas
    """

    # Phrase block header marker
    PHRASE_HEADER_MARKER = bytes([0x03, 0x1C])

    # MIDI data start marker
    MIDI_START_MARKER = bytes([0xF0, 0x00])

    # End of phrase marker
    PHRASE_END_MARKER = 0xF2

    # Padding byte
    PADDING_BYTE = 0x40

    def __init__(self, data: bytes):
        """
        Initialize parser with Q7P file data.

        Args:
            data: Raw Q7P file bytes (3072 or 5120 bytes)
        """
        self.data = data
        self.file_size = len(data)
        self.is_extended = len(data) == 5120

    def parse_phrases(self) -> List[PhraseBlock]:
        """
        Parse all phrase blocks from the file.

        Returns:
            List of PhraseBlock objects
        """
        if self.is_extended:
            return self._parse_5120_phrases()
        else:
            return self._parse_3072_phrases()

    def _parse_5120_phrases(self) -> List[PhraseBlock]:
        """Parse phrase blocks from 5120-byte file (inline format)."""
        phrases = []

        # Phrase data starts at 0x200 in 5120-byte files
        pos = 0x200

        while pos < len(self.data) - 28:
            # Look for phrase header marker (0x03 0x1C at offset 12)
            # First check if we have a valid name (printable ASCII)
            name_bytes = self.data[pos : pos + 12]

            # Skip padding areas
            if all(b == 0x40 for b in name_bytes):
                pos += 1
                continue

            # Check for phrase header marker at offset 12
            if pos + 14 <= len(self.data):
                marker = self.data[pos + 12 : pos + 14]
                if marker == self.PHRASE_HEADER_MARKER:
                    phrase = self._parse_phrase_block(pos)
                    if phrase:
                        phrases.append(phrase)
                        # Move past this phrase block
                        pos = self._find_phrase_end(pos + 28) + 1
                        continue

            pos += 1

        return phrases

    def _parse_3072_phrases(self) -> List[PhraseBlock]:
        """Parse phrase data from 3072-byte file (area-based format)."""
        # In 3072-byte files, phrase data is at 0x360-0x678
        # This format uses a different structure - phrase references
        # For now, return empty list as this needs more research
        return []

    def _parse_phrase_block(self, offset: int) -> Optional[PhraseBlock]:
        """
        Parse a single phrase block starting at offset.

        Args:
            offset: Start offset of phrase block

        Returns:
            PhraseBlock or None if invalid
        """
        if offset + 28 > len(self.data):
            return None

        # Extract name (bytes 0-11)
        name_bytes = self.data[offset : offset + 12]
        name = bytes(b if 0x20 <= b <= 0x7E else 0x20 for b in name_bytes).decode("ascii").strip()

        # Skip header marker (bytes 12-13: 0x03 0x1C)

        # Note range (bytes 14-17)
        note_low = self.data[offset + 16]
        note_high = self.data[offset + 17]

        # Tempo (bytes 24-25, big-endian)
        tempo_raw = (self.data[offset + 24] << 8) | self.data[offset + 25]
        tempo = tempo_raw // 10 if tempo_raw > 0 else 120

        # MIDI data starts after F0 00 marker (bytes 26-27)
        midi_offset = offset + 28

        # Find end of MIDI data (F2 marker or padding)
        midi_end = self._find_phrase_end(midi_offset)

        # Extract raw MIDI data
        raw_midi = self.data[midi_offset:midi_end]

        # Parse MIDI events
        events = self._parse_midi_events(raw_midi)

        return PhraseBlock(
            name=name,
            offset=offset,
            midi_offset=midi_offset,
            tempo=tempo,
            note_range=(note_low, note_high),
            events=events,
            raw_data=raw_midi,
        )

    def _find_phrase_end(self, start: int) -> int:
        """Find end of phrase MIDI data."""
        pos = start
        while pos < len(self.data):
            if self.data[pos] == self.PHRASE_END_MARKER:
                return pos
            if self.data[pos] == self.PADDING_BYTE:
                # Check if this is start of padding run
                if pos + 4 < len(self.data):
                    if all(self.data[pos + i] == self.PADDING_BYTE for i in range(4)):
                        return pos
            pos += 1
        return len(self.data)

    def _parse_midi_events(self, data: bytes) -> List[MidiEvent]:
        """
        Parse MIDI events from raw data.

        Args:
            data: Raw MIDI event bytes

        Returns:
            List of MidiEvent objects
        """
        events = []
        pos = 0

        while pos < len(data):
            cmd = data[pos]

            if cmd == 0xD0:  # Drum note on
                if pos + 3 < len(data):
                    note = data[pos + 1]
                    velocity = data[pos + 2]
                    next_byte = data[pos + 3]
                    events.append(
                        MidiEvent(
                            event_type="drum",
                            note=note,
                            velocity=velocity,
                            param=next_byte,
                            raw_bytes=data[pos : pos + 4],
                        )
                    )
                    pos += 4
                else:
                    break

            elif cmd == 0xE0:  # Melody note on
                if pos + 3 < len(data):
                    note = data[pos + 1]
                    velocity = data[pos + 2]
                    next_byte = data[pos + 3]
                    events.append(
                        MidiEvent(
                            event_type="note",
                            note=note,
                            velocity=velocity,
                            param=next_byte,
                            raw_bytes=data[pos : pos + 4],
                        )
                    )
                    pos += 4
                else:
                    break

            elif cmd == 0xC1:  # Alternate note encoding
                if pos + 2 < len(data):
                    note = data[pos + 1]
                    param = data[pos + 2]
                    events.append(
                        MidiEvent(
                            event_type="alt_note",
                            note=note,
                            param=param,
                            raw_bytes=data[pos : pos + 3],
                        )
                    )
                    pos += 3
                else:
                    break

            elif cmd >= 0xA0 and cmd <= 0xA7:  # Delta time
                if pos + 1 < len(data):
                    step_type = cmd - 0xA0
                    delta = data[pos + 1]
                    events.append(
                        MidiEvent(
                            event_type="delta",
                            delta=delta,
                            param=step_type,
                            raw_bytes=data[pos : pos + 2],
                        )
                    )
                    pos += 2
                else:
                    break

            elif cmd == 0xBE:  # Note off
                if pos + 1 < len(data):
                    param = data[pos + 1]
                    events.append(
                        MidiEvent(event_type="off", param=param, raw_bytes=data[pos : pos + 2])
                    )
                    pos += 2
                else:
                    break

            elif cmd == 0xBC:  # Control
                if pos + 1 < len(data):
                    param = data[pos + 1]
                    events.append(
                        MidiEvent(event_type="ctrl", param=param, raw_bytes=data[pos : pos + 2])
                    )
                    pos += 2
                else:
                    break

            elif cmd == 0xF2:  # End marker
                events.append(MidiEvent(event_type="end", raw_bytes=bytes([cmd])))
                break

            elif cmd == 0x40:  # Padding - stop parsing
                break

            else:
                # Unknown byte - skip
                pos += 1

        return events

    def get_midi_bytes(self, phrase: PhraseBlock) -> bytes:
        """
        Get raw MIDI bytes for a phrase, suitable for QY70 SysEx.

        The QY70 and QY700 use the same MIDI event encoding,
        so we can pass the raw bytes directly.

        Args:
            phrase: PhraseBlock to extract MIDI from

        Returns:
            Raw MIDI event bytes
        """
        return phrase.raw_data


def parse_q7p_phrases(data: bytes) -> List[PhraseBlock]:
    """
    Convenience function to parse phrases from Q7P data.

    Args:
        data: Raw Q7P file bytes

    Returns:
        List of PhraseBlock objects
    """
    parser = QY700PhraseParser(data)
    return parser.parse_phrases()
