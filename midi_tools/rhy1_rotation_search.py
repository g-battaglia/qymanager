#!/usr/bin/env python3
"""
Search for the rotation schedule + bit offset that makes velocities extractable.

For each (rotation_per_event, start_rotation, bit_offset) combination,
de-rotate each event and check if 7 bits at that offset equal the expected
velocity. Count matches across all 20 events.
"""

import json

WIDTH = 56


def rot_left(val, shift, width=WIDTH):
    shift = shift % width
    return ((val << shift) | (val >> (width - shift))) & ((1 << width) - 1)


def extract_7bit(bits, offset):
    return (bits >> (WIDTH - offset - 7)) & 0x7F


def main():
    with open("midi_tools/captured/summer_ground_truth_full.json") as f:
        gt = json.load(f)
    events = gt["tracks"]["RHY1"]["events"]

    samples = []
    for e in events:
        idx = (e["bar"] - 1) * 4 + (e["beat"] - 1)
        bits = int.from_bytes(bytes(e["event_decimal"]), "big")
        vels = [s["velocity"]
                for s in sorted(e["expected_strikes"],
                                key=lambda x: (x["subdivision_8th"], x["note"]))]
        samples.append((idx, bits, vels, e))

    # Try various rotation schedules
    # schedule(idx) = rotation amount to apply
    schedules = {
        "R=0": lambda i: 0,
        "R=9*i": lambda i: 9 * i,
        "R=-9*i": lambda i: -9 * i,
        "R=9*(i+1)": lambda i: 9 * (i + 1),
        "R=-9*(i+1)": lambda i: -9 * (i + 1),
        "R=7*i": lambda i: 7 * i,
        "R=8*i": lambda i: 8 * i,
        "R=18*i": lambda i: 18 * i,
        "R=-7*i": lambda i: -7 * i,
        "R=46*i": lambda i: 46 * i,
        "R=56*(i mod 8)": lambda i: (7 * (i % 8)),
        "R=i": lambda i: i,
    }

    print("Searching...")
    best_overall = []

    for sched_name, schedule in schedules.items():
        # Rotate each event
        rotated = []
        for idx, bits, vels, e in samples:
            r = schedule(idx) % WIDTH
            rot_bits = rot_left(bits, r)
            rotated.append((rot_bits, vels, e))

        # For each vel position (0, 1, 2), search for best offset
        for vel_idx in range(3):
            for offset in range(WIDTH - 6):
                matches = 0
                for bits, vels, _ in rotated:
                    if vel_idx < len(vels):
                        if extract_7bit(bits, offset) == vels[vel_idx]:
                            matches += 1
                if matches >= 5:
                    best_overall.append((sched_name, vel_idx, offset, matches))

    # Sort and print top hits
    best_overall.sort(key=lambda x: -x[3])
    print(f"Top rotation+offset hits (vel_idx, offset, matches):")
    for sched_name, vel_idx, offset, matches in best_overall[:30]:
        print(f"  {sched_name:18s} vel[{vel_idx}] offset={offset:2d}: {matches}/20 matches")

    print()
    print("=" * 72)
    print("SEARCH: shift-register decoder (progressive bit-stream)")
    print("=" * 72)
    # Each event's 56 bits might be read continuously, with a state that advances
    # Try a virtual shift register where reads advance the pointer
    # Read N bits for each field (note, velocity), consume bits

    # Alternative: check if bytes encode VELOCITY + VELOCITY-of-next-strike in different fields
    # Try: 7-bit velocity extraction with OFFSET that depends on strike index within event
    for width in [6, 7]:
        print(f"\n--- Width={width} bits per field, position-dependent offset ---")
        best = []
        for base_offset in range(WIDTH):
            for step in range(1, 15):
                matches = 0
                total = 0
                for idx, bits, vels, _ in samples:
                    for k in range(len(vels)):
                        off = (base_offset + k * step) % (WIDTH - width + 1)
                        val = (bits >> (WIDTH - off - width)) & ((1 << width) - 1)
                        total += 1
                        if val == vels[k]:
                            matches += 1
                if matches >= 20 and total > 0:
                    best.append((base_offset, step, matches, total))
        best.sort(key=lambda x: -x[2])
        for base, step, m, t in best[:10]:
            print(f"  base={base:2d} step={step:2d}: {m}/{t} vel matches")


if __name__ == "__main__":
    main()
