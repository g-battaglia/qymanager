#!/usr/bin/env python3
"""
Extend 7-var decode to ALL beats.

For each beat (1,2,3,4), find the variable bits split:
  - How many bits = bar_ID (unique per MAIN bar)
  - Remaining bits = vel/timing
"""

import json
import sys
from itertools import combinations
from pathlib import Path

GT = Path(__file__).parent / "captured" / "summer_ground_truth.json"


def compute_mask(events_bytes):
    mask = 0
    for bit in range(56):
        vals = {(int.from_bytes(b, "big") >> bit) & 1 for b in events_bytes}
        if len(vals) == 1:
            mask |= (1 << bit)
    return mask


def get_var_positions(mask, width=56):
    return [p for p in range(width) if not (mask >> p) & 1]


def extract_bits_at(val: int, positions: list[int]) -> list[int]:
    return [(val >> p) & 1 for p in positions]


def find_bar_id_bits(bar_to_bits: dict) -> list:
    """Find minimum subset of bits that uniquely identifies all bars."""
    n_bits = len(next(iter(bar_to_bits.values())))
    bars = list(bar_to_bits.keys())
    n_bars = len(bars)

    # Try subsets from size log2(n_bars) upward
    from math import ceil, log2
    min_size = max(1, ceil(log2(n_bars)))

    for size in range(min_size, n_bits + 1):
        for subset in combinations(range(n_bits), size):
            codes = {b: tuple(bar_to_bits[b][i] for i in subset) for b in bars}
            if len(set(codes.values())) == n_bars:
                return {"subset": list(subset), "size": size, "codes": codes}
    return None


def main():
    gt = json.loads(GT.read_text())
    events = gt["events"]

    print(f"═══ Per-beat variable bit analysis ═══\n")

    for beat in (1, 2, 3, 4):
        beat_events = [e for e in events if e["beat"] == beat and e["bar"] != 3]
        if len(beat_events) < 2:
            continue
        bytes_list = [bytes(e["event_decimal"]) for e in beat_events]
        mask = compute_mask(bytes_list)
        n_var = 56 - bin(mask).count("1")
        var_pos = get_var_positions(mask)

        print(f"─── Beat {beat}: {len(beat_events)} events, {n_var} variable bits ───")

        # Extract bits per event
        bar_to_bits = {}
        bar_to_vels = {}
        for e in beat_events:
            val = int.from_bytes(bytes(e["event_decimal"]), "big")
            bar_to_bits[e["bar"]] = extract_bits_at(val, var_pos)
            bar_to_vels[e["bar"]] = [s["velocity"] for s in e["expected_strikes"]]

        for bar in sorted(bar_to_bits.keys()):
            bits_str = "".join(str(b) for b in bar_to_bits[bar])
            print(f"  bar{bar}: bits={bits_str}  vels={bar_to_vels[bar]}")

        # Find min bar-ID subset
        result = find_bar_id_bits(bar_to_bits)
        if result:
            print(f"  Min bar-ID subset ({result['size']} bits at var positions {result['subset']}):")
            for bar, code in result["codes"].items():
                code_val = sum(b * (2**(len(code)-1-i)) for i, b in enumerate(code))
                print(f"    bar{bar} → {''.join(str(c) for c in code)} ({code_val})")
            remaining = n_var - result["size"]
            print(f"  Remaining {remaining} bits → vel/micro-timing")

            # For each bar, identify remaining bits
            non_id = [i for i in range(n_var) if i not in result["subset"]]
            for bar in sorted(bar_to_bits.keys()):
                remaining_bits = "".join(str(bar_to_bits[bar][i]) for i in non_id)
                print(f"    bar{bar} remaining={remaining_bits}  vels={bar_to_vels[bar]}")
        print()


if __name__ == "__main__":
    main()
