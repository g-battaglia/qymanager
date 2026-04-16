#!/usr/bin/env python3
"""
Direct comparison: Pattern C events vs Summer events, position-by-position.

Hypothesis: If Pattern C and Summer share byte-identical events, these events
likely represent shared template/lane data, not user-specific note content.

Tests:
1. Enumerate all unique events in each pattern (set intersection)
2. Compare events at matching (segment, event) positions
3. Identify which events are pattern-specific (user note data)
4. Identify which events are shared (likely template / lane signatures)
"""

import sys
import os
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from midi_tools.analyze_cross_pattern_signatures import parse_all_tracks, extract_events


def events_by_position(events):
    """Organize events as {(segment_idx, event_idx): event_bytes}."""
    return {(si, ei): evt for si, ei, evt, hdr in events}


def main():
    patterns = [
        ("PatternC", "midi_tools/captured/ground_truth_C_kick.syx"),
        ("Summer", "data/qy70_sysx/P -  Summer - 20231101.syx"),
    ]

    loaded = {}
    for name, path in patterns:
        tracks = parse_all_tracks(path)
        # Collect RHY1 (AL=0) drum events only
        events = extract_events(tracks.get(0x00, b""))
        loaded[name] = events
        print(f"{name}: {len(events)} RHY1 events")

    # Build position maps
    pc = events_by_position(loaded["PatternC"])
    sm = events_by_position(loaded["Summer"])

    print()
    print("=" * 70)
    print("SHARED vs UNIQUE EVENTS (as raw byte sets)")
    print("=" * 70)

    pc_set = set(bytes(e) for e in pc.values() if any(b != 0 for b in e))
    sm_set = set(bytes(e) for e in sm.values() if any(b != 0 for b in e))

    shared = pc_set & sm_set
    only_pc = pc_set - sm_set
    only_sm = sm_set - pc_set

    print(f"  Pattern C unique events: {len(pc_set)}")
    print(f"  Summer unique events:    {len(sm_set)}")
    print(f"  Shared events:           {len(shared)}")
    print(f"  Only in Pattern C:       {len(only_pc)}")
    print(f"  Only in Summer:          {len(only_sm)}")

    print()
    print("--- Shared events (byte-identical between PC and Summer) ---")
    for evt in sorted(shared):
        print(f"  {evt.hex()}")

    print()
    print("--- Only in Pattern C (likely user-specific kick data) ---")
    for evt in sorted(only_pc):
        print(f"  {evt.hex()}")

    print()
    print("=" * 70)
    print("POSITION-BY-POSITION COMPARISON (first 6 segments)")
    print("=" * 70)

    common_positions = sorted(set(pc.keys()) | set(sm.keys()))
    for seg_ei in common_positions:
        si, ei = seg_ei
        if si > 5:
            continue
        pc_evt = pc.get(seg_ei)
        sm_evt = sm.get(seg_ei)
        pc_hex = pc_evt.hex() if pc_evt else "(missing)"
        sm_hex = sm_evt.hex() if sm_evt else "(missing)"

        match = "==" if pc_evt == sm_evt else "!="
        print(f"  seg{si} e{ei}: PC={pc_hex}  {match}  SM={sm_hex}")

    print()
    print("=" * 70)
    print("XOR DIFFERENCES at matching positions (non-zero differences)")
    print("=" * 70)

    diff_counts = defaultdict(int)  # (byte_index, xor_value) -> count

    for seg_ei in common_positions:
        if seg_ei not in pc or seg_ei not in sm:
            continue
        pc_evt, sm_evt = pc[seg_ei], sm[seg_ei]
        if len(pc_evt) != len(sm_evt):
            continue

        xor_bytes = bytes(a ^ b for a, b in zip(pc_evt, sm_evt))
        if any(xor_bytes):
            print(f"  seg{seg_ei[0]} e{seg_ei[1]}: XOR = {xor_bytes.hex()}")
            # Count per-byte-position XOR values
            for i, x in enumerate(xor_bytes):
                if x != 0:
                    diff_counts[(i, x)] += 1

    print()
    print("--- Most common XOR differences by byte position ---")
    for (byte_idx, xor_val), count in sorted(diff_counts.items(),
                                              key=lambda x: -x[1])[:20]:
        print(f"  byte[{byte_idx}] XOR=0x{xor_val:02X}: {count} occurrences")

    print()
    print("=" * 70)
    print("BAR HEADER COMPARISON")
    print("=" * 70)

    # Group events by segment to compare bar headers
    pc_headers = {}
    sm_headers = {}
    for si, ei, evt, hdr in loaded["PatternC"]:
        pc_headers[si] = hdr
    for si, ei, evt, hdr in loaded["Summer"]:
        sm_headers[si] = hdr

    for si in sorted(set(pc_headers.keys()) | set(sm_headers.keys()))[:6]:
        pc_h = pc_headers.get(si, b"(none)").hex() if si in pc_headers else "(none)"
        sm_h = sm_headers.get(si, b"(none)").hex() if si in sm_headers else "(none)"
        match = "==" if pc_headers.get(si) == sm_headers.get(si) else "!="
        print(f"  seg{si}:")
        print(f"    PC: {pc_h}")
        print(f"    SM: {sm_h}  [{match}]")

    # Decode headers as 9-bit fields
    print()
    print("=" * 70)
    print("BAR HEADER 9-BIT FIELDS (high7 of each)")
    print("=" * 70)

    def decode_header_fields(hdr):
        val = int.from_bytes(hdr, "big")
        fields = []
        for i in range(11):
            shift = 104 - 9 * (i + 1)
            if shift >= 0:
                fields.append((val >> shift) & 0x1FF)
        return fields

    for si in sorted(set(pc_headers.keys()) | set(sm_headers.keys()))[:6]:
        print(f"\n  seg{si}:")
        if si in pc_headers:
            f = decode_header_fields(pc_headers[si])
            hi7 = [x & 0x7F for x in f]
            print(f"    PC fields(9bit): {f[:6]}")
            print(f"    PC fields(hi7):  {hi7[:6]}")
        if si in sm_headers:
            f = decode_header_fields(sm_headers[si])
            hi7 = [x & 0x7F for x in f]
            print(f"    SM fields(9bit): {f[:6]}")
            print(f"    SM fields(hi7):  {hi7[:6]}")


if __name__ == "__main__":
    main()
