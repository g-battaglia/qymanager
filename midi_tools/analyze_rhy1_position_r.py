#!/usr/bin/env python3
"""Test position-dependent R model for RHY1 drum events.

Cross-bar consistency analysis found:
  e0: R=9  → HH42 (4/4 bars)
  e1: R=22 → Snare38 (3/4 bars)
  e2: R=12 → HH42 (4/4 bars)
  e3: various R → Kick36 (3/4 bars)

This script tests all R combinations for e0-e3 to find optimal values,
then decodes with those R values and checks timing coherence.
"""
import sys
import os
from itertools import product

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qymanager.formats.qy70.sysex_parser import SysExParser
from midi_tools.event_decoder import rot_right, extract_9bit

GM_DRUMS = {
    35: 'Kick2', 36: 'Kick1', 37: 'SStick', 38: 'Snare1', 39: 'Clap',
    40: 'ElSnare', 41: 'LFlrTom', 42: 'HHclose', 43: 'HFlrTom',
    44: 'HHpedal', 45: 'LowTom', 46: 'HHopen', 47: 'LMidTom',
    48: 'HiMidTom', 49: 'Crash1', 50: 'HiTom', 51: 'Ride1',
}
EXPECTED = {36, 38, 42}


def get_track(syx_path, al_target):
    parser = SysExParser()
    messages = parser.parse_file(syx_path)
    data = b''
    for m in messages:
        if m.is_style_data and m.decoded_data and m.address_low == al_target:
            data += m.decoded_data
    return data


def get_segments(data):
    event_data = data[28:]
    delim_pos = [i for i, b in enumerate(event_data) if b in (0xDC, 0x9E)]
    segments = []
    prev = 0
    for dp in delim_pos:
        seg = event_data[prev:dp]
        if len(seg) >= 20:
            header = seg[:13]
            events = []
            for i in range((len(seg) - 13) // 7):
                evt = seg[13 + i*7:13 + (i+1)*7]
                if len(evt) == 7:
                    events.append(evt)
            segments.append((header, events))
        prev = dp + 1
    # Last segment
    seg = event_data[prev:]
    if len(seg) >= 20:
        header = seg[:13]
        events = []
        for i in range((len(seg) - 13) // 7):
            evt = seg[13 + i*7:13 + (i+1)*7]
            if len(evt) == 7:
                events.append(evt)
        segments.append((header, events))
    return segments


def decode_at_r(evt_bytes, r_value):
    """Full decode at given R value."""
    val = int.from_bytes(evt_bytes, "big")
    derot = rot_right(val, r_value)
    fields = [extract_9bit(derot, i) for i in range(6)]
    rem = derot & 0x3
    f0 = fields[0]
    note = f0 & 0x7F
    bit8 = (f0 >> 8) & 1
    bit7 = (f0 >> 7) & 1
    vel_code = (bit8 << 3) | (bit7 << 2) | rem
    velocity = max(1, 127 - vel_code * 8)
    f1 = fields[1]
    beat = f1 >> 7
    clock = ((f1 & 0x7F) << 2) | (fields[2] >> 7)
    tick = beat * 480 + clock
    return {
        "note": note, "velocity": velocity, "tick": tick,
        "gate": fields[5], "fields": fields, "rem": rem,
        "f0": f0, "valid": 13 <= note <= 87
    }


def main():
    data = get_track("midi_tools/captured/user_style_live.syx", 0)
    segments = get_segments(data)
    main_bars = [0, 1, 3, 4]  # bars where e0=HH42 at R=9

    # Collect events per position across main bars
    events_by_pos = {}
    for bi in main_bars:
        if bi >= len(segments):
            continue
        _, events = segments[bi]
        for ei, evt in enumerate(events):
            if ei not in events_by_pos:
                events_by_pos[ei] = []
            events_by_pos[ei].append((bi, evt))

    # For each position, find R that gives expected note in F0 most consistently
    print("=" * 70)
    print("  OPTIMAL R PER POSITION (F0 gives expected note)")
    print("=" * 70)

    best_r_per_pos = {}
    for ei in sorted(events_by_pos):
        events = events_by_pos[ei]
        best_r = -1
        best_score = 0
        best_note = -1

        for r in range(56):
            note_counts = {}
            for bi, evt in events:
                d = decode_at_r(evt, r)
                if d["valid"]:
                    n = d["note"]
                    note_counts[n] = note_counts.get(n, 0) + 1

            # Best = most frequent expected note
            for n in EXPECTED:
                if note_counts.get(n, 0) > best_score:
                    best_score = note_counts[n]
                    best_r = r
                    best_note = n

            # Also check most frequent ANY valid note
        best_r_per_pos[ei] = best_r

        # Also find best for ANY valid note (not just expected)
        any_best_r = -1
        any_best_score = 0
        any_best_note = -1
        for r in range(56):
            note_counts = {}
            for bi, evt in events:
                d = decode_at_r(evt, r)
                if d["valid"]:
                    n = d["note"]
                    note_counts[n] = note_counts.get(n, 0) + 1
            for n, cnt in note_counts.items():
                if cnt > any_best_score:
                    any_best_score = cnt
                    any_best_r = r
                    any_best_note = n

        nname_exp = GM_DRUMS.get(best_note, f"n{best_note}")
        nname_any = GM_DRUMS.get(any_best_note, f"n{any_best_note}")
        print(f"  e{ei}: Best expected R={best_r:2d} → {nname_exp}({best_note}) "
              f"({best_score}/{len(events)} bars)")
        print(f"       Best any     R={any_best_r:2d} → {nname_any}({any_best_note}) "
              f"({any_best_score}/{len(events)} bars)")

    # Now decode all bars with position-specific R
    # Try the found R values AND check if there's a mathematical pattern
    print(f"\n{'='*70}")
    print(f"  DECODE WITH POSITION-SPECIFIC R")
    print(f"{'='*70}")

    # Use: e0=9(HH42), e1=22(Snare38), e2=12(HH42), e3=53(Kick36)
    # But let's find the best from our analysis above
    r_map = {}
    for ei in sorted(best_r_per_pos):
        r_map[ei] = best_r_per_pos[ei]

    print(f"  R map: {r_map}")

    for bi, (header, events) in enumerate(segments):
        print(f"\n  Bar {bi} ({len(events)} events):")
        for ei, evt in enumerate(events):
            r = r_map.get(ei, 9)  # fallback to R=9
            d = decode_at_r(evt, r)
            n = d["note"]
            nname = GM_DRUMS.get(n, f"n{n}")
            valid = "OK" if d["valid"] else "BAD"
            exp = "***" if n in EXPECTED else "   "
            print(f"    e{ei}: R={r:2d} → {nname:>10s} n={n:3d} v={d['velocity']:3d} "
                  f"t={d['tick']:4d} g={d['gate']:3d} [{valid}] {exp}")

    # Look for mathematical pattern in R values
    print(f"\n{'='*70}")
    print(f"  R VALUE PATTERN ANALYSIS")
    print(f"{'='*70}")

    # Check: is R related to event position, note number, or both?
    # R values found: e0→9, e1→22, e2→12, e3→53(?)
    print(f"  Position 0: R={r_map.get(0, '?')}")
    print(f"  Position 1: R={r_map.get(1, '?')}")
    print(f"  Position 2: R={r_map.get(2, '?')}")
    print(f"  Position 3: R={r_map.get(3, '?')}")

    # Check various formulas
    for ei in range(min(4, len(r_map))):
        r = r_map.get(ei, 0)
        print(f"\n  R[{ei}]={r}:")
        print(f"    R mod 9 = {r % 9}")
        print(f"    R // 9 = {r // 9}")
        print(f"    R - 9*ei = {r - 9*ei}")
        print(f"    R - 9*(ei+1) = {r - 9*(ei+1)}")

    # Check if R_i = (something * i + offset) mod 56
    # Try all linear formulas R = a*i + b mod 56
    print(f"\n  LINEAR FORMULA SEARCH: R = a*i + b mod 56")
    target_rs = [r_map.get(i, -1) for i in range(min(4, len(r_map)))]
    if -1 not in target_rs:
        for a in range(56):
            for b in range(56):
                matches = all((a * i + b) % 56 == target_rs[i] for i in range(len(target_rs)))
                if matches:
                    formula = f"R = ({a}*i + {b}) mod 56"
                    # Verify
                    rs = [(a * i + b) % 56 for i in range(len(target_rs))]
                    print(f"    {formula} → {rs}")


if __name__ == "__main__":
    main()
