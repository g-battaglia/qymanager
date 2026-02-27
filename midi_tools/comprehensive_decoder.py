#!/usr/bin/env python3
"""
Comprehensive Bitstream Decoder — Session 8
============================================

Multi-pronged attack on the QY70 packed bitstream format:

1. BASS track analysis (single-note, simpler than chords)
2. F3/F4/F5 field decomposition with alternative bit widths
3. Cross-section musical content correlation
4. PC (percussion) track structure
5. D2 track analysis (secondary drums, shorter than D1)
6. Attempt to build a working note decoder

KEY INSIGHT: The BASS track plays single notes (not chords), so the event
encoding should be simpler. If we can crack single-note encoding first,
we can extend to chord tracks.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qymanager.formats.qy70.sysex_parser import SysExParser
from collections import Counter, defaultdict

NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

SGT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "tests",
    "fixtures",
    "QY70_SGT.syx",
)

TRACK_NAMES = ["D1", "D2", "PC", "BA", "C1", "C2", "C3", "C4"]


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


def extract_field(val, msb, width, total_width=56):
    shift = total_width - msb - width
    if shift < 0:
        return -1
    return (val >> shift) & ((1 << width) - 1)


def popcount(val):
    return bin(val).count("1")


def get_track_data(syx_path, section, track):
    parser = SysExParser()
    messages = parser.parse_file(syx_path)
    al = section * 8 + track
    data = b""
    for m in messages:
        if m.is_style_data and m.address_low == al:
            data += m.decoded_data
    return data


def get_all_bars_with_preamble(data):
    """Extract bars + preamble from track data.
    Returns (preamble_4bytes, [(header, [events])...])
    """
    if len(data) < 28:
        return None, []
    preamble = data[24:28]
    event_data = data[28:]
    dc_pos = [i for i, b in enumerate(event_data) if b == 0xDC]

    segments = []
    prev = 0
    for dp in dc_pos:
        segments.append(event_data[prev:dp])
        prev = dp + 1
    segments.append(event_data[prev:])

    bars = []
    for seg in segments:
        if len(seg) >= 7:
            bars.append(seg)

    return preamble, bars


def hex_str(data):
    return " ".join(f"{b:02X}" for b in data)


# ============================================================================
# PART 1: BASS Track Deep Analysis
# ============================================================================


def analyze_bass(syx_path):
    """Deep analysis of BASS track — single-note encoding should be simpler."""
    print("=" * 90)
    print("PART 1: BASS TRACK DEEP ANALYSIS")
    print("Bass plays single notes → simpler encoding than chords")
    print("=" * 90)

    # Get BASS from all 6 sections
    for section in range(6):
        data = get_track_data(syx_path, section, 3)  # track 3 = BA
        if not data or len(data) < 28:
            print(f"\n  S{section}: No data")
            continue

        header = data[:24]
        preamble = data[24:28]
        event_data = data[28:]

        print(f"\n{'=' * 60}")
        print(f"  S{section} BASS: {len(data)} bytes total, {len(event_data)} event bytes")
        print(f"  Header bytes 14-23: {hex_str(header[14:24])}")
        print(f"  Preamble: {hex_str(preamble)}")

        # Check for DC delimiters
        dc_pos = [i for i, b in enumerate(event_data) if b == 0xDC]
        print(f"  DC positions: {dc_pos}")

        # Show full event data in 7-byte groups
        print(f"\n  Event data ({len(event_data)} bytes):")
        for i in range(0, len(event_data), 7):
            chunk = event_data[i : i + 7]
            # Show as hex, binary, and 7-bit lo values
            hex_s = " ".join(f"{b:02X}" for b in chunk)
            lo7 = [b & 0x7F for b in chunk]
            hi1 = "".join(str((b >> 7) & 1) for b in chunk)
            print(f"    @{i:3d}: {hex_s:<24s}  hi={hi1}  lo7={lo7}")

        # Try 9-bit field extraction (same as chord tracks)
        if len(event_data) >= 7:
            print(f"\n  9-bit field extraction from event groups:")
            for gi in range(0, min(len(event_data), 70), 7):
                chunk = event_data[gi : gi + 7]
                if len(chunk) < 7:
                    break
                val = int.from_bytes(chunk, "big")
                fields = []
                for fi in range(6):
                    fields.append(extract_field(val, fi * 9, 9))
                rem = val & 0x3
                notes = [nn(f & 0x7F) if f <= 127 else f">{f}" for f in fields]
                print(f"    G{gi // 7}: fields={fields}  notes=[{', '.join(notes)}]  rem={rem}")

        # Find structural patterns
        print(f"\n  Byte frequency (top 10):")
        freq = Counter(event_data)
        for byte_val, count in freq.most_common(10):
            print(f"    0x{byte_val:02X} ({byte_val:3d}): {count}x")

        # Look for repeated groups
        groups_7 = []
        for i in range(0, len(event_data) - 6, 7):
            groups_7.append(event_data[i : i + 7])

        # Count unique groups
        unique_groups = set(tuple(g) for g in groups_7)
        print(f"\n  7-byte groups: {len(groups_7)} total, {len(unique_groups)} unique")
        if len(unique_groups) < len(groups_7):
            g_counter = Counter(tuple(g) for g in groups_7)
            for g, count in g_counter.most_common(5):
                if count > 1:
                    print(f"    {hex_str(bytes(g))}: {count}x")

    # Cross-section comparison
    print(f"\n{'=' * 60}")
    print("  Cross-section BASS comparison:")
    all_bass = {}
    for s in range(6):
        data = get_track_data(syx_path, s, 3)
        if data and len(data) >= 28:
            all_bass[s] = data[28:]  # event data only

    for s1 in range(6):
        for s2 in range(s1 + 1, 6):
            if s1 in all_bass and s2 in all_bass:
                d1, d2 = all_bass[s1], all_bass[s2]
                min_len = min(len(d1), len(d2))
                diffs = sum(1 for i in range(min_len) if d1[i] != d2[i])
                print(
                    f"    S{s1} vs S{s2}: {diffs}/{min_len} bytes differ ({100 * diffs / max(min_len, 1):.0f}%)"
                )


# ============================================================================
# PART 2: F3/F4/F5 Field Systematic Decode
# ============================================================================


def analyze_f345_fields(syx_path):
    """Systematic analysis of the per-beat F3/F4/F5 fields."""
    print()
    print("=" * 90)
    print("PART 2: F3/F4/F5 FIELD SYSTEMATIC DECODE (De-rotated, R=9)")
    print("=" * 90)

    # Collect ALL de-rotated fields across all sections and tracks
    field_data = defaultdict(list)  # (track_name, field_idx) -> [(section, bar, event, value)]

    for track_idx, track_name in [(4, "C2"), (5, "C3"), (6, "C1"), (7, "C4")]:
        for section in range(6):
            data = get_track_data(syx_path, section, track_idx)
            if not data or len(data) < 35:
                continue

            _, bars = get_all_bars_with_preamble(data)

            for bar_idx, bar_data in enumerate(bars):
                if len(bar_data) < 20:
                    continue

                header = bar_data[:13]
                for ei in range((len(bar_data) - 13) // 7):
                    evt_bytes = bar_data[13 + ei * 7 : 13 + (ei + 1) * 7]
                    if len(evt_bytes) != 7:
                        break
                    val = int.from_bytes(evt_bytes, "big")
                    derot = rot_right(val, ei * 9)
                    for fi in range(6):
                        fv = extract_field(derot, fi * 9, 9)
                        field_data[(track_name, fi)].append((section, bar_idx, ei, fv))

    # Report F3, F4, F5 value distributions per track
    for fi in [3, 4, 5]:
        print(f"\n--- Field F{fi} Value Distribution ---")
        for track_name in ["C1", "C2", "C3", "C4"]:
            key = (track_name, fi)
            if key not in field_data:
                continue
            values = [v for _, _, _, v in field_data[key]]
            uniq = sorted(set(values))
            print(f"\n  {track_name} F{fi}: {len(values)} samples, {len(uniq)} unique values")
            print(f"    Values: {uniq}")
            print(f"    Range: {min(values)}-{max(values)}")
            # Show as MIDI notes (lo7)
            notes = [nn(v & 0x7F) for v in uniq]
            print(f"    As MIDI notes (lo7): {notes}")
            # Show hi2 bits
            hi2 = sorted(set((v >> 7) & 0x3 for v in values))
            print(f"    hi2 bits: {hi2}")

            # Distribution by section
            by_section = defaultdict(list)
            for s, b, e, v in field_data[key]:
                by_section[s].append(v)
            for s in sorted(by_section):
                sv = by_section[s]
                print(f"    S{s}: {sorted(set(sv))}")

    # C2 vs C4 paired comparison for F3/F4/F5
    print(f"\n\n--- C2 vs C4 Paired F3/F4/F5 Comparison ---")
    for fi in [3, 4, 5]:
        c2_data = {(s, b, e): v for s, b, e, v in field_data.get(("C2", fi), [])}
        c4_data = {(s, b, e): v for s, b, e, v in field_data.get(("C4", fi), [])}

        common_keys = sorted(set(c2_data) & set(c4_data))
        if not common_keys:
            continue

        print(f"\n  F{fi}: {len(common_keys)} paired events")
        diffs = []
        for key in common_keys:
            diff = c4_data[key] - c2_data[key]
            diffs.append(diff)
            s, b, e = key
            if s == 0:  # Only show section 0 details
                c2v, c4v = c2_data[key], c4_data[key]
                print(
                    f"    S{s}B{b}E{e}: C2={c2v:3d} C4={c4v:3d} diff={diff:+4d}  "
                    f"C2_lo7={nn(c2v & 0x7F)} C4_lo7={nn(c4v & 0x7F)}"
                )

        # Summary of all diffs
        diff_counter = Counter(diffs)
        print(f"  All diffs: {dict(diff_counter)}")


# ============================================================================
# PART 3: Alternative Field Width Hypotheses
# ============================================================================


def try_alternative_widths(syx_path):
    """Maybe F3-F5 aren't 9-bit. Try 7, 8, 10, 11 bit fields."""
    print()
    print("=" * 90)
    print("PART 3: ALTERNATIVE FIELD WIDTH HYPOTHESES")
    print("F0-F2 shift with 9-bit period. But F3-F5 might use different widths.")
    print("=" * 90)

    # Get C2 and C4 section 0 bar 1 events
    c2_data = get_track_data(syx_path, 0, 4)
    c4_data = get_track_data(syx_path, 0, 7)

    _, c2_bars = get_all_bars_with_preamble(c2_data)
    _, c4_bars = get_all_bars_with_preamble(c4_data)

    if len(c2_bars) < 2 or len(c4_bars) < 2:
        print("  Not enough bars")
        return

    c2_bar = c2_bars[1]  # bar 1
    c4_bar = c4_bars[1]

    c2_events = [c2_bar[13 + i * 7 : 13 + (i + 1) * 7] for i in range(4)]
    c4_events = [c4_bar[13 + i * 7 : 13 + (i + 1) * 7] for i in range(4)]

    print(f"\n  Raw C2 bar1 events:")
    for i, e in enumerate(c2_events):
        print(f"    E{i}: {hex_str(e)}")
    print(f"  Raw C4 bar1 events:")
    for i, e in enumerate(c4_events):
        print(f"    E{i}: {hex_str(e)}")

    # De-rotate with R=9
    c2_derot = [rot_right(int.from_bytes(e, "big"), i * 9) for i, e in enumerate(c2_events)]
    c4_derot = [rot_right(int.from_bytes(e, "big"), i * 9) for i, e in enumerate(c4_events)]

    print(f"\n  De-rotated (R=9) as 56-bit binary:")
    for i in range(4):
        c2_bits = format(c2_derot[i], "056b")
        c4_bits = format(c4_derot[i], "056b")
        xor = c2_derot[i] ^ c4_derot[i]
        xor_bits = format(xor, "056b")
        diff_pos = [p for p in range(56) if xor_bits[p] == "1"]
        print(f"    E{i} C2: {c2_bits}")
        print(f"    E{i} C4: {c4_bits}")
        print(f"    E{i} XR: {xor_bits}  diffs@{diff_pos}")
        print()

    # Try different field layouts for the remaining 29 bits (after F0-F2 = 27 bits)
    print("  --- Field layout hypotheses for bits 27-55 (29 bits after F0-F2) ---")
    layouts = [
        ("3x9+2", [(0, 9), (9, 9), (18, 9), (27, 2)]),
        ("7+7+7+7+1", [(0, 7), (7, 7), (14, 7), (21, 7), (28, 1)]),
        ("8+8+8+5", [(0, 8), (8, 8), (16, 8), (24, 5)]),
        ("7+8+7+7", [(0, 7), (7, 8), (15, 7), (22, 7)]),
        ("10+10+9", [(0, 10), (10, 10), (20, 9)]),
        ("5+7+5+7+5", [(0, 5), (5, 7), (12, 5), (17, 7), (24, 5)]),
        ("9+7+7+6", [(0, 9), (9, 7), (16, 7), (23, 6)]),
        ("7+9+7+6", [(0, 7), (7, 9), (16, 7), (23, 6)]),
        ("9+8+8+4", [(0, 9), (9, 8), (17, 8), (25, 4)]),
    ]

    for name, widths in layouts:
        print(f"\n  Layout: {name} (for bits 27-55)")
        for i in range(4):
            # Extract the F3+ region (bits 27-55)
            c2_tail = c2_derot[i] & ((1 << 29) - 1)  # bottom 29 bits
            c4_tail = c4_derot[i] & ((1 << 29) - 1)

            c2_fields = []
            c4_fields = []
            pos = 0
            for _, w in widths:
                shift = 29 - pos - w
                if shift < 0:
                    break
                c2_fields.append((c2_tail >> shift) & ((1 << w) - 1))
                c4_fields.append((c4_tail >> shift) & ((1 << w) - 1))
                pos += w

            diffs = [c4_fields[j] - c2_fields[j] for j in range(len(c2_fields))]
            c2_notes = [nn(f & 0x7F) if f <= 127 else f">{f}" for f in c2_fields]
            c4_notes = [nn(f & 0x7F) if f <= 127 else f">{f}" for f in c4_fields]
            print(
                f"    E{i}: C2={c2_fields}  C4={c4_fields}  diff={diffs}  "
                f"C2_note={c2_notes}  C4_note={c4_notes}"
            )


# ============================================================================
# PART 4: PC (Percussion) Track Analysis
# ============================================================================


def analyze_pc(syx_path):
    """Analyze PC track — percussion, typically simpler patterns."""
    print()
    print("=" * 90)
    print("PART 4: PC (PERCUSSION) TRACK ANALYSIS")
    print("=" * 90)

    for section in range(6):
        data = get_track_data(syx_path, section, 2)  # track 2 = PC
        if not data or len(data) < 28:
            continue

        header = data[:24]
        preamble = data[24:28]
        event_data = data[28:]

        if section > 0:
            # Compare with section 0
            s0_data = get_track_data(syx_path, 0, 2)
            if s0_data and len(s0_data) >= 28:
                s0_events = s0_data[28:]
                min_len = min(len(event_data), len(s0_events))
                diffs = sum(1 for i in range(min_len) if event_data[i] != s0_events[i])
                if diffs == 0:
                    print(f"\n  S{section} PC: identical to S0")
                    continue
                else:
                    print(f"\n  S{section} PC: {diffs}/{min_len} bytes differ from S0")

        print(f"\n  S{section} PC: {len(data)} bytes, {len(event_data)} event bytes")
        print(f"  Header 14-23: {hex_str(header[14:24])}")
        print(f"  Preamble: {hex_str(preamble)}")

        # DC positions
        dc_pos = [i for i, b in enumerate(event_data) if b == 0xDC]
        print(f"  DC positions: {dc_pos}")

        # Full dump in 7-byte groups
        print(f"  Event data:")
        for i in range(0, len(event_data), 7):
            chunk = event_data[i : i + 7]
            hex_s = " ".join(f"{b:02X}" for b in chunk)
            hi1 = "".join(str((b >> 7) & 1) for b in chunk)
            print(f"    @{i:3d}: {hex_s:<24s}  hi={hi1}")


# ============================================================================
# PART 5: D2 Track Analysis (shorter drum track)
# ============================================================================


def analyze_d2(syx_path):
    """Analyze D2 — secondary drum, 256 bytes (simpler than D1's 768)."""
    print()
    print("=" * 90)
    print("PART 5: D2 TRACK ANALYSIS (Secondary Drums)")
    print("=" * 90)

    for section in range(6):
        data = get_track_data(syx_path, section, 1)  # track 1 = D2
        if not data or len(data) < 28:
            continue

        header = data[:24]
        preamble = data[24:28]
        event_data = data[28:]

        if section > 0:
            s0_data = get_track_data(syx_path, 0, 1)
            if s0_data and len(s0_data) >= 28:
                s0_events = s0_data[28:]
                min_len = min(len(event_data), len(s0_events))
                diffs = sum(1 for i in range(min_len) if event_data[i] != s0_events[i])
                if diffs == 0:
                    print(f"\n  S{section} D2: identical to S0")
                    continue
                print(f"\n  S{section} D2: {diffs}/{min_len} bytes differ from S0")

        print(f"\n  S{section} D2: {len(data)} bytes, {len(event_data)} event bytes")
        print(f"  Preamble: {hex_str(preamble)}")

        dc_pos = [i for i, b in enumerate(event_data) if b == 0xDC]
        print(f"  DC positions: {dc_pos}")

        # Look for 28 0F markers (found in D1)
        markers_28 = []
        for i in range(len(event_data) - 1):
            if event_data[i] == 0x28 and event_data[i + 1] == 0x0F:
                markers_28.append(i)
        print(f"  '28 0F' markers: {markers_28}")

        # Look for 40 78 markers
        markers_40 = []
        for i in range(len(event_data) - 1):
            if event_data[i] == 0x40 and event_data[i + 1] == 0x78:
                markers_40.append(i)
        print(f"  '40 78' markers: {markers_40}")

        # 7-byte group dump
        print(f"  Event data ({len(event_data)} bytes):")
        for i in range(0, len(event_data), 7):
            chunk = event_data[i : i + 7]
            hex_s = " ".join(f"{b:02X}" for b in chunk)
            hi1 = "".join(str((b >> 7) & 1) for b in chunk)
            lo7 = [b & 0x7F for b in chunk]
            print(f"    @{i:3d}: {hex_s:<24s}  hi={hi1}  lo7={lo7}")


# ============================================================================
# PART 6: Build Note Decoder Prototype
# ============================================================================


def build_note_decoder(syx_path):
    """Attempt to build a working note decoder using all discoveries."""
    print()
    print("=" * 90)
    print("PART 6: NOTE DECODER PROTOTYPE")
    print("=" * 90)

    # Strategy: Combine header chord notes with event field analysis
    # Header F0-F4 = chord notes (MIDI note values)
    # Event F3 = note modifier (F3+1 = semitone up for C2→C4)
    # Event F4 = register/pitch (large jumps)

    tracks_to_test = [
        (4, "C2"),
        (7, "C4"),
        (6, "C1"),
        (5, "C3"),
    ]

    for track_idx, track_name in tracks_to_test:
        print(f"\n{'=' * 60}")
        print(f"  {track_name} — Header chord notes + Event field analysis")

        for section in range(6):
            data = get_track_data(syx_path, section, track_idx)
            if not data or len(data) < 35:
                continue

            _, bars = get_all_bars_with_preamble(data)

            # Only show sections with unique data
            if section > 0 and track_name in ("C1",):
                prev_data = get_track_data(syx_path, 0, track_idx)
                if prev_data == data:
                    continue

            for bar_idx, bar_data in enumerate(bars):
                if len(bar_data) < 20:
                    continue

                header = bar_data[:13]

                # Decode header as 9-bit fields
                header_val = int.from_bytes(header, "big")
                header_bits = header_val  # 104 bits
                header_fields = []
                for fi in range(11):
                    shift = 104 - (fi + 1) * 9
                    if shift < 0:
                        break
                    header_fields.append((header_bits >> shift) & 0x1FF)
                header_rem = header_bits & ((1 << (104 - 11 * 9)) - 1)  # 104 - 99 = 5 bits

                # Decode events
                events = []
                for ei in range((len(bar_data) - 13) // 7):
                    evt = bar_data[13 + ei * 7 : 13 + (ei + 1) * 7]
                    if len(evt) != 7:
                        break
                    val = int.from_bytes(evt, "big")
                    derot = rot_right(val, ei * 9)
                    fields = [extract_field(derot, fi * 9, 9) for fi in range(6)]
                    rem = derot & 0x3
                    events.append(fields)

                # Print header and events
                hdr_notes = [nn(f) if f <= 127 else f">{f}" for f in header_fields[:5]]
                print(
                    f"\n    S{section} Bar{bar_idx}: header_notes={hdr_notes} "
                    f"hdr_F5-F10={header_fields[5:]} rem={header_rem:05b}"
                )

                for ei, fields in enumerate(events):
                    f0_lo7 = fields[0] & 0x7F
                    f3_lo7 = fields[3] & 0x7F
                    f4_lo7 = fields[4] & 0x7F
                    f5_lo7 = fields[5] & 0x7F
                    print(
                        f"      E{ei}: F0={fields[0]:3d} F1={fields[1]:3d} F2={fields[2]:3d} "
                        f"F3={fields[3]:3d}({nn(f3_lo7)}) F4={fields[4]:3d}({nn(f4_lo7)}) "
                        f"F5={fields[5]:3d}({nn(f5_lo7)})"
                    )

            if section == 0:
                # Show first 2 sections worth
                pass
            elif section >= 2 and track_name != "C3":
                break  # Don't dump all 6 identical sections


# ============================================================================
# PART 7: BASS 9-bit Rotation Test
# ============================================================================


def analyze_bass_rotation(syx_path):
    """Test if BASS track also uses 9-bit rotation (or a different scheme)."""
    print()
    print("=" * 90)
    print("PART 7: BASS TRACK 9-BIT ROTATION TEST")
    print("Does BASS use the same 9-bit rotation as chord tracks?")
    print("=" * 90)

    data = get_track_data(syx_path, 0, 3)  # S0 BASS
    if not data or len(data) < 28:
        print("  No BASS data")
        return

    preamble = data[24:28]
    event_data = data[28:]
    print(f"  Preamble: {hex_str(preamble)}")
    print(f"  Event data: {len(event_data)} bytes")

    # Check for DC delimiters
    dc_pos = [i for i, b in enumerate(event_data) if b == 0xDC]
    print(f"  DC positions: {dc_pos}")

    # If no DCs, treat the whole event stream as one block
    # Extract 7-byte groups
    groups = []
    for i in range(0, len(event_data) - 6, 7):
        groups.append(event_data[i : i + 7])

    print(f"  7-byte groups: {len(groups)}")

    # Test 9-bit rotation between consecutive groups
    if len(groups) >= 2:
        print(f"\n  Rotation test (all R values):")
        best_r = 0
        best_score = 999

        for R in range(1, 56):
            total_diff = 0
            pairs = 0
            for i in range(len(groups) - 1):
                v1 = int.from_bytes(groups[i], "big")
                v2 = int.from_bytes(groups[i + 1], "big")
                rotated = rot_left(v1, R)
                xor = rotated ^ v2
                total_diff += popcount(xor)
                pairs += 1
            avg_diff = total_diff / max(pairs, 1)
            if avg_diff < best_score:
                best_score = avg_diff
                best_r = R

        print(f"  Best rotation: R={best_r} (avg {best_score:.1f} bits differ)")
        print(f"  Top 5 rotations:")
        results = []
        for R in range(1, 56):
            total_diff = 0
            pairs = 0
            for i in range(len(groups) - 1):
                v1 = int.from_bytes(groups[i], "big")
                v2 = int.from_bytes(groups[i + 1], "big")
                rotated = rot_left(v1, R)
                xor = rotated ^ v2
                total_diff += popcount(xor)
                pairs += 1
            results.append((total_diff / max(pairs, 1), R))
        results.sort()
        for avg, R in results[:5]:
            print(f"    R={R:2d}: avg {avg:.1f} bits differ")

        # Show de-rotated with best R
        print(f"\n  De-rotated groups (R={best_r}):")
        for i, g in enumerate(groups[:8]):
            val = int.from_bytes(g, "big")
            derot = rot_right(val, i * best_r)
            fields = [extract_field(derot, fi * 9, 9) for fi in range(6)]
            rem = derot & 0x3
            notes = [nn(f & 0x7F) if f <= 127 else f for f in fields]
            print(f"    G{i}: {hex_str(g)}  derot_fields={fields}  notes={notes}  rem={rem}")

    # Also try without rotation — are consecutive groups related by simple XOR?
    if len(groups) >= 2:
        print(f"\n  Direct XOR between consecutive groups (no rotation):")
        for i in range(min(len(groups) - 1, 5)):
            v1 = int.from_bytes(groups[i], "big")
            v2 = int.from_bytes(groups[i + 1], "big")
            xor = v1 ^ v2
            diff_count = popcount(xor)
            diff_pos = [p for p in range(56) if (xor >> (55 - p)) & 1]
            print(f"    G{i}→G{i + 1}: {diff_count} bits differ at {diff_pos}")


# ============================================================================
# PART 8: Continuous Bitstream Analysis (ignore 7-byte boundaries)
# ============================================================================


def analyze_continuous_bitstream(syx_path):
    """Treat event data as a continuous bitstream and look for patterns."""
    print()
    print("=" * 90)
    print("PART 8: CONTINUOUS BITSTREAM — BASS TRACK")
    print("Ignore 7-byte boundaries, look for repeating patterns at various widths")
    print("=" * 90)

    data = get_track_data(syx_path, 0, 3)  # S0 BASS
    if not data or len(data) < 28:
        return

    event_data = data[28:]
    # Convert to bitstream
    bits = ""
    for b in event_data:
        bits += format(b, "08b")

    print(f"  Total bits: {len(bits)}")
    print(f"  First 160 bits: {bits[:160]}")

    # Try extracting fields at various widths
    for width in [7, 8, 9, 10, 12, 14]:
        print(f"\n  --- Width={width} bit fields ---")
        fields = []
        for i in range(0, len(bits) - width + 1, width):
            val = int(bits[i : i + width], 2)
            fields.append(val)

        # Show first 20 fields
        if width <= 9:
            notes = [nn(v) if v <= 127 else f">{v}" for v in fields[:20]]
            print(f"    Fields: {fields[:20]}")
            print(f"    Notes:  {notes}")
        else:
            print(f"    Fields: {fields[:15]}")

        # Look for repeated values
        counter = Counter(fields)
        repeats = [(v, c) for v, c in counter.most_common(10) if c > 1]
        if repeats:
            print(f"    Repeats: {repeats[:5]}")

    # Try the lo7 bitstream (clear bit 7 of each byte, treat as 7-bit stream)
    lo7_bits = ""
    for b in event_data:
        lo7_bits += format(b & 0x7F, "07b")
    print(f"\n  --- Lo7 bitstream (7-bit values) ---")
    print(f"  Total bits: {len(lo7_bits)}")

    for width in [7, 9, 12, 14]:
        fields = []
        for i in range(0, len(lo7_bits) - width + 1, width):
            val = int(lo7_bits[i : i + width], 2)
            fields.append(val)

        if width <= 9:
            notes = [nn(v) if v <= 127 else f">{v}" for v in fields[:20]]
            print(f"    Width={width}: {fields[:20]}")
            print(f"      Notes: {notes}")


# ============================================================================
# PART 9: Cross-Track Event Correlation
# ============================================================================


def cross_track_correlation(syx_path):
    """Compare events across tracks at the same beat position."""
    print()
    print("=" * 90)
    print("PART 9: CROSS-TRACK EVENT CORRELATION (Same Beat)")
    print("Compare de-rotated fields at the same beat across C1, C2, C3, C4")
    print("=" * 90)

    tracks = [(4, "C2"), (5, "C3"), (6, "C1"), (7, "C4")]

    # Collect bar 1 events from all chord tracks, section 0
    track_events = {}
    for track_idx, track_name in tracks:
        data = get_track_data(syx_path, 0, track_idx)
        if not data or len(data) < 35:
            continue
        _, bars = get_all_bars_with_preamble(data)
        if len(bars) >= 2 and len(bars[1]) >= 41:
            bar_data = bars[1]
            events = []
            for ei in range(4):
                evt = bar_data[13 + ei * 7 : 13 + (ei + 1) * 7]
                if len(evt) == 7:
                    val = int.from_bytes(evt, "big")
                    derot = rot_right(val, ei * 9)
                    fields = [extract_field(derot, fi * 9, 9) for fi in range(6)]
                    events.append(fields)
            track_events[track_name] = events

    # Show all tracks side by side
    for ei in range(4):
        print(f"\n  Beat {ei}:")
        for tname in ["C1", "C2", "C3", "C4"]:
            if tname in track_events and ei < len(track_events[tname]):
                fields = track_events[tname][ei]
                print(
                    f"    {tname}: F0={fields[0]:3d} F1={fields[1]:3d} F2={fields[2]:3d} "
                    f"F3={fields[3]:3d}({nn(fields[3] & 0x7F)}) "
                    f"F4={fields[4]:3d}({nn(fields[4] & 0x7F)}) "
                    f"F5={fields[5]:3d}({nn(fields[5] & 0x7F)})"
                )

    # Look for patterns: same F5 across tracks? F3 differing by note interval?
    print(f"\n  --- Correlation Analysis ---")
    if "C2" in track_events and "C4" in track_events:
        for ei in range(min(len(track_events["C2"]), len(track_events["C4"]))):
            c2 = track_events["C2"][ei]
            c4 = track_events["C4"][ei]
            print(
                f"  Beat {ei}: C2-C4 diffs: "
                f"F0={c4[0] - c2[0]:+d} F1={c4[1] - c2[1]:+d} F2={c4[2] - c2[2]:+d} "
                f"F3={c4[3] - c2[3]:+d} F4={c4[4] - c2[4]:+d} F5={c4[5] - c2[5]:+d}"
            )

    if "C1" in track_events and "C2" in track_events:
        for ei in range(min(len(track_events["C1"]), len(track_events["C2"]))):
            c1 = track_events["C1"][ei]
            c2 = track_events["C2"][ei]
            print(
                f"  Beat {ei}: C1-C2 diffs: "
                f"F0={c2[0] - c1[0]:+d} F1={c2[1] - c1[1]:+d} F2={c2[2] - c1[2]:+d} "
                f"F3={c2[3] - c1[3]:+d} F4={c2[4] - c1[4]:+d} F5={c2[5] - c1[5]:+d}"
            )


# ============================================================================
# PART 10: Header Field Deep Decode
# ============================================================================


def decode_header_fields(syx_path):
    """Deep analysis of the 13-byte bar header across all tracks/sections."""
    print()
    print("=" * 90)
    print("PART 10: BAR HEADER DEEP DECODE (13 bytes = 104 bits)")
    print("=" * 90)

    tracks = [(4, "C2"), (5, "C3"), (6, "C1"), (7, "C4")]

    all_headers = defaultdict(list)  # track_name -> [headers]

    for track_idx, track_name in tracks:
        for section in range(6):
            data = get_track_data(syx_path, section, track_idx)
            if not data or len(data) < 35:
                continue
            _, bars = get_all_bars_with_preamble(data)
            for bar_idx, bar_data in enumerate(bars):
                if len(bar_data) >= 20:
                    header = bar_data[:13]
                    all_headers[(track_name, section)].append((bar_idx, header))

    # Group unique headers
    unique = defaultdict(list)
    for (tname, sec), headers in all_headers.items():
        for bar_idx, hdr in headers:
            unique[tuple(hdr)].append((tname, sec, bar_idx))

    print(f"\n  {len(unique)} unique headers across all tracks/sections:")
    for hdr_tuple, locations in sorted(unique.items(), key=lambda x: -len(x[1])):
        hdr = bytes(hdr_tuple)
        hdr_val = int.from_bytes(hdr, "big")
        fields_9 = []
        for fi in range(11):
            shift = 104 - (fi + 1) * 9
            if shift < 0:
                break
            fields_9.append((hdr_val >> shift) & 0x1FF)
        rem = hdr_val & 0x1F  # 104 - 99 = 5 remainder bits

        notes = [nn(f) if f <= 127 else f">{f}" for f in fields_9[:5]]
        locs = [f"{t}S{s}B{b}" for t, s, b in locations[:8]]
        more = f" +{len(locations) - 8} more" if len(locations) > 8 else ""
        print(f"\n    {hex_str(hdr)}")
        print(f"      9-bit: {fields_9}")
        print(f"      Notes: {notes}  rem={rem:05b}")
        print(f"      Used by: {', '.join(locs)}{more}")


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    syx_path = sys.argv[1] if len(sys.argv) > 1 else SGT_PATH

    if not os.path.exists(syx_path):
        print(f"File not found: {syx_path}")
        sys.exit(1)

    print(f"Analyzing: {syx_path}")

    analyze_bass(syx_path)
    analyze_f345_fields(syx_path)
    try_alternative_widths(syx_path)
    analyze_pc(syx_path)
    analyze_d2(syx_path)
    build_note_decoder(syx_path)
    analyze_bass_rotation(syx_path)
    analyze_continuous_bitstream(syx_path)
    cross_track_correlation(syx_path)
    decode_header_fields(syx_path)

    print("\n" + "=" * 90)
    print("ANALYSIS COMPLETE")
    print("=" * 90)
