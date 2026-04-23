#!/usr/bin/env python3
"""
Decode Summer beat 3 7 variable bits.

Summer beat 3 events have 7 bits variable across MAIN bars 1,2,4,5.
Each event has 3 strikes (H+K+H at subs 0,1,1).

Hypothesis: 7 bits = 3 strike vel offsets + 1 overhead bit.
  - Each strike vel offset: 2 bits → 4 values × 8 = ±32 range
  - Or 3 strikes × 2 bits = 6 bits + 1 parity

Test: correlate 7 bits with captured velocities, find mapping.
"""

import json
import sys
from pathlib import Path
from itertools import permutations

GT = Path(__file__).parent / "captured" / "summer_ground_truth.json"


def get_var_bits(event_bytes: bytes, mask: int, width: int = 56) -> list[int]:
    """Return variable bits as list [bit0, bit1, ...] at positions where mask==0."""
    val = int.from_bytes(event_bytes, "big")
    bits = []
    for pos in range(width):
        if not (mask >> pos) & 1:
            bits.append((val >> pos) & 1)
    return bits


def compute_invariant_mask(events_bytes: list[bytes], width: int = 56) -> int:
    """Compute mask where bits are constant across all events."""
    mask = 0
    for bit in range(width):
        vals = {(int.from_bytes(b, "big") >> bit) & 1 for b in events_bytes}
        if len(vals) == 1:
            mask |= (1 << bit)
    return mask


def main():
    gt = json.loads(GT.read_text())
    events = gt["events"]

    # Get beat 3 events from MAIN bars (1, 2, 4, 5) — exclude bar 3 FILL
    beat3_main = [e for e in events if e["beat"] == 3 and e["bar"] != 3]
    print(f"Summer beat 3 MAIN events: {len(beat3_main)}")

    bytes_list = [bytes(e["event_decimal"]) for e in beat3_main]
    mask = compute_invariant_mask(bytes_list)
    n_inv = bin(mask).count("1")
    print(f"Invariant mask: 0x{mask:014x} ({n_inv}/56 bits)")
    print(f"Variable bits: {56 - n_inv}")

    # Extract var bits per event
    var_bits_per_event = []
    for e in beat3_main:
        vb = get_var_bits(bytes(e["event_decimal"]), mask)
        vels = [s["velocity"] for s in e["expected_strikes"]]
        var_bits_per_event.append({
            "bar": e["bar"],
            "var_bits": vb,
            "vels": vels,
            "var_bits_str": "".join(str(b) for b in vb),
        })

    print(f"\n═══ Per-event variable bits ═══")
    for entry in var_bits_per_event:
        print(f"  bar{entry['bar']}: var={entry['var_bits_str']}  vels={entry['vels']}")

    # Test hypothesis: 7 bits split into [2bit, 2bit, 2bit, 1bit]
    # Correlate with vel offsets
    print(f"\n═══ Test hypothesis: 7 bits = 3×2bit vel_offset + 1bit ═══")
    # Sort bits position - try different bit orderings
    # Strike 1 vel = vels[0], strike 2 = vels[1], strike 3 = vels[2]

    # For each possible bit-to-strike mapping, find best correlation
    # 7 bits → 7! permutations = 5040, too many
    # Better: assume bits are sequential (in order) and test split points

    all_vels = []
    for entry in var_bits_per_event:
        for vi, v in enumerate(entry["vels"]):
            all_vels.append((entry["bar"], vi, v, entry["var_bits"]))

    # Test: is there correlation between specific bit subsets and specific vel?
    # For each strike index (0, 1, 2), find 2-bit subset that predicts vel
    for strike_idx in range(3):
        print(f"\n  Strike {strike_idx} vels: {[v for _, si, v, _ in all_vels if si == strike_idx]}")

        # For each 2-bit window in the 7 bits, compute vel distribution
        bar_vels = {e["bar"]: e["vels"][strike_idx] for e in var_bits_per_event}
        bar_bits = {e["bar"]: e["var_bits"] for e in var_bits_per_event}

        # Test each pair of bit positions
        best = []
        for i in range(7):
            for j in range(i + 1, 7):
                # 2-bit value = bit_i * 2 + bit_j
                bar_to_code = {}
                for bar, bits in bar_bits.items():
                    code = bits[i] * 2 + bits[j]
                    bar_to_code[bar] = code
                # Check if code predicts vel
                code_to_vels = {}
                for bar, code in bar_to_code.items():
                    code_to_vels.setdefault(code, []).append(bar_vels[bar])
                # Variance
                unique_codes = len(code_to_vels)
                mean_vels = {c: sum(vs) / len(vs) for c, vs in code_to_vels.items()}
                # Print if codes differ between bars
                if unique_codes > 1 and len(set(bar_to_code.values())) == len(bar_to_code):
                    best.append((unique_codes, i, j, dict(bar_to_code), mean_vels))

        best.sort(reverse=True)
        for uc, i, j, codes, means in best[:3]:
            print(f"    Bits ({i},{j}): {uc} unique codes  bars→codes={codes}  means={means}")


if __name__ == "__main__":
    main()
