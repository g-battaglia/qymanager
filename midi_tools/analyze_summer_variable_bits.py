#!/usr/bin/env python3
"""
Isolate the 7 variable bits in Summer beat-3 events and correlate with
captured strike data (velocities, timing).

Goal: identify what those 7 bits encode.
  Hypotheses:
    A) Bar index (3 bits = 8 bars) + velocity hints (4 bits)
    B) Pure micro-velocity humanization (7 bits = 3 strikes × 2-3 bits each)
    C) Tick offset for micro-timing
"""

import json
from pathlib import Path
from collections import defaultdict

GT_PATH = Path(__file__).parent / "captured" / "summer_ground_truth.json"


def load():
    return json.loads(GT_PATH.read_text())


def get_variable_bits(event_bytes: bytes, invariant_mask: int, width: int = 56) -> int:
    """Extract only the variable bits of the event."""
    val = int.from_bytes(event_bytes, "big")
    full_mask = (1 << width) - 1
    var_mask = full_mask & ~invariant_mask
    # Compact variable bits by extracting them positionally
    result = 0
    out_pos = 0
    for bit_pos in range(width):
        if (var_mask >> bit_pos) & 1:
            if (val >> bit_pos) & 1:
                result |= (1 << out_pos)
            out_pos += 1
    return result, out_pos


def analyze():
    data = load()
    events = data["events"]
    by_beat = defaultdict(list)
    for e in events:
        by_beat[e["beat"]].append(e)

    # For each beat, compute the invariant mask across MAIN bars
    for beat in sorted(by_beat.keys()):
        evs = by_beat[beat]
        main_evs = [e for e in evs if e["bar"] != 3]
        if len(main_evs) < 2:
            continue
        # Invariant mask
        vals = [int.from_bytes(bytes(e["event_decimal"]), "big") for e in main_evs]
        mask = 0
        for bit in range(56):
            if len({(v >> bit) & 1 for v in vals}) == 1:
                mask |= (1 << bit)
        n_var = 56 - bin(mask).count("1")
        print(f"\n═══ Beat {beat} ({len(main_evs)} MAIN events) — {n_var} variable bits ═══")
        print(f"   Invariant mask: 0x{mask:014x}")

        # Extract variable bits per event
        for e in main_evs + [next((x for x in evs if x["bar"] == 3), None)]:
            if e is None:
                continue
            evt_bytes = bytes(e["event_decimal"])
            var_val, n_bits = get_variable_bits(evt_bytes, mask)
            strikes = e["expected_strikes"]
            st_summary = ", ".join(f"n{s['note']}v{s['velocity']}@{s['subdivision_8th']}" for s in strikes)
            bar_tag = "FILL" if e["bar"] == 3 else f"bar{e['bar']}"
            print(f"   {bar_tag:5s} bytes={evt_bytes.hex()} "
                  f"var={var_val:0{n_bits}b} ({var_val:4d})  strikes=[{st_summary}]")

        # Velocity correlation test
        if n_var <= 8:
            print(f"   Velocity correlation:")
            for e in main_evs:
                evt_bytes = bytes(e["event_decimal"])
                var_val, _ = get_variable_bits(evt_bytes, mask)
                strikes = e["expected_strikes"]
                vels = [s["velocity"] for s in strikes]
                # Maybe var_val encodes (v1_offset, v2_offset, v3_offset) where each is 2-3 bits
                print(f"      bar{e['bar']}: var={var_val:07b} vels={vels}")


if __name__ == "__main__":
    analyze()
