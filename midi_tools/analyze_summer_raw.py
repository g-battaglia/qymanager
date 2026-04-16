#!/usr/bin/env python3
"""
Raw structural analysis of Summer RHY1 bitstream.

Examine the actual bytes: delimiters, segment sizes, event positions,
and try to understand why bars 2/5 fail with the lane model.
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qymanager.formats.qy70.sysex_parser import SysExParser
from midi_tools.event_decoder import rot_right, extract_9bit, nn


def load_syx_track(syx_path, section=0, track=0):
    parser = SysExParser()
    messages = parser.parse_file(syx_path)
    al = section * 8 + track
    data = b""
    for m in messages:
        if m.is_style_data and m.address_low == al:
            if m.decoded_data is not None:
                data += m.decoded_data
    return data


def decode_at_r(evt_bytes, r_val):
    val = int.from_bytes(evt_bytes, "big")
    derot = rot_right(val, r_val)
    f0 = extract_9bit(derot, 0)
    note = f0 & 0x7F
    bit8 = (f0 >> 8) & 1
    bit7 = (f0 >> 7) & 1
    rem = derot & 0x3
    vel_code = (bit8 << 3) | (bit7 << 2) | rem
    velocity = max(1, 127 - vel_code * 8)
    f1 = extract_9bit(derot, 1)
    f2 = extract_9bit(derot, 2)
    beat = f1 >> 7
    clock = ((f1 & 0x7F) << 2) | (f2 >> 7)
    tick = beat * 480 + clock
    f5 = extract_9bit(derot, 5)
    return {"note": note, "velocity": velocity, "tick": tick, "gate": f5,
            "f0": f0, "f1": f1, "f2": f2, "vel_code": vel_code, "derot": derot}


def main():
    syx_path = "data/qy70_sysx/P -  Summer - 20231101.syx"
    data = load_syx_track(syx_path, section=0, track=0)

    print(f"Track data: {len(data)} bytes")
    print(f"First 28 bytes (metadata+preamble): {data[:28].hex()}")
    print(f"Preamble (bytes 24-27): {data[24:28].hex()}")

    # Raw hex dump with delimiter marking
    event_data = data[28:]
    print(f"\nEvent data ({len(event_data)} bytes):")

    # Find all delimiters
    delimiters = []
    for i, b in enumerate(event_data):
        if b in (0xDC, 0x9E):
            delimiters.append((i, "DC" if b == 0xDC else "9E"))

    print(f"Delimiters: {delimiters}")

    # Split by delimiters and show each segment
    prev = 0
    segments = []
    for pos, dtype in delimiters:
        segments.append(event_data[prev:pos])
        prev = pos + 1
    segments.append(event_data[prev:])

    print(f"\n{'='*80}")
    print(f"SEGMENT STRUCTURE")
    print(f"{'='*80}")

    for seg_idx, seg in enumerate(segments):
        if len(seg) < 13:
            print(f"\nSeg {seg_idx}: {len(seg)} bytes (too short for header)")
            if seg:
                print(f"  raw: {seg.hex()}")
            continue

        header = seg[:13]
        event_bytes = seg[13:]
        n_full_events = len(event_bytes) // 7
        trailing = len(event_bytes) % 7

        print(f"\nSeg {seg_idx}: {len(seg)} bytes = 13B header + {len(event_bytes)}B events")
        print(f"  Header: {header.hex()}")
        print(f"  Events: {n_full_events} × 7B + {trailing}B trailing")

        # Show each event
        events = []
        for i in range(n_full_events):
            evt = event_bytes[i*7:(i+1)*7]
            events.append(evt)
            print(f"  e{i}: {evt.hex()}", end="")

            # Check what this looks like at common R values
            best = None
            for r in [9, 12, 22, 53, 18, 27, 36, 45]:
                d = decode_at_r(evt, r)
                if d["note"] in {36, 38, 42}:
                    if best is None:
                        best = (r, d)
            if best:
                r, d = best
                print(f"  → R={r:2d}: {nn(d['note'])} vel={d['velocity']}", end="")
            print()

        # Show trailing bytes
        if trailing > 0:
            trail = event_bytes[n_full_events * 7:]
            print(f"  trailing: {trail.hex()}")

    # Cross-event byte similarity analysis
    print(f"\n{'='*80}")
    print(f"CROSS-BAR EVENT SIMILARITY")
    print(f"{'='*80}")

    # Collect all events by position within bar
    events_by_pos = {}  # pos -> [(bar_idx, raw_bytes)]
    for seg_idx, seg in enumerate(segments):
        if len(seg) < 20:
            continue
        event_bytes = seg[13:]
        for i in range(len(event_bytes) // 7):
            evt = event_bytes[i*7:(i+1)*7]
            events_by_pos.setdefault(i, []).append((seg_idx, evt))

    for pos in sorted(events_by_pos.keys()):
        if pos > 4:
            break
        entries = events_by_pos[pos]
        print(f"\n  Position e{pos}:")
        for bar_idx, evt in entries:
            # XOR with first entry
            if bar_idx == entries[0][0]:
                xor_str = "---"
            else:
                xor = bytes(a ^ b for a, b in zip(evt, entries[0][1]))
                diff_bits = sum(bin(x).count("1") for x in xor)
                xor_str = f"{diff_bits:2d} bits"
            print(f"    bar{bar_idx}: {evt.hex()}  ΔΔ={xor_str}")

    # KEY INSIGHT: Look at whether bars 2 and 5 events are PERMUTATIONS
    # of other bars' events
    print(f"\n{'='*80}")
    print(f"PERMUTATION CHECK: Are bar 2/5 events rearranged from other bars?")
    print(f"{'='*80}")

    # Collect events per bar
    bar_events = {}
    for seg_idx, seg in enumerate(segments):
        if len(seg) < 20:
            continue
        event_bytes = seg[13:]
        bar_events[seg_idx] = [event_bytes[i*7:(i+1)*7]
                                for i in range(min(4, len(event_bytes) // 7))]

    # For bar 2, check similarity of each event to all events in other bars
    for check_bar in [2, 5]:
        if check_bar not in bar_events:
            continue
        print(f"\n  Bar {check_bar} events vs all other bars:")
        for ei, evt in enumerate(bar_events[check_bar]):
            print(f"    e{ei} ({evt.hex()}):")
            for other_bar in sorted(bar_events.keys()):
                if other_bar == check_bar:
                    continue
                for oi, other_evt in enumerate(bar_events[other_bar]):
                    xor = bytes(a ^ b for a, b in zip(evt, other_evt))
                    diff_bits = sum(bin(x).count("1") for x in xor)
                    if diff_bits <= 10:
                        print(f"      ≈ bar{other_bar}/e{oi} ({other_evt.hex()}) "
                              f"Δ={diff_bits} bits")

    # BRUTE FORCE: For each bar, find THE BEST 4-event assignment
    # Try all permutations of R values for 4 events to maximize note matches
    print(f"\n{'='*80}")
    print(f"EXHAUSTIVE R SEARCH PER BAR — Best 4-R combination")
    print(f"{'='*80}")

    target = {36, 38, 42}
    for bar_idx in sorted(bar_events.keys()):
        evts = bar_events[bar_idx]
        if len(evts) < 4:
            continue
        print(f"\n  Bar {bar_idx}:")

        # For each event, find all R that give target notes
        valid_r_per_event = []
        for ei, evt in enumerate(evts[:4]):
            valid = []
            for r in range(56):
                d = decode_at_r(evt, r)
                if d["note"] in target:
                    valid.append((r, d["note"], d["velocity"], d["tick"], d["gate"]))
            valid_r_per_event.append(valid)

        # Find best combination: 4 events → 4 R values, with
        # constraint that we want all 3 instruments (36, 38, 42) covered
        # and the 4th can be duplicate (HH2)
        best_combos = []
        for r0, n0, v0, t0, g0 in valid_r_per_event[0]:
            for r1, n1, v1, t1, g1 in valid_r_per_event[1]:
                for r2, n2, v2, t2, g2 in valid_r_per_event[2]:
                    for r3, n3, v3, t3, g3 in valid_r_per_event[3]:
                        notes = {n0, n1, n2, n3}
                        if target.issubset(notes):
                            score = 4
                        else:
                            score = len(notes & target)
                        if score >= 3:
                            best_combos.append((
                                score, [r0,r1,r2,r3], [n0,n1,n2,n3],
                                [v0,v1,v2,v3], [t0,t1,t2,t3], [g0,g1,g2,g3]
                            ))

        if best_combos:
            best_combos.sort(key=lambda x: (-x[0], sum(x[1])))
            print(f"    Top 5 combos (of {len(best_combos)}):")
            for score, rs, notes, vels, ticks, gates in best_combos[:5]:
                print(f"    R={rs} notes={notes} vel={vels} tick={ticks} "
                      f"gate={gates} score={score}")
        else:
            print(f"    No combo covers all 3 instruments!")
            # Show what's available per event
            for ei, valid in enumerate(valid_r_per_event):
                if valid:
                    notes = sorted(set(n for _, n, _, _, _ in valid))
                    print(f"      e{ei}: notes={notes} ({len(valid)} R values)")
                else:
                    print(f"      e{ei}: NO target note at any R!")

    print("\nDone.")


if __name__ == "__main__":
    main()
