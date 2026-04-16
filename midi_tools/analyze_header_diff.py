#!/usr/bin/env python3
"""
Compare all available header tracks (AL=0x7F) to find which bytes
encode musical parameters vs fixed structure.

We have 4 files with headers:
- Summer: 4 bars, G-C-Em-D, 110 BPM, tracks RHY1/CHD1/CHD2/PAD/PHR1
- MR. Vain: unknown content
- GT_style (known_pattern): known chord and drum content
- GT_A: ground truth A, known content

By finding which bytes differ, we can identify:
- Tempo encoding
- Chord root/type per bar
- Track active flags
- Voice assignments
- Groove template parameters
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qymanager.formats.qy70.sysex_parser import SysExParser
from midi_tools.event_decoder import nn


def load_header(syx_path):
    parser = SysExParser()
    messages = parser.parse_file(syx_path)
    data = b""
    for msg in messages:
        if msg.is_style_data and msg.address_low == 0x7F:
            if msg.decoded_data is not None:
                data += msg.decoded_data
    return data


def load_track_info(syx_path):
    """Get summary of which tracks/sections exist."""
    parser = SysExParser()
    messages = parser.parse_file(syx_path)
    tracks = {}
    for msg in messages:
        if msg.is_style_data and msg.decoded_data and msg.address_low != 0x7F:
            al = msg.address_low
            tracks.setdefault(al, 0)
            tracks[al] += len(msg.decoded_data)
    return tracks


SECTION_NAMES = {0: "MAIN-A", 1: "MAIN-B", 2: "FILL-AB", 3: "INTRO",
                 4: "FILL-BA", 5: "ENDING"}
TRACK_NAMES = {0: "RHY1", 1: "RHY2", 2: "BASS", 3: "CHD1",
               4: "CHD2", 5: "PAD", 6: "PHR1", 7: "PHR2"}


def main():
    files = [
        ("data/qy70_sysx/P -  Summer - 20231101.syx", "Summer"),
        ("data/qy70_sysx/P -  MR. Vain - 20231101.syx", "MR_Vain"),
        ("midi_tools/captured/ground_truth_style.syx", "GT_style"),
        ("midi_tools/captured/ground_truth_A.syx", "GT_A"),
    ]

    headers = {}
    track_info = {}
    for path, name in files:
        if os.path.exists(path):
            h = load_header(path)
            if h:
                headers[name] = h
                track_info[name] = load_track_info(path)

    print(f"Loaded {len(headers)} headers")
    for name, h in headers.items():
        print(f"  {name}: {len(h)} bytes")
        ti = track_info.get(name, {})
        active = []
        for al in sorted(ti.keys()):
            sec = al // 8
            trk = al % 8
            active.append(f"{SECTION_NAMES.get(sec, f'S{sec}')}/{TRACK_NAMES.get(trk, f'T{trk}')}")
        print(f"    Active tracks: {', '.join(active)}")

    # Find bytes that are CONSTANT across all files
    names = list(headers.keys())
    n_files = len(names)
    min_len = min(len(h) for h in headers.values())

    constant_bytes = []
    variable_bytes = []
    for i in range(min_len):
        vals = [headers[n][i] for n in names]
        if len(set(vals)) == 1:
            constant_bytes.append(i)
        else:
            variable_bytes.append((i, vals))

    print(f"\n{'='*70}")
    print(f"BYTE CLASSIFICATION ({min_len} bytes compared)")
    print(f"{'='*70}")
    print(f"  Constant across all {n_files} files: {len(constant_bytes)} "
          f"({len(constant_bytes)*100/min_len:.1f}%)")
    print(f"  Variable: {len(variable_bytes)} "
          f"({len(variable_bytes)*100/min_len:.1f}%)")

    # Show ALL variable bytes with values
    print(f"\n{'='*70}")
    print(f"ALL VARIABLE BYTES")
    print(f"{'='*70}")
    print(f"\n  {'Offset':<8} " + "  ".join(f"{n:>10}" for n in names))
    print(f"  {'------':<8} " + "  ".join(f"{'---':>10}" for _ in names))

    # Group variable bytes into contiguous regions
    regions = []
    current_start = None
    current_bytes = []
    for i, vals in variable_bytes:
        if current_start is None:
            current_start = i
            current_bytes = [(i, vals)]
        elif i - current_bytes[-1][0] <= 2:  # gap of max 2
            current_bytes.append((i, vals))
        else:
            regions.append((current_start, current_bytes))
            current_start = i
            current_bytes = [(i, vals)]
    if current_bytes:
        regions.append((current_start, current_bytes))

    for ri, (start, bytes_in_region) in enumerate(regions):
        end = bytes_in_region[-1][0]
        print(f"\n  --- Region {ri}: 0x{start:03X}-0x{end:03X} ({len(bytes_in_region)} variable bytes) ---")

        for offset, vals in bytes_in_region:
            val_strs = []
            for v in vals:
                if 0 < v < 128:
                    val_strs.append(f"0x{v:02X}={v:3d}")
                else:
                    val_strs.append(f"0x{v:02X}    ")
            print(f"  0x{offset:03X}: " + "  ".join(f"{s:>10}" for s in val_strs))

    # Focused analysis: look for tempo encoding
    print(f"\n{'='*70}")
    print(f"TEMPO ANALYSIS")
    print(f"{'='*70}")
    # Summer = 110 BPM, MR. Vain = ?, GT_style = ?, GT_A = 120 BPM (probably)
    # Search for byte pairs that could encode tempo
    for offset, vals in variable_bytes:
        # Check if any value maps to tempo
        for vi, (name, v) in enumerate(zip(names, vals)):
            if v == 110 and name == "Summer":
                print(f"  Byte 110 at 0x{offset:03X} (Summer)")
            if v == 120 and name == "GT_A":
                print(f"  Byte 120 at 0x{offset:03X} (GT_A)")

    # Check 16-bit pairs
    for i in range(len(variable_bytes) - 1):
        off1, vals1 = variable_bytes[i]
        off2, vals2 = variable_bytes[i + 1]
        if off2 == off1 + 1:
            for vi, name in enumerate(names):
                val16 = (vals1[vi] << 8) | vals2[vi]
                if name == "Summer" and val16 == 110:
                    print(f"  16-bit 110 at 0x{off1:03X}-0x{off2:03X} (Summer)")
                if name == "GT_A" and val16 == 120:
                    print(f"  16-bit 120 at 0x{off1:03X}-0x{off2:03X} (GT_A)")

    # Track count / active tracks analysis
    print(f"\n{'='*70}")
    print(f"TRACK ACTIVITY CORRELATION")
    print(f"{'='*70}")

    for name in names:
        ti = track_info.get(name, {})
        # Count unique tracks per section
        sections = {}
        for al in ti:
            sec = al // 8
            trk = al % 8
            sections.setdefault(sec, set()).add(trk)
        print(f"\n  {name}:")
        for sec in sorted(sections):
            print(f"    {SECTION_NAMES.get(sec, f'S{sec}')}: tracks {sorted(sections[sec])}")
        n_sections = len(sections)
        n_tracks = len(set(al % 8 for al in ti))
        print(f"    Total: {n_sections} sections, {n_tracks} unique track types")

    # Now look at variable bytes that could encode track count
    print(f"\n  Variable bytes potentially encoding track/section counts:")
    for offset, vals in variable_bytes:
        # Check if values match section or track counts
        matches = []
        for vi, name in enumerate(names):
            ti = track_info.get(name, {})
            n_sec = len(set(al // 8 for al in ti))
            n_trk = len(set(al % 8 for al in ti))
            n_al = len(ti)
            if vals[vi] == n_sec:
                matches.append(f"{name}=#sections={n_sec}")
            if vals[vi] == n_trk:
                matches.append(f"{name}=#tracks={n_trk}")
            if vals[vi] == n_al:
                matches.append(f"{name}=#AL={n_al}")
        if len(matches) >= 2:
            print(f"    0x{offset:03X}: vals={vals} → {', '.join(matches)}")

    # The repeating `10 88 04 02 01 00` pattern
    print(f"\n{'='*70}")
    print(f"REPEATING '10 88 04 02 01' PATTERN ANALYSIS")
    print(f"{'='*70}")

    pattern = bytes([0x10, 0x88, 0x04, 0x02, 0x01])
    for name in names:
        h = headers[name]
        count = 0
        positions = []
        for i in range(len(h) - len(pattern)):
            if h[i:i+len(pattern)] == pattern:
                count += 1
                positions.append(i)
        print(f"  {name}: {count} occurrences at {[f'0x{p:03X}' for p in positions]}")

    # What IS this pattern?
    # 0x10 = 16 = 0001_0000
    # 0x88 = 136 = 1000_1000
    # 0x04 = 4 = 0000_0100
    # 0x02 = 2 = 0000_0010
    # 0x01 = 1 = 0000_0001
    # Followed by either 0x00 or something else
    #
    # In binary: 0001_0000 1000_1000 0000_0100 0000_0010 0000_0001
    # This is a very sparse pattern with isolated bits
    print(f"\n  Pattern in binary: 00010000 10001000 00000100 00000010 00000001")
    print(f"  Set bit positions (from MSB): 3, 8, 11, 21, 30, 39")
    # These are the positions of 1s in the 40-bit number 0x1088040201

    # What precedes and follows each occurrence in Summer?
    h = headers["Summer"]
    for pos in [i for i in range(len(h)-5) if h[i:i+5] == pattern]:
        before = h[max(0,pos-3):pos]
        after = h[pos+5:pos+8]
        print(f"  0x{pos:03X}: ...{before.hex()} [1088040201] {after.hex()}...")

    # Look for 0x40 10 88 04 02 01 00 (the 7-byte version)
    pattern7 = bytes([0x40, 0x10, 0x88, 0x04, 0x02, 0x01, 0x00])
    for name in names:
        h = headers[name]
        positions = [i for i in range(len(h)-7) if h[i:i+7] == pattern7]
        if positions:
            print(f"\n  {name}: 7-byte 40_10_88_04_02_01_00 at "
                  f"{[f'0x{p:03X}' for p in positions]}")

    # Decode the 7-byte pattern as a 56-bit event field decomposition
    val = int.from_bytes(pattern7, "big")
    from midi_tools.event_decoder import rot_right, extract_9bit
    print(f"\n  0x40108804020100 as 56-bit fields:")
    for r in [0, 9, 18, 27, 36, 45, 47]:
        derot = rot_right(val, r)
        fields = [extract_9bit(derot, i) for i in range(6)]
        rem = derot & 0x3
        print(f"    R={r:2d}: F={fields} rem={rem}")

    print("\nDone.")


if __name__ == "__main__":
    main()
