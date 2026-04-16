#!/usr/bin/env python3
"""
Deep analysis of Summer header track (AL=0x7F) — 640 decoded bytes.

The header track contains global pattern settings that may include:
- Groove template parameters (drum velocity humanization)
- Bass pattern template (auto-generated bass from chord root)
- Chord root/type encoding per bar/section
- Tempo, time signature, section structure

Session 25b proved that per-beat drum velocities are NOT in track data,
and bass track (AL=0x02) is absent from SysEx. Both must come from
header track or QY70 firmware.

Also compare against known_pattern header to find structural differences.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qymanager.formats.qy70.sysex_parser import SysExParser
from midi_tools.event_decoder import nn, SECTION_NAMES, TRACK_NAMES


def load_header_track(syx_path):
    """Load AL=0x7F header track data."""
    parser = SysExParser()
    messages = parser.parse_file(syx_path)

    header_data = b""
    raw_data = b""
    msg_count = 0
    for msg in messages:
        if msg.is_style_data and msg.address_low == 0x7F:
            if msg.decoded_data is not None:
                header_data += msg.decoded_data
                raw_data += msg.data
                msg_count += 1

    return header_data, raw_data, msg_count


def load_all_track_sizes(syx_path):
    """Load size of every AL track for overview."""
    parser = SysExParser()
    messages = parser.parse_file(syx_path)

    tracks = {}
    for msg in messages:
        if msg.is_style_data and msg.decoded_data:
            al = msg.address_low
            tracks.setdefault(al, 0)
            tracks[al] += len(msg.decoded_data)
    return tracks


def hex_dump(data, offset=0, width=16, limit=None):
    """Pretty hex dump with ASCII."""
    lines = []
    end = len(data) if limit is None else min(len(data), offset + limit)
    for i in range(offset, end, width):
        chunk = data[i:i+width]
        hex_part = " ".join(f"{b:02X}" for b in chunk)
        ascii_part = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
        lines.append(f"  {i:04X}: {hex_part:<{width*3}}  {ascii_part}")
    return "\n".join(lines)


def find_repeating_structures(data, min_len=4, max_len=16):
    """Find repeating byte patterns that suggest structured data."""
    results = []
    for plen in range(min_len, max_len + 1):
        for start in range(len(data) - plen * 2):
            pattern = data[start:start + plen]
            if all(b == pattern[0] for b in pattern):
                continue  # Skip uniform patterns
            count = 0
            pos = start
            while pos + plen <= len(data) and data[pos:pos + plen] == pattern:
                count += 1
                pos += plen
            if count >= 3:
                results.append((start, plen, count, pattern))
    # Deduplicate: keep longest pattern at each start position
    seen_starts = {}
    for start, plen, count, pattern in results:
        if start not in seen_starts or plen > seen_starts[start][1]:
            seen_starts[start] = (start, plen, count, pattern)
    return sorted(seen_starts.values())


def analyze_byte_distribution(data, name=""):
    """Statistical analysis of byte distribution."""
    from collections import Counter
    c = Counter(data)
    zeros = c.get(0, 0)
    ff = c.get(0xFF, 0)
    in_range = sum(v for k, v in c.items() if 1 <= k <= 127)
    hi_range = sum(v for k, v in c.items() if 128 <= k <= 254)
    print(f"  Byte distribution ({name}, {len(data)}B):")
    print(f"    0x00: {zeros} ({zeros*100/len(data):.0f}%)")
    print(f"    0x01-0x7F: {in_range} ({in_range*100/len(data):.0f}%)")
    print(f"    0x80-0xFE: {hi_range} ({hi_range*100/len(data):.0f}%)")
    print(f"    0xFF: {ff} ({ff*100/len(data):.0f}%)")
    # Most common non-zero values
    common = [(k, v) for k, v in c.most_common(20) if k != 0]
    print(f"    Most common (non-zero): {[(f'0x{k:02X}', v) for k, v in common[:10]]}")


def search_for_chord_roots(data):
    """Search for chord root encoding: G=7/55/67, C=0/48/60, Em=4/52/64, D=2/50/62."""
    # GT chord roots for Summer: G, C, E, D
    # As scale degree (0-11): G=7, C=0, E=4, D=2
    # As MIDI root: G3=55, C3=48, E3=52, D3=50  or  G4=67, C4=60, E4=64, D4=62
    print("\n  Chord root search:")

    # Search for [7,0,4,2] sequence (scale degrees)
    target_degrees = [7, 0, 4, 2]
    for i in range(len(data) - 3):
        if (data[i] == 7 and data[i+1] == 0 and
                data[i+2] == 4 and data[i+3] == 2):
            print(f"    FOUND scale degrees [7,0,4,2] at offset 0x{i:03X}")

    # Search for G,C,E,D as MIDI note sequences
    for base, label in [(55, "octave 3"), (67, "octave 4"), (43, "octave 2")]:
        targets = [base, base - 7, base - 3, base - 5]  # G, C, E, D relative
        # Actually: G=base, C=base-7, E=base-3, D=base-5 only for specific octaves
        pass

    # Better: search for any 4-byte window matching chord root pattern
    # G-C = -7 semitones, C-E = +4 semitones, E-D = -2 semitones
    diffs = [-7, 4, -2]
    for i in range(len(data) - 3):
        v = [data[i], data[i+1], data[i+2], data[i+3]]
        if all(1 <= x <= 127 for x in v):
            actual_diffs = [v[j+1] - v[j] for j in range(3)]
            if actual_diffs == diffs:
                notes = [nn(x) for x in v]
                print(f"    FOUND chord root pattern at 0x{i:03X}: "
                      f"{v} = {notes} (diffs={actual_diffs})")

    # Search for chord TYPE encoding: major=0, minor=1?
    # Summer chords: G=major, C=major, Em=minor, D=major → [0,0,1,0] or [1,1,0,1]
    for i in range(len(data) - 3):
        w = data[i:i+4]
        if list(w) == [0, 0, 1, 0]:
            print(f"    Possible chord types [maj,maj,min,maj] at 0x{i:03X}: {list(w)}")
        if list(w) == [1, 1, 0, 1]:
            print(f"    Possible chord types [inverted] at 0x{i:03X}: {list(w)}")

    # Also search for chord root as Yamaha chord code
    # Yamaha: root 0=C, 1=C#, ..., 7=G, 4=E, 2=D
    # So Summer = [G, C, E, D] = [7, 0, 4, 2]
    # With bar repetition (4 bars × sections), might appear multiple times
    for i in range(len(data) - 7):
        w = data[i:i+8]
        if list(w[:4]) == [7, 0, 4, 2] or list(w[::2]) == [7, 0, 4, 2]:
            print(f"    Possible Yamaha root codes at 0x{i:03X}: {list(w)}")


def search_for_groove_params(data):
    """Search for groove-related parameters."""
    print("\n  Groove parameter search:")

    # Known groove velocities from GT: [122,116,122,117,118,112,121,114]
    # These are 8th-note humanized velocities for RHY1
    # Look for the offsets: [0,-6,0,-5,-4,-10,-1,-8] relative to 122

    # Search for any 8-byte window with values in range 100-127
    for i in range(len(data) - 7):
        w = data[i:i+8]
        if all(100 <= b <= 127 for b in w):
            print(f"    Vel-range bytes at 0x{i:03X}: {list(w)}")

    # Search for groove strength or type byte
    # Common groove types: 16Beat, 8Beat, Shuffle, Swing
    # Might be encoded as a small integer (0-15 or similar)

    # Look for patterns that repeat every 8 bytes (8th note grid)
    for start in range(min(128, len(data))):
        if start + 64 > len(data):
            break
        vals = [data[start + j*8] for j in range(8) if start + j*8 < len(data)]
        if len(vals) == 8 and len(set(vals)) > 1 and all(0 < v < 128 for v in vals):
            # Check if these look like velocity modifiers
            mean = sum(vals) / len(vals)
            if 50 < mean < 127:
                spread = max(vals) - min(vals)
                if 5 <= spread <= 30:
                    print(f"    Possible groove template at 0x{start:03X} (stride=8): {vals}")


def search_for_tempo(data, raw_data):
    """Search for tempo encoding. Summer is 110 BPM."""
    print("\n  Tempo search (target: 110 BPM):")

    # Direct byte value
    for i, b in enumerate(data):
        if b == 110:
            ctx = data[max(0, i-2):i+3]
            print(f"    Byte 110 at 0x{i:03X}: context={list(ctx)}")

    # Yamaha tempo formula: raw[0]*95 - 133 + raw[1]
    # 110 = raw[0]*95 - 133 + raw[1]
    # If raw[0]=2: 2*95-133=57, raw[1]=53 → 110
    # If raw[0]=3: 3*95-133=152, too high unless raw[1] is negative
    for i in range(len(raw_data) - 1):
        tempo = raw_data[i] * 95 - 133 + raw_data[i+1]
        if tempo == 110:
            print(f"    Yamaha tempo formula at raw offset {i}: "
                  f"raw[{i}]={raw_data[i]}, raw[{i+1}]={raw_data[i+1]} → 110 BPM")

    # Also as 16-bit BE
    for i in range(len(data) - 1):
        val16 = (data[i] << 8) | data[i+1]
        if val16 == 110:
            print(f"    16-bit BE=110 at 0x{i:03X}")


def compare_headers(summer_data, kp_data):
    """Compare Summer vs known_pattern headers byte by byte."""
    print(f"\n{'='*70}")
    print(f"HEADER COMPARISON: Summer ({len(summer_data)}B) vs known_pattern ({len(kp_data)}B)")
    print(f"{'='*70}")

    min_len = min(len(summer_data), len(kp_data))
    diff_count = 0
    diff_regions = []
    current_region = None

    for i in range(min_len):
        if summer_data[i] != kp_data[i]:
            diff_count += 1
            if current_region is None:
                current_region = [i, i]
            else:
                if i - current_region[1] <= 2:
                    current_region[1] = i
                else:
                    diff_regions.append(tuple(current_region))
                    current_region = [i, i]
        else:
            if current_region is not None:
                diff_regions.append(tuple(current_region))
                current_region = None
    if current_region is not None:
        diff_regions.append(tuple(current_region))

    print(f"\n  Total differences: {diff_count}/{min_len} bytes "
          f"({diff_count*100/min_len:.1f}%)")
    print(f"  Difference regions: {len(diff_regions)}")

    for start, end in diff_regions:
        length = end - start + 1
        s_vals = summer_data[start:end+1]
        k_vals = kp_data[start:end+1]
        print(f"\n  0x{start:03X}-0x{end:03X} ({length}B):")
        print(f"    Summer:       {' '.join(f'{b:02X}' for b in s_vals)}")
        print(f"    known_pattern: {' '.join(f'{b:02X}' for b in k_vals)}")

        # Annotate if values look like notes, velocities, etc.
        for j, (sv, kv) in enumerate(zip(s_vals, k_vals)):
            offset = start + j
            diff = sv - kv
            annotation = ""
            if 0 < sv < 128:
                annotation += f" [{nn(sv)}]"
            if 0 < kv < 128:
                annotation += f" vs [{nn(kv)}]"
            if annotation:
                print(f"      0x{offset:03X}: {sv:3d} vs {kv:3d} (diff={diff:+d}){annotation}")


def analyze_section_structure(data):
    """Analyze if header has per-section or per-bar sub-structures."""
    print(f"\n  Section structure analysis:")

    # QY70 has 6 sections per pattern. If header stores per-section data,
    # we might see 6 repeating blocks.
    # 640 bytes / 6 sections = 106.67 → not evenly divisible
    # 640 bytes / 8 tracks = 80 → evenly divisible!
    # 640 bytes / 4 bars = 160 → evenly divisible!

    # Check for 80-byte track blocks
    for stride in [80, 64, 40, 32, 20, 16, 10, 8]:
        n_blocks = len(data) // stride
        if n_blocks < 4:
            continue
        # Count how many bytes are identical across blocks
        identical = 0
        for byte_pos in range(stride):
            vals = set()
            for block in range(min(n_blocks, 8)):
                offset = block * stride + byte_pos
                if offset < len(data):
                    vals.add(data[offset])
            if len(vals) == 1:
                identical += 1
        pct = identical * 100 / stride
        if pct > 20:  # Noteworthy
            print(f"    Stride {stride} ({n_blocks} blocks): "
                  f"{identical}/{stride} bytes constant ({pct:.0f}%)")

    # Check if specific offsets are always the same across sections
    # Pattern: maybe bytes 0-63 are global, then 64+ is per-section
    for split in [32, 64, 96, 128, 160, 256, 320, 384, 512]:
        if split >= len(data):
            break
        before = data[:split]
        after = data[split:]
        zeros_before = before.count(0)
        zeros_after = after.count(0) if after else 0
        pct_z_before = zeros_before * 100 / len(before)
        pct_z_after = zeros_after * 100 / len(after) if after else 0
        if abs(pct_z_before - pct_z_after) > 20:
            print(f"    Split at 0x{split:03X}: "
                  f"before {pct_z_before:.0f}% zeros, after {pct_z_after:.0f}% zeros")


def analyze_track_config_area(data):
    """Analyze bytes that could be per-track voice/channel config."""
    print(f"\n  Per-track config search:")

    # Known Summer tracks: RHY1(0), CHD1(3), CHD2(4), PAD(5), PHR1(6)
    # Empty: RHY2(1), BASS(2), PHR2(7)
    # Track activity bitmask: 01111001 = 0x79 if bits 0,3,4,5,6 set
    #                    or: 10000110 if inverted

    for i, b in enumerate(data):
        if b == 0x79:
            ctx = data[max(0, i-2):i+5]
            print(f"    0x79 (track mask?) at 0x{i:03X}: context={[f'0x{x:02X}' for x in ctx]}")
        if b == 0b01111001:
            pass  # same as 0x79
        # Also check individual bit patterns
        if b == 0b00111001:  # tracks 0,3,4,5
            ctx = data[max(0, i-2):i+5]
            print(f"    0x39 (partial mask?) at 0x{i:03X}: context={[f'0x{x:02X}' for x in ctx]}")

    # Search for MIDI channel assignments
    # Summer GT: ch9=RHY1, ch13=CHD1, ch14=CHD2, ch11=PAD, ch15=PHR1
    # As 0-indexed: 8, 12, 13, 10, 14
    # As sequence for tracks 0-7: [8, ?, ?, 12, 13, 10, 14, ?]
    target_chs = [8, 12, 13, 10, 14]  # channels for active tracks (0-indexed)
    for i in range(len(data) - 7):
        w = data[i:i+8]
        # Check if positions 0,3,4,5,6 match the channel assignments
        if (w[0] == 8 and w[3] == 12 and w[4] == 13 and
                w[5] == 10 and w[6] == 14):
            print(f"    MIDI channel map at 0x{i:03X}: {list(w)}")

    # Search for PATT OUT channel (9-16, stored as 8-15 or 1-8)
    for i in range(len(data) - 7):
        w = data[i:i+8]
        # PATT OUT 9-16 = channels 8-15 (0-indexed)
        if all(8 <= b <= 15 for b in w if b != 0):
            non_zero = [b for b in w if b != 0]
            if len(non_zero) >= 3:
                print(f"    PATT OUT range at 0x{i:03X}: {list(w)}")


def main():
    summer_path = "data/qy70_sysx/P -  Summer - 20231101.syx"
    kp_path = "data/qy70_sysx/ground_truth_style.syx"

    # Overview: all tracks present
    print("=" * 70)
    print("TRACK SIZE OVERVIEW")
    print("=" * 70)
    for path, name in [(summer_path, "Summer"), (kp_path, "known_pattern")]:
        if not os.path.exists(path):
            print(f"  {name}: FILE NOT FOUND")
            continue
        tracks = load_all_track_sizes(path)
        print(f"\n  {name}:")
        for al in sorted(tracks.keys()):
            section = al // 8
            track = al % 8
            sec_name = SECTION_NAMES.get(section, f"S{section}")
            trk_name = TRACK_NAMES.get(track, f"T{track}")
            if al == 0x7F:
                label = "HEADER"
            else:
                label = f"{sec_name}/{trk_name}"
            print(f"    AL=0x{al:02X} ({label}): {tracks[al]} bytes")

    # Load Summer header
    print(f"\n{'='*70}")
    print("SUMMER HEADER TRACK (AL=0x7F)")
    print("=" * 70)

    summer_hdr, summer_raw, summer_msgs = load_header_track(summer_path)
    print(f"  Messages: {summer_msgs}")
    print(f"  Decoded: {len(summer_hdr)} bytes")
    print(f"  Raw (7-bit): {len(summer_raw)} bytes")

    # Full hex dump in sections
    print(f"\n  FULL HEX DUMP:")
    print(hex_dump(summer_hdr))

    # Byte distribution
    analyze_byte_distribution(summer_hdr, "Summer header")

    # Section structure
    analyze_section_structure(summer_hdr)

    # Search for musical content
    search_for_chord_roots(summer_hdr)
    search_for_groove_params(summer_hdr)
    search_for_tempo(summer_hdr, summer_raw)
    analyze_track_config_area(summer_hdr)

    # Compare with known_pattern
    if os.path.exists(kp_path):
        kp_hdr, kp_raw, kp_msgs = load_header_track(kp_path)
        print(f"\n{'='*70}")
        print("KNOWN_PATTERN HEADER TRACK (AL=0x7F)")
        print("=" * 70)
        print(f"  Messages: {kp_msgs}")
        print(f"  Decoded: {len(kp_hdr)} bytes")
        print(f"\n  FULL HEX DUMP:")
        print(hex_dump(kp_hdr))

        analyze_byte_distribution(kp_hdr, "known_pattern header")

        compare_headers(summer_hdr, kp_hdr)
    else:
        print(f"\n  known_pattern file not found, skipping comparison")

    # Deep structural analysis: 8-byte blocks
    print(f"\n{'='*70}")
    print("8-BYTE BLOCK ANALYSIS (Summer)")
    print("=" * 70)
    for i in range(0, len(summer_hdr), 8):
        block = summer_hdr[i:i+8]
        if len(block) < 8:
            break
        # Classify block
        zeros = block.count(0)
        hex_str = " ".join(f"{b:02X}" for b in block)
        if zeros == 8:
            label = "[ALL ZERO]"
        elif zeros >= 6:
            label = "[MOSTLY ZERO]"
        elif all(b == block[0] for b in block):
            label = f"[UNIFORM 0x{block[0]:02X}]"
        else:
            # Check if values are MIDI notes
            if all(0 < b < 128 for b in block if b != 0):
                notes = [nn(b) if 0 < b < 128 else "." for b in block]
                label = f"[notes: {' '.join(notes)}]"
            else:
                label = ""
        print(f"  0x{i:03X}: {hex_str}  {label}")

    # Nibble analysis: some Yamaha formats pack 2 values per byte
    print(f"\n{'='*70}")
    print("NIBBLE ANALYSIS (Summer header, first 128 bytes)")
    print("=" * 70)
    for i in range(min(128, len(summer_hdr))):
        hi = (summer_hdr[i] >> 4) & 0x0F
        lo = summer_hdr[i] & 0x0F
        if summer_hdr[i] != 0:
            print(f"  0x{i:03X}: 0x{summer_hdr[i]:02X} = hi:{hi} lo:{lo}"
                  f"  (decimal: {summer_hdr[i]})")

    print("\nDone.")


if __name__ == "__main__":
    main()
