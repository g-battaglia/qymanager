#!/usr/bin/env python3
"""Test hypothesis: 0x9E/0xDC are NOT delimiters but data bytes.

If true, the entire event_data block should be parsed as:
  [header] + [7-byte events] without splitting.

Try different header sizes (10-16) and check R=9*(i+1) match rate.
"""

import sys
import os
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from midi_tools.event_decoder import (
    get_track_data, rot_right, extract_9bit, SECTION_NAMES, TRACK_NAMES,
)

SYX_PATH = "tests/fixtures/QY70_SGT.syx"
DRUM_TARGETS = {36, 38, 42, 44, 54, 68}


def test_header_sizes(slot, section=0):
    """Try different header sizes and parse as continuous stream."""
    data = get_track_data(SYX_PATH, section, slot)
    event_data = data[28:]  # Skip track header

    print(f"\n{'='*70}")
    print(f"  NO-DELIMITER TEST: Slot {slot} ({TRACK_NAMES[slot]}) "
          f"Section {SECTION_NAMES[section]}")
    print(f"  Event data: {len(event_data)} bytes")
    print(f"{'='*70}")

    best_header_size = 0
    best_score = 0

    for header_size in range(0, 25):
        events_data = event_data[header_size:]
        n_events = len(events_data) // 7

        if n_events < 5:
            continue

        # Extract 7-byte events
        events = []
        for i in range(n_events):
            evt = events_data[i * 7: (i + 1) * 7]
            events.append(evt)

        # Try R=9*(i+1)
        hits = 0
        notes = []
        for i, evt in enumerate(events):
            val = int.from_bytes(evt, "big")
            r = (9 * (i + 1)) % 56
            derot = rot_right(val, r)
            f0 = extract_9bit(derot, 0)
            note = f0 & 0x7F
            if note in DRUM_TARGETS:
                hits += 1
            notes.append(note)

        score = hits / n_events if n_events > 0 else 0
        leftover = len(events_data) % 7
        unique_notes = len(set(notes))

        marker = " ★" if score > best_score else ""
        if score > best_score:
            best_score = score
            best_header_size = header_size

        print(f"  Header={header_size:2d}: {n_events:3d} events, "
              f"hits={hits:3d}/{n_events:3d} ({score:5.1%}), "
              f"left={leftover}, unique={unique_notes}{marker}")

    # Show detailed results for best header size
    if best_header_size >= 0:
        print(f"\n  Best: header={best_header_size} ({best_score:.1%})")
        events_data = event_data[best_header_size:]
        n_events = len(events_data) // 7

        events = []
        for i in range(n_events):
            evt = events_data[i * 7: (i + 1) * 7]
            events.append(evt)

        print(f"\n  First 30 events with R=9*(i+1):")
        for i, evt in enumerate(events[:30]):
            val = int.from_bytes(evt, "big")
            r = (9 * (i + 1)) % 56
            derot = rot_right(val, r)
            f0 = extract_9bit(derot, 0)
            note = f0 & 0x7F
            bit8 = (f0 >> 8) & 1
            bit7 = (f0 >> 7) & 1
            rem = derot & 0x3
            vel_code = (bit8 << 3) | (bit7 << 2) | rem
            vel = max(1, 127 - vel_code * 8)

            status = "✓" if note in DRUM_TARGETS else " "
            # Also check if it's a "control event" (lo7 > 87)
            is_ctrl = note > 87
            ctrl_str = " [CTRL]" if is_ctrl else ""

            print(f"    e{i:3d} R={r:2d}: {evt.hex()} → "
                  f"note={note:3d} vel={vel:3d} {status}{ctrl_str}")

        # Note distribution
        note_counter = Counter()
        for i, evt in enumerate(events):
            val = int.from_bytes(evt, "big")
            r = (9 * (i + 1)) % 56
            derot = rot_right(val, r)
            f0 = extract_9bit(derot, 0)
            note = f0 & 0x7F
            note_counter[note] += 1

        print(f"\n  Note distribution (R=9*(i+1), header={best_header_size}):")
        for note in sorted(note_counter):
            count = note_counter[note]
            marker = "✓" if note in DRUM_TARGETS else " "
            bar = "█" * min(count, 30)
            print(f"    {marker} {note:3d}: {count:3d} {bar}")


def test_alternative_rotations(slot, section=0, header_size=13):
    """Try alternative rotation models."""
    data = get_track_data(SYX_PATH, section, slot)
    events_data = data[28 + header_size:]
    n_events = len(events_data) // 7

    events = [events_data[i*7:(i+1)*7] for i in range(n_events)]

    print(f"\n{'='*70}")
    print(f"  ROTATION MODEL COMPARISON: Slot {slot}, Header={header_size}")
    print(f"  Events: {n_events}")
    print(f"{'='*70}")

    target = DRUM_TARGETS if slot == 0 else set()

    models = {
        "R=9*(i+1)": lambda i: (9*(i+1)) % 56,
        "R=9*i": lambda i: (9*i) % 56,
        "R=7*(i+1)": lambda i: (7*(i+1)) % 56,
        "R=11*(i+1)": lambda i: (11*(i+1)) % 56,
        "R=13*(i+1)": lambda i: (13*(i+1)) % 56,
        "R=5*(i+1)": lambda i: (5*(i+1)) % 56,
        "R=3*(i+1)": lambda i: (3*(i+1)) % 56,
        "R=constant 9": lambda i: 9,
        "R=constant 47": lambda i: 47,
        "R=constant 0": lambda i: 0,
    }

    for name, r_func in models.items():
        hits = 0
        valid_range = 0  # Notes in 13-87 range
        for i, evt in enumerate(events):
            val = int.from_bytes(evt, "big")
            r = r_func(i)
            derot = rot_right(val, r)
            f0 = extract_9bit(derot, 0)
            note = f0 & 0x7F
            if note in target:
                hits += 1
            if 13 <= note <= 87:
                valid_range += 1

        hit_pct = hits / n_events * 100 if n_events > 0 else 0
        range_pct = valid_range / n_events * 100 if n_events > 0 else 0
        expected_random = len(target) / 128 * 100

        print(f"  {name:20s}: hits={hits:3d}/{n_events} ({hit_pct:5.1f}%) "
              f"range(13-87)={range_pct:5.1f}% "
              f"(random≈{expected_random:.1f}%)")


def main():
    # RHY1 (drum)
    test_header_sizes(0, section=0)
    test_alternative_rotations(0, section=0, header_size=13)

    # CHD2 (chord)
    test_header_sizes(4, section=0)


if __name__ == "__main__":
    main()
