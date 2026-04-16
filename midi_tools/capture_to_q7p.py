#!/usr/bin/env python3
"""Pipeline B: Capture → Quantize → Q7P + SMF output.

Reads a MIDI playback capture, quantizes it, and produces:
1. A Standard MIDI File (.mid) for verification
2. A Q7P file with metadata + D0/E0 phrase data (best-effort)

Usage:
    .venv/bin/python3 midi_tools/capture_to_q7p.py midi_tools/captured/sgt_full_capture.json
    .venv/bin/python3 midi_tools/capture_to_q7p.py capture.json -b 151 -n 6 -o output
"""

import argparse
import struct
import sys
from pathlib import Path
from typing import List, Optional, Tuple

import mido

# Add project root
sys.path.insert(0, str(Path(__file__).parent.parent))

from midi_tools.quantizer import (
    QuantizedNote,
    QuantizedPattern,
    QuantizedTrack,
    quantize_capture,
    export_json,
)


# --- Standard MIDI File Writer ---

def write_smf(pattern: QuantizedPattern, output_path: str) -> None:
    """Write quantized pattern as a Type 1 Standard MIDI File.

    Creates one MIDI track per quantized track, with correct timing,
    note on/off pairs, and program changes for drum tracks.
    """
    mid = mido.MidiFile(type=1, ticks_per_beat=pattern.ppqn)

    # Track 0: tempo map
    tempo_track = mido.MidiTrack()
    mid.tracks.append(tempo_track)
    tempo_track.append(mido.MetaMessage("track_name", name=pattern.name or "Capture", time=0))
    tempo_track.append(mido.MetaMessage(
        "set_tempo", tempo=mido.bpm2tempo(pattern.bpm), time=0
    ))
    tempo_track.append(mido.MetaMessage(
        "time_signature",
        numerator=pattern.time_sig[0],
        denominator=pattern.time_sig[1],
        time=0,
    ))
    tempo_track.append(mido.MetaMessage("end_of_track", time=0))

    # One track per QY70 track
    for track in pattern.active_tracks:
        midi_track = mido.MidiTrack()
        mid.tracks.append(midi_track)
        midi_track.append(mido.MetaMessage("track_name", name=track.name, time=0))

        # Channel: drums on ch 9 (0-indexed), melody on original channel - 1
        ch = 9 if track.is_drum else min(track.channel - 1, 15)

        # Build absolute-tick event list
        events = []
        for n in track.notes:
            abs_tick = n.bar * pattern.bar_ticks + n.tick_on
            events.append((abs_tick, "on", n.note, n.velocity))
            events.append((abs_tick + n.tick_dur, "off", n.note, 0))

        # Sort by tick, then off before on at same tick
        events.sort(key=lambda e: (e[0], 0 if e[1] == "off" else 1, e[2]))

        # Convert to delta time
        prev_tick = 0
        for tick, typ, note, vel in events:
            delta = tick - prev_tick
            if typ == "on":
                midi_track.append(mido.Message(
                    "note_on", channel=ch, note=note, velocity=vel, time=delta
                ))
            else:
                midi_track.append(mido.Message(
                    "note_off", channel=ch, note=note, velocity=0, time=delta
                ))
            prev_tick = tick

        midi_track.append(mido.MetaMessage("end_of_track", time=0))

    mid.save(output_path)


# --- Q7P D0/E0 Phrase Encoder ---

def encode_phrase_events(
    track: QuantizedTrack,
    pattern: QuantizedPattern,
) -> bytes:
    """Encode a quantized track as D0/E0 phrase data.

    Uses the QY700 phrase command format:
        D0 nn vv gg — drum note (note, velocity, gate)
        E0 nn vv gg — melody note (note, velocity, gate)
        A0 dd       — delta time (dd ticks, resolution 1x)
        BE 00       — note off / reset
        F0 00       — start marker
        F2          — end marker

    Gate encoding (gg): maps tick duration to a byte value.
    Delta encoding: A0 dd for deltas ≤ 127, A1 dd for 128-255, etc.
    """
    buf = bytearray()
    buf.extend(b"\xF0\x00")  # start marker

    cmd = 0xD0 if track.is_drum else 0xE0

    # Collect all events across all bars in absolute ticks
    events = []
    for n in track.notes:
        abs_tick = n.bar * pattern.bar_ticks + n.tick_on
        events.append((abs_tick, n))

    events.sort(key=lambda e: (e[0], e[1].note))

    prev_tick = 0
    for abs_tick, note in events:
        delta = abs_tick - prev_tick
        if delta > 0:
            _encode_delta(buf, delta)
        prev_tick = abs_tick

        # Encode note
        gate = _tick_to_gate(note.tick_dur)
        buf.extend([cmd, note.note & 0x7F, note.velocity & 0x7F, gate & 0x7F])

    buf.append(0xF2)  # end marker
    return bytes(buf)


def _encode_delta(buf: bytearray, ticks: int) -> None:
    """Encode a delta time value as A0-A7 commands.

    Hypothesis: A0 dd = dd ticks (0-127), A1 dd = 128+dd, etc.
    Each step type adds 128 to the range.
    Maximum: A7 0x7F = 7*128 + 127 = 1023 ticks.
    For larger deltas, emit multiple delta commands.
    """
    while ticks > 0:
        if ticks <= 127:
            buf.extend([0xA0, ticks])
            ticks = 0
        elif ticks <= 255:
            buf.extend([0xA1, ticks - 128])
            ticks = 0
        elif ticks <= 383:
            buf.extend([0xA2, ticks - 256])
            ticks = 0
        elif ticks <= 511:
            buf.extend([0xA3, ticks - 384])
            ticks = 0
        elif ticks <= 639:
            buf.extend([0xA4, ticks - 512])
            ticks = 0
        elif ticks <= 767:
            buf.extend([0xA5, ticks - 640])
            ticks = 0
        elif ticks <= 895:
            buf.extend([0xA6, ticks - 768])
            ticks = 0
        elif ticks <= 1023:
            buf.extend([0xA7, ticks - 896])
            ticks = 0
        else:
            # Emit maximum delta (A7 7F = 1023) and continue
            buf.extend([0xA7, 0x7F])
            ticks -= 1023


def _tick_to_gate(tick_dur: int) -> int:
    """Convert tick duration to Q7P gate byte.

    Hypothesis based on DECAY.Q7P example where gate=0x58 (88).
    Simple linear mapping: gate = min(127, tick_dur // 2).
    This is a rough approximation — actual mapping TBD from hardware testing.
    """
    return min(0x7F, max(1, tick_dur // 4))


def build_phrase_block(
    track: QuantizedTrack,
    pattern: QuantizedPattern,
    phrase_name: str = "",
) -> bytes:
    """Build a complete 5120-byte phrase block header + events.

    Returns the phrase block bytes (header + events + F2 + padding).
    This is a fragment — it must be placed within a 5120-byte Q7P file.
    """
    # Phrase header (28 bytes)
    name_bytes = (phrase_name or track.name).ljust(12)[:12].encode("ascii")
    header = bytearray(28)
    header[0:12] = name_bytes
    header[12:14] = b"\x03\x1C"  # marker
    header[14:18] = b"\x00\x00\x00\x7F"  # note range
    header[18:20] = b"\x00\x07"  # track flags
    header[20:24] = b"\x90\x00\x00\x00"  # MIDI setup
    tempo_val = int(pattern.bpm * 10)
    header[24:26] = struct.pack(">H", tempo_val)
    header[26:28] = b"\xF0\x00"  # start MIDI marker (redundant with F0 00 in events)

    # Encode events (already includes F0 00 start and F2 end)
    events = encode_phrase_events(track, pattern)

    # Combine: header + events (skip the F0 00 from events since header has it)
    block = bytes(header) + events[2:]  # skip events' F0 00, header already has it

    return block


# --- Q7P File Writer (3072-byte template-based) ---

def write_q7p_metadata(
    pattern: QuantizedPattern,
    template_path: Optional[str] = None,
    output_path: Optional[str] = None,
) -> bytes:
    """Write a Q7P file with metadata from the pattern.

    Uses the embedded template and overwrites SAFE fields only:
    name, tempo, time signature. Does NOT write musical events
    (the 3072-byte format's 128-byte event area is too small).

    For musical data, use write_smf() or the phrase blocks for 5120-byte Q7P.
    """
    # Import converter for template access
    from qymanager.converters.qy70_to_qy700 import _get_embedded_template

    if template_path:
        with open(template_path, "rb") as f:
            buf = bytearray(f.read())
    else:
        buf = bytearray(_get_embedded_template())

    # Name (0x876, 10 bytes)
    name = (pattern.name or "CAPTURE").upper()[:10].ljust(10)
    buf[0x876:0x880] = name.encode("ascii", errors="replace")

    # Tempo (0x188, 2 bytes BE, BPM * 10)
    tempo_val = int(pattern.bpm * 10)
    struct.pack_into(">H", buf, 0x188, tempo_val)

    # Time signature (0x18A)
    # 0x1C = 4/4 (default). Only change if not 4/4.
    if pattern.time_sig != (4, 4):
        # Encode as QY700 format (needs more research)
        pass

    if output_path:
        with open(output_path, "wb") as f:
            f.write(buf)

    return bytes(buf)


# --- Main Pipeline ---

def run_pipeline(
    capture_path: str,
    output_prefix: str,
    bpm: Optional[float] = None,
    bar_count: Optional[int] = None,
    resolution: int = 16,
) -> None:
    """Run the complete capture-to-output pipeline.

    Produces:
        {prefix}.mid  — Standard MIDI File
        {prefix}.Q7P  — Q7P with metadata (no events for 3072B)
        {prefix}_quantized.json — Quantized data for debugging
        {prefix}_phrases.bin — Raw D0/E0 phrase data (for 5120B Q7P)
    """
    print(f"Reading capture: {capture_path}")
    pattern = quantize_capture(
        capture_path,
        bpm=bpm,
        bar_count=bar_count,
        quantize_resolution=resolution,
    )
    print(pattern.summary())
    print()

    # 1. Standard MIDI File
    mid_path = f"{output_prefix}.mid"
    write_smf(pattern, mid_path)
    print(f"SMF written: {mid_path}")

    # 2. Quantized JSON
    json_path = f"{output_prefix}_quantized.json"
    export_json(pattern, json_path)
    print(f"Quantized data: {json_path}")

    # 3. Q7P with metadata
    q7p_path = f"{output_prefix}.Q7P"
    write_q7p_metadata(pattern, output_path=q7p_path)
    print(f"Q7P metadata: {q7p_path}")

    # 4. D0/E0 phrase data for each track
    phrases_path = f"{output_prefix}_phrases.bin"
    with open(phrases_path, "wb") as f:
        for track in pattern.active_tracks:
            phrase_data = encode_phrase_events(track, pattern)
            track_header = struct.pack(">BBH", track.track_idx, track.channel,
                                       len(phrase_data))
            f.write(track_header)
            f.write(phrase_data)
            print(f"  Track {track.name}: {len(phrase_data)} bytes "
                  f"({len(track.notes)} notes, "
                  f"{'D0' if track.is_drum else 'E0'} encoding)")
    print(f"Phrase data: {phrases_path}")

    # Summary
    total_phrase = sum(
        len(encode_phrase_events(t, pattern)) for t in pattern.active_tracks
    )
    print(f"\nTotal phrase data: {total_phrase} bytes across "
          f"{len(pattern.active_tracks)} tracks")
    if total_phrase > 128:
        print("NOTE: Total exceeds 3072-byte Q7P event area (128B). "
              "A 5120-byte Q7P template is needed for full conversion.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Pipeline B: Capture → Q7P + SMF conversion"
    )
    parser.add_argument("capture", help="Capture JSON file path")
    parser.add_argument("-o", "--output", default=None,
                       help="Output prefix (default: derived from capture name)")
    parser.add_argument("-b", "--bpm", type=float, help="BPM override")
    parser.add_argument("-n", "--bars", type=int, help="Number of bars")
    parser.add_argument("-r", "--resolution", type=int, default=16,
                       help="Quantize resolution (16=16th notes)")

    args = parser.parse_args()

    if args.output is None:
        args.output = str(Path(args.capture).with_suffix(""))

    run_pipeline(
        args.capture,
        args.output,
        bpm=args.bpm,
        bar_count=args.bars,
        resolution=args.resolution,
    )
