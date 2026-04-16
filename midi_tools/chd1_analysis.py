#!/usr/bin/env python3
"""
Analyze CHD1 (simplest case): always plays note 31 twice per beat.

CHD1 is a bass voice playing a single low note. Ground truth:
40 MIDI notes over 5 bars = 8 notes/bar = 2 notes/beat.
All notes are N31 (G1) with velocities 86-107.

Question: where is note 31 encoded in the 7-byte events? And what
distinguishes the varying velocities?
"""

import json


WIDTH = 56


def bytes_to_bits(b):
    return int.from_bytes(b, "big")


def main():
    with open("midi_tools/captured/summer_ground_truth_full.json") as f:
        gt = json.load(f)
    events = gt["tracks"]["CHD1"]["events"]

    print(f"CHD1: {len(events)} events")
    print()

    # Show all events with expected strikes (for segmented tracks)
    for e in events:
        if "expected_strikes" not in e:
            continue
        b = e["event_decimal"]
        strikes = sorted(e["expected_strikes"],
                         key=lambda x: (x["subdivision_8th"], x["note"]))
        notes = set(s["note"] for s in strikes)
        vels = [s["velocity"] for s in strikes]
        subs = [s["subdivision_8th"] for s in strikes]

        bits = bytes_to_bits(bytes(b))
        # Scan for note 31 (7-bit: 0011111 = 0x1F)
        found_31 = []
        for off in range(WIDTH - 6):
            if ((bits >> (WIDTH - off - 7)) & 0x7F) == 31:
                found_31.append(off)

        print(f"  bar{e['bar']} beat{e['beat']} | {e['event_hex']} | "
              f"notes={notes} vels={vels} subs={subs} | note31 at offsets={found_31}")


if __name__ == "__main__":
    main()
