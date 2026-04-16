#!/usr/bin/env python3
"""
Deep structural analysis of QY70 header track (AL=0x7F).

Key finding from initial analysis: most of the 640 bytes are filled with
the "walking zero" pattern BF DF EF F7 FB FD FE (empty/padding marker).
The actual config data is in a few concentrated regions.

This script:
1. Identifies and extracts ONLY the non-padding regions
2. Compares multiple SysEx files to find which bytes change
3. Analyzes the "walking zero" pattern as possible barrel-rotated empty data
4. Looks for chord progression, tempo, groove params in the active regions
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qymanager.formats.qy70.sysex_parser import SysExParser
from midi_tools.event_decoder import nn, rot_right, extract_9bit


PADDING_PATTERN = bytes([0xBF, 0xDF, 0xEF, 0xF7, 0xFB, 0xFD, 0xFE])


def load_header_track(syx_path):
    parser = SysExParser()
    messages = parser.parse_file(syx_path)
    header_data = b""
    raw_msgs = []
    for msg in messages:
        if msg.is_style_data and msg.address_low == 0x7F:
            if msg.decoded_data is not None:
                header_data += msg.decoded_data
                raw_msgs.append(msg)
    return header_data, raw_msgs


def is_padding_byte(data, pos):
    """Check if byte at pos is part of the BF DF EF F7 FB FD FE pattern."""
    # Check 7-byte alignment
    for start in range(max(0, pos - 6), min(len(data) - 6, pos + 1)):
        window = data[start:start + 7]
        if window == PADDING_PATTERN:
            return True
    return False


def find_active_regions(data, min_gap=3):
    """Find contiguous non-padding regions."""
    # Mark each byte as padding or active
    is_pad = [False] * len(data)
    for i in range(len(data) - 6):
        if data[i:i+7] == PADDING_PATTERN:
            for j in range(7):
                is_pad[i+j] = True

    # Also mark 0x00 runs as "inactive" for highlighting purposes
    # But don't merge with padding — zeros are meaningful (empty config)

    # Extract active regions
    regions = []
    start = None
    for i in range(len(data)):
        if not is_pad[i]:
            if start is None:
                start = i
        else:
            if start is not None:
                regions.append((start, i - 1))
                start = None
    if start is not None:
        regions.append((start, len(data) - 1))

    # Merge close regions
    merged = []
    for r in regions:
        if merged and r[0] - merged[-1][1] <= min_gap:
            merged[-1] = (merged[-1][0], r[1])
        else:
            merged.append(list(r))
    return [(s, e) for s, e in merged]


def analyze_walking_zero(data):
    """Analyze the BF DF EF F7 FB FD FE pattern."""
    print("\n" + "=" * 70)
    print("WALKING ZERO PATTERN ANALYSIS")
    print("=" * 70)

    # In binary:
    # BF = 10111111 (bit 6 clear)
    # DF = 11011111 (bit 5 clear)
    # EF = 11101111 (bit 4 clear)
    # F7 = 11110111 (bit 3 clear)
    # FB = 11111011 (bit 2 clear)
    # FD = 11111101 (bit 1 clear)
    # FE = 11111110 (bit 0 clear)

    print("\n  Each byte has exactly ONE bit clear, walking from bit 6 down to bit 0:")
    for b, name in zip(PADDING_PATTERN, range(6, -1, -1)):
        print(f"    0x{b:02X} = {b:08b}  (bit {name} clear)")

    # As a 56-bit value:
    val = int.from_bytes(PADDING_PATTERN, "big")
    print(f"\n  As 56-bit value: 0x{val:014X}")
    print(f"  Binary: {val:056b}")
    print(f"  Population count: {bin(val).count('1')} (of 56 bits)")
    print(f"  Zero bits: {56 - bin(val).count('1')}")

    # Try barrel rotation to see if it decodes to something meaningful
    print(f"\n  Barrel rotation decode attempts:")
    for r in [0, 9, 18, 22, 27, 36, 45, 47]:
        derot = rot_right(val, r)
        fields = [extract_9bit(derot, i) for i in range(6)]
        rem = derot & 0x3
        f_str = ", ".join(f"{f}" for f in fields)
        print(f"    R={r:2d}: fields=[{f_str}] rem={rem}")
        # Check if any field is 0 or 0x1FF (all ones)
        special = [i for i, f in enumerate(fields) if f in (0, 0x1FF, 0x1FE, 0x100)]
        if special:
            print(f"           Special fields: {special}")

    # Also try: what if padding is 7-byte event with all fields = max?
    # 6 × 9-bit max = 0x1FF = 511, plus 2-bit rem = 3
    # Total: 0x1FF << 47 | 0x1FF << 38 | ... = all 54 bits + 2 bits set
    all_max = 0
    for i in range(6):
        all_max |= 0x1FF << (47 - 9*i)
    all_max |= 0x3
    print(f"\n  All-max event (6×0x1FF + rem=3): 0x{all_max:014X}")
    print(f"  Matches padding: {all_max == val}")

    # What about all F0-F5 = 0x17F (lo7=0x7F, bit8=0)?
    all_7f = 0
    for i in range(6):
        all_7f |= 0x7F << (47 - 9*i)
    all_7f |= 0x3
    print(f"  All-0x7F event: 0x{all_7f:014X}")
    print(f"  Matches padding: {all_7f == val}")


def analyze_active_data(data, regions):
    """Deep analysis of active (non-padding) data regions."""
    print("\n" + "=" * 70)
    print("ACTIVE DATA REGIONS")
    print("=" * 70)

    total_active = sum(e - s + 1 for s, e in regions)
    total_padding = len(data) - total_active
    print(f"\n  Total: {len(data)}B, Active: {total_active}B ({total_active*100/len(data):.0f}%), "
          f"Padding: {total_padding}B ({total_padding*100/len(data):.0f}%)")

    for ri, (start, end) in enumerate(regions):
        length = end - start + 1
        region_data = data[start:end+1]
        zeros = region_data.count(0)

        print(f"\n  --- Region {ri}: 0x{start:03X}-0x{end:03X} ({length}B, "
              f"{zeros} zeros) ---")

        # Hex dump
        for i in range(0, length, 16):
            chunk = region_data[i:i+16]
            hex_str = " ".join(f"{b:02X}" for b in chunk)
            ascii_str = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
            print(f"    {start+i:04X}: {hex_str:<48}  {ascii_str}")

        # Per-byte annotation for small regions
        if length <= 32:
            print(f"    Per-byte breakdown:")
            for i, b in enumerate(region_data):
                off = start + i
                notes = ""
                if 0 < b < 128:
                    notes = f"  [{nn(b)}]"
                elif b == 0:
                    notes = "  [zero]"
                print(f"      0x{off:03X}: 0x{b:02X} = {b:3d} = {b:08b}{notes}")

        # Try to decode as 7-byte events
        if length >= 7:
            print(f"    As 7-byte events:")
            for ei in range(length // 7):
                evt = region_data[ei*7:(ei+1)*7]
                val = int.from_bytes(evt, "big")
                # Try R=0 (no rotation)
                fields = [extract_9bit(val, i) for i in range(6)]
                rem = val & 0x3
                lo7 = [f & 0x7F for f in fields]
                bit8 = [(f >> 8) & 1 for f in fields]
                notes = [nn(n) if 13 <= n <= 87 else "?" for n in lo7]
                print(f"      e{ei} R=0: F=[{','.join(f'{f}' for f in fields)}] "
                      f"lo7={lo7} notes=[{','.join(notes)}] bit8={bit8} rem={rem}")

        # Search for specific patterns in this region
        # Chord root sequence: G=7, C=0, E=4, D=2
        for i in range(len(region_data) - 3):
            w = list(region_data[i:i+4])
            if w == [7, 0, 4, 2]:
                print(f"    *** CHORD ROOTS [G,C,E,D] at 0x{start+i:03X} ***")
            # Also nibble-packed: 70, 42
            if region_data[i] == 0x70 and region_data[i+1] == 0x42:
                print(f"    *** CHORD ROOTS nibble-packed at 0x{start+i:03X} ***")


def analyze_128byte_blocks(data):
    """Analyze header as 5 × 128-byte blocks (one per SysEx message)."""
    print("\n" + "=" * 70)
    print("128-BYTE BLOCK ANALYSIS (per SysEx message)")
    print("=" * 70)

    n_blocks = (len(data) + 127) // 128
    for bi in range(n_blocks):
        block = data[bi*128:(bi+1)*128]
        pad_count = 0
        for i in range(len(block) - 6):
            if block[i:i+7] == PADDING_PATTERN:
                pad_count += 1

        zeros = block.count(0)
        active_bytes = len(block) - zeros
        # Count BF/DF/EF/F7/FB/FD/FE
        pad_bytes = sum(1 for b in block if b in PADDING_PATTERN)

        print(f"\n  Block {bi} (0x{bi*128:03X}-0x{min((bi+1)*128, len(data))-1:03X}):")
        print(f"    Zeros: {zeros}, Padding pattern bytes: {pad_bytes}, "
              f"Active: {len(block) - zeros - pad_bytes}")

        # Show just the non-padding, non-zero bytes
        active_offsets = []
        for i, b in enumerate(block):
            if b != 0 and b not in PADDING_PATTERN:
                active_offsets.append((bi*128 + i, b))
        if active_offsets:
            print(f"    Active bytes ({len(active_offsets)}):")
            for off, val in active_offsets:
                note = f" [{nn(val)}]" if 0 < val < 128 else ""
                print(f"      0x{off:03X}: 0x{val:02X} ({val:3d}){note}")


def compare_all_files():
    """Compare header tracks across all available SysEx files."""
    print("\n" + "=" * 70)
    print("CROSS-FILE HEADER COMPARISON")
    print("=" * 70)

    files = [
        ("data/qy70_sysx/P -  Summer - 20231101.syx", "Summer"),
        ("data/qy70_sysx/P -  MR. Vain - 20231101.syx", "MR. Vain"),
        ("data/qy70_sysx/A - QY70 -20231106.syx", "QY70-A"),
        ("midi_tools/captured/ground_truth_style.syx", "GT_style"),
        ("midi_tools/captured/ground_truth_A.syx", "GT_A"),
        ("midi_tools/captured/ground_truth_preset.syx", "GT_preset"),
    ]

    headers = {}
    for path, name in files:
        if os.path.exists(path):
            hdr, _ = load_header_track(path)
            if hdr:
                headers[name] = hdr
                print(f"\n  {name}: {len(hdr)} bytes")
            else:
                print(f"\n  {name}: no header track (AL=0x7F) found")
        else:
            print(f"\n  {name}: file not found")

    if len(headers) < 2:
        print("\n  Need at least 2 files with header tracks for comparison")
        return headers

    # Compare pairwise
    names = list(headers.keys())
    for i in range(len(names)):
        for j in range(i+1, len(names)):
            a_name, b_name = names[i], names[j]
            a_data, b_data = headers[a_name], headers[b_name]
            min_len = min(len(a_data), len(b_data))

            diffs = []
            for k in range(min_len):
                if a_data[k] != b_data[k]:
                    diffs.append(k)

            print(f"\n  {a_name} vs {b_name}: "
                  f"{len(diffs)}/{min_len} bytes differ ({len(diffs)*100/min_len:.1f}%)")

            if len(diffs) <= 60:
                for d in diffs:
                    a_val = a_data[d]
                    b_val = b_data[d]
                    print(f"    0x{d:03X}: {a_name}=0x{a_val:02X}({a_val:3d}) "
                          f"vs {b_name}=0x{b_val:02X}({b_val:3d}) "
                          f"diff={a_val-b_val:+d}")

    return headers


def analyze_9bit_fields(data, start, count, label=""):
    """Interpret a region as 9-bit fields (like bar headers)."""
    region = data[start:start + (count * 9 + 7) // 8]
    val = int.from_bytes(region, "big")
    total_bits = len(region) * 8

    print(f"\n  9-bit field decode at 0x{start:03X} ({label}):")
    for i in range(count):
        shift = total_bits - (i + 1) * 9
        if shift < 0:
            break
        field = (val >> shift) & 0x1FF
        lo7 = field & 0x7F
        bit8 = (field >> 8) & 1
        note = nn(lo7) if 13 <= lo7 <= 87 else "?"
        print(f"    F{i}: {field:3d} (0x{field:03X}) lo7={lo7} [{note}] bit8={bit8}")


def main():
    summer_path = "data/qy70_sysx/P -  Summer - 20231101.syx"

    # Load Summer header
    summer_hdr, summer_msgs = load_header_track(summer_path)
    if not summer_hdr:
        print("No header data found!")
        return

    print(f"Summer header: {len(summer_hdr)} bytes, {len(summer_msgs)} messages")

    # Walking zero analysis
    analyze_walking_zero(summer_hdr)

    # Find active regions
    regions = find_active_regions(summer_hdr)
    analyze_active_data(summer_hdr, regions)

    # 128-byte block analysis
    analyze_128byte_blocks(summer_hdr)

    # Cross-file comparison
    all_headers = compare_all_files()

    # Try 9-bit field decoding on interesting regions
    print("\n" + "=" * 70)
    print("9-BIT FIELD DECODE OF KEY REGIONS")
    print("=" * 70)

    # Region 0x000: first 13 bytes (same size as bar header)
    analyze_9bit_fields(summer_hdr, 0, 11, "header bytes 0-12")

    # Region 0x080: secondary data start
    if len(summer_hdr) > 0x8D:
        analyze_9bit_fields(summer_hdr, 0x80, 11, "header bytes 0x80-0x8C")

    # Region 0x0A0
    if len(summer_hdr) > 0xAD:
        analyze_9bit_fields(summer_hdr, 0xA0, 11, "header bytes 0xA0-0xAC")

    # Specific analysis: bytes 0x048-0x04B (30 20 14 0C)
    print("\n" + "=" * 70)
    print("SPECIFIC PATTERN ANALYSIS")
    print("=" * 70)

    # 30 20 14 0C — decreasing values
    vals = [summer_hdr[0x48+i] for i in range(4)]
    print(f"\n  0x048: {vals} — decreasing by ~factor")
    print(f"    Ratios: {[f'{vals[i]/vals[i+1]:.2f}' for i in range(3)]}")
    print(f"    As binary: {[f'{v:08b}' for v in vals]}")
    print(f"    Sum: {sum(vals)}")

    # 0x098-0x09F: 00 80 09 4B 15 51
    if len(summer_hdr) > 0x9F:
        region = summer_hdr[0x98:0xA0]
        print(f"\n  0x098: {[f'0x{b:02X}' for b in region]}")
        # 09 4B = could be tempo or voice parameter
        # 15 51 = 21, 81
        val16 = (region[2] << 8) | region[3]
        print(f"    0x9A-0x9B as 16-bit: {val16} (0x{val16:04X})")
        val16b = (region[4] << 8) | region[5]
        print(f"    0x9C-0x9D as 16-bit: {val16b} (0x{val16b:04X})")

    # 0x1A2-0x1B0: 64 19 8C C6 23 11 C8 (repeats twice!)
    if len(summer_hdr) > 0x1B0:
        region1 = summer_hdr[0x1A2:0x1A9]
        region2 = summer_hdr[0x1A9:0x1B0]
        print(f"\n  REPEATING 7-BYTE BLOCK:")
        print(f"    0x1A2: {[f'0x{b:02X}' for b in region1]}")
        print(f"    0x1A9: {[f'0x{b:02X}' for b in region2]}")
        print(f"    Identical: {region1 == region2}")

        # Try as barrel-rotated event
        val = int.from_bytes(region1, "big")
        print(f"    As 56-bit: 0x{val:014X}")
        for r in [0, 9, 18, 22, 27, 36, 45, 47]:
            derot = rot_right(val, r)
            fields = [extract_9bit(derot, i) for i in range(6)]
            lo7 = [f & 0x7F for f in fields]
            notes = [nn(n) if 13 <= n <= 87 else "?" for n in lo7]
            is_valid = any(13 <= n <= 87 for n in lo7)
            marker = " <<<" if is_valid and lo7[0] in range(13, 88) else ""
            print(f"      R={r:2d}: lo7={lo7} [{','.join(notes)}]{marker}")

    print("\nDone.")


if __name__ == "__main__":
    main()
