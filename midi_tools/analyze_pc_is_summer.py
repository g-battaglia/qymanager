#!/usr/bin/env python3
"""
Verify the hypothesis: Pattern C capture IS Summer (slot U01 wasn't empty).

Comparison strategy:
- For each track (AL=0..7 + 0x7F), compute byte-level similarity between PC and SM
- Report: total bytes, shared bytes, unique bytes
- Report: decoded content differences per track
"""

import sys
import os
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from midi_tools.analyze_cross_pattern_signatures import parse_all_tracks


TRACK_NAMES = {
    0: "RHY1", 1: "RHY2", 2: "BASS", 3: "CHD1",
    4: "CHD2", 5: "PHR1", 6: "PHR2", 7: "PHR3",
    0x7F: "HEADER"
}


def main():
    pc_tracks = parse_all_tracks("midi_tools/captured/ground_truth_C_kick.syx")
    sm_tracks = parse_all_tracks("data/qy70_sysx/P -  Summer - 20231101.syx")

    print("=" * 70)
    print("ALL-TRACKS COMPARISON: Pattern C vs Summer")
    print("=" * 70)

    all_als = sorted(set(pc_tracks.keys()) | set(sm_tracks.keys()))

    for al in all_als:
        name = TRACK_NAMES.get(al, f"UNK_{al:02X}")
        pc_data = pc_tracks.get(al, b"")
        sm_data = sm_tracks.get(al, b"")

        pc_len = len(pc_data)
        sm_len = len(sm_data)

        print(f"\n--- AL=0x{al:02X} ({name}) ---")
        print(f"  PC: {pc_len} bytes")
        print(f"  SM: {sm_len} bytes")

        if pc_data == sm_data:
            print(f"  => IDENTICAL")
            continue

        if not pc_data and sm_data:
            print(f"  => PC empty, SM has data")
            continue

        if pc_data and not sm_data:
            print(f"  => PC has data, SM empty")
            continue

        # Compare common prefix
        min_len = min(pc_len, sm_len)
        common = 0
        for i in range(min_len):
            if pc_data[i] == sm_data[i]:
                common += 1
            else:
                break

        # First differing byte
        first_diff = None
        for i in range(min_len):
            if pc_data[i] != sm_data[i]:
                first_diff = i
                break

        # Count total matching bytes
        matching = sum(1 for a, b in zip(pc_data, sm_data) if a == b)
        pct = 100 * matching / min_len if min_len else 0

        print(f"  Common prefix: {common} bytes")
        print(f"  First diff at byte: {first_diff}")
        print(f"  Total matching (min_len): {matching}/{min_len} = {pct:.1f}%")

        if first_diff is not None and first_diff < 64:
            # Show context around first difference
            start = max(0, first_diff - 8)
            end = min(min_len, first_diff + 16)
            print(f"  Context (byte {start}-{end}):")
            print(f"    PC: {pc_data[start:end].hex()}")
            print(f"    SM: {sm_data[start:end].hex()}")
            # Mark the differing byte with ^
            marker_pos = 2 * (first_diff - start)
            marker = " " * (8 + marker_pos) + "^^"
            print(f"    {marker}")

    print()
    print("=" * 70)
    print("CONCLUSION")
    print("=" * 70)

    identical = sum(1 for al in all_als if pc_tracks.get(al) == sm_tracks.get(al))
    total = len(all_als)
    print(f"  Identical tracks: {identical}/{total}")

    # Check if PC is a subset (prefix) of Summer
    is_summer_truncated = True
    for al in all_als:
        pc_data = pc_tracks.get(al, b"")
        sm_data = sm_tracks.get(al, b"")
        if pc_data and not sm_data:
            is_summer_truncated = False
            break
        if pc_data and sm_data and not sm_data.startswith(pc_data[:min(len(pc_data), 100)]):
            # Not a prefix match in first 100 bytes
            pass

    print()
    if identical >= total - 1:
        print("  >>> Pattern C is (nearly) identical to Summer")
        print("  >>> Slot U01 contained Summer, NOT empty as assumed")
        print("  >>> The user's 'kick only' programming did NOT take effect")

    print()
    print("=" * 70)
    print("PATTERN C HEADER (AL=0x7F) DETAILED DIFF vs SUMMER")
    print("=" * 70)

    if 0x7F in pc_tracks and 0x7F in sm_tracks:
        pc_h = pc_tracks[0x7F]
        sm_h = sm_tracks[0x7F]

        differences = [(i, pc_h[i], sm_h[i]) for i in range(min(len(pc_h), len(sm_h))) if pc_h[i] != sm_h[i]]
        print(f"  Total differences: {len(differences)}")

        if differences:
            for i, (idx, p, s) in enumerate(differences[:30]):
                print(f"  byte[0x{idx:03X}]: PC=0x{p:02X} SM=0x{s:02X} (XOR=0x{p^s:02X})")

        # Check "pattern name" area (usually near the start or at a known offset)
        # Header byte 0x004 is often the section marker (MAIN-A=0, MAIN-B=1)
        print()
        print(f"  Byte 0x000 (format type): PC=0x{pc_h[0]:02X}, SM=0x{sm_h[0]:02X}")
        print(f"  Byte 0x004 (section):     PC=0x{pc_h[4]:02X}, SM=0x{sm_h[4]:02X}")

        # Look for pattern length field (commonly at certain header positions)
        # Scan for 7-bit values that could be bar count
        print()
        print("  Bytes 0x008-0x01F (likely pattern settings):")
        print(f"    PC: {pc_h[8:32].hex()}")
        print(f"    SM: {sm_h[8:32].hex()}")


if __name__ == "__main__":
    main()
