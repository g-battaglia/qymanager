#!/usr/bin/env python3
"""QY70 Chord Track Event Decoder Prototype.

Decodes QY70 SysEx packed bitstream events into readable musical data
and generates Standard MIDI File output for verification.

Based on discoveries from Sessions 6-8:
- R=9 barrel rotation between consecutive events
- 6 x 9-bit fields per event (F0-F5 + 2-bit remainder)
- F3 = hi2|mid3|lo4 (lo4 = one-hot beat counter)
- F4 = 5-bit chord-tone mask + 4-bit parameter
- F5 = timing/gate encoding (+16 per beat)
- 13-byte bar headers encode chord notes as 9-bit fields
"""

import struct
import sys
import os
from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Dict

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from qymanager.formats.qy70.sysex_parser import SysExParser

# --- Constants ---

TRACK_NAMES = {0: "D1", 1: "D2", 2: "BASS", 3: "C1", 4: "C2", 5: "PC", 6: "C3", 7: "C4"}
CHORD_TRACKS = [3, 4, 6, 7]  # C1, C2, C3, C4
BASS_TRACK = 2
DRUM_TRACKS = [0, 1, 5]  # D1, D2, PC

SECTION_NAMES = {
    0: "MAIN-A",
    1: "MAIN-B",
    2: "FILL-AB",
    3: "INTRO",
    4: "FILL-BA",
    5: "ENDING",
}

NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

R = 9  # Universal rotation constant
TICKS_PER_BEAT = 480  # Standard MIDI resolution

# Preamble-based track type classification (discovered Session 9)
# Preamble bytes 0-1 determine the event encoding type
PREAMBLE_CHORD = bytes.fromhex("1fa3")  # Standard chord: SR works, beat counter works
PREAMBLE_ARPEGGIO = bytes.fromhex("29cb")  # Arpeggio/complex: no SR, no beat counter
PREAMBLE_BASS = bytes.fromhex("2be3")  # Bass line
PREAMBLE_DRUM = bytes.fromhex("2543")  # D1 drum

ENCODING_CHORD = "chord"  # Shift register + chord-tone mask (high confidence)
ENCODING_ARPEGGIO = "arpeggio"  # Different field layout (low confidence)
ENCODING_BASS = "bass"  # Bass-specific encoding (low confidence)
ENCODING_DRUM = "drum"  # Drum-specific encoding (not decoded)
ENCODING_UNKNOWN = "unknown"


# --- Data Classes ---


@dataclass
class DecodedEvent:
    """A fully decoded QY70 event."""

    bar_index: int
    event_index: int
    # Raw fields
    f0: int
    f1: int
    f2: int
    f3: int
    f4: int
    f5: int
    remainder: int
    # F3 decomposition
    f3_hi2: int
    f3_mid3: int
    f3_lo4: int
    beat_number: int  # Derived from lo4 one-hot
    # F4 decomposition
    f4_mask5: int
    f4_param4: int
    selected_notes: List[int]  # MIDI notes selected by mask
    # F5 decomposition
    f5_top2: int
    f5_mid4: int
    f5_lo3: int
    tick_position: int  # Absolute tick within bar


@dataclass
class DecodedBar:
    """A decoded bar with header chord and events."""

    bar_index: int
    header_raw: bytes
    header_fields: List[int]  # 11 x 9-bit fields from header
    chord_notes: List[int]  # First 5 header fields (MIDI notes)
    chord_names: List[str]
    events: List[DecodedEvent]
    confidence: float = 1.0  # 0.0-1.0, based on header validity and SR match


@dataclass
class DecodedTrack:
    """A fully decoded track."""

    section: int
    track_index: int
    track_name: str
    section_name: str
    preamble: bytes
    encoding_type: str = ENCODING_UNKNOWN  # chord/arpeggio/bass/drum
    bars: List[DecodedBar] = field(default_factory=list)
    total_events: int = 0
    confidence: float = 0.0  # Overall decode confidence


# --- Helper Functions ---


def nn(n: int) -> str:
    """MIDI note number to name (e.g., 60 → 'C4')."""
    if 0 <= n <= 127:
        return f"{NOTE_NAMES[n % 12]}{n // 12 - 1}"
    return f">{n}"


def rot_right(val: int, shift: int, width: int = 56) -> int:
    """Barrel rotate right by shift bits within a width-bit word."""
    shift = shift % width
    return ((val >> shift) | (val << (width - shift))) & ((1 << width) - 1)


def extract_9bit(val: int, field_idx: int, total_width: int = 56) -> int:
    """Extract 9-bit field at position field_idx (0=MSB)."""
    shift = total_width - (field_idx + 1) * 9
    if shift < 0:
        return -1
    return (val >> shift) & 0x1FF


def lo4_to_beat(lo4: int) -> int:
    """Convert one-hot lo4 to beat number (0-3). Returns -1 if not one-hot."""
    mapping = {0b1000: 0, 0b0100: 1, 0b0010: 2, 0b0001: 3}
    return mapping.get(lo4, -1)


def classify_encoding(preamble: bytes) -> str:
    """Classify track encoding type based on preamble bytes 0-1.

    Preamble correlates perfectly with decoder behavior:
    - 1fa3: shift register works, beat counter works → chord encoding
    - 29cb: no shift register, no beat counter → arpeggio/complex
    - 2be3: bass-specific encoding
    - 2543: drum encoding (D1)
    """
    if len(preamble) < 2:
        return ENCODING_UNKNOWN
    key = preamble[:2]
    if key == PREAMBLE_CHORD:
        return ENCODING_CHORD
    elif key == PREAMBLE_ARPEGGIO:
        return ENCODING_ARPEGGIO
    elif key == PREAMBLE_BASS:
        return ENCODING_BASS
    elif key == PREAMBLE_DRUM:
        return ENCODING_DRUM
    return ENCODING_UNKNOWN


def compute_bar_confidence(header_fields: List[int], events: List["DecodedEvent"]) -> float:
    """Compute decode confidence for a bar (0.0 to 1.0).

    Based on:
    - Header field validity (all 5 chord notes 0-127)
    - Beat counter one-hot rate (strongest signal)
    - F5 monotonicity (timing should be sequential)
    - Shift register is NOT used — it only works when all beats play the same
      chord, which is track-specific, not a format property.
    """
    score = 0.0
    weights = 0.0

    # Header validity: what fraction of first 5 fields are valid MIDI notes?
    valid_notes = sum(1 for v in header_fields[:5] if 0 <= v <= 127)
    score += (valid_notes / 5.0) * 3.0  # Weight 3x — strongest signal
    weights += 3.0

    if not events:
        return score / weights if weights > 0 else 0.0

    # Beat counter: lo4 is one-hot (weight 2x)
    onehot_count = sum(1 for e in events if e.beat_number >= 0)
    score += (onehot_count / len(events)) * 2.0
    weights += 2.0

    if len(events) >= 2:
        # F5 monotonicity (weight 1x)
        f5_vals = [e.f5 for e in events]
        sr_total = len(events) - 1
        mono_pairs = sum(1 for i in range(sr_total) if f5_vals[i + 1] >= f5_vals[i])
        score += (mono_pairs / sr_total) * 1.0
        weights += 1.0

        # Selected notes non-empty rate (weight 1x)
        has_notes = sum(1 for e in events if e.selected_notes)
        score += (has_notes / len(events)) * 1.0
        weights += 1.0

    return score / weights if weights > 0 else 0.0


# --- Core Decoder ---


def get_track_data(syx_path: str, section: int, track: int) -> bytes:
    """Get concatenated decoded data for a specific section/track."""
    parser = SysExParser()
    messages = parser.parse_file(syx_path)
    al = section * 8 + track
    data = b""
    for m in messages:
        if m.is_style_data and m.address_low == al:
            if m.decoded_data is not None:
                data += m.decoded_data
    return data


def extract_bars(data: bytes) -> Tuple[bytes, List[Tuple[bytes, List[bytes]]]]:
    """Extract preamble and bars from decoded track data.

    Returns:
        (preamble_4bytes, [(header_13bytes, [event_7bytes, ...]), ...])
    """
    if len(data) < 28:
        return b"", []

    preamble = data[24:28]
    event_data = data[28:]

    # Split by DC delimiter
    dc_pos = [i for i, b in enumerate(event_data) if b == 0xDC]

    segments = []
    prev = 0
    for dp in dc_pos:
        segments.append(event_data[prev:dp])
        prev = dp + 1
    segments.append(event_data[prev:])

    bars = []
    for seg in segments:
        if len(seg) >= 20:  # 13-byte header + at least 1 event
            header = seg[:13]
            events = []
            for i in range((len(seg) - 13) // 7):
                evt = seg[13 + i * 7 : 13 + (i + 1) * 7]
                if len(evt) == 7:
                    events.append(evt)
            bars.append((header, events))

    return preamble, bars


def decode_header_notes(header: bytes) -> List[int]:
    """Decode 13-byte (104-bit) header as 9-bit fields.

    Returns raw 9-bit values. Use header_to_midi_notes() to extract
    MIDI note numbers (lo7 of each field).
    """
    val = int.from_bytes(header, "big")
    fields = []
    for fi in range(11):
        shift = 104 - (fi + 1) * 9
        if shift < 0:
            break
        fields.append((val >> shift) & 0x1FF)
    return fields


def header_to_midi_notes(header_fields: List[int]) -> List[int]:
    """Extract MIDI notes from header 9-bit fields.

    Each 9-bit field decomposes as: [bit8: flag][lo7: MIDI note + bit7 flag]
    - bit8: appears to be a voicing/register flag (not part of note number)
    - bit7: may be an octave or active flag
    - lo7 (bits 0-6): the actual MIDI note number (0-127)

    For MAIN-A C2: fields are all <=127, so lo7 == raw value.
    For INTRO C2: fields have bit8 set, but lo7 still gives valid notes.
    """
    notes = []
    for v in header_fields[:5]:
        lo7 = v & 0x7F
        # Filter out likely padding/empty values
        # C-1 (note 0) appearing 3+ times likely means empty slots
        notes.append(lo7)
    return notes


def f5_to_tick(f5: int, ticks_per_beat: int = TICKS_PER_BEAT) -> int:
    """Convert F5 field value to tick position within bar.

    F5 spacing is +16 per beat. We normalize so that:
    - F5 value 0 = tick 0
    - F5 spacing of 16 = one beat = ticks_per_beat ticks

    The actual F5 values start around 94, so we use the first event's F5
    as the base offset.
    """
    # For now, return raw F5 value — we'll calibrate during analysis
    return f5


def decode_event(
    evt_bytes: bytes,
    event_index: int,
    bar_header_fields: List[int],
    midi_notes: Optional[List[int]] = None,
) -> DecodedEvent:
    """Decode a single 7-byte event using R=9 de-rotation.

    Args:
        evt_bytes: 7-byte raw event data
        event_index: Position within bar (0-based, used for rotation)
        bar_header_fields: Raw 9-bit header fields (for reference)
        midi_notes: MIDI note numbers extracted from header (lo7 values).
                    If None, falls back to header_fields[:5] filtered to 0-127.
    """
    val = int.from_bytes(evt_bytes, "big")
    derot = rot_right(val, event_index * R)

    # Extract 6 x 9-bit fields
    f0 = extract_9bit(derot, 0)
    f1 = extract_9bit(derot, 1)
    f2 = extract_9bit(derot, 2)
    f3 = extract_9bit(derot, 3)
    f4 = extract_9bit(derot, 4)
    f5 = extract_9bit(derot, 5)
    remainder = derot & 0x3

    # F3 decomposition
    f3_lo4 = f3 & 0xF
    f3_mid3 = (f3 >> 4) & 0x7
    f3_hi2 = (f3 >> 7) & 0x3

    beat = lo4_to_beat(f3_lo4)

    # F4 decomposition
    f4_mask5 = (f4 >> 4) & 0x1F
    f4_param4 = f4 & 0xF

    # Apply mask to chord notes (lo7 interpretation)
    if midi_notes is not None:
        chord_notes = midi_notes
    else:
        chord_notes = [n for n in bar_header_fields[:5] if 0 <= n <= 127]

    selected = []
    for i in range(min(5, len(chord_notes))):
        if (f4_mask5 >> (4 - i)) & 1:
            note = chord_notes[i]
            if 0 <= note <= 127:
                selected.append(note)

    # F5 decomposition
    f5_top2 = (f5 >> 7) & 0x3
    f5_mid4 = (f5 >> 3) & 0xF
    f5_lo3 = f5 & 0x7

    return DecodedEvent(
        bar_index=0,  # Set by caller
        event_index=event_index,
        f0=f0,
        f1=f1,
        f2=f2,
        f3=f3,
        f4=f4,
        f5=f5,
        remainder=remainder,
        f3_hi2=f3_hi2,
        f3_mid3=f3_mid3,
        f3_lo4=f3_lo4,
        beat_number=beat,
        f4_mask5=f4_mask5,
        f4_param4=f4_param4,
        selected_notes=selected,
        f5_top2=f5_top2,
        f5_mid4=f5_mid4,
        f5_lo3=f5_lo3,
        tick_position=f5_to_tick(f5),
    )


def decode_track(syx_path: str, section: int, track: int) -> Optional[DecodedTrack]:
    """Decode a complete track from a .syx file.

    Classifies encoding type based on preamble and computes confidence scores.
    """
    data = get_track_data(syx_path, section, track)
    if len(data) < 28:
        return None

    preamble, raw_bars = extract_bars(data)
    if not raw_bars:
        return None

    encoding = classify_encoding(preamble)

    decoded_bars = []
    total_events = 0
    confidence_sum = 0.0

    for bar_idx, (header, events) in enumerate(raw_bars):
        header_fields = decode_header_notes(header)
        midi_notes = header_to_midi_notes(header_fields)
        # Filter out empty-slot notes (multiple C-1 = note 0 = likely padding)
        zero_count = sum(1 for n in midi_notes if n == 0)
        if zero_count >= 3:
            # Mostly empty — only keep non-zero
            chord_notes = [n for n in midi_notes if n > 0]
        else:
            chord_notes = midi_notes
        chord_names = [nn(n) for n in chord_notes]

        decoded_events = []
        for evt_idx, evt in enumerate(events):
            de = decode_event(evt, evt_idx, header_fields, midi_notes)
            de.bar_index = bar_idx
            decoded_events.append(de)
            total_events += 1

        bar_conf = compute_bar_confidence(header_fields, decoded_events)
        # Boost confidence for chord-type preamble, reduce for others
        if encoding == ENCODING_CHORD:
            bar_conf = min(1.0, bar_conf * 1.1)
        elif encoding in (ENCODING_ARPEGGIO, ENCODING_BASS):
            bar_conf *= 0.5

        decoded_bars.append(
            DecodedBar(
                bar_index=bar_idx,
                header_raw=header,
                header_fields=header_fields,
                chord_notes=chord_notes,
                chord_names=chord_names,
                events=decoded_events,
                confidence=bar_conf,
            )
        )
        confidence_sum += bar_conf

    overall_conf = confidence_sum / len(decoded_bars) if decoded_bars else 0.0

    return DecodedTrack(
        section=section,
        track_index=track,
        track_name=TRACK_NAMES[track],
        section_name=SECTION_NAMES[section],
        preamble=preamble,
        encoding_type=encoding,
        bars=decoded_bars,
        total_events=total_events,
        confidence=overall_conf,
    )


# --- MIDI File Writer ---


def write_midi_file(tracks: List[DecodedTrack], output_path: str, bpm: float = 151.0):
    """Write decoded tracks to a Standard MIDI File (Format 1).

    Uses the mido library if available, otherwise writes raw SMF bytes.
    """
    try:
        import mido

        return _write_midi_mido(tracks, output_path, bpm)
    except ImportError:
        return _write_midi_raw(tracks, output_path, bpm)


def _write_midi_mido(tracks: List[DecodedTrack], output_path: str, bpm: float):
    """Write MIDI using mido library."""
    import mido

    mid = mido.MidiFile(ticks_per_beat=TICKS_PER_BEAT, type=1)

    # Tempo track
    tempo_track = mido.MidiTrack()
    tempo_track.append(mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(bpm), time=0))
    tempo_track.append(mido.MetaMessage("time_signature", numerator=4, denominator=4, time=0))
    mid.tracks.append(tempo_track)

    for dt in tracks:
        midi_track = mido.MidiTrack()
        midi_track.append(
            mido.MetaMessage("track_name", name=f"{dt.section_name} {dt.track_name}", time=0)
        )

        # Assign channel based on track type
        if dt.track_name in ("D1", "D2", "PC"):
            channel = 9  # Drums
        elif dt.track_name == "BASS":
            channel = 1
        elif dt.track_name == "C1":
            channel = 2
        elif dt.track_name == "C2":
            channel = 3
        elif dt.track_name == "C3":
            channel = 4
        elif dt.track_name == "C4":
            channel = 5
        else:
            channel = 0

        # Collect all note events with absolute tick positions
        note_events = []
        bar_offset = 0

        for bar in dt.bars:
            # Calculate F5 base for this bar (first event's F5)
            f5_base = bar.events[0].f5 if bar.events else 0

            for evt in bar.events:
                if not evt.selected_notes:
                    continue

                # Convert F5 to tick offset within bar
                f5_delta = evt.f5 - f5_base
                # F5 spacing of 16 = 1 beat = TICKS_PER_BEAT
                tick_in_bar = int(f5_delta * TICKS_PER_BEAT / 16) if f5_delta >= 0 else 0

                abs_tick = bar_offset + tick_in_bar

                # Velocity from f4_param4 (scale 0-15 to 40-120)
                velocity = min(127, max(40, 40 + evt.f4_param4 * 6))

                # Note duration: one beat for now (will refine)
                duration = TICKS_PER_BEAT // 2  # Eighth note default

                for note in evt.selected_notes:
                    note_events.append((abs_tick, "on", note, velocity))
                    note_events.append((abs_tick + duration, "off", note, 0))

            # Advance bar offset by 4 beats
            bar_offset += TICKS_PER_BEAT * 4

        # Sort by absolute tick, then off before on at same tick
        note_events.sort(key=lambda x: (x[0], 0 if x[1] == "off" else 1))

        # Convert to delta times
        last_tick = 0
        for abs_tick, typ, note, vel in note_events:
            delta = abs_tick - last_tick
            if typ == "on":
                midi_track.append(
                    mido.Message("note_on", note=note, velocity=vel, channel=channel, time=delta)
                )
            else:
                midi_track.append(
                    mido.Message("note_off", note=note, velocity=0, channel=channel, time=delta)
                )
            last_tick = abs_tick

        midi_track.append(mido.MetaMessage("end_of_track", time=0))
        mid.tracks.append(midi_track)

    mid.save(output_path)
    return len(mid.tracks) - 1  # Exclude tempo track


def _write_midi_raw(tracks: List[DecodedTrack], output_path: str, bpm: float):
    """Write MIDI without mido — raw SMF byte construction."""

    def write_varlen(value: int) -> bytes:
        """Encode a variable-length quantity."""
        result = []
        result.append(value & 0x7F)
        value >>= 7
        while value:
            result.append((value & 0x7F) | 0x80)
            value >>= 7
        return bytes(reversed(result))

    def make_track_chunk(events: list) -> bytes:
        """Build an MTrk chunk from a list of (delta, bytes) pairs."""
        data = b""
        for delta, msg in events:
            data += write_varlen(delta) + msg
        return b"MTrk" + struct.pack(">I", len(data)) + data

    all_track_chunks = []

    # Tempo track
    tempo_us = int(60_000_000 / bpm)
    tempo_events = [
        (0, b"\xff\x51\x03" + struct.pack(">I", tempo_us)[1:]),  # Set tempo
        (0, b"\xff\x58\x04\x04\x02\x18\x08"),  # 4/4 time sig
        (0, b"\xff\x2f\x00"),  # End of track
    ]
    all_track_chunks.append(make_track_chunk(tempo_events))

    for dt in tracks:
        if dt.track_name in ("D1", "D2", "PC"):
            channel = 9
        elif dt.track_name == "BASS":
            channel = 1
        elif dt.track_name == "C1":
            channel = 2
        elif dt.track_name == "C2":
            channel = 3
        elif dt.track_name == "C3":
            channel = 4
        elif dt.track_name == "C4":
            channel = 5
        else:
            channel = 0

        note_events = []
        bar_offset = 0

        for bar in dt.bars:
            f5_base = bar.events[0].f5 if bar.events else 0
            for evt in bar.events:
                if not evt.selected_notes:
                    continue
                f5_delta = evt.f5 - f5_base
                tick_in_bar = int(f5_delta * TICKS_PER_BEAT / 16) if f5_delta >= 0 else 0
                abs_tick = bar_offset + tick_in_bar
                velocity = min(127, max(40, 40 + evt.f4_param4 * 6))
                duration = TICKS_PER_BEAT // 2
                for note in evt.selected_notes:
                    note_events.append((abs_tick, "on", note, velocity))
                    note_events.append((abs_tick + duration, "off", note, 0))
            bar_offset += TICKS_PER_BEAT * 4

        note_events.sort(key=lambda x: (x[0], 0 if x[1] == "off" else 1))

        midi_events = []
        # Track name
        name = f"{dt.section_name} {dt.track_name}"
        name_bytes = name.encode("ascii")
        midi_events.append((0, b"\xff\x03" + write_varlen(len(name_bytes)) + name_bytes))

        last_tick = 0
        for abs_tick, typ, note, vel in note_events:
            delta = abs_tick - last_tick
            if typ == "on":
                midi_events.append((delta, bytes([0x90 | channel, note, vel])))
            else:
                midi_events.append((delta, bytes([0x80 | channel, note, 0])))
            last_tick = abs_tick

        midi_events.append((0, b"\xff\x2f\x00"))
        all_track_chunks.append(make_track_chunk(midi_events))

    # MThd header: Format 1, N tracks, 480 ticks/beat
    n_tracks = len(all_track_chunks)
    header = b"MThd" + struct.pack(">IHhH", 6, 1, n_tracks, TICKS_PER_BEAT)

    with open(output_path, "wb") as f:
        f.write(header)
        for chunk in all_track_chunks:
            f.write(chunk)

    return n_tracks - 1


# --- Analysis & Reporting ---


def print_decoded_track(dt: DecodedTrack, verbose: bool = False):
    """Print a decoded track in human-readable format."""
    conf_bar = "█" * int(dt.confidence * 10) + "░" * (10 - int(dt.confidence * 10))
    print(f"\n{'=' * 70}")
    print(f"  {dt.section_name} / {dt.track_name}  |  Preamble: {dt.preamble.hex()}")
    print(f"  Encoding: {dt.encoding_type:10s}  |  Confidence: [{conf_bar}] {dt.confidence:.0%}")
    print(f"  {dt.total_events} events across {len(dt.bars)} bars")
    print(f"{'=' * 70}")

    for bar in dt.bars:
        chord_str = ", ".join(bar.chord_names) if bar.chord_names else "(no valid MIDI notes)"
        hdr_all = [f"{v}" for v in bar.header_fields]
        print(f"\n  Bar {bar.bar_index}: chord = [{chord_str}]")
        if verbose:
            print(f"    Header fields (11x9b): {hdr_all}")

        for evt in bar.events:
            beat_str = (
                f"beat {evt.beat_number}" if evt.beat_number >= 0 else f"lo4={evt.f3_lo4:04b}"
            )
            mask_str = f"{evt.f4_mask5:05b}"
            notes_str = (
                ", ".join(nn(n) for n in evt.selected_notes) if evt.selected_notes else "---"
            )
            vel_str = f"p4={evt.f4_param4:2d}"

            print(
                f"    E{evt.event_index}: {beat_str:8s} | "
                f"mask={mask_str} → [{notes_str:20s}] | "
                f"{vel_str} | F5={evt.f5:3d} (t2={evt.f5_top2} m4={evt.f5_mid4:2d} l3={evt.f5_lo3})"
            )

            if verbose:
                print(
                    f"         F0={evt.f0:3d} F1={evt.f1:3d} F2={evt.f2:3d} "
                    f"F3={evt.f3:3d}(h{evt.f3_hi2}m{evt.f3_mid3}l{evt.f3_lo4:04b}) "
                    f"F4={evt.f4:3d} F5={evt.f5:3d} rem={evt.remainder}"
                )


def analyze_shift_register(dt: DecodedTrack):
    """Verify the F0→F1→F2 shift register property."""
    print(f"\n  Shift Register Analysis:")
    for bar in dt.bars:
        if len(bar.events) < 2:
            continue
        f01_match = 0
        f12_match = 0
        total = 0
        for i in range(1, len(bar.events)):
            if bar.events[i].f1 == bar.events[i - 1].f0:
                f01_match += 1
            if bar.events[i].f2 == bar.events[i - 1].f1:
                f12_match += 1
            total += 1
        print(
            f"    Bar {bar.bar_index}: F1[i]==F0[i-1]: {f01_match}/{total}, "
            f"F2[i]==F1[i-1]: {f12_match}/{total}"
        )


def analyze_timing(dt: DecodedTrack):
    """Analyze F5 timing patterns across bars."""
    print(f"\n  F5 Timing Analysis:")
    for bar in dt.bars:
        if not bar.events:
            continue
        f5_vals = [e.f5 for e in bar.events]
        spacings = [f5_vals[i + 1] - f5_vals[i] for i in range(len(f5_vals) - 1)]
        mono = all(s >= 0 for s in spacings)
        print(f"    Bar {bar.bar_index}: F5 = {f5_vals}, spacings = {spacings}, monotonic = {mono}")


def analyze_beat_counter(dt: DecodedTrack):
    """Verify the F3 lo4 one-hot beat counter."""
    print(f"\n  Beat Counter (F3 lo4) Analysis:")
    for bar in dt.bars:
        lo4s = [f"{e.f3_lo4:04b}" for e in bar.events]
        beats = [e.beat_number for e in bar.events]
        perfect = beats == list(range(len(beats)))
        print(
            f"    Bar {bar.bar_index}: lo4 = {lo4s}, beats = {beats}, perfect_sequence = {perfect}"
        )


# --- Main ---


def main():
    import argparse

    parser = argparse.ArgumentParser(description="QY70 Chord Track Event Decoder")
    parser.add_argument("syx_file", help="Path to .syx file")
    parser.add_argument(
        "--section", "-s", type=int, default=None, help="Section index (0-5). Default: all sections"
    )
    parser.add_argument(
        "--track",
        "-t",
        type=str,
        default=None,
        help="Track name (C1,C2,C3,C4,BASS) or index. Default: all chord tracks",
    )
    parser.add_argument("--midi", "-m", type=str, default=None, help="Output MIDI file path")
    parser.add_argument(
        "--bpm", type=float, default=151.0, help="BPM for MIDI output (default: 151 for SGT)"
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Show all field values")
    parser.add_argument(
        "--analyze",
        "-a",
        action="store_true",
        help="Run shift register, timing, and beat counter analysis",
    )
    args = parser.parse_args()

    syx_path = args.syx_file
    if not os.path.exists(syx_path):
        print(f"Error: {syx_path} not found")
        sys.exit(1)

    # Determine which tracks to decode
    name_to_idx = {v: k for k, v in TRACK_NAMES.items()}
    if args.track:
        t = args.track.upper()
        if t in name_to_idx:
            track_indices = [name_to_idx[t]]
        elif t.isdigit():
            track_indices = [int(t)]
        else:
            print(f"Error: unknown track '{args.track}'")
            sys.exit(1)
    else:
        track_indices = CHORD_TRACKS  # Default: C1, C2, C3, C4

    sections = [args.section] if args.section is not None else range(6)

    # Decode all requested tracks
    all_decoded = []
    for sec in sections:
        for trk in track_indices:
            dt = decode_track(syx_path, sec, trk)
            if dt and dt.bars:
                all_decoded.append(dt)
                print_decoded_track(dt, verbose=args.verbose)

                if args.analyze:
                    analyze_shift_register(dt)
                    analyze_timing(dt)
                    analyze_beat_counter(dt)

    # Summary
    print(f"\n{'=' * 70}")
    print(
        f"SUMMARY: Decoded {len(all_decoded)} tracks, "
        f"{sum(t.total_events for t in all_decoded)} total events, "
        f"{sum(len(t.bars) for t in all_decoded)} total bars"
    )

    # Count notes extracted
    total_notes = 0
    valid_notes = 0
    for dt in all_decoded:
        for bar in dt.bars:
            for evt in bar.events:
                total_notes += 1
                if evt.selected_notes:
                    valid_notes += 1
    print(
        f"Events with selected notes: {valid_notes}/{total_notes} "
        f"({100 * valid_notes / total_notes:.1f}%)"
        if total_notes > 0
        else ""
    )

    # MIDI output
    if args.midi and all_decoded:
        n = write_midi_file(all_decoded, args.midi, bpm=args.bpm)
        print(f"\nMIDI written to: {args.midi} ({n} tracks)")

    return all_decoded


if __name__ == "__main__":
    main()
