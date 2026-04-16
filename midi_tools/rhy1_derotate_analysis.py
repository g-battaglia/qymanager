#!/usr/bin/env python3
"""
Apply barrel de-rotation to RHY1 events and look for decoded structure.

Hypothesis: the 7 raw bytes per event are obtained from a canonical event
representation after rotating left by R bits, where R varies with event
position. After undoing the rotation, canonical bytes should have
recognizable fields (note, velocity, timing).

Try multiple rotation schedules:
    R = 9 * (i + 1)           (original hypothesis)
    R = 9 * i
    R = 46 * (i + 1)
    R = 7 * (i + 1)
    R = cumulative per-bar
"""

import json
from collections import defaultdict

WIDTH = 56


def rot_left(val, shift, width=WIDTH):
    shift = shift % width
    return ((val << shift) | (val >> (width - shift))) & ((1 << width) - 1)


def rot_right(val, shift, width=WIDTH):
    return rot_left(val, width - shift, width)


def bytes_to_int(b):
    return int.from_bytes(b, "big")


def int_to_bytes(v, n=7):
    return v.to_bytes(n, "big")


def strikes_summary(strikes):
    drum = {36: "K", 38: "S", 42: "H"}
    parts = []
    for s in sorted(strikes, key=lambda x: (x["subdivision_8th"], x["note"])):
        parts.append(f"{drum.get(s['note'], '?')}{s['subdivision_8th']}")
    return "+".join(parts)


def main():
    with open("midi_tools/captured/summer_ground_truth_full.json") as f:
        gt = json.load(f)
    events = gt["tracks"]["RHY1"]["events"]

    # Index each event by its global position within the track
    # (bar-1)*4 + (beat-1) for bar in 1..5
    def ev_idx(e):
        return (e["bar"] - 1) * 4 + (e["beat"] - 1)

    events = sorted(events, key=ev_idx)

    # Schedules to try
    schedules = {
        "R=9*(i+1)": lambda i: 9 * (i + 1),
        "R=9*i": lambda i: 9 * i,
        "R=46*(i+1)": lambda i: 46 * (i + 1),
        "R=7*(i+1)": lambda i: 7 * (i + 1),
        "R=18*(i+1)": lambda i: 18 * (i + 1),
        "R=0 (no rot)": lambda i: 0,
        "R=8*(i+1)": lambda i: 8 * (i + 1),
        "R=-9*i": lambda i: -9 * i,
    }

    print("=" * 72)
    print("ROTATION SCAN — check if de-rotated events group by signature")
    print("=" * 72)

    for name, schedule in schedules.items():
        print(f"\n--- Schedule {name} ---")
        derot_events = []
        for i, e in enumerate(events):
            R = schedule(i)
            raw = bytes_to_int(bytes(e["event_decimal"]))
            derot = rot_right(raw, R)
            derot_bytes = int_to_bytes(derot)
            derot_events.append((i, e, derot_bytes))

        # Group by signature and show how consistent byte 0 is
        by_sig = defaultdict(list)
        for i, e, db in derot_events:
            sig = strikes_summary(e["expected_strikes"])
            by_sig[sig].append((i, e, db))

        # Compute intra-group variance for each byte position
        scores = []
        for sig, group in by_sig.items():
            if len(group) < 2:
                continue
            for byte_pos in range(7):
                vals = set(db[byte_pos] for _, _, db in group)
                scores.append((sig, byte_pos, len(vals), len(group)))

        # For each group, print byte 0 of de-rotated events
        for sig, group in sorted(by_sig.items(), key=lambda x: -len(x[1])):
            if len(group) < 2:
                continue
            b0_vals = [db[0] for _, _, db in group]
            b0_str = " ".join(f"{v:02x}" for v in b0_vals)
            unique = len(set(b0_vals))
            print(f"  {sig:15s} ({len(group)} events): b0=[{b0_str}] unique={unique}/{len(group)}")

    print()
    print("=" * 72)
    print("DETAILED: de-rotation R=9*(i+1) showing all bytes per event group")
    print("=" * 72)

    for sig_filter in ["K0+H0+H1", "H0+K1+H1", "S0+H0+H1"]:
        print(f"\n--- {sig_filter} ---")
        for i, e in enumerate(events):
            if strikes_summary(e["expected_strikes"]) != sig_filter:
                continue
            raw = bytes_to_int(bytes(e["event_decimal"]))
            for R in [0, 9, 18, 27, 36, 45, 54]:
                derot = rot_right(raw, R)
                db = int_to_bytes(derot)
                print(f"  e#{i:2d} bar{e['bar']}b{e['beat']} R={R:2d}: "
                      f"{db.hex()}  original={e['event_hex']}")
            print()


if __name__ == "__main__":
    main()
