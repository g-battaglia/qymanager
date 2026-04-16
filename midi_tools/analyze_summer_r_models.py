#!/usr/bin/env python3
"""
Compare R models on Summer RHY1: cumulative vs fixed-lane vs brute-force.

For each event in each bar, find which R gives the correct note (42/38/36)
from ground truth. Map which model predicts correctly.
"""

import json
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qymanager.formats.qy70.sysex_parser import SysExParser
from midi_tools.event_decoder import rot_right, extract_9bit, extract_bars, nn

GT_INSTRUMENTS = {42: "HHclosed", 38: "Snare1", 36: "Kick1"}

LANE_R = [9, 22, 12, 53]


def load_syx_track(syx_path: str, section: int = 0, track: int = 0) -> bytes:
    parser = SysExParser()
    messages = parser.parse_file(syx_path)
    al = section * 8 + track
    data = b""
    for m in messages:
        if m.is_style_data and m.address_low == al:
            if m.decoded_data is not None:
                data += m.decoded_data
    return data


def decode_at_r(evt_bytes: bytes, r_val: int) -> dict:
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
    f5 = extract_9bit(derot, 5)
    beat = f1 >> 7
    clock = ((f1 & 0x7F) << 2) | (f2 >> 7)
    tick = beat * 480 + clock
    return {"note": note, "velocity": velocity, "tick": tick, "gate": f5,
            "f0": f0, "f1": f1, "f2": f2, "vel_code": vel_code, "derot": derot}


def find_all_valid_r(evt_bytes: bytes, target_notes=None):
    """Find all R values that give valid drum notes."""
    results = []
    for r in range(56):
        d = decode_at_r(evt_bytes, r)
        if target_notes and d["note"] in target_notes:
            results.append((r, d))
        elif not target_notes and 13 <= d["note"] <= 87:
            results.append((r, d))
    return results


def main():
    syx_path = "data/qy70_sysx/P -  Summer - 20231101.syx"
    data = load_syx_track(syx_path, section=0, track=0)
    preamble, bars = extract_bars(data)

    target_notes = {42, 38, 36}  # HH, Snare, Kick

    print("=" * 80)
    print("MODEL COMPARISON: Which R gives correct GM notes for each event?")
    print("Target notes: 42(HH) 38(Snare) 36(Kick)")
    print("=" * 80)

    # For each bar and event, find R values that produce target notes
    all_correct_r = []  # [bar_idx][evt_idx] = [(r, note, vel, tick, gate)]

    for bar_idx, (header, events) in enumerate(bars):
        print(f"\n{'='*60}")
        print(f"Bar {bar_idx} — {len(events)} events, header: {header[:6].hex()}...")
        print(f"{'='*60}")

        bar_correct = []
        for evt_idx, evt in enumerate(events[:8]):  # Limit to first 8
            cum_r = (9 * (evt_idx + 1)) % 56
            lane_r = LANE_R[evt_idx] if evt_idx < 4 else -1

            # Find all R giving target notes
            target_matches = find_all_valid_r(evt, target_notes)
            # Also find all valid R (any drum note)
            all_valid = find_all_valid_r(evt)

            # Check cumulative and lane models
            cum_d = decode_at_r(evt, cum_r)
            lane_d = decode_at_r(evt, lane_r) if lane_r >= 0 else None

            cum_ok = cum_d["note"] in target_notes
            lane_ok = lane_d["note"] in target_notes if lane_d else False

            # Report
            print(f"\n  e{evt_idx} raw={evt.hex()}")
            print(f"    Cumul R={cum_r:2d}: note={cum_d['note']:3d} ({nn(cum_d['note']):>4s}) "
                  f"vel={cum_d['velocity']:3d} tick={cum_d['tick']:4d} "
                  f"{'✓' if cum_ok else '✗'}")
            if lane_d:
                print(f"    Lane  R={lane_r:2d}: note={lane_d['note']:3d} ({nn(lane_d['note']):>4s}) "
                      f"vel={lane_d['velocity']:3d} tick={lane_d['tick']:4d} "
                      f"{'✓' if lane_ok else '✗'}")

            if target_matches:
                print(f"    Correct R values for target notes:")
                for r, d in target_matches:
                    markers = []
                    if r == cum_r:
                        markers.append("CUM")
                    if r == lane_r:
                        markers.append("LANE")
                    marker = f" ← {','.join(markers)}" if markers else ""
                    print(f"      R={r:2d}: note={d['note']:3d} ({nn(d['note']):>4s}) "
                          f"vel={d['velocity']:3d} tick={d['tick']:4d} gate={d['gate']:3d}{marker}")
            else:
                print(f"    NO R gives target notes! Valid R gives:")
                for r, d in all_valid[:5]:
                    print(f"      R={r:2d}: note={d['note']:3d} ({nn(d['note']):>4s})")

            bar_correct.append(target_matches)
        all_correct_r.append(bar_correct)

    # Summary: what R pattern works per bar?
    print("\n" + "=" * 80)
    print("SUMMARY: Correct R values per bar per event")
    print("=" * 80)

    for bar_idx, bar_correct in enumerate(all_correct_r):
        _, events = bars[bar_idx]
        n_evt = min(len(events), 8)
        print(f"\n  Bar {bar_idx} ({n_evt} events):")
        for evt_idx, matches in enumerate(bar_correct[:4]):
            if matches:
                r_notes = [(r, d["note"]) for r, d in matches]
                print(f"    e{evt_idx}: R={[r for r,_ in r_notes]} → notes={[n for _,n in r_notes]}")
            else:
                print(f"    e{evt_idx}: NO MATCH")

    # Check: are there R values that CONSISTENTLY give the right note across all bars?
    print("\n" + "=" * 80)
    print("CROSS-BAR CONSISTENCY: Same R works across all bars for same event position?")
    print("=" * 80)

    for evt_idx in range(4):
        print(f"\n  Event position e{evt_idx}:")
        r_sets = []
        for bar_idx, bar_correct in enumerate(all_correct_r):
            if evt_idx < len(bar_correct):
                r_vals = {r for r, d in bar_correct[evt_idx]}
                r_sets.append((bar_idx, r_vals))
                print(f"    Bar {bar_idx}: R={sorted(r_vals)} → notes={sorted(set(d['note'] for _,d in bar_correct[evt_idx]))}")

        if r_sets:
            common = r_sets[0][1]
            for _, rs in r_sets[1:]:
                common = common & rs
            print(f"    COMMON R across all bars: {sorted(common) if common else 'NONE'}")

    # Try: maybe the R depends on the bar header?
    print("\n" + "=" * 80)
    print("BAR HEADER ANALYSIS — Do failing bars have different header patterns?")
    print("=" * 80)

    for bar_idx, (header, events) in enumerate(bars):
        val = int.from_bytes(header, "big")
        # Extract 11 x 9-bit fields from 104-bit header
        fields = []
        for fi in range(11):
            shift = 104 - (fi + 1) * 9
            if shift >= 0:
                fields.append((val >> shift) & 0x1FF)

        # Count how many lanes decode correctly at fixed R
        correct = 0
        for ei in range(min(4, len(events))):
            d = decode_at_r(events[ei], LANE_R[ei])
            if d["note"] in target_notes:
                correct += 1

        print(f"  Bar {bar_idx}: correct={correct}/4  header_fields={fields[:6]}")
        print(f"    full: {header.hex()}")

    # Deep: For bars where cumulative R fails, check if there's a DIFFERENT
    # cumulative base that works
    print("\n" + "=" * 80)
    print("ALTERNATIVE BASE SEARCH: R = base × (i+1) mod 56")
    print("=" * 80)

    for bar_idx, (header, events) in enumerate(bars):
        if len(events) < 4:
            continue

        print(f"\n  Bar {bar_idx}:")
        best_bases = []
        for base in range(1, 56):
            matches = 0
            notes_found = []
            for ei in range(min(4, len(events))):
                r = (base * (ei + 1)) % 56
                d = decode_at_r(events[ei], r)
                if d["note"] in target_notes:
                    matches += 1
                    notes_found.append(d["note"])
                else:
                    notes_found.append(None)
            if matches >= 3:
                best_bases.append((base, matches, notes_found))

        for base, score, notes in sorted(best_bases, key=lambda x: -x[1])[:5]:
            r_vals = [(base * (i + 1)) % 56 for i in range(4)]
            print(f"    base={base:2d}: {score}/4 match, R={r_vals}, notes={notes}")

    print("\nDone.")


if __name__ == "__main__":
    main()
