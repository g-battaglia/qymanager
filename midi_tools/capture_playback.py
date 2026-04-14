#!/usr/bin/env python3
"""Capture MIDI playback from QY70 style.

Sends MIDI Start to trigger style playback, captures all incoming MIDI
messages for a specified duration, then sends MIDI Stop.

This validates whether a loaded style plays the expected notes.
"""

import sys
import time
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def find_midi_ports():
    """Find Steinberg UR22C MIDI ports."""
    import mido
    out_ports = mido.get_output_names()
    in_ports = mido.get_input_names()

    out = next((p for p in out_ports if "steinberg" in p.lower() or "ur22" in p.lower()), None)
    inp = next((p for p in in_ports if "steinberg" in p.lower() or "ur22" in p.lower()), None)

    return inp, out


def capture_playback(duration_sec=5.0, bpm=120, verbose=True, send_start=True):
    """Start style playback on QY70 and capture MIDI output.

    Sends MIDI Start + Clock (24 ppqn) to drive QY70 in External sync mode.
    Returns list of (timestamp, message) tuples.
    """
    import mido

    in_port_name, out_port_name = find_midi_ports()
    if not in_port_name or not out_port_name:
        print(f"ERROR: MIDI ports not found. In={in_port_name}, Out={out_port_name}")
        return []

    # 24 MIDI clocks per quarter note
    clock_interval = 60.0 / (bpm * 24)

    if verbose:
        print(f"Input:  {in_port_name}")
        print(f"Output: {out_port_name}")
        print(f"Duration: {duration_sec}s")
        print(f"Tempo: {bpm} BPM (clock interval: {clock_interval*1000:.1f}ms)")
        print()

    captured = []
    clock_msg = mido.Message('clock')

    with mido.open_input(in_port_name) as inp, mido.open_output(out_port_name) as out:
        # Flush any pending input
        for _ in inp.iter_pending():
            pass

        # Send MIDI Start
        if send_start:
            if verbose:
                print("Sending MIDI Start (0xFA)...")
            out.send(mido.Message('start'))

        t0 = time.time()
        next_clock = t0 + clock_interval

        # Capture for the specified duration, sending clock pulses
        while time.time() - t0 < duration_sec:
            now = time.time()

            # Send clock pulses at the correct rate
            while now >= next_clock:
                out.send(clock_msg)
                next_clock += clock_interval

            # Read incoming messages
            for msg in inp.iter_pending():
                t = now - t0
                if msg.type != 'clock':  # Don't capture echoed clocks
                    captured.append((t, msg))
                    if verbose and msg.type in ('note_on', 'note_off'):
                        ch = msg.channel + 1
                        print(f"  {t:6.3f}s ch{ch:2d} {msg.type:8s} n={msg.note:3d} v={msg.velocity:3d}")

            time.sleep(0.0005)  # ~0.5ms sleep for tight clock timing

        # Send MIDI Stop
        out.send(mido.Message('stop'))
        if verbose:
            print("\nSent MIDI Stop (0xFC)")

        # Capture any remaining messages
        time.sleep(0.1)
        for msg in inp.iter_pending():
            t = time.time() - t0
            if msg.type != 'clock':
                captured.append((t, msg))

    return captured


def analyze_drum_events(captured, known_pattern=None):
    """Analyze captured drum events.

    With PATT OUT CH=9~16: D1=ch9, D2=ch10, PC=ch11, BA=ch12, C1-C4=ch13-16.
    With PATT OUT CH=1~8:  D1=ch1, D2=ch2, PC=ch3, BA=ch4, C1-C4=ch5-8.
    """
    # Collect note_on events from drum channels (ch 9 and 10 for PATT OUT=9~16)
    drum_notes = []
    for t, msg in captured:
        if msg.type == 'note_on' and msg.channel in (8, 9) and msg.velocity > 0:
            drum_notes.append((t, msg.note, msg.velocity, msg.channel + 1))

    print(f"\n{'='*60}")
    print(f"  DRUM NOTE ANALYSIS (D1=ch9, D2=ch10 with PATT OUT=9~16)")
    print(f"{'='*60}")
    print(f"  Total drum note-on events: {len(drum_notes)}")

    if not drum_notes:
        print("  No drum events captured!")
        print("  Check: UTILITY → MIDI → PATT OUT CH must be '9~16' (or '1~8')")
        print("  Check: MIDI CONTROL must be 'In' or 'In/Out' for Start/Stop")
        print("  Check: is the user style loaded? (should be after SysEx send)")
        return

    GM_DRUMS = {
        36: "Kick1", 38: "Snare1", 44: "HHpedal", 49: "Crash1",
        42: "HHclose", 46: "HHopen", 51: "Ride1"
    }

    # Group by beat (assuming 120 BPM = 500ms per beat)
    print(f"\n  {'Time':>8} {'Ch':>3} {'Note':>4} {'Vel':>4} {'Name':<12}")
    for entry in drum_notes:
        t, note, vel = entry[0], entry[1], entry[2]
        ch = entry[3] if len(entry) > 3 else 10
        name = GM_DRUMS.get(note, f"n{note}")
        print(f"  {t:8.3f} {ch:3d} {note:4d} {vel:4d} {name:<12}")

    if known_pattern:
        print(f"\n  Expected pattern:")
        for note, vel, gate, tick, name in known_pattern:
            vel_code = max(0, min(15, round((127 - vel) / 8)))
            vel_q = max(1, 127 - vel_code * 8)
            print(f"    {name:>8} n={note} v={vel_q} t={tick}")

    # Count unique notes
    note_set = set(entry[1] for entry in drum_notes)
    print(f"\n  Unique notes: {sorted(note_set)}")
    for n in sorted(note_set):
        count = sum(1 for entry in drum_notes if entry[1] == n)
        name = GM_DRUMS.get(n, f"n{n}")
        print(f"    {name:>8} ({n}): {count} hits")


def main():
    parser = argparse.ArgumentParser(description="Capture QY70 style playback via MIDI")
    parser.add_argument("--duration", "-d", type=float, default=5.0,
                        help="Capture duration in seconds (default: 5)")
    parser.add_argument("--bpm", type=int, default=120,
                        help="Tempo in BPM for MIDI clock (default: 120)")
    parser.add_argument("--no-start", action="store_true",
                        help="Don't send MIDI Start (assume already playing)")
    parser.add_argument("--quiet", "-q", action="store_true")
    args = parser.parse_args()

    print("=" * 60)
    print("  QY70 STYLE PLAYBACK CAPTURE")
    print("=" * 60)
    print()

    known_pattern = [
        (36, 127, 412, 240, "Kick1"),
        (49, 127,  74, 240, "Crash1"),
        (44, 119,  30, 240, "HHpedal"),
        (44,  95,  30, 720, "HHpedal"),
        (38, 127, 200, 960, "Snare1"),
        (44,  95,  30, 960, "HHpedal"),
        (44,  95,  30, 1440, "HHpedal"),
    ]

    captured = capture_playback(args.duration, bpm=args.bpm,
                                verbose=not args.quiet,
                                send_start=not args.no_start)
    print(f"\nTotal captured messages: {len(captured)}")

    # Show all message types
    types = {}
    for _, msg in captured:
        types[msg.type] = types.get(msg.type, 0) + 1
    print(f"Message types: {dict(sorted(types.items()))}")

    analyze_drum_events(captured, known_pattern)


if __name__ == "__main__":
    main()
