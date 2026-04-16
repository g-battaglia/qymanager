#!/usr/bin/env python3
"""
Summer ground truth extractor.

Links Summer's 20 RHY1 events (4 per bar × 5 bars) to the exact MIDI notes
captured during playback (summer_playback_s25.json). Each event encodes
one quarter-note beat containing up to 3 drum strikes.

Output: a test vector of (event_bytes, [(note, vel, eighth_offset), ...])
that any candidate decoder must reproduce exactly.
"""

import sys
import os
import json
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from midi_tools.analyze_cross_pattern_signatures import parse_all_tracks, extract_events


BPM = 120.0
BEAT_S = 60.0 / BPM  # 0.500s
BAR_S = BEAT_S * 4   # 2.000s
PATTERN_BARS = 5
PATTERN_S = BAR_S * PATTERN_BARS  # 10.0s


def load_midi_drum_notes(json_path, max_loop=1):
    """Load drum notes from first pattern iteration only (0..10s)."""
    with open(json_path) as f:
        data = json.load(f)

    notes = []
    for ev in data["events"]:
        d = ev["data"]
        if len(d) < 3:
            continue
        if d[0] != 0x98:  # Note-on on ch9 (0x90 | 8)
            continue
        if d[2] == 0:
            continue
        t = ev["t"]
        if t >= PATTERN_S * max_loop:
            break
        notes.append((t, d[1], d[2]))
    return notes


def assign_to_beats(notes):
    """Assign each note to (bar_idx, beat_idx_0to3, subdiv_0to1)."""
    beat_events = defaultdict(list)  # (bar, beat) -> [(note, vel, subdiv)]
    for t, note, vel in notes:
        bar = int(t / BAR_S)
        bar_t = t - bar * BAR_S
        # Each bar has 4 beats × 2 subdivisions = 8 eighth notes
        eighth = round(bar_t / (BEAT_S / 2))
        beat = eighth // 2
        sub = eighth % 2
        # Quantize onset to nearest eighth; record actual subdivision
        if beat < 4:
            beat_events[(bar, beat)].append((note, vel, sub))
    return beat_events


def main():
    sm = parse_all_tracks("data/qy70_sysx/P -  Summer - 20231101.syx")
    events = extract_events(sm[0])

    # Collect events for seg1..seg5 (skip seg6 = tail/padding)
    # extract_events returns si starting at 1 (si=0 is a pre-segment that gets
    # skipped for being <13 bytes). si=1..5 correspond to music bars 1..5.
    by_seg = defaultdict(list)
    for si, ei, evt, hdr in events:
        if 1 <= si <= 5:
            by_seg[si].append((ei, evt))

    # Load MIDI ground truth
    midi_notes = load_midi_drum_notes("midi_tools/captured/summer_playback_s25.json",
                                       max_loop=1)
    beat_events = assign_to_beats(midi_notes)

    print("=" * 72)
    print("SUMMER RHY1 GROUND TRUTH: event → expected MIDI notes")
    print("=" * 72)

    total_matched = 0
    note_names = {36: "KICK ", 38: "SNARE", 42: "HAT  "}

    for bar_idx in range(5):  # 0..4 = music bars 1..5
        si = bar_idx + 1
        print(f"\n--- Bar {bar_idx + 1} (si={si}) ---")
        evs = by_seg[si]
        for ei, evt_bytes in evs:
            expected = beat_events.get((bar_idx, ei), [])
            expected_sorted = sorted(expected, key=lambda x: (x[2], x[0]))

            print(f"  e{ei}: {evt_bytes.hex()}")
            print(f"      {'decimal:':10} {list(evt_bytes)}")
            print(f"      {'binary:':10} {' '.join(f'{b:08b}' for b in evt_bytes)}")

            for note, vel, sub in expected_sorted:
                eighth_label = "8th" if sub == 0 else "8nd"
                print(f"      → {note_names.get(note, f'N{note}')} "
                      f"vel={vel:3d} ({eighth_label})")
            total_matched += len(expected)

    print()
    print("=" * 72)
    print(f"Total ground-truth strikes: {total_matched} across 20 events")
    print("=" * 72)

    # Output as machine-readable JSON for decoder testing
    output = {
        "source": "Summer_20231101.syx",
        "bpm": BPM,
        "pattern_bars": PATTERN_BARS,
        "track": "RHY1",
        "channel": 9,
        "events": []
    }

    for bar_idx in range(5):
        si = bar_idx + 1
        for ei, evt_bytes in by_seg[si]:
            expected = sorted(beat_events.get((bar_idx, ei), []),
                              key=lambda x: (x[2], x[0]))
            output["events"].append({
                "bar": bar_idx + 1,
                "beat": ei + 1,
                "event_hex": evt_bytes.hex(),
                "event_decimal": list(evt_bytes),
                "expected_strikes": [
                    {"note": n, "velocity": v, "subdivision_8th": s}
                    for n, v, s in expected
                ]
            })

    out_path = Path("midi_tools/captured/summer_ground_truth.json")
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\nSaved ground truth test vector: {out_path}")


if __name__ == "__main__":
    main()
