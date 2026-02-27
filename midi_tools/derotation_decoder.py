#!/usr/bin/env python3
"""
De-Rotation Decoder — Exploit the 9-bit barrel rotation between events
to decode QY70 chord event bitstream format.

STRATEGY:
1. De-rotate each event by (index × 9) bits to normalize all events
   to the same field layout
2. Use C2/C4 XOR to locate the note field in de-rotated space
3. Cross-validate with C3 S0 (unique musical data) and C1 (identical across sections)
4. Try different rotation amounts (8, 9, 10) to find the true period
5. Attempt to identify note, velocity, timing, gate fields

KEY DATA:
- C2 bar1 events: BE 9F 8F C5 85 61 78 | BE 9F 8A 8B C3 71 78 | BE 94 97 87 E3 71 78 | A8 AE 8F C7 E3 71 78
- C4 bar1 events: BE 9F 8F C5 9D 01 78 | BE 9F 8A AA C3 71 78 | BE 94 B6 87 E3 71 78 | A8 EC 8F C7 E3 71 78
- Best rotation: 9 bits left, 10 bits differ per transition
- C2/C4 XOR positions: E0=[35,36,41,42], E1=[26,31], E2=[18,23], E3=[9,14]
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qymanager.formats.qy70.sysex_parser import SysExParser
from collections import defaultdict, Counter

NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def nn(n):
    """MIDI note to name."""
    if 0 <= n <= 127:
        return f"{NOTE_NAMES[n % 12]}{n // 12 - 1}"
    return f"?{n}"


def rot_left(val, shift, width=56):
    """Barrel rotate left by shift bits within a width-bit word."""
    shift = shift % width
    return ((val << shift) | (val >> (width - shift))) & ((1 << width) - 1)


def rot_right(val, shift, width=56):
    """Barrel rotate right by shift bits within a width-bit word."""
    return rot_left(val, width - shift, width)


def bits_to_str(val, width=56):
    """Format value as binary string with width."""
    return format(val, f"0{width}b")


def popcount(val):
    """Count number of 1 bits."""
    return bin(val).count("1")


def extract_field(val, msb, width, total_width=56):
    """Extract a field of 'width' bits starting at bit position 'msb' (0=MSB)."""
    shift = total_width - msb - width
    return (val >> shift) & ((1 << width) - 1)


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


def get_bar_events(data, bar_index=1):
    """Extract 7-byte events from a specific bar.
    Returns (header_13bytes, [event0, event1, ...]) for 41-byte bars.
    """
    if len(data) < 28:
        return None, []

    event_data = data[28:]  # Skip track header (24) + preamble (4)
    dc_pos = [i for i, b in enumerate(event_data) if b == 0xDC]

    # Split into segments
    segments = []
    prev = 0
    for dp in dc_pos:
        segments.append(event_data[prev:dp])
        prev = dp + 1
    segments.append(event_data[prev:])

    if bar_index >= len(segments):
        return None, []

    bar_data = segments[bar_index]
    if len(bar_data) < 20:
        return None, []

    header = bar_data[:13]
    events = []
    for i in range(4):
        start = 13 + i * 7
        end = start + 7
        if end <= len(bar_data):
            events.append(bar_data[start:end])

    return header, events


def get_all_bars(data):
    """Extract all bars from track data."""
    if len(data) < 28:
        return []

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
        if len(seg) >= 20:
            header = seg[:13]
            events = []
            for i in range((len(seg) - 13) // 7):
                start = 13 + i * 7
                events.append(seg[start : start + 7])
            bars.append((header, events))

    return bars


# ============================================================================
# PART 1: De-rotation analysis
# ============================================================================


def analyze_derotation(syx_path):
    """De-rotate events and look for consistent field layout."""
    print("=" * 80)
    print("PART 1: DE-ROTATION ANALYSIS")
    print("Rotate each event RIGHT by (index × R) bits to normalize")
    print("=" * 80)

    c2 = get_track_data(syx_path, 0, 4)
    c4 = get_track_data(syx_path, 0, 7)

    _, c2_events = get_bar_events(c2, bar_index=1)
    _, c4_events = get_bar_events(c4, bar_index=1)

    c2_vals = [int.from_bytes(e, "big") for e in c2_events]
    c4_vals = [int.from_bytes(e, "big") for e in c4_events]

    # Try rotation amounts from 7 to 11
    for R in range(7, 12):
        print(f"\n--- Rotation period R={R} ---")

        # De-rotate: event[i] → rotate_right(event[i], i*R)
        c2_derot = [rot_right(v, i * R) for i, v in enumerate(c2_vals)]
        c4_derot = [rot_right(v, i * R) for i, v in enumerate(c4_vals)]

        # Check consistency: do all de-rotated events match better?
        print("  De-rotated C2 events:")
        for i, v in enumerate(c2_derot):
            print(f"    E{i}: {bits_to_str(v)}")

        # Check pairwise XOR between de-rotated events
        print("  Pairwise diff bits (de-rotated):")
        for i in range(4):
            for j in range(i + 1, 4):
                xor = c2_derot[i] ^ c2_derot[j]
                print(f"    E{i}^E{j}: {popcount(xor):2d} bits differ")

        # Check C2 vs C4 XOR positions in de-rotated space
        print("  C2 vs C4 XOR (de-rotated):")
        xor_positions_per_event = []
        for i in range(4):
            xor = c2_derot[i] ^ c4_derot[i]
            positions = [b for b in range(56) if (xor >> (55 - b)) & 1]
            xor_positions_per_event.append(positions)
            print(f"    E{i}: {popcount(xor)} bits at {positions}")

        # KEY TEST: Do all de-rotated events have the SAME XOR positions?
        if all(p == xor_positions_per_event[0] for p in xor_positions_per_event):
            print(f"  >>> ALL EVENTS HAVE IDENTICAL XOR POSITIONS! R={R} is correct!")
        else:
            # Check if most match
            matching = sum(1 for p in xor_positions_per_event if p == xor_positions_per_event[1])
            print(f"  (E1-E3 matching: {matching}/3)")


# ============================================================================
# PART 2: Exhaustive rotation search with XOR alignment metric
# ============================================================================


def exhaustive_rotation_search(syx_path):
    """Try every possible rotation and measure how well C2/C4 XOR aligns."""
    print()
    print("=" * 80)
    print("PART 2: EXHAUSTIVE ROTATION SEARCH")
    print("Find R that minimizes variance in C2/C4 XOR positions across events")
    print("=" * 80)

    c2 = get_track_data(syx_path, 0, 4)
    c4 = get_track_data(syx_path, 0, 7)

    _, c2_events = get_bar_events(c2, bar_index=1)
    _, c4_events = get_bar_events(c4, bar_index=1)

    c2_vals = [int.from_bytes(e, "big") for e in c2_events]
    c4_vals = [int.from_bytes(e, "big") for e in c4_events]

    best_r = -1
    best_score = 999

    for R in range(1, 56):
        c2_derot = [rot_right(v, i * R) for i, v in enumerate(c2_vals)]
        c4_derot = [rot_right(v, i * R) for i, v in enumerate(c4_vals)]

        xor_sets = []
        for i in range(4):
            xor = c2_derot[i] ^ c4_derot[i]
            positions = frozenset(b for b in range(56) if (xor >> (55 - b)) & 1)
            xor_sets.append(positions)

        # Score: number of unique XOR position sets (1 = perfect alignment)
        unique_sets = len(set(xor_sets))

        # Also measure: total unique bit positions involved
        all_positions = set()
        for s in xor_sets:
            all_positions.update(s)

        # Combined score: fewer unique patterns and fewer total positions = better
        score = unique_sets * 10 + len(all_positions)

        if score < best_score:
            best_score = score
            best_r = R

        if unique_sets == 1:
            print(
                f"  R={R:2d}: PERFECT ALIGNMENT! {len(all_positions)} bits differ, "
                f"positions={sorted(all_positions)}"
            )
        elif unique_sets <= 2 and len(all_positions) <= 6:
            print(
                f"  R={R:2d}: {unique_sets} unique XOR sets, {len(all_positions)} total positions"
            )

    print(f"\n  Best R={best_r} with score {best_score}")


# ============================================================================
# PART 3: Try non-uniform rotation (e.g., 9-bit for events within bar,
# but different alignment for bar header)
# ============================================================================


def analyze_header_event_relationship(syx_path):
    """Analyze how the 13-byte bar header relates to the following events."""
    print()
    print("=" * 80)
    print("PART 3: BAR HEADER ↔ EVENT RELATIONSHIP")
    print("Look for header fields that control event interpretation")
    print("=" * 80)

    c2 = get_track_data(syx_path, 0, 4)
    c4 = get_track_data(syx_path, 0, 7)
    c3_s0 = get_track_data(syx_path, 0, 6)

    for name, data in [("C2", c2), ("C4", c4), ("C3_S0", c3_s0)]:
        bars = get_all_bars(data)
        print(f"\n  {name}: {len(bars)} bars")
        for bar_idx, (header, events) in enumerate(bars):
            hdr_hex = " ".join(f"{b:02X}" for b in header)
            print(f"    Bar {bar_idx}: header=[{hdr_hex}] events={len(events)}")

            # Show header as 13-byte value
            hdr_val = int.from_bytes(header, "big")
            print(f"            header bits: {bits_to_str(hdr_val, 104)}")

            # Show first event
            if events:
                evt_hex = " ".join(f"{b:02X}" for b in events[0])
                print(f"            E0=[{evt_hex}]")


# ============================================================================
# PART 4: 9-bit field extraction from de-rotated events
# ============================================================================


def extract_9bit_fields(syx_path):
    """After de-rotation by R=9, extract 9-bit fields and interpret."""
    print()
    print("=" * 80)
    print("PART 4: 9-BIT FIELD EXTRACTION FROM DE-ROTATED EVENTS")
    print("56 bits = 6 × 9-bit fields + 2 remaining bits")
    print("=" * 80)

    c2 = get_track_data(syx_path, 0, 4)
    c4 = get_track_data(syx_path, 0, 7)
    c3_s0 = get_track_data(syx_path, 0, 6)

    _, c2_events = get_bar_events(c2, bar_index=1)
    _, c4_events = get_bar_events(c4, bar_index=1)

    c2_vals = [int.from_bytes(e, "big") for e in c2_events]
    c4_vals = [int.from_bytes(e, "big") for e in c4_events]

    # De-rotate with R=9
    R = 9
    c2_derot = [rot_right(v, i * R) for i, v in enumerate(c2_vals)]
    c4_derot = [rot_right(v, i * R) for i, v in enumerate(c4_vals)]

    # Extract 9-bit fields at various offsets
    for field_offset in range(0, 56 - 8):
        c2_fields = [extract_field(v, field_offset, 9) for v in c2_derot]
        c4_fields = [extract_field(v, field_offset, 9) for v in c4_derot]

        # Check if fields are in MIDI note range for all events
        c2_in_range = all(24 <= f <= 108 for f in c2_fields)
        c4_in_range = all(24 <= f <= 108 for f in c4_fields)

        # Check if C2/C4 have consistent difference (same interval)
        if c2_in_range and c4_in_range:
            diffs = [c4_fields[i] - c2_fields[i] for i in range(4)]
            c2_notes = [nn(f) for f in c2_fields]
            c4_notes = [nn(f) for f in c4_fields]
            consistent = len(set(diffs)) == 1
            marker = " *** CONSISTENT INTERVAL" if consistent else ""
            print(
                f"  @bit {field_offset:2d}: C2={c2_fields} ({c2_notes}) "
                f"C4={c4_fields} ({c4_notes}) diffs={diffs}{marker}"
            )

    # Also try 7-bit fields
    print(f"\n--- 7-bit fields ---")
    for field_offset in range(0, 56 - 6):
        c2_fields = [extract_field(v, field_offset, 7) for v in c2_derot]
        c4_fields = [extract_field(v, field_offset, 7) for v in c4_derot]

        c2_in_range = all(36 <= f <= 96 for f in c2_fields)
        c4_in_range = all(36 <= f <= 96 for f in c4_fields)

        if c2_in_range and c4_in_range:
            diffs = [c4_fields[i] - c2_fields[i] for i in range(4)]
            c2_notes = [nn(f) for f in c2_fields]
            c4_notes = [nn(f) for f in c4_fields]
            consistent = len(set(diffs)) == 1
            marker = " *** CONSISTENT INTERVAL" if consistent else ""
            print(
                f"  @bit {field_offset:2d}: C2={c2_fields} ({c2_notes}) "
                f"C4={c4_fields} ({c4_notes}) diffs={diffs}{marker}"
            )

    # Also try 5-bit and 6-bit
    for field_width in [5, 6]:
        print(f"\n--- {field_width}-bit fields ---")
        for field_offset in range(0, 56 - field_width + 1):
            c2_fields = [extract_field(v, field_offset, field_width) for v in c2_derot]
            c4_fields = [extract_field(v, field_offset, field_width) for v in c4_derot]
            diffs = [c4_fields[i] - c2_fields[i] for i in range(4)]
            consistent = len(set(diffs)) == 1 and diffs[0] != 0
            if consistent:
                print(f"  @bit {field_offset:2d}: C2={c2_fields} C4={c4_fields} diff={diffs[0]:+d}")


# ============================================================================
# PART 5: Try treating the full bar as a continuous bitstream
# ============================================================================


def continuous_bitstream_analysis(syx_path):
    """Instead of treating events as independent 56-bit words,
    treat the full 41-byte bar (header+events) as a continuous 328-bit stream
    and extract fields at 9-bit intervals."""
    print()
    print("=" * 80)
    print("PART 5: CONTINUOUS BITSTREAM (328 bits = 13 header + 4×7 events)")
    print("Extract fields at 9-bit intervals from the full bar")
    print("=" * 80)

    c2 = get_track_data(syx_path, 0, 4)
    c4 = get_track_data(syx_path, 0, 7)

    c2_bar = c2[43:84]  # 41 bytes
    c4_bar = c4[57:98]  # 41 bytes

    c2_bits = int.from_bytes(c2_bar, "big")
    c4_bits = int.from_bytes(c4_bar, "big")
    total_bits = 41 * 8  # 328

    xor = c2_bits ^ c4_bits
    xor_positions = [b for b in range(total_bits) if (xor >> (total_bits - 1 - b)) & 1]
    print(f"XOR diff positions: {xor_positions}")
    print(f"Total diff bits: {len(xor_positions)}")

    # Extract 9-bit fields from the continuous stream
    print(f"\n9-bit fields from continuous bar bitstream:")
    print(
        f"{'Field':>5} {'Start':>5} {'C2':>5} {'C4':>5} {'Diff':>5} {'C2 note':>8} {'C4 note':>8}"
    )
    for field_idx in range(total_bits // 9):
        start = field_idx * 9
        c2_val = extract_field(c2_bits, start, 9, total_bits)
        c4_val = extract_field(c4_bits, start, 9, total_bits)
        diff = c4_val - c2_val
        c2_note = nn(c2_val) if 0 <= c2_val <= 127 else str(c2_val)
        c4_note = nn(c4_val) if 0 <= c4_val <= 127 else str(c4_val)
        marker = " <<<" if diff != 0 else ""
        print(
            f"  F{field_idx:2d}  @{start:3d}   {c2_val:3d}   {c4_val:3d}   {diff:+4d}   {c2_note:>8} {c4_note:>8}{marker}"
        )

    # Try 7-bit fields from continuous stream
    print(f"\n7-bit fields from continuous bar bitstream:")
    for field_idx in range(total_bits // 7):
        start = field_idx * 7
        c2_val = extract_field(c2_bits, start, 7, total_bits)
        c4_val = extract_field(c4_bits, start, 7, total_bits)
        diff = c4_val - c2_val
        marker = " <<<" if diff != 0 else ""
        if diff != 0:
            c2_note = nn(c2_val) if 0 <= c2_val <= 127 else str(c2_val)
            c4_note = nn(c4_val) if 0 <= c4_val <= 127 else str(c4_val)
            print(
                f"  F{field_idx:2d}  @{start:3d}   {c2_val:3d}   {c4_val:3d}   {diff:+4d}   "
                f"{c2_note:>8} {c4_note:>8}{marker}"
            )


# ============================================================================
# PART 6: Cross-validate with C3 S0 (different musical content)
# ============================================================================


def cross_validate_c3(syx_path):
    """C3 section 0 has unique musical content while sections 1-5 have defaults.
    If we found the note field, the unique content should show different notes."""
    print()
    print("=" * 80)
    print("PART 6: CROSS-VALIDATION WITH C3 S0 (UNIQUE MUSIC)")
    print("=" * 80)

    c3_s0 = get_track_data(syx_path, 0, 6)
    c3_s1 = get_track_data(syx_path, 1, 6)

    bars_s0 = get_all_bars(c3_s0)
    bars_s1 = get_all_bars(c3_s1)

    print(f"C3 S0: {len(bars_s0)} bars, C3 S1: {len(bars_s1)} bars")

    # For each bar with 4 events, do the 9-bit rotation analysis
    R = 9
    for name, bars in [("C3_S0", bars_s0), ("C3_S1", bars_s1)]:
        print(f"\n--- {name} ---")
        for bar_idx, (header, events) in enumerate(bars):
            if len(events) < 2:
                continue

            vals = [int.from_bytes(e, "big") for e in events[:4]]

            # Check if 9-bit rotation holds
            for i in range(min(len(vals) - 1, 3)):
                best_rot = -1
                best_diff = 56
                for rot in range(1, 56):
                    rotated = rot_left(vals[i], rot)
                    xor = rotated ^ vals[i + 1]
                    diff_bits = popcount(xor)
                    if diff_bits < best_diff:
                        best_diff = diff_bits
                        best_rot = rot

                print(
                    f"  Bar {bar_idx} E{i}→E{i + 1}: best rot={best_rot}, {best_diff} bits differ"
                )


# ============================================================================
# PART 7: Try different de-rotation widths (not just 56-bit)
# ============================================================================


def try_wider_bitstream(syx_path):
    """What if the rotation operates on a wider field?
    Try 63 bits (9×7), 72 bits (9×8), 81 bits (9×9)."""
    print()
    print("=" * 80)
    print("PART 7: WIDER BITSTREAM ROTATION")
    print("Test if rotation works on non-56-bit fields")
    print("=" * 80)

    c2 = get_track_data(syx_path, 0, 4)

    # Get bar 1 raw bytes (after DC): header + events
    bar1_data = c2[43:84]  # 41 bytes

    # Try treating header + events as one continuous stream
    # If the events are 9-bit rotated, maybe the header contains
    # the initial phase / state

    # Let's check: does the 9-bit rotation work on the events portion only?
    events_only = bar1_data[13:]  # 28 bytes = 224 bits

    print(f"Events only: {len(events_only)} bytes = {len(events_only) * 8} bits")
    print(f"Events: {' '.join(f'{b:02X}' for b in events_only)}")

    # Convert to 224-bit integer
    events_val = int.from_bytes(events_only, "big")

    # Check if there's a 9-bit period in the 224-bit stream
    # Split into 9-bit fields
    print(f"\n224-bit stream as 9-bit fields ({224 // 9} complete fields + {224 % 9} remainder):")
    for i in range(224 // 9 + 1):
        start_bit = i * 9
        if start_bit + 9 > 224:
            remaining = 224 - start_bit
            if remaining > 0:
                val = extract_field(events_val, start_bit, remaining, 224)
                print(
                    f"  F{i:2d} @{start_bit:3d}: {val:3d} (0b{val:0{remaining}b}) [{remaining}-bit remainder]"
                )
            break
        val = extract_field(events_val, start_bit, 9, 224)
        note = nn(val) if 0 <= val <= 127 else str(val)
        print(f"  F{i:2d} @{start_bit:3d}: {val:3d} (0b{val:09b}) = {note}")


# ============================================================================
# PART 8: Analyze the captured QY70 pattern dump (simpler data)
# ============================================================================


def analyze_captured_pattern(syx_path, captured_path):
    """Compare the style (SGT) with the captured pattern dump.
    The captured pattern may have simpler/known content."""
    print()
    print("=" * 80)
    print("PART 8: CAPTURED PATTERN vs STYLE COMPARISON")
    print("=" * 80)

    if not os.path.exists(captured_path):
        print(f"  Captured file not found: {captured_path}")
        return

    parser = SysExParser()

    style_msgs = parser.parse_file(syx_path)
    captured_msgs = parser.parse_file(captured_path)

    print(f"Style: {len(style_msgs)} messages")
    print(f"Captured: {len(captured_msgs)} messages")

    # Show captured message details
    for m in captured_msgs:
        if m.is_style_data:
            print(
                f"  AL=0x{m.address_low:02X} ({m.address_low}) decoded={len(m.decoded_data)} bytes"
            )
            # Show first 32 bytes
            data = m.decoded_data[:32]
            print(f"    {' '.join(f'{b:02X}' for b in data)}")


# ============================================================================
# PART 9: Compare C1 events (100% identical across sections) more deeply
# ============================================================================


def analyze_c1_events(syx_path):
    """C1 is identical across all sections — it's the simplest chord track.
    Analyze its event structure in detail."""
    print()
    print("=" * 80)
    print("PART 9: C1 EVENT DEEP ANALYSIS (identical across all sections)")
    print("=" * 80)

    c1 = get_track_data(syx_path, 0, 3)
    print(f"C1 total: {len(c1)} bytes")

    # Show track header
    header = c1[:24]
    print(f"Track header: {' '.join(f'{b:02X}' for b in header)}")

    # Preamble
    preamble = c1[24:28]
    print(f"Preamble: {' '.join(f'{b:02X}' for b in preamble)}")

    # Event data
    event_data = c1[28:]
    dc_pos = [i for i, b in enumerate(event_data) if b == 0xDC]
    print(f"DC positions in event data: {dc_pos}")
    print(f"Event data length: {len(event_data)} bytes")

    # Split by DC and show each segment
    segments = []
    prev = 0
    for dp in dc_pos:
        segments.append(event_data[prev:dp])
        prev = dp + 1
    segments.append(event_data[prev:])

    for seg_idx, seg in enumerate(segments):
        print(f"\n  Segment {seg_idx}: {len(seg)} bytes")
        # Show as 7-byte groups
        for g in range(0, len(seg), 7):
            chunk = seg[g : g + 7]
            hex_str = " ".join(f"{b:02X}" for b in chunk)
            if len(chunk) == 7:
                bit7 = "".join(str((b >> 7) & 1) for b in chunk)
                lo7 = [b & 0x7F for b in chunk]
                print(f"    G{g // 7} @{g}: {hex_str}  b7={bit7}  lo7={lo7}")
            else:
                print(f"    G{g // 7} @{g}: {hex_str}")

    # Check 9-bit rotation on C1 events
    bars = get_all_bars(c1)
    print(f"\n  C1 bars: {len(bars)}")
    for bar_idx, (hdr, events) in enumerate(bars):
        if len(events) >= 2:
            vals = [int.from_bytes(e, "big") for e in events[:4]]
            for i in range(min(len(vals) - 1, 3)):
                best_rot = -1
                best_diff = 56
                for rot in range(1, 56):
                    rotated = rot_left(vals[i], rot)
                    xor = rotated ^ vals[i + 1]
                    diff_bits = popcount(xor)
                    if diff_bits < best_diff:
                        best_diff = diff_bits
                        best_rot = rot
                print(
                    f"    Bar {bar_idx} E{i}→E{i + 1}: best rot={best_rot}, {best_diff} bits differ"
                )


# ============================================================================
# PART 10: Full event catalog - de-rotate ALL events and cluster
# ============================================================================


def full_event_catalog(syx_path):
    """De-rotate all events across all tracks/sections and catalog
    the unique de-rotated values."""
    print()
    print("=" * 80)
    print("PART 10: FULL EVENT CATALOG (de-rotated with R=9)")
    print("=" * 80)

    R = 9
    catalog = []

    for track_idx, track_name in [(3, "C1"), (4, "C2"), (6, "C3"), (7, "C4")]:
        for section in range(6):
            data = get_track_data(syx_path, section, track_idx)
            bars = get_all_bars(data)

            for bar_idx, (header, events) in enumerate(bars):
                for evt_idx, evt in enumerate(events):
                    if len(evt) != 7:
                        continue
                    val = int.from_bytes(evt, "big")
                    derot = rot_right(val, evt_idx * R)
                    catalog.append(
                        {
                            "track": track_name,
                            "section": section,
                            "bar": bar_idx,
                            "event": evt_idx,
                            "raw": val,
                            "derot": derot,
                            "raw_bytes": evt,
                        }
                    )

    print(f"Total events: {len(catalog)}")

    # Group de-rotated values by uniqueness
    derot_counts = Counter(e["derot"] for e in catalog)
    print(f"Unique de-rotated values: {len(derot_counts)}")

    # Show most common de-rotated values
    print(f"\nMost common de-rotated values:")
    for val, count in derot_counts.most_common(20):
        # Find which tracks have this value
        tracks = set(e["track"] for e in catalog if e["derot"] == val)
        raw_hex = format(val, "014X")
        print(f"  0x{raw_hex}: {count:3d}× from {tracks}")

    # For each unique de-rotated value, extract candidate note fields
    print(f"\nNote field candidates (de-rotated, 7-bit at various offsets):")
    print(f"  Testing bit offsets that produce MIDI note range values...")

    for offset in range(50):
        vals_at_offset = [extract_field(e["derot"], offset, 7) for e in catalog]
        in_range = sum(1 for v in vals_at_offset if 36 <= v <= 96)
        if in_range > len(catalog) * 0.4:
            unique = sorted(set(vals_at_offset))
            notes = [nn(v) for v in unique[:15]]
            print(
                f"  @{offset:2d}: {in_range}/{len(catalog)} in range, "
                f"unique={len(unique)}, values={unique[:15]}"
            )
            print(f"         notes={notes}")


if __name__ == "__main__":
    syx_path = sys.argv[1] if len(sys.argv) > 1 else "tests/fixtures/QY70_SGT.syx"
    captured_path = "midi_tools/captured/qy70_dump_20260226_200743.syx"

    analyze_derotation(syx_path)
    exhaustive_rotation_search(syx_path)
    analyze_header_event_relationship(syx_path)
    extract_9bit_fields(syx_path)
    continuous_bitstream_analysis(syx_path)
    cross_validate_c3(syx_path)
    try_wider_bitstream(syx_path)
    analyze_captured_pattern(syx_path, captured_path)
    analyze_c1_events(syx_path)
    full_event_catalog(syx_path)
