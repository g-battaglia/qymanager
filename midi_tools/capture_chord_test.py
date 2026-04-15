#!/usr/bin/env python3
"""Capture chord transposition test from QY70.

Sends the known_pattern.syx, starts playback via external clock,
and captures output for a duration. Run multiple times with different
chord settings on QY70 to build a transposition lookup table.

The known_pattern outputs on CHD1 (ch13 with PATT OUT 9~16).
With default C major chord → [60,64,67] (C4,E4,G4).

Test plan:
  1. Set QY70: PATT OUT=9~16, ECHO BACK=Off, MIDI SYNC=External
  2. Run with CM → capture [60,64,67]
  3. Change chord on QY70 to Dm, run again → expect [62,65,69]?
  4. Change to G, run → expect [67,71,74]?
  5. Compare captures to derive transposition formula

Usage:
    python3 midi_tools/capture_chord_test.py --chord CM -d 15
    python3 midi_tools/capture_chord_test.py --chord Dm -d 15
    python3 midi_tools/capture_chord_test.py --chord G7 -d 15
"""

import sys
import time
import json
import argparse
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

KNOWN_PATTERN = str(Path(__file__).parent / "captured" / "known_pattern.syx")

PATT_OUT_MAP = {
    1: "D1/RHY1", 2: "D2/RHY2", 3: "PC/PAD", 4: "BA/BASS",
    5: "C1/CHD1", 6: "C2/CHD2", 7: "C3/PHR1", 8: "C4/PHR2",
    9: "D1/RHY1", 10: "D2/RHY2", 11: "PC/PAD", 12: "BA/BASS",
    13: "C1/CHD1", 14: "C2/CHD2", 15: "C3/PHR1", 16: "C4/PHR2",
}

GM_DRUMS = {
    35: "Kick2", 36: "Kick1", 37: "SideStk", 38: "Snare1",
    39: "Clap", 40: "Snare2", 42: "HHclose", 44: "HHpedal",
    46: "HHopen", 49: "Crash1", 51: "Ride1", 53: "RideBell",
}


def run_capture(chord_name, duration, bpm=120, send_style=True):
    """Send known_pattern, start playback, capture notes."""
    import rtmidi

    mo = rtmidi.MidiOut()
    mi = rtmidi.MidiIn()
    mi.ignore_types(sysex=False, timing=True, active_sense=True)

    mo.open_port(0)
    mi.open_port(0)
    time.sleep(0.3)
    while mi.get_message():
        pass

    # Send known_pattern
    if send_style:
        from midi_tools.send_style import parse_syx_file

        messages = parse_syx_file(KNOWN_PATTERN)
        print(f"  Sending {len(messages)} SysEx messages...")
        for msg_bytes, info in messages:
            mo.send_message(list(msg_bytes))
            if info["type"] == "init":
                time.sleep(0.5)
            elif info["type"] != "close":
                time.sleep(0.15)
        print("  Waiting 3s for QY70 to load...")
        time.sleep(3.0)
        while mi.get_message():
            pass

    # Background listener
    captured = []
    stop = threading.Event()

    def listener():
        while not stop.is_set():
            m = mi.get_message()
            if m:
                captured.append((time.time(), m[0]))
            else:
                time.sleep(0.0005)

    t = threading.Thread(target=listener, daemon=True)
    t.start()
    t0 = time.time()

    # Start playback with external clock
    print(f"  Starting playback at {bpm} BPM...")
    mo.send_message([0xFA])
    clock_interval = 60.0 / (bpm * 24)
    next_clock = time.time() + clock_interval

    while time.time() - t0 < duration:
        now = time.time()
        while now >= next_clock:
            mo.send_message([0xF8])
            next_clock += clock_interval
        time.sleep(0.0005)

    mo.send_message([0xFC])
    time.sleep(0.5)
    stop.set()
    t.join(timeout=1)

    mo.close_port()
    mi.close_port()

    return [(ts - t0, data) for ts, data in captured]


def analyze_notes(captured, chord_name):
    """Extract note-on events and group by channel."""
    note_ons = []
    for t, d in captured:
        if len(d) >= 3 and d[0] & 0xF0 == 0x90 and d[2] > 0:
            ch = (d[0] & 0x0F) + 1
            note_ons.append((t, ch, d[1], d[2]))

    print(f"\n{'='*60}")
    print(f"  CHORD TEST: {chord_name}")
    print(f"{'='*60}")
    print(f"  Total notes: {len(note_ons)}")

    ch_notes = {}
    for t, ch, note, vel in note_ons:
        ch_notes.setdefault(ch, []).append((t, note, vel))

    for ch in sorted(ch_notes.keys()):
        events = ch_notes[ch]
        label = PATT_OUT_MAP.get(ch, f"ch{ch}")
        unique = sorted(set(n for _, n, _ in events))
        print(f"\n  {label} (ch{ch}): {len(events)} notes")
        print(f"    Unique notes: {unique}")
        for t, note, vel in events[:10]:
            if ch in (1, 2, 3, 9, 10, 11):
                name = GM_DRUMS.get(note, f"n{note}")
            else:
                name = f"n{note}"
            print(f"      t={t:.3f}s {name:>8} ({note:3d}) v={vel:3d}")

    # Extract chord clusters (notes at same time on chord channels)
    chord_ch = {5, 13}  # CHD1 on both PATT OUT settings
    chord_events = [(t, n, v) for t, ch, n, v in note_ons if ch in chord_ch]

    if chord_events:
        clusters = []
        current = [chord_events[0]]
        for t, n, v in chord_events[1:]:
            if t - current[-1][0] < 0.05:  # Same chord cluster
                current.append((t, n, v))
            else:
                clusters.append(current)
                current = [(t, n, v)]
        clusters.append(current)

        print(f"\n  Chord clusters: {len(clusters)}")
        for i, cluster in enumerate(clusters[:10]):
            notes = sorted(set(n for _, n, _ in cluster))
            vel = cluster[0][2]
            t = cluster[0][0]
            print(f"    #{i}: t={t:.3f}s notes={notes} vel={vel}")

        return clusters
    return []


def main():
    parser = argparse.ArgumentParser(description="QY70 chord transposition test")
    parser.add_argument("--chord", "-c", type=str, default="CM",
                        help="Chord name for labeling (e.g., CM, Dm, G7)")
    parser.add_argument("-d", "--duration", type=float, default=15.0,
                        help="Capture duration (default: 15s)")
    parser.add_argument("--bpm", type=int, default=120)
    parser.add_argument("--no-send", action="store_true",
                        help="Don't send pattern (already loaded)")
    args = parser.parse_args()

    print("=" * 60)
    print(f"  QY70 CHORD TRANSPOSITION TEST — {args.chord}")
    print("=" * 60)
    print(f"  Prerequisites:")
    print(f"    PATT OUT CH: 9~16")
    print(f"    ECHO BACK: Off")
    print(f"    MIDI SYNC: External")
    print(f"    Chord set to: {args.chord}")
    print()

    captured = run_capture(args.chord, args.duration, args.bpm,
                           send_style=not args.no_send)

    clusters = analyze_notes(captured, args.chord)

    # Save result
    outdir = Path(__file__).parent / "captured"
    outpath = outdir / f"chord_test_{args.chord}.json"
    result = {
        "chord": args.chord,
        "bpm": args.bpm,
        "duration": args.duration,
        "captured_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total_notes": sum(1 for _, d in captured
                           if len(d) >= 3 and d[0] & 0xF0 == 0x90 and d[2] > 0),
        "clusters": [
            {
                "time": round(c[0][0], 3),
                "notes": sorted(set(n for _, n, _ in c)),
                "velocity": c[0][2],
            }
            for c in clusters
        ],
        "raw_events": [{"t": round(t, 6), "data": list(d)} for t, d in captured],
    }
    with open(outpath, "w") as f:
        json.dump(result, f, indent=2)
    print(f"\n  Saved to {outpath}")


if __name__ == "__main__":
    main()
