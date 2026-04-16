#!/usr/bin/env python3
"""
Q7P Real-time MIDI Playback.

Parses a Q7P file and plays it through a MIDI output port in real-time.
This lets you hear QY700 patterns through ANY MIDI-connected tone generator
(QY70, QY700, or any GM/XG synth).

Voice mapping:
  Drum tracks → channel 10 (GM Standard Kit by default)
  Melody tracks → channels 1-9, 11-16

The script can optionally send XG-specific setup messages to configure
the tone generator before playback.

Usage:
    python3 midi_tools/q7p_playback.py data/q7p/DECAY.Q7P
    python3 midi_tools/q7p_playback.py data/q7p/DECAY.Q7P --port "USB MIDI"
    python3 midi_tools/q7p_playback.py data/q7p/DECAY.Q7P --loop 4
"""

import argparse
import sys
import time
from pathlib import Path
from typing import List, Tuple

# Use rtmidi directly (mido SysEx is broken on macOS — see memory)
try:
    import rtmidi
except ImportError:
    print("ERROR: rtmidi not installed. Run: pip install python-rtmidi", file=sys.stderr)
    sys.exit(1)

from q7p_to_midi import (
    PPQN,
    PhraseInfo,
    NoteEvent,
    parse_q7p_header,
    find_phrase_blocks,
    parse_phrase_events,
)


def list_midi_ports():
    """List available MIDI output ports."""
    midiout = rtmidi.MidiOut()
    ports = midiout.get_ports()
    del midiout
    return ports


def build_playback_events(phrases: List[PhraseInfo]) -> List[Tuple[int, bytes]]:
    """
    Merge all phrases into a single timeline of (tick, midi_bytes) events.

    Returns sorted list of (absolute_tick, raw_midi_message).
    """
    events = []

    for phrase in phrases:
        ch = phrase.channel & 0x0F
        for ev in phrase.events:
            # Note on
            events.append((ev.tick, bytes([0x90 | ch, ev.note, ev.velocity])))
            # Note off
            off_tick = ev.tick + ev.gate_ticks
            events.append((off_tick, bytes([0x80 | ch, ev.note, 0])))

    # Sort by tick, note-off before note-on at same tick
    events.sort(key=lambda x: (x[0], 0 if x[1][0] & 0xF0 == 0x80 else 1))
    return events


def play_events(midiout, events: List[Tuple[int, bytes]], tempo_bpm: float,
                loops: int = 1, verbose: bool = False):
    """
    Play events through MIDI output in real-time.

    Args:
        midiout: rtmidi.MidiOut with port open
        events: Sorted list of (tick, midi_bytes)
        tempo_bpm: Tempo in BPM
        loops: Number of times to loop the pattern
        verbose: Print progress
    """
    if not events:
        print("No events to play.")
        return

    # Calculate tick duration in seconds
    tick_duration = 60.0 / (tempo_bpm * PPQN)

    # Pattern length (4 bars at 4/4)
    pattern_ticks = PPQN * 4 * 4  # 7680 ticks

    for loop_num in range(loops):
        if verbose:
            print(f"  Loop {loop_num + 1}/{loops}")

        start_time = time.time()
        prev_tick = 0

        for tick, midi_bytes in events:
            # Wait for the right time
            target_time = start_time + (tick * tick_duration)
            now = time.time()
            if target_time > now:
                time.sleep(target_time - now)

            # Send MIDI message
            midiout.send_message(list(midi_bytes))

        # Wait for pattern end (remaining time to fill 4 bars)
        max_tick = events[-1][0] if events else 0
        if max_tick < pattern_ticks:
            remaining = (pattern_ticks - max_tick) * tick_duration
            time.sleep(remaining)

    # All notes off on all channels
    for ch in range(16):
        midiout.send_message([0xB0 | ch, 123, 0])  # All Notes Off
        midiout.send_message([0xB0 | ch, 121, 0])  # Reset All Controllers


def send_gm_reset(midiout):
    """Send GM System On to reset tone generator."""
    # GM System On: F0 7E 7F 09 01 F7
    midiout.send_message([0xF0, 0x7E, 0x7F, 0x09, 0x01, 0xF7])
    time.sleep(0.1)


def send_voice_setup(midiout, phrases: List[PhraseInfo]):
    """
    Send program changes to set up voices for playback.

    For drum tracks: channel 10, Standard Kit (bank 0, prog 0)
    For melody tracks: use reasonable GM defaults based on phrase name
    """
    # GM voice mapping by phrase name keyword
    VOICE_MAP = {
        "piano": 0,      # Acoustic Grand Piano
        "pad": 89,        # Warm Pad
        "bass": 33,       # Finger Bass
        "guitar": 25,     # Acoustic Guitar (steel)
        "bell": 14,       # Tubular Bells
        "dream": 88,      # New Age (pad)
        "string": 48,     # String Ensemble
        "tik": 115,       # Woodblock
        "noise": 127,     # Gun Shot (closest to noise)
    }

    assigned_channels = set()
    for phrase in phrases:
        ch = phrase.channel & 0x0F
        if ch in assigned_channels:
            continue
        assigned_channels.add(ch)

        if phrase.is_drum:
            # Bank select for Standard Kit
            midiout.send_message([0xB0 | ch, 0, 127])   # Bank MSB = 127 (drums)
            midiout.send_message([0xB0 | ch, 32, 0])    # Bank LSB = 0
            midiout.send_message([0xC0 | ch, 0])        # Program 0 = Standard Kit
        else:
            # Find matching voice
            prog = 0
            name_lower = phrase.name.lower()
            for keyword, program in VOICE_MAP.items():
                if keyword in name_lower:
                    prog = program
                    break

            midiout.send_message([0xB0 | ch, 0, 0])     # Bank MSB = 0 (GM)
            midiout.send_message([0xB0 | ch, 32, 0])    # Bank LSB = 0
            midiout.send_message([0xC0 | ch, prog])     # Program Change

        # Set volume
        midiout.send_message([0xB0 | ch, 7, 100])       # Volume = 100

    time.sleep(0.05)


def main():
    parser = argparse.ArgumentParser(description="Play Q7P pattern via MIDI")
    parser.add_argument("q7p_file", nargs="?", help="Path to Q7P file")
    parser.add_argument("--port", "-p", help="MIDI output port name (substring match)")
    parser.add_argument("--loop", "-l", type=int, default=2,
                        help="Number of loops (default: 2)")
    parser.add_argument("--list-ports", action="store_true",
                        help="List available MIDI ports and exit")
    parser.add_argument("--no-setup", action="store_true",
                        help="Skip GM reset and voice setup")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    if args.list_ports:
        ports = list_midi_ports()
        if ports:
            for i, p in enumerate(ports):
                print(f"  {i}: {p}")
        else:
            print("No MIDI output ports found.")
        return

    if not args.q7p_file:
        parser.error("q7p_file is required unless --list-ports is used")

    # Parse Q7P
    q7p_path = Path(args.q7p_file)
    data = q7p_path.read_bytes()
    if len(data) != 5120:
        print(f"ERROR: Only 5120-byte Q7P files supported (got {len(data)})", file=sys.stderr)
        sys.exit(1)

    header = parse_q7p_header(data)
    tempo = header["tempo"]
    print(f"Pattern: {header['name']} @ {tempo} BPM")

    blocks = find_phrase_blocks(data)
    phrases = []
    melody_ch = 0
    for offset, name in blocks:
        ch = melody_ch
        phrase = parse_phrase_events(data, offset, channel=ch)
        if not phrase.is_drum:
            melody_ch += 1
            if melody_ch == 9:
                melody_ch = 10
        phrase.channel = 9 if phrase.is_drum else ch
        phrases.append(phrase)

    # Build merged timeline
    events = build_playback_events(phrases)
    print(f"Phrases: {len(phrases)}, Total events: {len(events)}")

    # Open MIDI port
    midiout = rtmidi.MidiOut()
    ports = midiout.get_ports()

    if not ports:
        print("ERROR: No MIDI output ports available.", file=sys.stderr)
        sys.exit(1)

    port_idx = 0
    if args.port:
        for i, p in enumerate(ports):
            if args.port.lower() in p.lower():
                port_idx = i
                break
        else:
            print(f"ERROR: No port matching '{args.port}'. Available:", file=sys.stderr)
            for p in ports:
                print(f"  {p}", file=sys.stderr)
            sys.exit(1)

    midiout.open_port(port_idx)
    print(f"Using port: {ports[port_idx]}")

    try:
        if not args.no_setup:
            print("Sending GM reset + voice setup...")
            send_gm_reset(midiout)
            send_voice_setup(midiout, phrases)

        duration = (PPQN * 4 * 4 * args.loop) / (tempo * PPQN / 60)
        print(f"Playing {args.loop} loops ({duration:.1f}s)...")
        play_events(midiout, events, tempo, loops=args.loop, verbose=args.verbose)
        print("Done.")
    except KeyboardInterrupt:
        print("\nStopped.")
        # All notes off
        for ch in range(16):
            midiout.send_message([0xB0 | ch, 123, 0])
    finally:
        del midiout


if __name__ == "__main__":
    main()
