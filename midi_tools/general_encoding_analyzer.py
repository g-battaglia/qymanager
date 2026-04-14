#!/usr/bin/env python3
"""
General Encoding Analyzer — Deep analysis of the general encoding (preamble 29 CB)
used by track slots 1 (RHY2/D2), 3 (CHD1/C1), and 5 (PAD/PC) in QY70 SysEx data.

Key facts from previous sessions:
- Preamble bytes 24-25: 29 CB
- Each track has 256 decoded bytes (2 SysEx messages per section)
- 24-byte track header + 4-byte preamble = 28 bytes, leaving 228 bytes of event data
- R=47 (left-rotate by 9 inverse) was found optimal for these tracks
- Shift register completely fails (0%)
- DC delimiters present but only 1/4 aligned to 7-byte boundaries
- CHD1 S0 vs S4: first 169 bytes identical, last 59 bytes differ
"""

import sys
import os
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qymanager.formats.qy70.sysex_parser import SysExParser

# ── Constants ──────────────────────────────────────────────────────────────────

NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

SLOT_NAMES = {1: "RHY2(D2)", 3: "CHD1(C1)", 5: "PAD(PC)"}
GENERAL_SLOTS = [1, 3, 5]

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

ALL_TRACK_NAMES = {
    0: "D1(RHY1)",
    1: "D2(RHY2)",
    2: "BASS",
    3: "C1(CHD1)",
    4: "C2(CHD2)",
    5: "PC(PAD)",
    6: "C3(CHD3)",
    7: "C4(PHR)",
}


# ── Helper functions ──────────────────────────────────────────────────────────


def nn(n):
    """MIDI note number to name."""
    if 0 <= n <= 127:
        return f"{NOTE_NAMES[n % 12]}{n // 12 - 1}"
    return f">{n}"


def rot_left(val, shift, width=56):
    shift = shift % width
    return ((val << shift) | (val >> (width - shift))) & ((1 << width) - 1)


def rot_right(val, shift, width=56):
    shift = shift % width
    return ((val >> shift) | (val << (width - shift))) & ((1 << width) - 1)


def popcount(val):
    return bin(val).count("1")


def extract_9bit(val, field_idx, total_width=56):
    """Extract 9-bit field at position field_idx (0=MSB-side)."""
    shift = total_width - (field_idx + 1) * 9
    if shift < 0:
        return -1
    return (val >> shift) & 0x1FF


def extract_field(val, msb, width, total_width=56):
    """Extract field of 'width' bits starting at bit position 'msb' (0=MSB)."""
    shift = total_width - msb - width
    if shift < 0:
        return -1
    return (val >> shift) & ((1 << width) - 1)


def bits_to_str(val, width=56):
    return format(val, f"0{width}b")


def hex_dump(data, prefix="    ", bytes_per_line=16):
    for i in range(0, len(data), bytes_per_line):
        chunk = data[i : i + bytes_per_line]
        hex_str = " ".join(f"{b:02X}" for b in chunk)
        ascii_str = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
        print(f"{prefix}@{i:3d}: {hex_str:<{bytes_per_line * 3}}  |{ascii_str}|")


# ── Data extraction ───────────────────────────────────────────────────────────


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


def get_all_slot_sections(syx_path, track_idx):
    """Get decoded data for a given track across all 6 sections."""
    parser = SysExParser()
    messages = parser.parse_file(syx_path)
    sections = {}
    for section in range(6):
        al = section * 8 + track_idx
        data = b""
        for m in messages:
            if m.is_style_data and m.address_low == al:
                data += m.decoded_data
        if data:
            sections[section] = data
    return sections


def split_by_dc(event_data):
    """Split event data at DC (0xDC) delimiters. Return list of segments."""
    dc_pos = [i for i, b in enumerate(event_data) if b == 0xDC]
    segments = []
    prev = 0
    for dp in dc_pos:
        segments.append(event_data[prev:dp])
        prev = dp + 1
    segments.append(event_data[prev:])
    return segments, dc_pos


# ── PART 1: Track Header Analysis ─────────────────────────────────────────────


def analyze_track_header(data, slot_idx, section_idx):
    """Decode the 24-byte track header."""
    if len(data) < 24:
        print(f"  S{section_idx}: too short ({len(data)} bytes)")
        return

    header = data[:24]
    print(f"\n  S{section_idx} Track Header ({len(data)} bytes total):")
    print(f"    Raw: {' '.join(f'{b:02X}' for b in header)}")

    # bytes 0-11: pattern/structure bytes
    pattern = header[0:12]
    expected_pattern = bytes(
        [0x08, 0x04, 0x82, 0x01, 0x00, 0x40, 0x20, 0x08, 0x04, 0x82, 0x01, 0x00]
    )
    print(f"    [00-11] Pattern:    {' '.join(f'{b:02X}' for b in pattern)}")
    if pattern == expected_pattern:
        print(f"               -> Matches standard pattern")
    else:
        diff_pos = [i for i in range(12) if pattern[i] != expected_pattern[i]]
        print(f"               -> DIFFERS from standard at positions {diff_pos}")

    # bytes 12-13: identifier
    b12, b13 = header[12], header[13]
    print(f"    [12-13] ID:         {b12:02X} {b13:02X} (dec: {b12}, {b13})")

    # bytes 14-15: voice encoding
    b14, b15 = header[14], header[15]
    print(f"    [14-15] Voice:      {b14:02X} {b15:02X}")
    if b14 == 0x40 and b15 == 0x80:
        print(f"               -> Drum voice (Bank MSB=64, bit7 set)")
    elif b14 == 0x00 and b15 == 0x04:
        print(f"               -> Bass marker (00 04)")
    else:
        bank_msb = b14 & 0x7F
        prog = b15 & 0x7F
        hi_bits = f"hi={b14 >> 7},{b15 >> 7}"
        print(f"               -> Bank MSB={bank_msb}, Prog={prog} ({hi_bits})")
        drum = GM_DRUM_NAMES.get(prog, "")
        if drum:
            print(f"               -> GM drum map: {drum}")

    # bytes 16-17: note range
    b16, b17 = header[16], header[17]
    print(f"    [16-17] Note range: {b16:02X} {b17:02X} = {nn(b16 & 0x7F)} to {nn(b17 & 0x7F)}")
    print(f"               -> lo7: {b16 & 0x7F} to {b17 & 0x7F}, hi bits: {b16 >> 7},{b17 >> 7}")

    # bytes 18-20: type flags
    b18, b19, b20 = header[18], header[19], header[20]
    print(f"    [18-20] Type flags: {b18:02X} {b19:02X} {b20:02X}")
    print(f"               -> bin: {b18:08b} {b19:08b} {b20:08b}")

    # bytes 21-22: pan
    b21, b22 = header[21], header[22]
    print(f"    [21-22] Pan:        {b21:02X} {b22:02X}")
    if b22 == 0x40:
        print(f"               -> Center (64)")
    elif b22 < 0x40:
        print(f"               -> Left {64 - b22}")
    else:
        print(f"               -> Right {b22 - 64}")

    # byte 23: reserved
    b23 = header[23]
    print(f"    [23]    Reserved:   {b23:02X}")


# ── PART 2: Preamble & DC Analysis ────────────────────────────────────────────


def analyze_preamble_and_dc(data, slot_idx, section_idx):
    """Show preamble, DC positions, and 7-byte boundary alignment."""
    if len(data) < 28:
        return

    preamble = data[24:28]
    event_data = data[28:]

    print(f"\n  S{section_idx} Preamble: {' '.join(f'{b:02X}' for b in preamble)}")
    print(
        f"    Byte 0-1: {preamble[0]:02X} {preamble[1]:02X} (encoding ID 0x{preamble[0]:02X}{preamble[1]:02X})"
    )
    print(f"    Byte 2:   {preamble[2]:02X} (= {preamble[2]})")
    print(f"    Byte 3:   {preamble[3]:02X} (= {preamble[3]})")

    print(f"\n  S{section_idx} Event Data: {len(event_data)} bytes")

    # Find DC positions
    dc_pos = [i for i, b in enumerate(event_data) if b == 0xDC]
    print(f"    DC (0xDC) positions: {dc_pos}")
    print(f"    Number of DCs: {len(dc_pos)}")

    # Check DC alignment to 7-byte boundaries
    aligned = sum(1 for p in dc_pos if p % 7 == 0)
    print(f"    DC on 7-byte boundary: {aligned}/{len(dc_pos)}", end="")
    if dc_pos:
        print(f" ({aligned / len(dc_pos) * 100:.0f}%)")
        for p in dc_pos:
            print(f"      DC @{p}: mod7={p % 7}, group {p // 7}")
    else:
        print()

    return event_data, dc_pos


# ── PART 3: Segment analysis with 7-byte grouping ─────────────────────────────


def analyze_segments(event_data, dc_pos, slot_idx, section_idx):
    """Split by DC, show segments, 7-byte groups."""
    segments, _ = split_by_dc(event_data)

    print(f"\n  S{section_idx} Segments (split by DC): {len(segments)}")
    for seg_idx, seg in enumerate(segments):
        full_groups = len(seg) // 7
        remainder = len(seg) % 7
        print(f"\n    --- Segment {seg_idx}: {len(seg)} bytes ({full_groups}x7 + {remainder}) ---")

        # Show first 20 bytes hex
        show_len = min(len(seg), 20)
        print(f"        First {show_len}B: {' '.join(f'{b:02X}' for b in seg[:show_len])}")

        if len(seg) == 0:
            print(f"        (empty)")
            continue

        # Show as 7-byte groups
        for g in range(0, len(seg), 7):
            chunk = seg[g : g + 7]
            hex_str = " ".join(f"{b:02X}" for b in chunk)
            if len(chunk) == 7:
                val_56 = int.from_bytes(chunk, "big")
                lo7 = [b & 0x7F for b in chunk]
                bit7 = "".join(str((b >> 7) & 1) for b in chunk)
                print(f"          G{g // 7} @{g:3d}: {hex_str}  b7={bit7}  lo7={lo7}")
            else:
                print(f"          G{g // 7} @{g:3d}: {hex_str}  (partial: {len(chunk)} bytes)")

    return segments


# ── PART 4: De-rotation analysis (R=47 and R=9) ──────────────────────────────


def analyze_derotation(event_data, slot_idx, section_idx):
    """Apply R=47 and R=9 de-rotation to consecutive 7-byte groups."""
    segments, _ = split_by_dc(event_data)

    print(f"\n  S{section_idx} De-rotation Analysis:")

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

        # Find best rotation
        best_r_scores = {}
        for R in range(1, 56):
            total_diff = 0
            for i in range(len(groups) - 1):
                rotated = rot_left(groups[i], R)
                xor = rotated ^ groups[i + 1]
                total_diff += popcount(xor)
            avg_diff = total_diff / (len(groups) - 1)
            best_r_scores[R] = avg_diff

        sorted_r = sorted(best_r_scores.items(), key=lambda x: x[1])
        print(f"      Top 5 best rotations:")
        for R, score in sorted_r[:5]:
            print(f"        R={R:2d}: avg {score:.1f} bits differ")

        # Apply R=47 de-rotation
        for R_test in [47, 9]:
            print(f"\n      === R={R_test} De-rotated ===")
            derotated = [rot_right(v, i * R_test) for i, v in enumerate(groups)]

            for i, (orig, derot) in enumerate(zip(groups, derotated)):
                orig_hex = format(orig, "014X")
                derot_hex = format(derot, "014X")
                print(f"        E{i}: orig=0x{orig_hex} derot=0x{derot_hex}")

                # Extract 9-bit fields from de-rotated
                fields = [extract_9bit(derot, fi) for fi in range(6)]
                r_bits = derot & 0x3  # last 2 bits
                field_str = " ".join(f"F{fi}={f:3d}" for fi, f in enumerate(fields))
                print(f"             9-bit: {field_str} R={r_bits}")

                # F3 decomposition: hi2|mid3|lo4
                f3 = fields[3]
                if f3 >= 0:
                    f3_hi2 = (f3 >> 7) & 0x3
                    f3_mid3 = (f3 >> 4) & 0x7
                    f3_lo4 = f3 & 0xF
                    print(f"             F3 decomp: hi2={f3_hi2} mid3={f3_mid3} lo4={f3_lo4:04b}")

                # F4 / F5 decomposition
                f4, f5 = fields[4], fields[5]
                if f4 >= 0:
                    print(f"             F4={f4:3d} (0b{f4:09b})  F5={f5:3d} (0b{f5:09b})")

                # MIDI note range check
                for fi, f in enumerate(fields):
                    if 0 <= f <= 127:
                        print(f"             F{fi}={f} -> {nn(f)}")
                    lo7 = f & 0x7F
                    if lo7 != f and 24 <= lo7 <= 96:
                        print(f"             F{fi} lo7={lo7} -> {nn(lo7)}")

            # Shift register check: F1[i] == F0[i-1]
            print(f"\n      R={R_test} Shift register (F1[i]==F0[i-1]):")
            matches = 0
            total = 0
            for i in range(1, len(derotated)):
                f0_prev = extract_9bit(derotated[i - 1], 0)
                f1_curr = extract_9bit(derotated[i], 1)
                total += 1
                match = f0_prev == f1_curr
                if match:
                    matches += 1
                tag = "MATCH" if match else f"differ ({f0_prev} vs {f1_curr})"
                print(f"        E{i - 1}->E{i}: F0[{i - 1}]={f0_prev}, F1[{i}]={f1_curr} -> {tag}")
            if total > 0:
                print(f"      Shift register: {matches}/{total} ({matches / total * 100:.0f}%)")


# ── PART 5: Cross-section comparison per slot ──────────────────────────────────


def cross_section_comparison(all_data, slot_idx):
    """Compare all section pairs for one slot."""
    slot_name = SLOT_NAMES.get(slot_idx, f"T{slot_idx}")
    print(f"\n  {slot_name} Cross-Section Comparison Matrix:")

    sec_indices = sorted(all_data.keys())

    # Difference matrix
    print(f"        ", end="")
    for j in sec_indices:
        print(f"  S{j}  ", end="")
    print()

    for i in sec_indices:
        print(f"    S{i}: ", end="")
        for j in sec_indices:
            if i == j:
                print(f"  --  ", end="")
            else:
                d1, d2 = all_data[i], all_data[j]
                min_len = min(len(d1), len(d2))
                diff_count = sum(1 for k in range(min_len) if d1[k] != d2[k])
                print(f" {diff_count:3d}  ", end="")
        print()

    # Identify identical groups
    groups = defaultdict(list)
    for i in sec_indices:
        found_group = None
        for g, members in groups.items():
            ref = all_data[members[0]]
            cur = all_data[i]
            if len(ref) == len(cur) and ref == cur:
                found_group = g
                break
        if found_group is not None:
            groups[found_group].append(i)
        else:
            groups[i].append(i)

    print(f"\n    Identical groups:")
    for g, members in groups.items():
        print(f"      Group: {['S' + str(m) for m in members]}")

    # Find first differing byte for non-identical pairs
    print(f"\n    First/last differing byte positions:")
    done_pairs = set()
    for i in sec_indices:
        for j in sec_indices:
            if j <= i:
                continue
            pair = (i, j)
            if pair in done_pairs:
                continue
            done_pairs.add(pair)
            d1, d2 = all_data[i], all_data[j]
            if d1 == d2:
                continue
            min_len = min(len(d1), len(d2))
            diff_positions = [k for k in range(min_len) if d1[k] != d2[k]]
            if diff_positions:
                first = diff_positions[0]
                last = diff_positions[-1]
                region_first = (
                    "header" if first < 24 else "preamble" if first < 28 else f"event@{first - 28}"
                )
                region_last = (
                    "header" if last < 24 else "preamble" if last < 28 else f"event@{last - 28}"
                )
                print(
                    f"      S{i} vs S{j}: {len(diff_positions)} bytes differ, "
                    f"first @{first} ({region_first}), last @{last} ({region_last})"
                )
                # Show all differing positions
                for pos in diff_positions:
                    region = (
                        "header" if pos < 24 else "preamble" if pos < 28 else f"event@{pos - 28}"
                    )
                    v1, v2 = d1[pos], d2[pos]
                    xor = v1 ^ v2
                    print(
                        f"        @{pos:3d} ({region:15s}): S{i}=0x{v1:02X}({v1:3d}) "
                        f"S{j}=0x{v2:02X}({v2:3d}) XOR=0x{xor:02X}({xor:08b})"
                    )


# ── PART 6: Cross-slot comparison within same section ──────────────────────────


def cross_slot_comparison(syx_path, section_idx=0):
    """Compare slots 1, 3, 5 within the same section."""
    print(f"\n  Cross-Slot Comparison (Section {section_idx}):")

    slot_data = {}
    for slot in GENERAL_SLOTS:
        data = get_track_data(syx_path, section_idx, slot)
        if data:
            slot_data[slot] = data

    if len(slot_data) < 2:
        print("    Insufficient data")
        return

    # Overall byte comparison
    print(f"    Byte difference matrix:")
    for i in GENERAL_SLOTS:
        for j in GENERAL_SLOTS:
            if j <= i:
                continue
            if i not in slot_data or j not in slot_data:
                continue
            d1, d2 = slot_data[i], slot_data[j]
            min_len = min(len(d1), len(d2))
            diff_count = sum(1 for k in range(min_len) if d1[k] != d2[k])
            pct = diff_count / min_len * 100 if min_len > 0 else 0
            print(
                f"      {SLOT_NAMES[i]} vs {SLOT_NAMES[j]}: "
                f"{diff_count}/{min_len} bytes differ ({pct:.1f}%)"
            )

    # Compare headers
    print(f"\n    Track Header Comparison:")
    for slot in GENERAL_SLOTS:
        if slot in slot_data and len(slot_data[slot]) >= 24:
            hdr = slot_data[slot][:24]
            print(f"      {SLOT_NAMES[slot]:12s}: {' '.join(f'{b:02X}' for b in hdr)}")

    # Compare preambles
    print(f"\n    Preamble Comparison:")
    for slot in GENERAL_SLOTS:
        if slot in slot_data and len(slot_data[slot]) >= 28:
            pre = slot_data[slot][24:28]
            print(f"      {SLOT_NAMES[slot]:12s}: {' '.join(f'{b:02X}' for b in pre)}")

    # Compare DC positions in event data
    print(f"\n    DC Position Comparison:")
    for slot in GENERAL_SLOTS:
        if slot in slot_data and len(slot_data[slot]) >= 28:
            ev = slot_data[slot][28:]
            dc_pos = [i for i, b in enumerate(ev) if b == 0xDC]
            print(f"      {SLOT_NAMES[slot]:12s}: DCs at {dc_pos}")

    # Same DC positions?
    dc_sets = {}
    for slot in GENERAL_SLOTS:
        if slot in slot_data and len(slot_data[slot]) >= 28:
            ev = slot_data[slot][28:]
            dc_sets[slot] = [i for i, b in enumerate(ev) if b == 0xDC]
    dc_vals = list(dc_sets.values())
    if len(dc_vals) >= 2:
        all_same = all(d == dc_vals[0] for d in dc_vals)
        print(f"      All slots same DC positions? {all_same}")

    # Compare segment sizes
    print(f"\n    Segment Size Comparison:")
    for slot in GENERAL_SLOTS:
        if slot in slot_data and len(slot_data[slot]) >= 28:
            ev = slot_data[slot][28:]
            segs, dc_pos = split_by_dc(ev)
            sizes = [len(s) for s in segs]
            print(
                f"      {SLOT_NAMES[slot]:12s}: {sizes} (total={sum(sizes)}+{len(dc_pos)}DCs={sum(sizes) + len(dc_pos)})"
            )

    # Compare event data byte by byte (region mapping)
    print(f"\n    Header field comparison (bytes 12-23 only):")
    for byte_idx in range(12, 24):
        vals = {}
        for slot in GENERAL_SLOTS:
            if slot in slot_data and len(slot_data[slot]) > byte_idx:
                vals[slot] = slot_data[slot][byte_idx]
        if vals:
            val_str = "  ".join(f"{SLOT_NAMES[s]}={v:02X}" for s, v in vals.items())
            all_same = len(set(vals.values())) == 1
            tag = " (same)" if all_same else " << DIFFER"
            print(f"      Byte {byte_idx:2d}: {val_str}{tag}")


# ── PART 7: Structural pattern search ─────────────────────────────────────────


def structural_patterns(event_data, slot_idx, section_idx):
    """Look for repeating sequences, MIDI correlations, markers beyond DC."""
    print(f"\n  S{section_idx} {SLOT_NAMES.get(slot_idx, f'T{slot_idx}')} Structural Patterns:")

    # 1. Byte value histogram
    counter = Counter(event_data)
    print(f"    Byte value frequency (top 20):")
    for val, cnt in counter.most_common(20):
        bar = "#" * min(cnt, 40)
        note = nn(val) if 0 <= val <= 127 else ""
        drum = GM_DRUM_NAMES.get(val, "")
        tag = ""
        if val == 0xDC:
            tag = " <-DC"
        elif val == 0xFE:
            tag = " <-FILL"
        elif val == 0xF8:
            tag = " <-PAD"
        elif drum:
            tag = f" <-drum:{drum}"
        print(f"      0x{val:02X} ({val:3d}): {cnt:3d}x  {bar}{tag}")

    # 2. Repeating byte sequences (2-8 bytes)
    print(f"\n    Repeating sequences:")
    for seq_len in range(2, 9):
        seq_counter = Counter()
        for i in range(len(event_data) - seq_len + 1):
            seq = event_data[i : i + seq_len]
            if 0xDC not in seq:  # Exclude DC-containing sequences
                seq_counter[seq] += 1
        top = seq_counter.most_common(3)
        for seq, cnt in top:
            if cnt >= 3:
                hex_str = " ".join(f"{b:02X}" for b in seq)
                print(f"      {seq_len}B: [{hex_str}] x{cnt}")

    # 3. Recognizable markers besides DC
    print(f"\n    Special markers:")
    for marker, name in [
        (0xDC, "DC"),
        (0xFE, "FILL"),
        (0xF8, "PAD"),
        (0xFF, "FF"),
        (0x00, "NULL"),
        (0x80, "0x80"),
        (0x7F, "0x7F"),
        (0xFC, "FC"),
        (0xFD, "FD"),
    ]:
        positions = [i for i, b in enumerate(event_data) if b == marker]
        if positions:
            print(f"      {name} (0x{marker:02X}): {len(positions)}x at {positions[:20]}")

    # 4. Bar boundary candidates (even divisions of event data)
    print(f"\n    Even division candidates (bar boundaries):")
    ed_len = len(event_data)
    for n_bars in range(1, 9):
        if ed_len % n_bars == 0:
            bar_size = ed_len // n_bars
            print(
                f"      {n_bars} bars: {bar_size} bytes each ({bar_size // 7} x7 + {bar_size % 7})"
            )

    # 5. Check for any correlation between bytes and MIDI note numbers
    print(f"\n    Bytes in common MIDI ranges:")
    bass_range = sum(1 for b in event_data if 24 <= (b & 0x7F) <= 48)
    mid_range = sum(1 for b in event_data if 48 <= (b & 0x7F) <= 72)
    high_range = sum(1 for b in event_data if 72 <= (b & 0x7F) <= 96)
    drum_range = sum(1 for b in event_data if 35 <= (b & 0x7F) <= 59)
    print(f"      Bass (24-48 lo7): {bass_range}/{len(event_data)}")
    print(f"      Mid  (48-72 lo7): {mid_range}/{len(event_data)}")
    print(f"      High (72-96 lo7): {high_range}/{len(event_data)}")
    print(f"      Drum (35-59 lo7): {drum_range}/{len(event_data)}")


# ── PART 8: CHD1 special analysis (bass marker voice) ─────────────────────────


def chd1_special_analysis(syx_path):
    """Special analysis of CHD1 (slot 3) which has bass marker voice (00 04)."""
    print(f"\n{'=' * 80}")
    print(f"PART 8: CHD1 SPECIAL ANALYSIS (bass marker voice 00 04)")
    print(f"{'=' * 80}")

    # Get CHD1 and actual BASS track data
    chd1_s0 = get_track_data(syx_path, 0, 3)  # CHD1 = slot 3
    bass_s0 = get_track_data(syx_path, 0, 2)  # BASS = slot 2

    if not chd1_s0 or not bass_s0:
        print("  Missing data")
        return

    print(f"  CHD1 (slot 3): {len(chd1_s0)} bytes total")
    print(f"  BASS (slot 2): {len(bass_s0)} bytes total")

    # Compare preambles
    if len(chd1_s0) >= 28 and len(bass_s0) >= 28:
        print(f"\n  Preambles:")
        print(f"    CHD1: {' '.join(f'{b:02X}' for b in chd1_s0[24:28])}")
        print(f"    BASS: {' '.join(f'{b:02X}' for b in bass_s0[24:28])}")

    # Compare event data
    chd1_ev = chd1_s0[28:] if len(chd1_s0) >= 28 else b""
    bass_ev = bass_s0[28:] if len(bass_s0) >= 28 else b""

    print(f"\n  Event data sizes: CHD1={len(chd1_ev)}, BASS={len(bass_ev)}")

    # DC positions
    chd1_dc = [i for i, b in enumerate(chd1_ev) if b == 0xDC]
    bass_dc = [i for i, b in enumerate(bass_ev) if b == 0xDC]
    print(f"  DC positions: CHD1={chd1_dc}, BASS={bass_dc}")

    # Byte-level similarity
    min_len = min(len(chd1_ev), len(bass_ev))
    if min_len > 0:
        same = sum(1 for i in range(min_len) if chd1_ev[i] == bass_ev[i])
        print(
            f"  Byte similarity (first {min_len}): {same}/{min_len} ({same / min_len * 100:.1f}%)"
        )

    # XOR comparison
    if min_len > 0:
        print(f"\n  Byte-by-byte XOR (first 60 bytes):")
        show_len = min(min_len, 60)
        for i in range(0, show_len, 16):
            end = min(i + 16, show_len)
            chd1_hex = " ".join(f"{chd1_ev[j]:02X}" for j in range(i, end))
            bass_hex = " ".join(f"{bass_ev[j]:02X}" for j in range(i, end))
            xor_hex = " ".join(f"{chd1_ev[j] ^ bass_ev[j]:02X}" for j in range(i, end))
            print(f"    @{i:3d} CHD1: {chd1_hex}")
            print(f"    @{i:3d} BASS: {bass_hex}")
            print(f"    @{i:3d}  XOR: {xor_hex}")
            print()

    # Look for bass-line note patterns in CHD1
    print(f"\n  CHD1 event data — looking for bass note patterns:")
    print(f"    Low note bytes (val & 0x7F in 24-48 range):")
    for i, b in enumerate(chd1_ev):
        lo7 = b & 0x7F
        if 24 <= lo7 <= 48:
            print(f"      @{i:3d}: 0x{b:02X} -> lo7={lo7} = {nn(lo7)}")

    # Compare headers byte by byte
    print(f"\n  Header comparison (CHD1 vs BASS):")
    for i in range(min(24, len(chd1_s0), len(bass_s0))):
        c, b = chd1_s0[i], bass_s0[i]
        tag = "" if c == b else " << DIFFER"
        print(f"    Byte {i:2d}: CHD1=0x{c:02X} BASS=0x{b:02X}{tag}")


# ── PART 9: Cross-slot consistency of identical/different regions ──────────────


def cross_slot_section_identity(syx_path):
    """Check if the identical/different regions are consistent across slots."""
    print(f"\n{'=' * 80}")
    print(f"PART 9: CROSS-SLOT SECTION IDENTITY CONSISTENCY")
    print(f"{'=' * 80}")

    for slot in GENERAL_SLOTS:
        slot_name = SLOT_NAMES[slot]
        all_data = get_all_slot_sections(syx_path, slot)

        print(f"\n  {slot_name} (slot {slot}):")
        sec_indices = sorted(all_data.keys())

        # Identical groups
        groups = defaultdict(list)
        for i in sec_indices:
            found_group = None
            for g, members in groups.items():
                ref = all_data[members[0]]
                cur = all_data[i]
                if len(ref) == len(cur) and ref == cur:
                    found_group = g
                    break
            if found_group is not None:
                groups[found_group].append(i)
            else:
                groups[i].append(i)

        for g, members in groups.items():
            print(f"    Identical: {['S' + str(m) for m in members]}")

        # Show event data identity at byte level (header vs event)
        for i in sec_indices:
            for j in sec_indices:
                if j <= i:
                    continue
                d1, d2 = all_data[i], all_data[j]
                if d1 == d2:
                    continue
                min_len = min(len(d1), len(d2))
                hdr_same = d1[:24] == d2[:24]
                pre_same = d1[24:28] == d2[24:28]
                evt_diff = sum(1 for k in range(28, min_len) if d1[k] != d2[k])
                evt_total = min_len - 28
                first_diff = next((k for k in range(28, min_len) if d1[k] != d2[k]), None)
                last_diff = next((k for k in range(min_len - 1, 27, -1) if d1[k] != d2[k]), None)
                print(
                    f"    S{i} vs S{j}: hdr={'same' if hdr_same else 'DIFF'}, "
                    f"pre={'same' if pre_same else 'DIFF'}, "
                    f"evt: {evt_diff}/{evt_total} differ, "
                    f"range @{first_diff}-@{last_diff}"
                )

    # Show if the pattern is consistent
    print(f"\n  Summary: Which sections differ for each slot?")
    for slot in GENERAL_SLOTS:
        all_data = get_all_slot_sections(syx_path, slot)
        sec_indices = sorted(all_data.keys())
        ref = all_data[sec_indices[0]]
        diff_secs = [s for s in sec_indices if all_data[s] != ref]
        same_secs = [s for s in sec_indices if all_data[s] == ref]
        print(
            f"    {SLOT_NAMES[slot]}: same as S0 = {['S' + str(s) for s in same_secs]}, "
            f"differs = {['S' + str(s) for s in diff_secs]}"
        )


# ── PART 10: All tracks overview ──────────────────────────────────────────────


def all_tracks_overview(syx_path, section_idx=0):
    """Show all 8 tracks in one section for context."""
    print(f"\n{'=' * 80}")
    print(f"PART 10: ALL TRACKS OVERVIEW (Section {section_idx})")
    print(f"{'=' * 80}")

    for track_idx in range(8):
        data = get_track_data(syx_path, section_idx, track_idx)
        name = ALL_TRACK_NAMES.get(track_idx, f"T{track_idx}")
        if len(data) < 28:
            print(f"  {name:12s}: {len(data)} bytes (too short)")
            continue
        pre = data[24:28]
        ev = data[28:]
        dc_pos = [i for i, b in enumerate(ev) if b == 0xDC]
        segs, _ = split_by_dc(ev)
        seg_sizes = [len(s) for s in segs]
        is_general = pre[0:2] == bytes([0x29, 0xCB])
        enc_type = "GENERAL(29CB)" if is_general else f"other({pre[0]:02X}{pre[1]:02X})"
        print(
            f"  {name:12s}: {len(data):4d}B, pre={' '.join(f'{b:02X}' for b in pre)}, "
            f"evt={len(ev):3d}B, DCs@{dc_pos}, segs={seg_sizes}, {enc_type}"
        )


# ── PART 11: Full hex dump of event data ───────────────────────────────────────


def full_hex_dump(data, slot_idx, section_idx):
    """Full hex dump of event data."""
    if len(data) < 28:
        return
    event_data = data[28:]
    print(
        f"\n  S{section_idx} {SLOT_NAMES.get(slot_idx, f'T{slot_idx}')} Full Event Hex Dump ({len(event_data)} bytes):"
    )
    hex_dump(event_data, prefix="    ")


# ══════════════════════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════════════════════


def main():
    syx_path = sys.argv[1] if len(sys.argv) > 1 else "tests/fixtures/QY70_SGT.syx"

    print("=" * 80)
    print("GENERAL ENCODING (29 CB) DEEP ANALYSIS")
    print(f"Tracks: slot 1 (RHY2/D2), slot 3 (CHD1/C1), slot 5 (PAD/PC)")
    print(f"Source: {syx_path}")
    print("=" * 80)

    if not os.path.exists(syx_path):
        print(f"ERROR: File not found: {syx_path}")
        sys.exit(1)

    # Collect all data
    all_slot_data = {}
    for slot in GENERAL_SLOTS:
        all_slot_data[slot] = get_all_slot_sections(syx_path, slot)
        slot_name = SLOT_NAMES[slot]
        print(f"\n{slot_name} sections:")
        for sec_idx, data in sorted(all_slot_data[slot].items()):
            print(f"  S{sec_idx}: {len(data)} bytes")

    # ── PART 1: Track Headers ──
    print(f"\n{'=' * 80}")
    print(f"PART 1: TRACK HEADER ANALYSIS (24 bytes)")
    print(f"{'=' * 80}")
    for slot in GENERAL_SLOTS:
        slot_name = SLOT_NAMES[slot]
        print(f"\n--- {slot_name} (slot {slot}) ---")
        for sec_idx in sorted(all_slot_data[slot].keys()):
            analyze_track_header(all_slot_data[slot][sec_idx], slot, sec_idx)

    # ── PART 2: Preamble & DC ──
    print(f"\n{'=' * 80}")
    print(f"PART 2: PREAMBLE & DC DELIMITER ANALYSIS")
    print(f"{'=' * 80}")
    event_data_cache = {}  # (slot, section) -> (event_data, dc_pos)
    for slot in GENERAL_SLOTS:
        slot_name = SLOT_NAMES[slot]
        print(f"\n--- {slot_name} (slot {slot}) ---")
        for sec_idx in sorted(all_slot_data[slot].keys()):
            result = analyze_preamble_and_dc(all_slot_data[slot][sec_idx], slot, sec_idx)
            if result:
                event_data_cache[(slot, sec_idx)] = result

    # ── PART 3: Segments & 7-byte grouping ──
    print(f"\n{'=' * 80}")
    print(f"PART 3: SEGMENTS & 7-BYTE GROUPING")
    print(f"{'=' * 80}")
    for slot in GENERAL_SLOTS:
        slot_name = SLOT_NAMES[slot]
        print(f"\n--- {slot_name} (slot {slot}) S0 only ---")
        if (slot, 0) in event_data_cache:
            ev, dc = event_data_cache[(slot, 0)]
            analyze_segments(ev, dc, slot, 0)

    # ── PART 4: De-rotation (R=47 and R=9) ──
    print(f"\n{'=' * 80}")
    print(f"PART 4: DE-ROTATION ANALYSIS (R=47 and R=9)")
    print(f"{'=' * 80}")
    for slot in GENERAL_SLOTS:
        slot_name = SLOT_NAMES[slot]
        # Show S0 and one differing section if any
        sections_to_show = [0]
        # Find a differing section
        ref = all_slot_data[slot].get(0, b"")
        for s in range(1, 6):
            if s in all_slot_data[slot] and all_slot_data[slot][s] != ref:
                sections_to_show.append(s)
                break
        for sec_idx in sections_to_show:
            print(f"\n--- {slot_name} (slot {slot}) S{sec_idx} ---")
            if (slot, sec_idx) in event_data_cache:
                ev, dc = event_data_cache[(slot, sec_idx)]
                analyze_derotation(ev, slot, sec_idx)

    # ── PART 5: Cross-section comparison ──
    print(f"\n{'=' * 80}")
    print(f"PART 5: CROSS-SECTION COMPARISON")
    print(f"{'=' * 80}")
    for slot in GENERAL_SLOTS:
        cross_section_comparison(all_slot_data[slot], slot)

    # ── PART 6: Cross-slot comparison ──
    print(f"\n{'=' * 80}")
    print(f"PART 6: CROSS-SLOT COMPARISON (within same section)")
    print(f"{'=' * 80}")
    for sec_idx in [0, 4]:
        print(f"\n--- Section {sec_idx} ---")
        cross_slot_comparison(syx_path, sec_idx)

    # ── PART 7: Structural patterns ──
    print(f"\n{'=' * 80}")
    print(f"PART 7: STRUCTURAL PATTERNS")
    print(f"{'=' * 80}")
    for slot in GENERAL_SLOTS:
        if (slot, 0) in event_data_cache:
            ev, dc = event_data_cache[(slot, 0)]
            structural_patterns(ev, slot, 0)

    # ── PART 8: CHD1 special analysis ──
    chd1_special_analysis(syx_path)

    # ── PART 9: Cross-slot section identity consistency ──
    cross_slot_section_identity(syx_path)

    # ── PART 10: All tracks overview ──
    all_tracks_overview(syx_path, 0)

    # ── PART 11: Full hex dump of S0 event data for all 3 slots ──
    print(f"\n{'=' * 80}")
    print(f"PART 11: FULL HEX DUMPS (S0)")
    print(f"{'=' * 80}")
    for slot in GENERAL_SLOTS:
        if 0 in all_slot_data[slot]:
            full_hex_dump(all_slot_data[slot][0], slot, 0)

    # ── PART 12: Differing section hex dump ──
    print(f"\n{'=' * 80}")
    print(f"PART 12: DIFFERING SECTIONS — SIDE-BY-SIDE EVENT DATA")
    print(f"{'=' * 80}")
    for slot in GENERAL_SLOTS:
        slot_name = SLOT_NAMES[slot]
        ref = all_slot_data[slot].get(0, b"")
        for sec_idx in range(1, 6):
            data = all_slot_data[slot].get(sec_idx, b"")
            if data and data != ref and len(data) >= 28 and len(ref) >= 28:
                print(f"\n  {slot_name} S0 vs S{sec_idx} event data:")
                ev0 = ref[28:]
                evN = data[28:]
                min_len = min(len(ev0), len(evN))
                for i in range(0, min_len, 16):
                    end = min(i + 16, min_len)
                    s0_hex = " ".join(f"{ev0[j]:02X}" for j in range(i, end))
                    sn_hex = " ".join(f"{evN[j]:02X}" for j in range(i, end))
                    diff_mark = ""
                    for j in range(i, end):
                        if ev0[j] != evN[j]:
                            diff_mark += "^^"
                        else:
                            diff_mark += "  "
                        if j < end - 1:
                            diff_mark += " "
                    has_diff = any(ev0[j] != evN[j] for j in range(i, end))
                    if has_diff:
                        print(f"    @{i:3d} S0: {s0_hex}")
                        print(f"    @{i:3d} S{sec_idx}: {sn_hex}")
                        print(f"    @{i:3d}     {diff_mark}")
                        print()

    print(f"\n{'=' * 80}")
    print("ANALYSIS COMPLETE")
    print(f"{'=' * 80}")


if __name__ == "__main__":
    main()
