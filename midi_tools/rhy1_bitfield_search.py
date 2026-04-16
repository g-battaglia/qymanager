#!/usr/bin/env python3
"""
Brute-force search for bit-field positions in RHY1 events that encode velocities.

Convert each 7-byte event to a 56-bit integer. For each pair of bit-offsets
(a, b, c) with 7-bit width, check if the tuple of extracted values matches
the ground-truth velocities across ALL events consistently.

If a fixed (offset, mask, transform) scheme works for all 20 events, that's
the encoding.
"""

import json
from collections import defaultdict

WIDTH = 56


def bytes_to_bits(b):
    return int.from_bytes(b, "big")


def extract_7bit(bits, offset):
    """Extract 7 bits starting at bit position 'offset' (0 = MSB)."""
    if offset + 7 > WIDTH:
        return None
    return (bits >> (WIDTH - offset - 7)) & 0x7F


def extract_field(bits, offset, width):
    """Extract 'width' bits starting at 'offset' from MSB."""
    if offset + width > WIDTH:
        return None
    return (bits >> (WIDTH - offset - width)) & ((1 << width) - 1)


def main():
    with open("midi_tools/captured/summer_ground_truth_full.json") as f:
        gt = json.load(f)
    events = gt["tracks"]["RHY1"]["events"]

    # Build event list: (bits, [velocities]) pairs sorted by (sub, note)
    samples = []
    for e in events:
        bits = bytes_to_bits(bytes(e["event_decimal"]))
        vels = [s["velocity"]
                for s in sorted(e["expected_strikes"],
                                key=lambda x: (x["subdivision_8th"], x["note"]))]
        samples.append((bits, vels, e))

    # Hypothesis 1: search for a single offset where 7 bits = first velocity
    # (assuming most events have >=1 strike)
    print("=" * 72)
    print("SEARCH 1: offset where 7-bit field = strike-0 velocity")
    print("=" * 72)
    results = []
    for offset in range(WIDTH - 6):
        matches = 0
        for bits, vels, _ in samples:
            if extract_7bit(bits, offset) == vels[0]:
                matches += 1
        if matches >= 5:
            results.append((offset, matches))
    for offset, m in sorted(results, key=lambda x: -x[1])[:20]:
        print(f"  offset={offset:2d}: {m}/{len(samples)} matches for vel[0]")

    print()
    print("=" * 72)
    print("SEARCH 2: offset where 7-bit field = strike-1 velocity (if strike 1 exists)")
    print("=" * 72)
    samples_2 = [(b, v, e) for b, v, e in samples if len(v) >= 2]
    results = []
    for offset in range(WIDTH - 6):
        matches = 0
        for bits, vels, _ in samples_2:
            if extract_7bit(bits, offset) == vels[1]:
                matches += 1
        if matches >= 5:
            results.append((offset, matches))
    for offset, m in sorted(results, key=lambda x: -x[1])[:20]:
        print(f"  offset={offset:2d}: {m}/{len(samples_2)} matches for vel[1]")

    print()
    print("=" * 72)
    print("SEARCH 3: offset where 7-bit field = strike-2 velocity")
    print("=" * 72)
    samples_3 = [(b, v, e) for b, v, e in samples if len(v) >= 3]
    results = []
    for offset in range(WIDTH - 6):
        matches = 0
        for bits, vels, _ in samples_3:
            if extract_7bit(bits, offset) == vels[2]:
                matches += 1
        if matches >= 5:
            results.append((offset, matches))
    for offset, m in sorted(results, key=lambda x: -x[1])[:20]:
        print(f"  offset={offset:2d}: {m}/{len(samples_3)} matches for vel[2]")

    print()
    print("=" * 72)
    print("SEARCH 4: velocity may be stored shifted/masked — try XOR relations")
    print("=" * 72)
    # For each offset, check if (extracted ^ constant) == velocity for a fixed constant
    best = []
    for offset in range(WIDTH - 6):
        for constant in range(128):
            matches_0 = 0
            matches_1 = 0
            matches_2 = 0
            for bits, vels, _ in samples:
                val = extract_7bit(bits, offset) ^ constant
                if val == vels[0]:
                    matches_0 += 1
                if len(vels) >= 2 and val == vels[1]:
                    matches_1 += 1
                if len(vels) >= 3 and val == vels[2]:
                    matches_2 += 1
            for idx, m in enumerate([matches_0, matches_1, matches_2]):
                if m >= 15:
                    best.append((idx, offset, constant, m))
    for idx, offset, constant, m in sorted(best, key=lambda x: -x[3])[:20]:
        print(f"  vel[{idx}] = (bits[{offset}:+7] ^ 0x{constant:02x}): {m}/{len(samples)} matches")

    print()
    print("=" * 72)
    print("SEARCH 5: try extracting non-7-bit fields with offset/width combinations")
    print("=" * 72)
    # Search (offset, width) pairs for any field that correlates with vel[0]
    vel_0s = [v[0] for _, v, _ in samples]
    best = []
    for width in [6, 7, 8]:
        for offset in range(WIDTH - width + 1):
            values = [extract_field(b, offset, width) for b, _, _ in samples]
            # Check if values are bijection with vel_0s
            if len(set(values)) >= 8:  # high diversity
                # Check linear relation: vel = a*val + b
                pass
            # Exact match count
            exact = sum(1 for v, vv in zip(values, vel_0s) if v == vv)
            if exact >= 10:
                best.append((offset, width, exact))
    for offset, width, m in sorted(best, key=lambda x: -x[2])[:10]:
        print(f"  width={width} offset={offset:2d}: {m}/{len(samples)} exact matches to vel[0]")


if __name__ == "__main__":
    main()
