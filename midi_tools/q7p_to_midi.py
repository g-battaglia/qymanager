#!/usr/bin/env python3
"""
Q7P to Standard MIDI File converter.

Parses Yamaha QY700 Q7P pattern files (5120-byte format) and generates
standard MIDI files (.mid) from the phrase event data.

Event format (confirmed from DECAY.Q7P analysis, Session 23):
  D0/D1/DC [velocity] [GM_note] [gate_time]     — 4-byte drum/percussion note
  E0       [gate] [param] [GM_note] [velocity]   — 5-byte melody note
  C1       [note] [velocity_or_gate]              — 3-byte short note
  A0-AF    [value]  → delta = (cmd-0xA0)*128+val — 2-byte delta time (ppqn=480)
  BA/BB    [param]                                — 2-byte control/release variant
  BE       [param]                                — 2-byte note off
  BC       [param]                                — 2-byte control change
  F0 00    — start of MIDI data marker
  F2       — end of phrase marker
  0x40     — padding byte

Usage:
    python3 midi_tools/q7p_to_midi.py data/q7p/DECAY.Q7P -o data/q7p/DECAY.mid
"""

import argparse
import struct
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple

import mido


PPQN = 480  # Ticks per quarter note (confirmed from timing analysis)


@dataclass
class NoteEvent:
    """A decoded MIDI note event."""
    tick: int           # Absolute tick position
    channel: int        # MIDI channel (0-15)
    note: int           # MIDI note number (0-127)
    velocity: int       # MIDI velocity (0-127)
    gate_ticks: int     # Duration in ticks
    event_type: str     # "drum", "melody", "alt"


@dataclass
class ControlEvent:
    """A decoded control event."""
    tick: int
    channel: int
    control: int
    value: int


@dataclass
class PhraseInfo:
    """Parsed phrase block from Q7P."""
    name: str
    offset: int
    tempo: int          # BPM
    events: List[NoteEvent] = field(default_factory=list)
    controls: List[ControlEvent] = field(default_factory=list)
    is_drum: bool = False
    channel: int = 0    # Assigned MIDI channel


def parse_q7p_header(data: bytes) -> dict:
    """Parse Q7P file header and metadata."""
    if len(data) < 5120:
        raise ValueError(f"Expected 5120-byte Q7P file, got {len(data)}")

    magic = data[0:16]
    if not magic.startswith(b"YQ7PAT"):
        raise ValueError(f"Not a Q7P file: {magic[:6]}")

    # Extended metadata at 0xA00
    name = data[0xA00:0xA08].decode("ascii", errors="replace").strip()
    tempo_raw = struct.unpack(">H", data[0xA08:0xA0A])[0]
    tempo = tempo_raw // 10 if tempo_raw > 0 else 120

    # Channel assignments at 0xA5C
    channels = list(data[0xA5C:0xA6C])

    return {
        "name": name,
        "tempo": tempo,
        "channels": channels,
    }


def find_phrase_blocks(data: bytes) -> List[Tuple[int, str]]:
    """Find all phrase blocks in 5120-byte Q7P by scanning for 0x03/0x07 0x1C marker."""
    blocks = []
    pos = 0x200  # Phrase data starts here in 5120-byte files

    while pos < len(data) - 28:
        # Check for phrase header marker at offset+12
        if pos + 14 <= len(data):
            marker_lo = data[pos + 12]
            marker_hi = data[pos + 13]
            if marker_hi == 0x1C and marker_lo in (0x03, 0x07):
                # Valid phrase block — extract name
                name_bytes = data[pos:pos + 12]
                name = bytes(b if 0x20 <= b <= 0x7E else 0x20
                             for b in name_bytes).decode("ascii").strip()
                if name:
                    blocks.append((pos, name))
                    # Skip to end of this phrase to find next
                    end = find_phrase_end(data, pos + 28)
                    pos = end + 1
                    continue
        pos += 1

    return blocks


def find_phrase_end(data: bytes, start: int) -> int:
    """Find end of phrase MIDI data (F2 marker or padding run)."""
    pos = start
    while pos < len(data):
        if data[pos] == 0xF2:
            return pos
        if data[pos] == 0x40 and pos + 4 < len(data):
            if all(data[pos + i] == 0x40 for i in range(4)):
                return pos
        pos += 1
    return len(data) - 1


def classify_phrase(data: bytes, offset: int, midi_start: int, midi_end: int) -> bool:
    """Determine if phrase is drum (D0/D1/DC commands) or melody (E0/C1)."""
    pos = midi_start
    d_count = 0
    e_count = 0
    while pos < midi_end:
        cmd = data[pos]
        if cmd in (0xD0, 0xD1) or (0xD8 <= cmd <= 0xDF):
            d_count += 1
            pos += 4
        elif cmd == 0xE0:
            e_count += 1
            pos += 5
        elif cmd == 0xC1:
            e_count += 1
            pos += 3
        elif 0xA0 <= cmd <= 0xAF:
            pos += 2
        elif cmd in (0xBA, 0xBB, 0xBE, 0xBC):
            pos += 2
        elif cmd == 0xF2:
            break
        elif cmd == 0x40:
            break
        else:
            pos += 1
    return d_count > e_count


def parse_phrase_events(data: bytes, offset: int, channel: int) -> PhraseInfo:
    """Parse all MIDI events from a phrase block."""
    name_bytes = data[offset:offset + 12]
    name = bytes(b if 0x20 <= b <= 0x7E else 0x20
                 for b in name_bytes).decode("ascii").strip()

    # Tempo from phrase header (offset+24, big-endian)
    tempo_raw = struct.unpack(">H", data[offset + 24:offset + 26])[0]
    tempo = tempo_raw // 10 if tempo_raw > 0 else 120

    # MIDI data starts after F0 00 marker (offset+26..+27)
    midi_start = offset + 28
    midi_end = find_phrase_end(data, midi_start)

    is_drum = classify_phrase(data, offset, midi_start, midi_end)

    phrase = PhraseInfo(
        name=name,
        offset=offset,
        tempo=tempo,
        is_drum=is_drum,
        channel=9 if is_drum else channel,  # ch10 for drums
    )

    # Parse events
    pos = midi_start
    current_tick = 0
    active_notes = []  # Track notes for BE (note off)

    while pos < midi_end:
        cmd = data[pos]

        # D0/D1/DC..DF — Drum/percussion note (4 bytes)
        if cmd == 0xD0 or cmd == 0xD1 or (0xD8 <= cmd <= 0xDF):
            if pos + 3 >= len(data):
                break
            velocity = data[pos + 1]
            note = data[pos + 2]
            gate = data[pos + 3]
            # Clamp to MIDI range
            velocity = min(127, max(1, velocity))
            note = min(127, note)
            gate_ticks = max(gate, 30)  # Minimum gate time
            phrase.events.append(NoteEvent(
                tick=current_tick,
                channel=phrase.channel,
                note=note,
                velocity=velocity,
                gate_ticks=gate_ticks,
                event_type="drum",
            ))
            active_notes.append(note)
            pos += 4

        # E0 — Melody note (5 bytes)
        elif cmd == 0xE0:
            if pos + 4 >= len(data):
                break
            gate = data[pos + 1]
            param = data[pos + 2]
            note = data[pos + 3]
            velocity = data[pos + 4]
            velocity = min(127, max(1, velocity))
            note = min(127, note)
            gate_ticks = max(gate * 4, 60)  # Scale gate time
            phrase.events.append(NoteEvent(
                tick=current_tick,
                channel=phrase.channel,
                note=note,
                velocity=velocity,
                gate_ticks=gate_ticks,
                event_type="melody",
            ))
            active_notes.append(note)
            pos += 5

        # C1 — Alternate/short note (3 bytes)
        elif cmd == 0xC1:
            if pos + 2 >= len(data):
                break
            note = data[pos + 1]
            vel_or_gate = data[pos + 2]
            note = min(127, note)
            velocity = min(127, max(1, vel_or_gate))
            phrase.events.append(NoteEvent(
                tick=current_tick,
                channel=phrase.channel,
                note=note,
                velocity=velocity,
                gate_ticks=120,  # Default gate for C1
                event_type="alt",
            ))
            active_notes.append(note)
            pos += 3

        # A0-AF — Delta time (2 bytes)
        elif 0xA0 <= cmd <= 0xAF:
            if pos + 1 >= len(data):
                break
            step_type = cmd - 0xA0
            value = data[pos + 1]
            delta = step_type * 128 + value
            current_tick += delta
            pos += 2

        # BA/BB — Control/release with timing (2 bytes)
        # In "bells" track: BB 18 appears between note groups,
        # likely provides delta = value byte (small timing gap)
        elif cmd in (0xBA, 0xBB):
            if pos + 1 >= len(data):
                break
            value = data[pos + 1]
            current_tick += value  # Treat value as delta ticks
            pos += 2

        # BE — Note off (2 bytes)
        elif cmd == 0xBE:
            if pos + 1 >= len(data):
                break
            active_notes.clear()
            pos += 2

        # BC — Control change (2 bytes)
        elif cmd == 0xBC:
            if pos + 1 >= len(data):
                break
            pos += 2

        # F2 — End marker
        elif cmd == 0xF2:
            break

        # 0x40 — Padding
        elif cmd == 0x40:
            break

        else:
            # Unknown byte — skip
            pos += 1

    # Post-process: handle phrases with no delta events (chord/pad patterns)
    # These have all notes at tick 0 — distribute chord groups across 4 bars
    max_tick = max((e.tick for e in phrase.events), default=0)
    if max_tick == 0 and len(phrase.events) > 0:
        phrase.events = _distribute_chords(phrase.events)

    return phrase


def _distribute_chords(events: List[NoteEvent]) -> List[NoteEvent]:
    """
    Distribute chord events (all at tick 0) evenly across 4 bars.

    Splits events into "chord groups" — consecutive notes that play together.
    In Q7P, chord groups are separated by the absence of BE events in between
    (we detect groups as sets of notes at the same original tick position,
    which is always 0 in the no-delta case).

    Each group gets an equal slice of the 4-bar duration.
    Notes sustain for most of their slice.
    """
    pattern_ticks = PPQN * 4 * 4  # 4 bars at 4/4

    # Find chord groups by looking at event_type patterns
    # In the parsed data, all events are at tick 0
    # We infer groups from the original parse order:
    # E0 E0 E0 (chord 1) ... E0 E0 E0 (chord 2) etc.
    # The BE events were already consumed during parsing, so we just
    # split evenly based on common note patterns.

    # Count distinct "chords" — assume equal-sized groups
    n_events = len(events)
    if n_events <= 1:
        events[0].gate_ticks = pattern_ticks - 120
        return events

    # Try to detect chord size: find the most common note count per chord
    # For DECAY: piano pad has 3+3, bass has 1+1, guitarpaddy has 1+1
    # Simple heuristic: if all notes are melody type and count is even,
    # try splitting in half; if divisible by 3, try 3-note chords
    n_groups = 2  # Default: 2 chords over 4 bars
    for size in (3, 4, 2, 1):
        if n_events % size == 0 and n_events // size >= 2:
            n_groups = n_events // size
            break

    ticks_per_group = pattern_ticks // n_groups
    sustain_ticks = ticks_per_group - 60  # Small gap between chords

    group_size = n_events // n_groups
    for i, ev in enumerate(events):
        group_idx = i // group_size
        ev.tick = group_idx * ticks_per_group
        ev.gate_ticks = sustain_ticks

    return events


def phrases_to_midi(phrases: List[PhraseInfo], tempo: int) -> mido.MidiFile:
    """Convert parsed phrases to a standard MIDI file."""
    mid = mido.MidiFile(type=1, ticks_per_beat=PPQN)

    # Track 0: tempo and metadata
    meta_track = mido.MidiTrack()
    mid.tracks.append(meta_track)
    meta_track.append(mido.MetaMessage("set_tempo",
                                        tempo=mido.bpm2tempo(tempo), time=0))
    meta_track.append(mido.MetaMessage("time_signature",
                                        numerator=4, denominator=4, time=0))
    meta_track.append(mido.MetaMessage("end_of_track", time=0))

    # One MIDI track per phrase
    for phrase in phrases:
        track = mido.MidiTrack()
        mid.tracks.append(track)

        # Track name
        track.append(mido.MetaMessage("track_name", name=phrase.name, time=0))

        ch = phrase.channel & 0x0F

        # Build absolute-tick event list (note_on + note_off pairs)
        abs_events = []
        for ev in phrase.events:
            abs_events.append((ev.tick, "on", ev.note, ev.velocity, ch))
            abs_events.append((ev.tick + ev.gate_ticks, "off", ev.note, 0, ch))

        # Sort by tick, then note_off before note_on at same tick
        abs_events.sort(key=lambda x: (x[0], 0 if x[1] == "off" else 1))

        # Convert to delta time
        prev_tick = 0
        for tick, etype, note, vel, channel in abs_events:
            delta = max(0, tick - prev_tick)
            if etype == "on":
                track.append(mido.Message("note_on", note=note,
                                          velocity=vel, channel=channel,
                                          time=delta))
            else:
                track.append(mido.Message("note_off", note=note,
                                          velocity=0, channel=channel,
                                          time=delta))
            prev_tick = tick

        track.append(mido.MetaMessage("end_of_track", time=0))

    return mid


def convert_q7p_to_midi(q7p_path: str, output_path: Optional[str] = None,
                         verbose: bool = False) -> str:
    """
    Convert a Q7P file to standard MIDI.

    Args:
        q7p_path: Path to .Q7P file
        output_path: Output .mid path (auto-generated if None)
        verbose: Print detailed info

    Returns:
        Path to generated MIDI file
    """
    q7p_path = Path(q7p_path)
    data = q7p_path.read_bytes()

    if len(data) != 5120:
        raise ValueError(f"Only 5120-byte Q7P files supported (got {len(data)})")

    # Parse header
    header = parse_q7p_header(data)
    tempo = header["tempo"]
    channels = header["channels"]

    if verbose:
        print(f"Pattern: {header['name']}")
        print(f"Tempo: {tempo} BPM")
        print(f"Channels: {channels[:12]}")

    # Find phrase blocks
    blocks = find_phrase_blocks(data)
    if verbose:
        print(f"Found {len(blocks)} phrase blocks:")
        for off, name in blocks:
            print(f"  0x{off:04X}: {name}")

    # Parse each phrase
    phrases = []
    melody_ch = 0  # Assign melody channels sequentially, skipping ch10
    for i, (offset, name) in enumerate(blocks):
        # Assign channel: drums always ch10 (index 9)
        ch = melody_ch
        phrase = parse_phrase_events(data, offset, channel=ch)

        if not phrase.is_drum:
            melody_ch += 1
            if melody_ch == 9:
                melody_ch = 10  # Skip drum channel
        phrase.channel = 9 if phrase.is_drum else ch

        phrases.append(phrase)

        if verbose:
            note_count = len(phrase.events)
            drum_str = "DRUM" if phrase.is_drum else "MELODY"
            max_tick = max((e.tick for e in phrase.events), default=0)
            bars = max_tick / (PPQN * 4) if max_tick > 0 else 0
            print(f"  [{drum_str:6s} ch{phrase.channel + 1:2d}] "
                  f"{phrase.name:14s}: {note_count:3d} notes, "
                  f"{bars:.1f} bars")

    # Generate MIDI
    mid = phrases_to_midi(phrases, tempo)

    # Output path
    if output_path is None:
        output_path = str(q7p_path.with_suffix(".mid"))
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    mid.save(str(output_path))

    if verbose:
        print(f"\nSaved: {output_path} ({output_path.stat().st_size} bytes)")
        print(f"Tracks: {len(mid.tracks)} (1 meta + {len(phrases)} phrases)")

    return str(output_path)


def main():
    parser = argparse.ArgumentParser(description="Convert Q7P to standard MIDI")
    parser.add_argument("q7p_file", help="Path to Q7P file")
    parser.add_argument("-o", "--output", help="Output MIDI file path")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Print detailed info")
    args = parser.parse_args()

    try:
        result = convert_q7p_to_midi(args.q7p_file, args.output, args.verbose)
        print(f"OK: {result}")
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
