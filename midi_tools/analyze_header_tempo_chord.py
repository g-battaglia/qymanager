#!/usr/bin/env python3
"""
Focused analysis of tempo and chord encoding in QY70 header track.

Key regions identified from cross-file comparison:
- 0x000: format marker (03=user, 4C=style, 2C=empty)
- 0x005-0x00D: packed global config
- 0x046-0x053: per-track data sizes/config
- 0x0AA-0x0B0: voice parameters
- 0x18C-0x19B: TEMPO (Summer=GT_style, MR_Vain=GT_A)

Summer: 110 BPM, chords G-C-Em-D, MAIN-A, tracks RHY1/CHD1/CHD2/PAD/PHR1
GT_style: known_pattern, MAIN-A, tracks RHY1-PHR1 (7 tracks)
GT_A: empty (120 BPM default?)
MR_Vain: MAIN-B, tracks RHY1/CHD1/CHD2/PAD/PHR1
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qymanager.formats.qy70.sysex_parser import SysExParser
from midi_tools.event_decoder import nn, rot_right, extract_9bit


def load_header(syx_path):
    parser = SysExParser()
    messages = parser.parse_file(syx_path)
    decoded = b""
    raw = b""
    for msg in messages:
        if msg.is_style_data and msg.address_low == 0x7F:
            if msg.decoded_data is not None:
                decoded += msg.decoded_data
                raw += msg.data
    return decoded, raw


def bits_to_int(data, bit_offset, bit_length):
    """Extract bit_length bits starting at bit_offset from data bytes."""
    result = 0
    for i in range(bit_length):
        byte_idx = (bit_offset + i) // 8
        bit_idx = 7 - ((bit_offset + i) % 8)
        if byte_idx < len(data):
            result = (result << 1) | ((data[byte_idx] >> bit_idx) & 1)
        else:
            result <<= 1
    return result


def main():
    files = {
        "Summer": "data/qy70_sysx/P -  Summer - 20231101.syx",
        "MR_Vain": "data/qy70_sysx/P -  MR. Vain - 20231101.syx",
        "GT_style": "midi_tools/captured/ground_truth_style.syx",
        "GT_A": "midi_tools/captured/ground_truth_A.syx",
    }

    headers = {}
    raw_headers = {}
    for name, path in files.items():
        if os.path.exists(path):
            d, r = load_header(path)
            if d:
                headers[name] = d
                raw_headers[name] = r

    # =========================================================
    # TEMPO ANALYSIS: region 0x18C-0x19B
    # =========================================================
    print("=" * 70)
    print("TEMPO REGION ANALYSIS (0x18C-0x19B)")
    print("=" * 70)

    # Known tempos: Summer=110, GT_A=probably 120 (default)
    # Summer=GT_style values identical, MR_Vain=GT_A identical

    for name in sorted(headers.keys()):
        h = headers[name]
        region = h[0x18C:0x19C]
        print(f"\n  {name}:")
        print(f"    Raw: {' '.join(f'{b:02X}' for b in region)}")
        print(f"    Dec: {list(region)}")

        # Try various tempo extraction methods
        for i in range(len(region) - 1):
            # Method 1: direct byte
            if 40 <= region[i] <= 300:
                pass  # Too many false positives

            # Method 2: 16-bit BE
            v16 = (region[i] << 8) | region[i+1]
            if 40 <= v16 <= 300:
                print(f"      16BE at +{i}: {v16}")

            # Method 3: 16-bit LE
            v16le = region[i] | (region[i+1] << 8)
            if 40 <= v16le <= 300:
                print(f"      16LE at +{i}: {v16le}")

        # Method 4: bit-level extraction from the region
        for bit_start in range(len(region) * 8 - 8):
            for bit_len in [7, 8, 9, 10]:
                val = bits_to_int(region, bit_start, bit_len)
                if name == "Summer" and val == 110:
                    print(f"      *** TEMPO 110 at bit {bit_start}, {bit_len} bits ***")
                if name == "GT_A" and val == 120:
                    print(f"      *** TEMPO 120 at bit {bit_start}, {bit_len} bits ***")

    # Also check the raw (7-bit encoded) data for tempo
    print(f"\n  Raw (pre-decode) tempo search:")
    for name in sorted(raw_headers.keys()):
        r = raw_headers[name]
        # The tempo formula from syx_analyzer: tempo = raw[0] * 95 - 133 + raw[1]
        # But that's for the beginning of raw data
        for i in range(min(len(r) - 1, 50)):
            t = r[i] * 95 - 133 + r[i+1]
            if name == "Summer" and t == 110:
                print(f"    {name}: tempo formula at raw[{i}]={r[i]}, raw[{i+1}]={r[i+1]} → 110")
            if name == "GT_A" and t == 120:
                print(f"    {name}: tempo formula at raw[{i}]={r[i]}, raw[{i+1}]={r[i+1]} → 120")

    # =========================================================
    # GLOBAL CONFIG: region 0x005-0x00D
    # =========================================================
    print(f"\n{'='*70}")
    print("GLOBAL CONFIG (0x005-0x00D)")
    print("=" * 70)

    for name in sorted(headers.keys()):
        h = headers[name]
        region = h[0x005:0x00E]
        print(f"\n  {name}:")
        print(f"    Hex: {' '.join(f'{b:02X}' for b in region)}")
        print(f"    Bin: {' '.join(f'{b:08b}' for b in region)}")

        # 9-bit field interpretation
        val = int.from_bytes(region, "big")
        n_bits = len(region) * 8  # 72 bits = 8 × 9-bit fields
        for i in range(8):
            shift = n_bits - (i + 1) * 9
            if shift >= 0:
                field = (val >> shift) & 0x1FF
                lo7 = field & 0x7F
                bit8 = (field >> 8) & 1
                note = nn(lo7) if 13 <= lo7 <= 87 else f"{lo7}"
                print(f"      F{i}: {field:3d} (0x{field:03X}) lo7={lo7} [{note}] bit8={bit8}")

    # =========================================================
    # TRACK CONFIG: region 0x046-0x07C
    # =========================================================
    print(f"\n{'='*70}")
    print("TRACK CONFIG (0x046-0x07C)")
    print("=" * 70)

    # Known track assignments:
    # Summer MAIN-A: RHY1(0)=384B, CHD1(3)=256B, CHD2(4)=128B, PAD(5)=128B, PHR1(6)=256B
    # GT_style MAIN-A: all 7 tracks active
    # MR_Vain MAIN-B: same 5 tracks as Summer
    # GT_A: empty

    for name in sorted(headers.keys()):
        h = headers[name]
        region = h[0x046:0x07D]
        print(f"\n  {name}:")

        # First, the clear data bytes
        for i in range(0x046, 0x080):
            v = h[i]
            if v != 0:
                print(f"    0x{i:03X}: 0x{v:02X} = {v:3d} = {v:08b}")

    # =========================================================
    # VOICE PARAMETERS: 0x0AA-0x0B0
    # =========================================================
    print(f"\n{'='*70}")
    print("VOICE PARAMS (0x0AA-0x0B0)")
    print("=" * 70)

    for name in sorted(headers.keys()):
        h = headers[name]
        region = h[0x0AA:0x0B1]
        print(f"\n  {name}:")
        print(f"    Hex: {' '.join(f'{b:02X}' for b in region)}")

        # As 7-byte barrel-rotated event at R=0
        if len(region) >= 7:
            val = int.from_bytes(region[:7], "big")
            for r in [0, 9]:
                derot = rot_right(val, r)
                fields = [extract_9bit(derot, i) for i in range(6)]
                lo7 = [f & 0x7F for f in fields]
                notes = [nn(n) if 0 < n < 128 else "?" for n in lo7]
                print(f"      R={r}: lo7={lo7} notes={notes}")

        # Yamaha voice: MSB=0, Program=0-127
        # Standard Kit 1 = MSB 127, PRG 0
        # Finger Bass = PRG 33
        # Strings = PRG 48
        print(f"    As individual bytes:")
        for i, b in enumerate(region):
            off = 0x0AA + i
            note = f" [{nn(b)}]" if 0 < b < 128 else ""
            print(f"      0x{off:03X}: 0x{b:02X} = {b:3d}{note}")

    # =========================================================
    # CHORD ENCODING SEARCH
    # =========================================================
    print(f"\n{'='*70}")
    print("CHORD ROOT SEARCH IN VARIABLE REGIONS")
    print("=" * 70)

    # Summer chords: G(7), C(0), Em(4), D(2) as Yamaha root codes
    # Also as MIDI: G=55/67, C=48/60, E=52/64, D=50/62

    summer = headers["Summer"]
    gt_style = headers["GT_style"]

    # Look for chord roots in regions that DIFFER between Summer and GT_style
    print(f"\n  Differences Summer vs GT_style:")
    diffs = [(i, summer[i], gt_style[i])
             for i in range(min(len(summer), len(gt_style)))
             if summer[i] != gt_style[i]]
    print(f"  Total: {len(diffs)} bytes differ")

    # Focus on regions unique to Summer
    for i, sv, gv in diffs:
        if sv != 0 and gv != 0:  # Both have data (not just empty vs full)
            note_s = f" [{nn(sv)}]" if 0 < sv < 128 else ""
            note_g = f" [{nn(gv)}]" if 0 < gv < 128 else ""
            print(f"    0x{i:03X}: Summer=0x{sv:02X}({sv:3d}){note_s}  "
                  f"GT_style=0x{gv:02X}({gv:3d}){note_g}")

    # =========================================================
    # BITFIELD ANALYSIS OF 0x005-0x00D
    # =========================================================
    print(f"\n{'='*70}")
    print("BITFIELD ANALYSIS: GLOBAL CONFIG")
    print("=" * 70)

    # These 9 bytes (72 bits) likely encode:
    # - Number of bars (1-8 per section)
    # - Time signature (4/4, 3/4, etc.)
    # - Tempo (40-300 BPM)
    # - Section count
    # - Key/chord info

    # Let me try to find tempo here instead
    for name in sorted(headers.keys()):
        h = headers[name]
        region = h[0x005:0x00E]
        print(f"\n  {name}: {' '.join(f'{b:02X}' for b in region)}")

        # Extract all possible bit ranges for tempo (7-10 bits wide)
        hits = []
        for bit_start in range(72 - 7):
            for bit_len in range(7, 11):
                if bit_start + bit_len > 72:
                    break
                val = bits_to_int(region, bit_start, bit_len)
                if name == "Summer" and val == 110:
                    hits.append((bit_start, bit_len, val))
                if name == "MR_Vain" and 60 <= val <= 200:
                    # MR. Vain could be any tempo, but likely 120-140 for dance
                    pass
        if hits:
            for bs, bl, v in hits:
                print(f"    *** Found {v} at bit {bs}, {bl} bits ***")

    # =========================================================
    # 0x004 BYTE: SECTION INDEX?
    # =========================================================
    print(f"\n{'='*70}")
    print("BYTE 0x004: SECTION INDICATOR")
    print("=" * 70)

    # Summer=0, MR_Vain=1, GT_style=0, GT_A=0
    # Summer is MAIN-A (section 0), MR_Vain is MAIN-B (section 1)!
    for name in sorted(headers.keys()):
        h = headers[name]
        print(f"  {name}: byte[4] = {h[4]}")

    # =========================================================
    # REPEATING 64 19 8C C6 23 11 C8 BLOCK
    # =========================================================
    print(f"\n{'='*70}")
    print("REPEATING BLOCK 64 19 8C C6 23 11 C8")
    print("=" * 70)

    target = bytes([0x64, 0x19, 0x8C, 0xC6, 0x23, 0x11, 0xC8])
    for name in sorted(headers.keys()):
        h = headers[name]
        positions = [i for i in range(len(h) - 6) if h[i:i+7] == target]
        if positions:
            print(f"  {name}: found at {[f'0x{p:03X}' for p in positions]}")
        else:
            # Also search for similar patterns
            similar = []
            for i in range(len(h) - 6):
                block = h[i:i+7]
                match_count = sum(1 for a, b in zip(block, target) if a == b)
                if match_count >= 5:
                    similar.append((i, match_count, block))
            if similar:
                for pos, mc, blk in similar:
                    print(f"  {name}: similar ({mc}/7) at 0x{pos:03X}: "
                          f"{' '.join(f'{b:02X}' for b in blk)}")
            else:
                print(f"  {name}: not found (no 5/7 match either)")

    # =========================================================
    # SPECIAL: Track data size relationship
    # =========================================================
    print(f"\n{'='*70}")
    print("TRACK SIZE CORRELATION")
    print("=" * 70)

    # Summer: 0x048=[48,32,20,12], tracks: RHY1=384, CHD1=256, CHD2=128, PAD=128, PHR1=256
    # If these are message counts (128B blocks): 384/128=3, 256/128=2, 128/128=1
    # Or in 8-byte units: 384/8=48✓, 256/8=32✓, 128/8=16≠20, 128/8=16≠12

    summer_sizes = {"RHY1": 384, "CHD1": 256, "CHD2": 128, "PAD": 128, "PHR1": 256}
    config_vals = [48, 32, 20, 12]  # from 0x048-0x04B

    print(f"  Config at 0x048: {config_vals}")
    print(f"  Track sizes: {summer_sizes}")

    # Check all simple relationships
    for divisor in [1, 2, 4, 8, 16, 32]:
        mapped = {k: v // divisor for k, v in summer_sizes.items()}
        matches = [k for k, v in mapped.items() if v in config_vals]
        if len(matches) >= 2:
            print(f"    ÷{divisor}: {mapped} → matches: {matches}")

    # Maybe the 4 bytes encode 4 bars, not 4 tracks?
    # Summer has 4 bars, each bar could have a "density" or "event count" parameter
    print(f"\n  Maybe 4 bar parameters?")
    # Bar sizes in the RHY1 track: all bars have ~4 events
    # 48/4=12, 32/4=8, 20/4=5, 12/4=3 — doesn't obviously match

    # Or perhaps 4 sections/fields of config
    print(f"  As bit offsets: {[v*8 for v in config_vals]} → {[v*8 for v in config_vals]}")

    print("\nDone.")


if __name__ == "__main__":
    main()
