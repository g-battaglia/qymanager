#!/usr/bin/env python3
"""
Bass Slot Deep Analyzer — Comprehensive analysis of the BASS track (track index 2)
encoding in QY70 SysEx data.

Preamble bytes 24-27: 2B E3 60 00
Each section has 128 decoded bytes (1 SysEx message).
24-byte track header + 4-byte preamble = 28 bytes overhead, leaving ~100 bytes of event data.

Key questions:
- Does bass use 7-byte event groups like chord tracks?
- Does R=9 rotation apply?
- Does shift register (F1[i]==F0[i-1]) work?
- What do the DC delimiters separate?
- Why does the SGT bass slot have a drum voice (bytes 14-15 = 40 80)?
- S0=S1=S2=S3=S5 identical; S4 differs by ~26% — what changes?
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qymanager.formats.qy70.sysex_parser import SysExParser
from collections import Counter, defaultdict

NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
GM_DRUM_NAMES = {
    35: "Kick2",
    36: "Kick1",
    37: "SideStick",
    38: "Snare1",
    39: "Clap",
    40: "Snare2",
    41: "LowTom2",
    42: "HHClosed",
    43: "LowTom1",
    44: "HHPedal",
    45: "MidTom2",
    46: "HHOpen",
    47: "MidTom1",
    48: "HighTom2",
    49: "Crash1",
    50: "HighTom1",
    51: "Ride1",
    52: "China",
    53: "RideBell",
    54: "Tamb",
    55: "Splash",
    56: "Cowbell",
    57: "Crash2",
    59: "Ride2",
}
TRACK_NAMES = {0: "D1", 1: "D2", 2: "BASS", 3: "C1", 4: "C2", 5: "PC", 6: "C3", 7: "C4"}


def nn(n):
    """MIDI note to name."""
    if 0 <= n <= 127:
        return f"{NOTE_NAMES[n % 12]}{n // 12 - 1}"
    return f"?{n}"


def rot_left(val, shift, width=56):
    shift = shift % width
    return ((val << shift) | (val >> (width - shift))) & ((1 << width) - 1)


def rot_right(val, shift, width=56):
    return rot_left(val, width - shift, width)


def popcount(val):
    return bin(val).count("1")


def extract_field(val, msb, width, total_width=56):
    """Extract field of 'width' bits starting at bit position 'msb' (0=MSB)."""
    shift = total_width - msb - width
    if shift < 0:
        return -1
    return (val >> shift) & ((1 << width) - 1)


def bits_to_str(val, width=56):
    return format(val, f"0{width}b")


def hex_dump(data, prefix="    ", bytes_per_line=16):
    """Print hex dump of data."""
    for i in range(0, len(data), bytes_per_line):
        chunk = data[i : i + bytes_per_line]
        hex_str = " ".join(f"{b:02X}" for b in chunk)
        ascii_str = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
        print(f"{prefix}@{i:3d}: {hex_str:<{bytes_per_line * 3}}  |{ascii_str}|")


def get_all_bass_sections(syx_path):
    """Get decoded bass track data for all 6 sections."""
    parser = SysExParser()
    messages = parser.parse_file(syx_path)

    sections = {}
    for section in range(6):
        al = section * 8 + 2  # track index 2 = BASS
        data = b""
        for m in messages:
            if m.is_style_data and m.address_low == al:
                data += m.decoded_data
        if data:
            sections[section] = data
    return sections


def get_track_data(syx_path, section, track):
    """Get decoded data for a specific section/track."""
    parser = SysExParser()
    messages = parser.parse_file(syx_path)
    al = section * 8 + track
    data = b""
    for m in messages:
        if m.is_style_data and m.address_low == al:
            data += m.decoded_data
    return data


# ============================================================================
# PART 1: Track Header Analysis
# ============================================================================


def analyze_track_header(data, section_idx):
    """Decode the 24-byte track header."""
    if len(data) < 24:
        print(f"  S{section_idx}: too short ({len(data)} bytes)")
        return

    header = data[:24]
    print(f"\n  S{section_idx} Track Header ({len(data)} bytes total):")
    print(f"    Raw: {' '.join(f'{b:02X}' for b in header)}")

    # bytes 0-11: pattern/structure bytes
    pattern = header[0:12]
    print(f"    [00-11] Pattern:    {' '.join(f'{b:02X}' for b in pattern)}")

    # Check if pattern matches expected 08 04 82 01 00 40 20 08 04 82 01 00
    expected_pattern = bytes(
        [0x08, 0x04, 0x82, 0x01, 0x00, 0x40, 0x20, 0x08, 0x04, 0x82, 0x01, 0x00]
    )
    if pattern == expected_pattern:
        print(f"               → Matches expected pattern ✓")
    else:
        diff_pos = [i for i in range(12) if pattern[i] != expected_pattern[i]]
        print(f"               → DIFFERS at positions {diff_pos}")

    # bytes 12-13: unknown identifier
    b12, b13 = header[12], header[13]
    print(f"    [12-13] ID:         {b12:02X} {b13:02X} (dec: {b12}, {b13})")

    # bytes 14-15: voice encoding
    b14, b15 = header[14], header[15]
    # In XG: Bank MSB, Program Change (or special encoding)
    print(f"    [14-15] Voice:      {b14:02X} {b15:02X}")
    if b14 == 0x40 and b15 == 0x80:
        print(f"               → Drum voice! (Bank MSB=64, bit7 set)")
    elif b14 & 0x80:
        print(f"               → High bit set: bank MSB = {b14 & 0x7F}, prog = {b15}")
    else:
        print(f"               → Normal: bank MSB = {b14}, prog = {b15}")
        drum = GM_DRUM_NAMES.get(b15 & 0x7F, "")
        if drum:
            print(f"               → lo7 prog {b15 & 0x7F} = {drum}")

    # bytes 16-17: note range
    b16, b17 = header[16], header[17]
    print(f"    [16-17] Note range: {b16:02X} {b17:02X} = {nn(b16 & 0x7F)} to {nn(b17 & 0x7F)}")
    print(f"               → lo7: {b16 & 0x7F} to {b17 & 0x7F}")
    print(f"               → hi bits: {b16 >> 7}, {b17 >> 7}")

    # bytes 18-20: track type flags
    b18, b19, b20 = header[18], header[19], header[20]
    print(f"    [18-20] Type flags: {b18:02X} {b19:02X} {b20:02X}")
    print(f"               → bin: {b18:08b} {b19:08b} {b20:08b}")

    # bytes 21-22: pan flag + pan value
    b21, b22 = header[21], header[22]
    print(f"    [21-22] Pan:        {b21:02X} {b22:02X}")
    if b22 == 0x40:
        print(f"               → Center (64)")
    elif b22 < 0x40:
        print(f"               → Left {64 - b22}")
    else:
        print(f"               → Right {b22 - 64}")

    # byte 23: reserved
    b23 = header[23]
    print(f"    [23]    Reserved:   {b23:02X}")


# ============================================================================
# PART 2: Preamble and Event Data Structure
# ============================================================================


def analyze_event_structure(data, section_idx):
    """Analyze preamble and event data with DC delimiters."""
    if len(data) < 28:
        print(f"  S{section_idx}: too short for event data")
        return

    preamble = data[24:28]
    event_data = data[28:]

    print(f"\n  S{section_idx} Preamble: {' '.join(f'{b:02X}' for b in preamble)}")
    print(
        f"    Byte 0-1: {preamble[0]:02X} {preamble[1]:02X} (identifier 0x{preamble[0]:02X}{preamble[1]:02X})"
    )
    print(f"    Byte 2:   {preamble[2]:02X} (= {preamble[2]})")
    print(f"    Byte 3:   {preamble[3]:02X} (= {preamble[3]})")

    print(f"\n  S{section_idx} Event Data: {len(event_data)} bytes")

    # Find DC positions
    dc_pos = [i for i, b in enumerate(event_data) if b == 0xDC]
    print(f"    DC (0xDC) positions: {dc_pos}")
    print(f"    Number of DCs: {len(dc_pos)}")

    # Show full event data hex dump
    print(f"    Full event data hex dump:")
    hex_dump(event_data, prefix="      ")

    # Split by DC into segments
    segments = []
    prev = 0
    for dp in dc_pos:
        segments.append(event_data[prev:dp])
        prev = dp + 1
    segments.append(event_data[prev:])

    print(f"\n    Segments (split by DC): {len(segments)}")
    for seg_idx, seg in enumerate(segments):
        print(f"\n    --- Segment {seg_idx}: {len(seg)} bytes ---")
        print(f"        Raw: {' '.join(f'{b:02X}' for b in seg)}")

        if len(seg) == 0:
            print(f"        (empty)")
            continue

        # Check if 7-byte groups present
        full_groups = len(seg) // 7
        remainder = len(seg) % 7
        print(f"        7-byte groups: {full_groups} complete + {remainder} remainder")

        # Show as 7-byte groups
        for g in range(0, len(seg), 7):
            chunk = seg[g : g + 7]
            hex_str = " ".join(f"{b:02X}" for b in chunk)
            if len(chunk) == 7:
                bit7 = "".join(str((b >> 7) & 1) for b in chunk)
                lo7 = [b & 0x7F for b in chunk]
                val_56 = int.from_bytes(chunk, "big")
                notes = [nn(v) for v in lo7 if 24 <= v <= 72]
                note_str = " ".join(notes) if notes else ""
                print(f"          G{g // 7} @{g:3d}: {hex_str}  b7={bit7}  lo7={lo7}  {note_str}")
            else:
                print(f"          G{g // 7} @{g:3d}: {hex_str}  (partial: {len(chunk)} bytes)")

        # Check for 13-byte header + 4×7-byte events = 41 bytes structure (chord-like)
        if len(seg) >= 41:
            hdr13 = seg[:13]
            print(f"\n        If chord-like (13+4×7=41):")
            print(f"          Header 13B: {' '.join(f'{b:02X}' for b in hdr13)}")
            for ei in range(4):
                start = 13 + ei * 7
                end = start + 7
                if end <= len(seg):
                    evt = seg[start:end]
                    print(f"          Event {ei}:    {' '.join(f'{b:02X}' for b in evt)}")

        # Check for alternative structures
        # Try 2-byte, 3-byte, 4-byte, 5-byte, 6-byte groupings
        for gsize in [3, 4, 5, 6]:
            ngroups = len(seg) // gsize
            rem = len(seg) % gsize
            if ngroups >= 3 and rem <= 2:
                print(f"\n        As {gsize}-byte groups ({ngroups} groups + {rem} remainder):")
                for g in range(min(ngroups, 8)):
                    chunk = seg[g * gsize : (g + 1) * gsize]
                    hex_str = " ".join(f"{b:02X}" for b in chunk)
                    lo7 = [b & 0x7F for b in chunk]
                    print(f"          G{g} @{g * gsize}: {hex_str}  lo7={lo7}")


# ============================================================================
# PART 3: 9-bit field extraction
# ============================================================================


def analyze_9bit_fields(data, section_idx):
    """Extract 9-bit fields from event data (56 bits = 6×9 + 2 remainder)."""
    if len(data) < 28:
        return

    event_data = data[28:]

    # Split by DC
    dc_pos = [i for i, b in enumerate(event_data) if b == 0xDC]
    segments = []
    prev = 0
    for dp in dc_pos:
        segments.append(event_data[prev:dp])
        prev = dp + 1
    segments.append(event_data[prev:])

    print(f"\n  S{section_idx} 9-bit Field Analysis:")

    for seg_idx, seg in enumerate(segments):
        if len(seg) < 7:
            continue

        print(f"\n    Segment {seg_idx} ({len(seg)} bytes):")

        # Extract 7-byte groups
        groups = []
        for g in range(0, len(seg) - 6, 7):
            chunk = seg[g : g + 7]
            if len(chunk) == 7:
                groups.append(chunk)

        if not groups:
            continue

        # For each 7-byte group, extract 9-bit fields (56 bits = 6×9 + 2)
        for gi, group in enumerate(groups):
            val = int.from_bytes(group, "big")
            fields = []
            for fi in range(6):
                f = extract_field(val, fi * 9, 9, 56)
                fields.append(f)
            remainder = extract_field(val, 54, 2, 56)

            hex_str = " ".join(f"{b:02X}" for b in group)
            field_str = " ".join(f"F{fi}={f:3d}(0b{f:09b})" for fi, f in enumerate(fields))
            print(f"      G{gi}: [{hex_str}]")
            print(f"           {field_str} R={remainder:02b}")

            # Decompose F3: hi2|mid3|lo4
            f3 = fields[3]
            f3_hi2 = (f3 >> 7) & 0x3
            f3_mid3 = (f3 >> 4) & 0x7
            f3_lo4 = f3 & 0xF
            beat_map = {1: "beat1", 2: "beat2", 4: "beat3", 8: "beat4"}
            beat = beat_map.get(f3_lo4, f"?{f3_lo4}")
            print(f"           F3 decomp: hi2={f3_hi2} mid3={f3_mid3} lo4={f3_lo4:04b}({beat})")

            # Decompose F4: mask5|param4 (or hi5|lo4)
            f4 = fields[4]
            f4_hi5 = (f4 >> 4) & 0x1F
            f4_lo4 = f4 & 0xF
            f4_hi4 = (f4 >> 5) & 0xF
            f4_lo5 = f4 & 0x1F
            print(
                f"           F4 decomp: hi5={f4_hi5:05b}|lo4={f4_lo4:04b}  OR  hi4={f4_hi4:04b}|lo5={f4_lo5:05b}"
            )

            # Decompose F5
            f5 = fields[5]
            f5_hi4 = (f5 >> 5) & 0xF
            f5_lo5 = f5 & 0x1F
            f5_hi5 = (f5 >> 4) & 0x1F
            f5_lo4 = f5 & 0xF
            print(
                f"           F5 decomp: hi4={f5_hi4:04b}|lo5={f5_lo5:05b}  OR  hi5={f5_hi5:05b}|lo4={f5_lo4:04b}"
            )

            # Check if fields are in MIDI note range
            for fi, f in enumerate(fields):
                if 24 <= f <= 96:
                    print(f"           F{fi}={f} is in MIDI note range: {nn(f)}")
                if 24 <= (f & 0x7F) <= 96 and f != (f & 0x7F):
                    print(f"           F{fi} lo7={f & 0x7F} is in MIDI note range: {nn(f & 0x7F)}")


# ============================================================================
# PART 4: R=9 De-rotation Analysis
# ============================================================================


def analyze_derotation(data, section_idx):
    """Apply R=9 de-rotation to consecutive 7-byte events."""
    if len(data) < 28:
        return

    event_data = data[28:]
    dc_pos = [i for i, b in enumerate(event_data) if b == 0xDC]

    segments = []
    prev = 0
    for dp in dc_pos:
        segments.append(event_data[prev:dp])
        prev = dp + 1
    segments.append(event_data[prev:])

    print(f"\n  S{section_idx} De-rotation Analysis (R=9):")

    for seg_idx, seg in enumerate(segments):
        if len(seg) < 14:  # Need at least 2 groups
            continue

        groups = []
        for g in range(0, len(seg) - 6, 7):
            chunk = seg[g : g + 7]
            if len(chunk) == 7:
                groups.append(int.from_bytes(chunk, "big"))

        if len(groups) < 2:
            continue

        print(f"\n    Segment {seg_idx}: {len(groups)} groups")

        # Test various rotation amounts
        best_r_scores = {}
        for R in range(1, 56):
            total_diff = 0
            for i in range(len(groups) - 1):
                rotated = rot_left(groups[i], R)
                xor = rotated ^ groups[i + 1]
                total_diff += popcount(xor)
            avg_diff = total_diff / (len(groups) - 1)
            best_r_scores[R] = avg_diff

        # Show top 5 best rotations
        sorted_r = sorted(best_r_scores.items(), key=lambda x: x[1])
        print(f"      Top 5 best rotations:")
        for R, score in sorted_r[:5]:
            print(f"        R={R:2d}: avg {score:.1f} bits differ")

        # Apply R=9 de-rotation
        R = 9
        derotated = [rot_right(v, i * R) for i, v in enumerate(groups)]

        print(f"\n      R=9 De-rotated values:")
        for i, (orig, derot) in enumerate(zip(groups, derotated)):
            orig_hex = format(orig, "014X")
            derot_hex = format(derot, "014X")
            derot_bin = bits_to_str(derot, 56)
            print(f"        E{i}: orig=0x{orig_hex} derot=0x{derot_hex}")
            print(f"             derot_bin={derot_bin}")

            # Extract 9-bit fields from de-rotated
            fields = [extract_field(derot, fi * 9, 9, 56) for fi in range(6)]
            r_bits = extract_field(derot, 54, 2, 56)
            field_str = " ".join(f"F{fi}={f:3d}" for fi, f in enumerate(fields))
            print(f"             9-bit fields: {field_str} R={r_bits}")

        # Check shift register: F1[i] == F0[i-1] ?
        print(f"\n      Shift register check (F1[i]==F0[i-1]):")
        for i in range(1, len(derotated)):
            f0_prev = extract_field(derotated[i - 1], 0, 9, 56)
            f1_curr = extract_field(derotated[i], 9, 9, 56)
            match = "✓ MATCH" if f0_prev == f1_curr else f"✗ differ ({f0_prev} vs {f1_curr})"
            print(f"        E{i - 1}→E{i}: F0[{i - 1}]={f0_prev}, F1[{i}]={f1_curr} → {match}")

        # Also check F2[i]==F1[i-1]
        print(f"\n      Extended shift check (F2[i]==F1[i-1]):")
        for i in range(1, len(derotated)):
            f1_prev = extract_field(derotated[i - 1], 9, 9, 56)
            f2_curr = extract_field(derotated[i], 18, 9, 56)
            match = "✓ MATCH" if f1_prev == f2_curr else f"✗ differ ({f1_prev} vs {f2_curr})"
            print(f"        E{i - 1}→E{i}: F1[{i - 1}]={f1_prev}, F2[{i}]={f2_curr} → {match}")

        # Check pairwise XOR in de-rotated space
        if len(derotated) >= 2:
            print(f"\n      Pairwise XOR (de-rotated):")
            for i in range(len(derotated)):
                for j in range(i + 1, min(len(derotated), i + 3)):
                    xor = derotated[i] ^ derotated[j]
                    diff_bits = popcount(xor)
                    diff_pos = [b for b in range(56) if (xor >> (55 - b)) & 1]
                    print(f"        E{i}^E{j}: {diff_bits} bits at {diff_pos}")


# ============================================================================
# PART 5: F3 Decomposition (beat counter analysis)
# ============================================================================


def analyze_f3_beat_counter(sections_data):
    """Analyze F3 low-4-bit one-hot beat counter hypothesis across all sections."""
    print("\n" + "=" * 80)
    print("PART 5: F3 BEAT COUNTER ANALYSIS (lo4 one-hot)")
    print("=" * 80)

    for sec_idx, data in sections_data.items():
        if len(data) < 28:
            continue

        event_data = data[28:]
        dc_pos = [i for i, b in enumerate(event_data) if b == 0xDC]

        segments = []
        prev = 0
        for dp in dc_pos:
            segments.append(event_data[prev:dp])
            prev = dp + 1
        segments.append(event_data[prev:])

        print(f"\n  S{sec_idx}:")
        for seg_idx, seg in enumerate(segments):
            groups = []
            for g in range(0, len(seg) - 6, 7):
                chunk = seg[g : g + 7]
                if len(chunk) == 7:
                    groups.append(int.from_bytes(chunk, "big"))

            if not groups:
                continue

            # De-rotate with R=9
            derotated = [rot_right(v, i * 9) for i, v in enumerate(groups)]

            beat_matches = 0
            total = 0
            for i, derot in enumerate(derotated):
                f3 = extract_field(derot, 27, 9, 56)  # F3 at position 3*9=27
                f3_lo4 = f3 & 0xF
                expected_beat = 1 << (i % 4)
                is_beat = f3_lo4 == expected_beat
                if is_beat:
                    beat_matches += 1
                total += 1

            pct = beat_matches / total * 100 if total else 0
            print(f"    Seg{seg_idx}: {beat_matches}/{total} beat matches ({pct:.0f}%)")

            # Show actual F3 lo4 values
            lo4_vals = []
            for i, derot in enumerate(derotated):
                f3 = extract_field(derot, 27, 9, 56)
                lo4_vals.append(f3 & 0xF)
            print(f"      F3 lo4 values: {[f'{v:04b}' for v in lo4_vals]}")


# ============================================================================
# PART 6: S0 vs S4 Detailed Comparison
# ============================================================================


def compare_s0_vs_s4(sections_data):
    """Compare S0 and S4 byte-by-byte to understand what differs."""
    print("\n" + "=" * 80)
    print("PART 6: S0 vs S4 BYTE-BY-BYTE COMPARISON")
    print("=" * 80)

    if 0 not in sections_data or 4 not in sections_data:
        print("  Missing S0 or S4 data")
        return

    s0 = sections_data[0]
    s4 = sections_data[4]

    print(f"  S0: {len(s0)} bytes")
    print(f"  S4: {len(s4)} bytes")

    min_len = min(len(s0), len(s4))

    # Find all differing byte positions
    diff_positions = []
    for i in range(min_len):
        if s0[i] != s4[i]:
            diff_positions.append(i)

    print(
        f"\n  Total differing bytes: {len(diff_positions)} / {min_len} ({len(diff_positions) / min_len * 100:.1f}%)"
    )
    print(f"  Diff positions: {diff_positions}")

    # Show each difference with context
    print(f"\n  Detailed differences:")
    region_names = {
        (0, 12): "Pattern bytes",
        (12, 14): "ID",
        (14, 16): "Voice",
        (16, 18): "Note range",
        (18, 21): "Type flags",
        (21, 23): "Pan",
        (23, 24): "Reserved",
        (24, 28): "Preamble",
    }

    for pos in diff_positions:
        region = "Event data"
        for (start, end), name in region_names.items():
            if start <= pos < end:
                region = name
                break
        if pos >= 28:
            region = f"Event data @{pos - 28}"

        s0_val = s0[pos]
        s4_val = s4[pos]
        xor = s0_val ^ s4_val
        print(
            f"    @{pos:3d} ({region:20s}): S0=0x{s0_val:02X}({s0_val:3d}) S4=0x{s4_val:02X}({s4_val:3d}) XOR=0x{xor:02X}({xor:08b})"
        )

    # Check track header differences
    print(f"\n  Track header comparison:")
    print(f"    S0 header: {' '.join(f'{b:02X}' for b in s0[:24])}")
    print(f"    S4 header: {' '.join(f'{b:02X}' for b in s4[:24])}")
    hdr_same = s0[:24] == s4[:24]
    print(f"    Headers identical: {hdr_same}")

    # Check preamble differences
    print(f"\n  Preamble comparison:")
    print(f"    S0 preamble: {' '.join(f'{b:02X}' for b in s0[24:28])}")
    print(f"    S4 preamble: {' '.join(f'{b:02X}' for b in s4[24:28])}")

    # Compare event data segment by segment
    s0_events = s0[28:]
    s4_events = s4[28:]

    # Get DC positions for both
    s0_dc = [i for i, b in enumerate(s0_events) if b == 0xDC]
    s4_dc = [i for i, b in enumerate(s4_events) if b == 0xDC]
    print(f"\n  DC positions: S0={s0_dc}, S4={s4_dc}")
    print(f"  DC positions same: {s0_dc == s4_dc}")

    # Split and compare segments
    def split_by_dc(event_data, dc_positions):
        segments = []
        prev = 0
        for dp in dc_positions:
            segments.append(event_data[prev:dp])
            prev = dp + 1
        segments.append(event_data[prev:])
        return segments

    s0_segs = split_by_dc(s0_events, s0_dc)
    s4_segs = split_by_dc(s4_events, s4_dc)

    for seg_idx in range(max(len(s0_segs), len(s4_segs))):
        s0_seg = s0_segs[seg_idx] if seg_idx < len(s0_segs) else b""
        s4_seg = s4_segs[seg_idx] if seg_idx < len(s4_segs) else b""

        if s0_seg == s4_seg:
            print(f"\n    Segment {seg_idx}: IDENTICAL ({len(s0_seg)} bytes)")
        else:
            diff_count = sum(
                1 for i in range(min(len(s0_seg), len(s4_seg))) if s0_seg[i] != s4_seg[i]
            )
            print(
                f"\n    Segment {seg_idx}: {diff_count} bytes differ (S0={len(s0_seg)}B, S4={len(s4_seg)}B)"
            )
            print(f"      S0: {' '.join(f'{b:02X}' for b in s0_seg)}")
            print(f"      S4: {' '.join(f'{b:02X}' for b in s4_seg)}")

            # Show XOR
            min_seg = min(len(s0_seg), len(s4_seg))
            xor_bytes = bytes(s0_seg[i] ^ s4_seg[i] for i in range(min_seg))
            xor_str = " ".join(f"{b:02X}" for b in xor_bytes)
            print(f"      XOR: {xor_str}")

            # Show as 7-byte groups side by side
            for g in range(0, max(len(s0_seg), len(s4_seg)), 7):
                s0_chunk = s0_seg[g : g + 7] if g < len(s0_seg) else b""
                s4_chunk = s4_seg[g : g + 7] if g < len(s4_seg) else b""
                s0_hex = " ".join(f"{b:02X}" for b in s0_chunk) if s0_chunk else "(none)"
                s4_hex = " ".join(f"{b:02X}" for b in s4_chunk) if s4_chunk else "(none)"
                same = "=" if s0_chunk == s4_chunk else "≠"
                print(f"        G{g // 7} @{g}: S0=[{s0_hex}] {same} S4=[{s4_hex}]")


# ============================================================================
# PART 7: Cross-section Comparison (All pairs)
# ============================================================================


def cross_section_comparison(sections_data):
    """Compare all section pairs to confirm which are identical."""
    print("\n" + "=" * 80)
    print("PART 7: CROSS-SECTION COMPARISON MATRIX")
    print("=" * 80)

    sec_indices = sorted(sections_data.keys())
    print(f"  Available sections: {sec_indices}")

    # Comparison matrix
    print(f"\n  Byte-level difference matrix:")
    print(f"        ", end="")
    for j in sec_indices:
        print(f"  S{j:d}  ", end="")
    print()

    for i in sec_indices:
        print(f"    S{i}: ", end="")
        for j in sec_indices:
            if i == j:
                print(f"  --  ", end="")
            else:
                d1 = sections_data[i]
                d2 = sections_data[j]
                min_len = min(len(d1), len(d2))
                diff_count = sum(1 for k in range(min_len) if d1[k] != d2[k])
                print(f" {diff_count:3d}  ", end="")
        print()

    # Identify unique groups
    groups = defaultdict(list)
    for i in sec_indices:
        found_group = None
        for g, members in groups.items():
            ref = sections_data[members[0]]
            cur = sections_data[i]
            if len(ref) == len(cur) and ref == cur:
                found_group = g
                break
        if found_group is not None:
            groups[found_group].append(i)
        else:
            groups[i].append(i)

    print(f"\n  Identical groups:")
    for g, members in groups.items():
        print(f"    Group {g}: {['S' + str(m) for m in members]}")


# ============================================================================
# PART 8: Compare with Chord Track Structure
# ============================================================================


def compare_with_chord_tracks(syx_path, sections_data):
    """Check if bass uses the same structure as chord tracks (13-byte header + 4×7-byte events)."""
    print("\n" + "=" * 80)
    print("PART 8: STRUCTURAL COMPARISON WITH CHORD TRACKS")
    print("=" * 80)

    # Get chord track C2 for reference
    c2 = get_track_data(syx_path, 0, 4)
    bass = sections_data.get(0, b"")

    if not c2 or not bass:
        print("  Missing data")
        return

    print(f"  C2 (chord): {len(c2)} bytes")
    print(f"  BASS:       {len(bass)} bytes")

    # Compare preambles
    c2_preamble = c2[24:28] if len(c2) >= 28 else b""
    bass_preamble = bass[24:28] if len(bass) >= 28 else b""
    print(f"\n  Preambles:")
    print(f"    C2:   {' '.join(f'{b:02X}' for b in c2_preamble)}")
    print(f"    BASS: {' '.join(f'{b:02X}' for b in bass_preamble)}")

    # Compare DC structure
    c2_events = c2[28:] if len(c2) >= 28 else b""
    bass_events = bass[28:] if len(bass) >= 28 else b""

    c2_dc = [i for i, b in enumerate(c2_events) if b == 0xDC]
    bass_dc = [i for i, b in enumerate(bass_events) if b == 0xDC]

    print(f"\n  DC positions:")
    print(f"    C2 ({len(c2_events)}B): {c2_dc}")
    print(f"    BASS ({len(bass_events)}B): {bass_dc}")

    # Compare segment sizes
    def get_seg_sizes(event_data, dc_positions):
        sizes = []
        prev = 0
        for dp in dc_positions:
            sizes.append(dp - prev)
            prev = dp + 1
        sizes.append(len(event_data) - prev)
        return sizes

    c2_sizes = get_seg_sizes(c2_events, c2_dc)
    bass_sizes = get_seg_sizes(bass_events, bass_dc)

    print(f"\n  Segment sizes:")
    print(f"    C2:   {c2_sizes}")
    print(f"    BASS: {bass_sizes}")

    # Check if chord 41-byte structure applies
    print(f"\n  41-byte structure check (13-hdr + 4×7-byte events):")
    for seg_idx, size in enumerate(bass_sizes):
        if size == 41:
            print(f"    BASS Seg {seg_idx}: {size} bytes → ✓ matches chord structure!")
        elif size > 0:
            n_events = (size - 13) / 7 if size > 13 else 0
            print(
                f"    BASS Seg {seg_idx}: {size} bytes → {n_events:.1f} events (not exactly chord-like)"
            )

    # Also compare ALL tracks side by side
    print(f"\n  All tracks overview (section 0):")
    for track_idx in range(8):
        tdata = get_track_data(syx_path, 0, track_idx)
        if len(tdata) < 28:
            print(
                f"    {TRACK_NAMES.get(track_idx, f'T{track_idx}')}: {len(tdata)} bytes (too short)"
            )
            continue
        te = tdata[28:]
        tdc = [i for i, b in enumerate(te) if b == 0xDC]
        t_sizes = get_seg_sizes(te, tdc)
        preamble = tdata[24:28]
        print(
            f"    {TRACK_NAMES.get(track_idx, f'T{track_idx}'):4s}: {len(tdata):4d}B total, "
            f"preamble={' '.join(f'{b:02X}' for b in preamble)}, "
            f"event={len(te):3d}B, DCs@{tdc}, seg_sizes={t_sizes}"
        )


# ============================================================================
# PART 9: Continuous Bitstream Analysis
# ============================================================================


def continuous_bitstream_analysis(sections_data):
    """Treat entire event data as continuous bitstream with 9-bit fields."""
    print("\n" + "=" * 80)
    print("PART 9: CONTINUOUS BITSTREAM ANALYSIS (9-bit fields)")
    print("=" * 80)

    for sec_idx in [0, 4]:
        data = sections_data.get(sec_idx)
        if not data or len(data) < 28:
            continue

        event_data = data[28:]
        total_bits = len(event_data) * 8
        bs = int.from_bytes(event_data, "big")

        print(f"\n  S{sec_idx}: {len(event_data)} bytes = {total_bits} bits")
        print(f"  9-bit fields ({total_bits // 9} complete + {total_bits % 9} remainder):")

        for i in range(total_bits // 9):
            val = extract_field(bs, i * 9, 9, total_bits)
            lo7 = val & 0x7F
            note = nn(lo7) if 0 <= lo7 <= 127 else ""
            bass_range = " <<BASS" if 24 <= lo7 <= 60 else ""
            drum_name = GM_DRUM_NAMES.get(val, "")
            drum_tag = f" <<DRUM({drum_name})" if drum_name else ""
            is_dc = " <<DC" if val == 0xDC else ""
            print(
                f"    F{i:2d} @{i * 9:3d}: {val:3d} (0x{val:03X}, 0b{val:09b}) lo7={lo7:3d}({note}){bass_range}{drum_tag}{is_dc}"
            )


# ============================================================================
# PART 10: Byte Position Analysis (what changes vs what's fixed)
# ============================================================================


def byte_position_analysis(sections_data):
    """For each byte position, check variance across sections."""
    print("\n" + "=" * 80)
    print("PART 10: BYTE POSITION VARIANCE ANALYSIS")
    print("=" * 80)

    sec_indices = sorted(sections_data.keys())
    max_len = max(len(sections_data[s]) for s in sec_indices)

    # Classify each byte position
    fixed_bytes = []
    variable_bytes = []

    for pos in range(max_len):
        vals = set()
        for s in sec_indices:
            d = sections_data[s]
            if pos < len(d):
                vals.add(d[pos])
        if len(vals) == 1:
            fixed_bytes.append(pos)
        else:
            variable_bytes.append((pos, vals))

    print(f"  Fixed bytes: {len(fixed_bytes)} / {max_len}")
    print(f"  Variable bytes: {len(variable_bytes)} / {max_len}")

    if variable_bytes:
        print(f"\n  Variable byte positions:")
        for pos, vals in variable_bytes:
            vals_str = ", ".join(f"0x{v:02X}" for v in sorted(vals))
            region = "header" if pos < 24 else "preamble" if pos < 28 else f"event@{pos - 28}"
            print(f"    @{pos:3d} ({region:15s}): {vals_str}")


# ============================================================================
# PART 11: F4/F5 Chord-Tone Mask Analysis
# ============================================================================


def analyze_chord_tone_mask(sections_data):
    """Check if F4 contains chord-tone mask (like chord tracks) or something else for bass."""
    print("\n" + "=" * 80)
    print("PART 11: F4/F5 MASK & TIMING ANALYSIS")
    print("=" * 80)

    for sec_idx in [0, 4]:
        data = sections_data.get(sec_idx)
        if not data or len(data) < 35:
            continue

        event_data = data[28:]
        dc_pos = [i for i, b in enumerate(event_data) if b == 0xDC]

        segments = []
        prev = 0
        for dp in dc_pos:
            segments.append(event_data[prev:dp])
            prev = dp + 1
        segments.append(event_data[prev:])

        print(f"\n  S{sec_idx}:")

        for seg_idx, seg in enumerate(segments):
            groups = []
            for g in range(0, len(seg) - 6, 7):
                chunk = seg[g : g + 7]
                if len(chunk) == 7:
                    groups.append(int.from_bytes(chunk, "big"))

            if not groups:
                continue

            # De-rotate
            derotated = [rot_right(v, i * 9) for i, v in enumerate(groups)]

            print(f"\n    Segment {seg_idx}: {len(groups)} groups")
            print(
                f"      {'Evt':>3} {'F0':>5} {'F1':>5} {'F2':>5} {'F3':>5} {'F4':>5}  F4bin     {'F5':>5}  F5bin     R"
            )

            for i, derot in enumerate(derotated):
                fields = [extract_field(derot, fi * 9, 9, 56) for fi in range(6)]
                r_bits = extract_field(derot, 54, 2, 56)
                f4_bin = format(fields[4], "09b")
                f5_bin = format(fields[5], "09b")
                print(
                    f"      E{i:2d} {fields[0]:5d} {fields[1]:5d} {fields[2]:5d} "
                    f"{fields[3]:5d} {fields[4]:5d}  {f4_bin} {fields[5]:5d}  {f5_bin} {r_bits:2d}"
                )

            # Check for patterns in F4 across events
            f4_vals = [extract_field(d, 36, 9, 56) for d in derotated]
            f4_unique = sorted(set(f4_vals))
            print(f"\n      F4 unique values: {f4_unique}")
            print(f"      F4 as bins: {[format(v, '09b') for v in f4_unique]}")

            # Check popcount of F4 values (chord-tone mask would have specific bit counts)
            for v in f4_unique:
                pc = popcount(v)
                print(f"        F4={v:3d} (0b{v:09b}): popcount={pc}")

            # F5 analysis
            f5_vals = [extract_field(d, 45, 9, 56) for d in derotated]
            f5_unique = sorted(set(f5_vals))
            print(f"\n      F5 unique values: {f5_unique}")

            # Check if F5 encodes timing/position
            # Bass would have quarter note, eighth note patterns
            # Check if F5 values correspond to tick positions
            for v in f5_unique:
                # PPQN=120: quarter=120, eighth=60, sixteenth=30
                if v > 0:
                    pct_bar = v / 480 * 100 if v < 480 else 0
                    print(f"        F5={v:3d}: {pct_bar:.1f}% of bar (if ticks)")


# ============================================================================
# PART 12: Summary
# ============================================================================


def print_summary(sections_data, syx_path):
    """Print comprehensive summary of findings."""
    print("\n" + "=" * 80)
    print("COMPREHENSIVE SUMMARY")
    print("=" * 80)

    s0 = sections_data.get(0, b"")

    print(f"\n  1. DATA SIZE:")
    for sec_idx, data in sorted(sections_data.items()):
        print(f"     S{sec_idx}: {len(data)} bytes ({len(data) - 28} event bytes)")

    print(f"\n  2. TRACK HEADER:")
    if s0:
        header = s0[:24]
        print(f"     Pattern bytes [0-11]: {' '.join(f'{b:02X}' for b in header[:12])}")
        print(f"     ID [12-13]: {header[12]:02X} {header[13]:02X}")
        print(
            f"     Voice [14-15]: {header[14]:02X} {header[15]:02X} ({'DRUM' if header[14] == 0x40 and header[15] == 0x80 else 'Normal'})"
        )
        print(f"     Note range [16-17]: {header[16]:02X} {header[17]:02X}")
        print(f"     Type flags [18-20]: {header[18]:02X} {header[19]:02X} {header[20]:02X}")
        print(f"     Pan [21-22]: {header[21]:02X} {header[22]:02X}")
        print(f"     Reserved [23]: {header[23]:02X}")

    print(f"\n  3. PREAMBLE:")
    if s0:
        preamble = s0[24:28]
        print(f"     {' '.join(f'{b:02X}' for b in preamble)} (expected: 2B E3 60 00)")

    print(f"\n  4. EVENT DATA STRUCTURE:")
    if s0:
        event_data = s0[28:]
        dc_pos = [i for i, b in enumerate(event_data) if b == 0xDC]
        print(f"     Total event bytes: {len(event_data)}")
        print(f"     DC positions: {dc_pos}")

        segments = []
        prev = 0
        for dp in dc_pos:
            segments.append(event_data[prev:dp])
            prev = dp + 1
        segments.append(event_data[prev:])

        for seg_idx, seg in enumerate(segments):
            n_groups = len(seg) // 7
            rem = len(seg) % 7
            print(f"     Segment {seg_idx}: {len(seg)} bytes = {n_groups}×7 + {rem}")

    print(f"\n  5. SECTION IDENTITY:")
    sec_indices = sorted(sections_data.keys())
    for i in sec_indices:
        for j in sec_indices:
            if j <= i:
                continue
            d1 = sections_data[i]
            d2 = sections_data[j]
            if d1 == d2:
                print(f"     S{i} == S{j}")
            else:
                diff = sum(1 for k in range(min(len(d1), len(d2))) if d1[k] != d2[k])
                print(f"     S{i} != S{j} ({diff} bytes differ)")

    print(f"\n  6. ROTATION ANALYSIS:")
    if s0 and len(s0) >= 35:
        event_data = s0[28:]
        dc_pos = [i for i, b in enumerate(event_data) if b == 0xDC]
        seg0 = event_data[: dc_pos[0]] if dc_pos else event_data

        groups = []
        for g in range(0, len(seg0) - 6, 7):
            chunk = seg0[g : g + 7]
            if len(chunk) == 7:
                groups.append(int.from_bytes(chunk, "big"))

        if len(groups) >= 2:
            # Test rotations
            for R in [7, 8, 9, 10, 11]:
                total_diff = 0
                for i in range(len(groups) - 1):
                    rotated = rot_left(groups[i], R)
                    xor = rotated ^ groups[i + 1]
                    total_diff += popcount(xor)
                avg = total_diff / (len(groups) - 1)
                marker = " ← BEST" if R == 9 else ""
                print(f"     R={R:2d}: avg {avg:.1f} bits differ{marker}")


# ============================================================================
# MAIN
# ============================================================================


def main():
    syx_path = sys.argv[1] if len(sys.argv) > 1 else "tests/fixtures/QY70_SGT.syx"

    print("=" * 80)
    print("BASS SLOT (Track Index 2) DEEP ANALYSIS")
    print(f"Source: {syx_path}")
    print("=" * 80)

    # Verify file exists
    if not os.path.exists(syx_path):
        print(f"ERROR: File not found: {syx_path}")
        sys.exit(1)

    # Get all bass section data
    sections_data = get_all_bass_sections(syx_path)
    print(f"\nFound bass data for sections: {sorted(sections_data.keys())}")
    for sec_idx, data in sorted(sections_data.items()):
        print(f"  S{sec_idx}: {len(data)} bytes")

    # ── PART 1: Track Header Analysis ──
    print("\n" + "=" * 80)
    print("PART 1: TRACK HEADER ANALYSIS (24 bytes)")
    print("=" * 80)
    for sec_idx in sorted(sections_data.keys()):
        analyze_track_header(sections_data[sec_idx], sec_idx)

    # ── PART 2: Event Structure ──
    print("\n" + "=" * 80)
    print("PART 2: EVENT DATA STRUCTURE & DC DELIMITERS")
    print("=" * 80)
    for sec_idx in sorted(sections_data.keys()):
        analyze_event_structure(sections_data[sec_idx], sec_idx)

    # ── PART 3: 9-bit Fields ──
    print("\n" + "=" * 80)
    print("PART 3: 9-BIT FIELD EXTRACTION (raw, no de-rotation)")
    print("=" * 80)
    for sec_idx in [0, 4]:  # Only show S0 and S4 (the differing ones)
        if sec_idx in sections_data:
            analyze_9bit_fields(sections_data[sec_idx], sec_idx)

    # ── PART 4: De-rotation ──
    print("\n" + "=" * 80)
    print("PART 4: DE-ROTATION ANALYSIS (R=9)")
    print("=" * 80)
    for sec_idx in [0, 4]:
        if sec_idx in sections_data:
            analyze_derotation(sections_data[sec_idx], sec_idx)

    # ── PART 5: F3 Beat Counter ──
    analyze_f3_beat_counter(sections_data)

    # ── PART 6: S0 vs S4 ──
    compare_s0_vs_s4(sections_data)

    # ── PART 7: Cross-Section Comparison ──
    cross_section_comparison(sections_data)

    # ── PART 8: Chord Track Comparison ──
    compare_with_chord_tracks(syx_path, sections_data)

    # ── PART 9: Continuous Bitstream ──
    continuous_bitstream_analysis(sections_data)

    # ── PART 10: Byte Position Variance ──
    byte_position_analysis(sections_data)

    # ── PART 11: F4/F5 Analysis ──
    analyze_chord_tone_mask(sections_data)

    # ── PART 12: Summary ──
    print_summary(sections_data, syx_path)

    print("\n" + "=" * 80)
    print("ANALYSIS COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    main()
