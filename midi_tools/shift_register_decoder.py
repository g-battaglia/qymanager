#!/usr/bin/env python3
"""
Shift Register Decoder — The de-rotated 9-bit fields show that each event
SHIFTS previous values and inserts a NEW 9-bit value.

BREAKTHROUGH HYPOTHESIS:
- The 56-bit event word is a SHIFT REGISTER of 9-bit fields
- Each beat: new 9-bit value inserted at F0, old values shift to F1→F2→...
- The 9-bit rotation IS this shift — de-rotation undoes it
- The "new" value at F0 encodes the musical event for that beat
- C2/C4 difference is in bits 35-42 (F3/F4 region) after de-rotation

VERIFICATION PLAN:
1. Extract de-rotated 9-bit F0 values (the "new" data per beat)
2. Compare C2 vs C4 F0 values — should differ by a consistent note interval
3. Cross-validate with C3 S0 (different music → different F0 values)
4. Check if F0 values across bars/tracks form recognizable patterns
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qymanager.formats.qy70.sysex_parser import SysExParser
from collections import Counter, defaultdict

NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def nn(n):
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


def get_all_bars(data):
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
                events.append(seg[13 + i * 7 : 13 + (i + 1) * 7])
            bars.append((header, events))
    return bars


# ============================================================================
# PART 1: Confirm Shift Register Model
# ============================================================================


def confirm_shift_register(syx_path):
    """Verify that de-rotated 9-bit fields F1[i] == F0[i-1]."""
    print("=" * 80)
    print("PART 1: SHIFT REGISTER MODEL VERIFICATION")
    print("Test: F1[i] should equal F0[i-1] after de-rotation with R=9")
    print("=" * 80)

    tracks = [(4, "C2"), (7, "C4"), (6, "C3_S0"), (3, "C1")]

    for track_idx, track_name in tracks:
        section = 0
        data = get_track_data(syx_path, section, track_idx)
        bars = get_all_bars(data)

        print(f"\n--- {track_name} S0 ---")
        for bar_idx, (header, events) in enumerate(bars):
            if len(events) < 2:
                continue

            print(f"\n  Bar {bar_idx} ({len(events)} events):")

            # De-rotate all events
            derot_vals = []
            for ei, evt in enumerate(events[:4]):
                if len(evt) != 7:
                    break
                val = int.from_bytes(evt, "big")
                derot = rot_right(val, ei * 9)
                derot_vals.append(derot)

            # Extract 9-bit fields from each de-rotated event
            for ei, dv in enumerate(derot_vals):
                fields = []
                for fi in range(6):
                    fields.append(extract_field(dv, fi * 9, 9))
                remainder = dv & 0x3  # last 2 bits
                print(f"    E{ei}: fields={fields} rem={remainder:02b}")

            # Verify shift register: F[k][i] == F[k-1][i-1]
            print(f"    Shift register check:")
            for ei in range(1, len(derot_vals)):
                prev_fields = [extract_field(derot_vals[ei - 1], fi * 9, 9) for fi in range(6)]
                curr_fields = [extract_field(derot_vals[ei], fi * 9, 9) for fi in range(6)]

                matches = 0
                for fi in range(1, 6):
                    if curr_fields[fi] == prev_fields[fi - 1]:
                        matches += 1

                print(
                    f"      E{ei - 1}→E{ei}: "
                    f"F1==prev_F0? {curr_fields[1] == prev_fields[0]} "
                    f"F2==prev_F1? {curr_fields[2] == prev_fields[1]} "
                    f"F3==prev_F2? {curr_fields[3] == prev_fields[2]} "
                    f"({matches}/5 match)"
                )


# ============================================================================
# PART 2: Extract "New" Values (F0 of de-rotated events)
# ============================================================================


def extract_new_values(syx_path):
    """The F0 field of each de-rotated event is the NEW data for that beat."""
    print()
    print("=" * 80)
    print("PART 2: NEW 9-BIT VALUES PER BEAT (F0 of de-rotated)")
    print("=" * 80)

    tracks = [(4, "C2"), (7, "C4"), (6, "C3_S0"), (3, "C1")]

    for track_idx, track_name in tracks:
        section = 0
        data = get_track_data(syx_path, section, track_idx)
        bars = get_all_bars(data)

        print(f"\n--- {track_name} S0 ---")
        for bar_idx, (header, events) in enumerate(bars):
            if not events:
                continue

            new_values = []
            for ei, evt in enumerate(events[:4]):
                if len(evt) != 7:
                    break
                val = int.from_bytes(evt, "big")
                derot = rot_right(val, ei * 9)
                f0 = extract_field(derot, 0, 9)
                new_values.append(f0)

            # Also extract the "initial" values from the first event
            first_derot = rot_right(int.from_bytes(events[0], "big"), 0)
            init_fields = [extract_field(first_derot, fi * 9, 9) for fi in range(6)]

            notes = [nn(v & 0x7F) for v in new_values]
            lo7 = [v & 0x7F for v in new_values]
            hi2 = [(v >> 7) & 0x3 for v in new_values]

            print(f"  Bar {bar_idx}: init={init_fields}")
            print(f"    New values: {new_values}")
            print(f"    lo7: {lo7}  notes: {notes}")
            print(f"    hi2: {hi2}  (top 2 bits of 9-bit field)")
            print(f"    binary: {[format(v, '09b') for v in new_values]}")


# ============================================================================
# PART 3: C2 vs C4 New Values Comparison
# ============================================================================


def compare_c2_c4_new_values(syx_path):
    """Compare F0 values between C2 and C4 to find the note interval."""
    print()
    print("=" * 80)
    print("PART 3: C2 vs C4 NEW VALUE COMPARISON")
    print("If note encoding is in F0, C2/C4 should differ by consistent interval")
    print("=" * 80)

    c2 = get_track_data(syx_path, 0, 4)
    c4 = get_track_data(syx_path, 0, 7)

    c2_bars = get_all_bars(c2)
    c4_bars = get_all_bars(c4)

    print(f"C2: {len(c2_bars)} bars, C4: {len(c4_bars)} bars")

    # For bars that have matching event counts
    for bi in range(min(len(c2_bars), len(c4_bars))):
        _, c2_events = c2_bars[bi]
        _, c4_events = c4_bars[bi]

        n = min(len(c2_events), len(c4_events), 4)
        if n == 0:
            continue

        print(f"\n  Bar {bi} ({n} events):")

        for ei in range(n):
            c2_val = int.from_bytes(c2_events[ei], "big")
            c4_val = int.from_bytes(c4_events[ei], "big")

            c2_derot = rot_right(c2_val, ei * 9)
            c4_derot = rot_right(c4_val, ei * 9)

            # Extract all 9-bit fields
            c2_fields = [extract_field(c2_derot, fi * 9, 9) for fi in range(6)]
            c4_fields = [extract_field(c4_derot, fi * 9, 9) for fi in range(6)]

            diffs = [c4_fields[fi] - c2_fields[fi] for fi in range(6)]

            # Show only differing fields
            diff_str = " ".join(
                f"F{fi}:{c2_fields[fi]}→{c4_fields[fi]}({diffs[fi]:+d})"
                for fi in range(6)
                if diffs[fi] != 0
            )
            print(f"    E{ei}: {diff_str or 'IDENTICAL'}")

            # Also show the XOR in bit-level detail
            xor = c2_derot ^ c4_derot
            if xor != 0:
                diff_positions = [b for b in range(56) if (xor >> (55 - b)) & 1]
                print(f"         XOR bits: {diff_positions}")

    # Aggregate: for all events, what is the typical C2/C4 difference?
    print(f"\n  Aggregate C2/C4 F0-F5 differences:")
    all_diffs = defaultdict(list)
    for bi in range(min(len(c2_bars), len(c4_bars))):
        _, c2_events = c2_bars[bi]
        _, c4_events = c4_bars[bi]
        n = min(len(c2_events), len(c4_events), 4)
        for ei in range(n):
            c2_derot = rot_right(int.from_bytes(c2_events[ei], "big"), ei * 9)
            c4_derot = rot_right(int.from_bytes(c4_events[ei], "big"), ei * 9)
            for fi in range(6):
                c2_f = extract_field(c2_derot, fi * 9, 9)
                c4_f = extract_field(c4_derot, fi * 9, 9)
                if c2_f != c4_f:
                    all_diffs[fi].append(c4_f - c2_f)

    for fi in sorted(all_diffs):
        diffs = all_diffs[fi]
        print(f"    F{fi}: diffs={diffs} (mean={sum(diffs) / len(diffs):.1f})")


# ============================================================================
# PART 4: Cross-section analysis of new values
# ============================================================================


def cross_section_new_values(syx_path):
    """Compare F0 values across sections for the same track."""
    print()
    print("=" * 80)
    print("PART 4: CROSS-SECTION NEW VALUE ANALYSIS")
    print("Same track, different sections — do F0 values change?")
    print("=" * 80)

    for track_idx, track_name in [(4, "C2"), (3, "C1")]:
        print(f"\n--- {track_name} ---")
        for section in range(6):
            data = get_track_data(syx_path, section, track_idx)
            bars = get_all_bars(data)

            for bar_idx, (header, events) in enumerate(bars):
                if len(events) < 2:
                    continue

                f0_values = []
                for ei, evt in enumerate(events[:4]):
                    if len(evt) != 7:
                        break
                    derot = rot_right(int.from_bytes(evt, "big"), ei * 9)
                    f0_values.append(extract_field(derot, 0, 9))

                # Only show first bar of each section for brevity
                if bar_idx == 1:
                    print(f"  S{section} bar{bar_idx}: F0={f0_values}")


# ============================================================================
# PART 5: Decompose 9-bit F0 into sub-fields
# ============================================================================


def decompose_f0(syx_path):
    """The 9-bit F0 value likely has sub-fields. Try various splits."""
    print()
    print("=" * 80)
    print("PART 5: DECOMPOSE 9-BIT F0 INTO SUB-FIELDS")
    print("Try: 1+8, 2+7, 3+6, 4+5, 1+4+4, 2+3+4, etc.")
    print("=" * 80)

    # Collect all F0 values from C2, C3, C4, C1
    all_f0 = defaultdict(list)

    for track_idx, track_name in [(3, "C1"), (4, "C2"), (6, "C3"), (7, "C4")]:
        for section in range(6):
            data = get_track_data(syx_path, section, track_idx)
            bars = get_all_bars(data)

            for bar_idx, (header, events) in enumerate(bars):
                for ei, evt in enumerate(events[:4]):
                    if len(evt) != 7:
                        break
                    derot = rot_right(int.from_bytes(evt, "big"), ei * 9)
                    f0 = extract_field(derot, 0, 9)
                    all_f0[track_name].append(f0)

    # Show unique F0 values per track
    for track_name in ["C1", "C2", "C3", "C4"]:
        values = all_f0[track_name]
        unique = sorted(set(values))
        print(f"\n  {track_name}: {len(values)} events, {len(unique)} unique F0 values")
        print(f"    Values: {unique}")

        # Binary representation of unique values
        print(f"    Binary:")
        for v in unique:
            print(
                f"      {v:3d} = {v:09b} "
                f"| 1+8: {(v >> 8) & 1},{v & 0xFF:3d} "
                f"| 2+7: {(v >> 7) & 3},{v & 0x7F:3d}({nn(v & 0x7F)}) "
                f"| 3+6: {(v >> 6) & 7},{v & 0x3F:3d} "
                f"| 4+5: {(v >> 5) & 0xF},{v & 0x1F:3d}"
            )

    # Compare C2 vs C4 F0 values (paired by position)
    print(f"\n  C2 vs C4 paired F0 comparison:")
    c2_f0 = all_f0["C2"]
    c4_f0 = all_f0["C4"]
    n = min(len(c2_f0), len(c4_f0))

    for i in range(n):
        c2v = c2_f0[i]
        c4v = c4_f0[i]
        if c2v != c4v:
            # Show various decompositions
            c2_lo7 = c2v & 0x7F
            c4_lo7 = c4v & 0x7F
            c2_lo6 = c2v & 0x3F
            c4_lo6 = c4v & 0x3F
            c2_lo5 = c2v & 0x1F
            c4_lo5 = c4v & 0x1F
            print(
                f"    [{i:2d}] C2={c2v:3d}({c2v:09b}) C4={c4v:3d}({c4v:09b}) "
                f"diff={c4v - c2v:+4d} "
                f"lo7:{c4_lo7 - c2_lo7:+d} lo6:{c4_lo6 - c2_lo6:+d} lo5:{c4_lo5 - c2_lo5:+d}"
            )


# ============================================================================
# PART 6: Analyze the FULL de-rotated word structure
# ============================================================================


def full_derotated_structure(syx_path):
    """Look at all 6 de-rotated 9-bit fields and the 2-bit remainder."""
    print()
    print("=" * 80)
    print("PART 6: FULL DE-ROTATED WORD STRUCTURE")
    print("56 = 6×9 + 2: Show all fields and their meaning")
    print("=" * 80)

    c2 = get_track_data(syx_path, 0, 4)
    c4 = get_track_data(syx_path, 0, 7)
    c3_s0 = get_track_data(syx_path, 0, 6)
    c1 = get_track_data(syx_path, 0, 3)

    for name, data in [("C2", c2), ("C4", c4), ("C3_S0", c3_s0), ("C1", c1)]:
        bars = get_all_bars(data)
        print(f"\n--- {name} ---")

        for bar_idx, (header, events) in enumerate(bars):
            if not events:
                continue
            print(f"\n  Bar {bar_idx}:")

            for ei, evt in enumerate(events[:4]):
                if len(evt) != 7:
                    break
                val = int.from_bytes(evt, "big")
                derot = rot_right(val, ei * 9)

                fields = [extract_field(derot, fi * 9, 9) for fi in range(6)]
                remainder = derot & 0x3

                # For each field, show lo7 and top 2 bits
                field_strs = []
                for f in fields:
                    hi2 = (f >> 7) & 0x3
                    lo7 = f & 0x7F
                    note = nn(lo7) if 36 <= lo7 <= 96 else f"{lo7:3d}"
                    field_strs.append(f"{f:3d}({hi2}|{lo7:3d}={note})")

                print(f"    E{ei}: {' '.join(field_strs)} rem={remainder}")

            # Show the header too
            hdr = int.from_bytes(header, "big")
            hdr_fields = [extract_field(hdr, fi * 9, 9, 104) for fi in range(11)]
            hdr_notes = [nn(f) if 0 <= f <= 127 else str(f) for f in hdr_fields[:5]]
            print(f"    HDR F0-4: {hdr_fields[:5]} = {hdr_notes}")


# ============================================================================
# PART 7: Test alternative field widths (not 9-bit)
# ============================================================================


def test_alternative_widths(syx_path):
    """What if the event isn't 6×9+2 but some other decomposition?
    Try: 7×8=56, 8×7=56, 4×14=56, etc."""
    print()
    print("=" * 80)
    print("PART 7: ALTERNATIVE FIELD WIDTHS")
    print("=" * 80)

    c2 = get_track_data(syx_path, 0, 4)
    c4 = get_track_data(syx_path, 0, 7)

    _, c2_events = get_all_bars(c2)[1]  # bar 1
    _, c4_events = get_all_bars(c4)[1]  # bar 1

    # De-rotate
    c2_derot = [rot_right(int.from_bytes(e, "big"), i * 9) for i, e in enumerate(c2_events[:4])]
    c4_derot = [rot_right(int.from_bytes(e, "big"), i * 9) for i, e in enumerate(c4_events[:4])]

    for width in [7, 8, 14]:
        n_fields = 56 // width
        remainder = 56 % width

        print(f"\n--- {width}-bit fields ({n_fields} fields + {remainder} remainder) ---")
        for ei in range(4):
            c2_fields = [extract_field(c2_derot[ei], fi * width, width) for fi in range(n_fields)]
            c4_fields = [extract_field(c4_derot[ei], fi * width, width) for fi in range(n_fields)]
            diffs = [c4_fields[fi] - c2_fields[fi] for fi in range(n_fields)]

            diff_str = " ".join(f"F{fi}:{diffs[fi]:+d}" for fi in range(n_fields) if diffs[fi] != 0)
            print(f"    E{ei}: C2={c2_fields} diffs=[{diff_str}]")

    # Try: what if the event is structured as:
    # [flag_byte(7)] [note(7)] [velocity(7)] [gate(7)] [timing(7)] [extra1(7)] [extra2(7)] [padding(7)]
    # This is the 7-byte = 7 x 7-bit (lo7) interpretation
    print(f"\n--- 7 lo7 bytes interpretation ---")
    for ei in range(4):
        c2_evt = c2_events[ei]
        c4_evt = c4_events[ei]
        c2_lo7 = [b & 0x7F for b in c2_evt]
        c4_lo7 = [b & 0x7F for b in c4_evt]
        diffs = [c4_lo7[i] - c2_lo7[i] for i in range(7)]
        c2_notes = [nn(v) if 36 <= v <= 96 else f"{v:3d}" for v in c2_lo7]
        print(f"    E{ei}: C2_lo7={c2_lo7} ({c2_notes}) diffs={diffs}")


# ============================================================================
# PART 8: Analyze if bar header 9-bit fields are truly chord notes
# ============================================================================


def header_chord_analysis(syx_path):
    """Deep analysis of whether header 9-bit fields encode chord notes."""
    print()
    print("=" * 80)
    print("PART 8: HEADER 9-BIT FIELDS = CHORD NOTES?")
    print("C2 header F0-F4 = [63,61,59,55,36] = D#4,C#4,B3,G3,C2")
    print("Are these chord tones for the style?")
    print("=" * 80)

    # Collect all unique headers and their 9-bit F0-F4 values
    header_chords = defaultdict(list)

    for track_idx, track_name in [(3, "C1"), (4, "C2"), (6, "C3"), (7, "C4")]:
        for section in range(6):
            data = get_track_data(syx_path, section, track_idx)
            bars = get_all_bars(data)

            for bar_idx, (header, events) in enumerate(bars):
                hdr_val = int.from_bytes(header, "big")
                fields = [extract_field(hdr_val, fi * 9, 9, 104) for fi in range(5)]
                hdr_hex = header.hex()
                header_chords[hdr_hex].append(
                    {
                        "track": track_name,
                        "section": section,
                        "bar": bar_idx,
                        "fields": fields,
                    }
                )

    print(f"Unique headers: {len(header_chords)}")
    for hdr_hex, entries in sorted(header_chords.items(), key=lambda x: -len(x[1])):
        fields = entries[0]["fields"]
        tracks = set(e["track"] for e in entries)
        # Check if F0-F4 are all valid MIDI notes
        all_midi = all(0 <= f <= 127 for f in fields)
        notes = [nn(f) if 0 <= f <= 127 else str(f) for f in fields]

        # Only show if interesting
        if len(entries) > 1 or all_midi:
            print(f"\n  {hdr_hex[:26]}...")
            print(f"    F0-F4: {fields} = {notes}")
            print(f"    Count: {len(entries)}× from {tracks}")

            if all_midi and all(f > 0 for f in fields):
                # Analyze as chord
                root = min(f for f in fields if f > 0)
                intervals = sorted([(f - root) % 12 for f in fields])
                print(f"    Root={nn(root)}, intervals={intervals}")

                # Common chord patterns:
                # Major: [0,4,7] Minor: [0,3,7] Dom7: [0,4,7,10]
                # Maj7: [0,4,7,11] Min7: [0,3,7,10]
                intervals_set = set(intervals)
                if {0, 4, 7}.issubset(intervals_set):
                    print(f"    → Contains MAJOR triad!")
                if {0, 3, 7}.issubset(intervals_set):
                    print(f"    → Contains MINOR triad!")
                if {0, 4, 7, 10}.issubset(intervals_set):
                    print(f"    → Contains DOMINANT 7th!")


# ============================================================================
# PART 9: Try reading events WITHOUT de-rotation as note data
# ============================================================================


def raw_event_analysis(syx_path):
    """Maybe the 9-bit rotation is an encoding artifact and the
    actual note data is in specific byte positions."""
    print()
    print("=" * 80)
    print("PART 9: RAW EVENT BYTE-LEVEL ANALYSIS (no de-rotation)")
    print("Check each byte position for note-like values")
    print("=" * 80)

    all_events = defaultdict(lambda: defaultdict(list))

    for track_idx, track_name in [(3, "C1"), (4, "C2"), (6, "C3"), (7, "C4")]:
        for section in range(6):
            data = get_track_data(syx_path, section, track_idx)
            bars = get_all_bars(data)

            for bar_idx, (header, events) in enumerate(bars):
                for ei, evt in enumerate(events[:4]):
                    if len(evt) != 7:
                        break
                    for byte_pos in range(7):
                        all_events[track_name][byte_pos].append(evt[byte_pos])

    for track_name in ["C2", "C4", "C1"]:
        print(f"\n  {track_name}:")
        for byte_pos in range(7):
            values = all_events[track_name][byte_pos]
            lo7_values = [v & 0x7F for v in values]
            unique_lo7 = sorted(set(lo7_values))
            in_note_range = sum(1 for v in lo7_values if 36 <= v <= 96)

            bit7_1 = sum(1 for v in values if v & 0x80)
            bit7_0 = len(values) - bit7_1

            print(
                f"    Byte {byte_pos}: bit7=1:{bit7_1}/0:{bit7_0}  "
                f"lo7_unique={len(unique_lo7)}  "
                f"in_note_range={in_note_range}/{len(values)}  "
                f"values={unique_lo7[:15]}"
            )


# ============================================================================
# PART 10: Correlate header fields with event content
# ============================================================================


def header_event_correlation(syx_path):
    """Test: does the bar header's F0-F4 (potential chord notes) determine
    which notes appear in the events?"""
    print()
    print("=" * 80)
    print("PART 10: HEADER-EVENT CORRELATION")
    print("Do header MIDI notes appear in the events?")
    print("=" * 80)

    c2 = get_track_data(syx_path, 0, 4)
    c3_s0 = get_track_data(syx_path, 0, 6)

    for name, data in [("C2", c2), ("C3_S0", c3_s0)]:
        bars = get_all_bars(data)
        print(f"\n--- {name} ---")

        for bar_idx, (header, events) in enumerate(bars):
            hdr_val = int.from_bytes(header, "big")
            hdr_fields = [extract_field(hdr_val, fi * 9, 9, 104) for fi in range(5)]
            hdr_midi = [f for f in hdr_fields if 0 <= f <= 127]

            # Extract all byte values from events
            event_bytes = []
            event_lo7 = []
            for evt in events[:4]:
                for b in evt:
                    event_bytes.append(b)
                    event_lo7.append(b & 0x7F)

            # Check if header MIDI values appear in event lo7
            found = {h: event_lo7.count(h) for h in hdr_midi}
            print(f"  Bar {bar_idx}: header MIDI={hdr_midi} → found in events: {found}")


if __name__ == "__main__":
    syx_path = sys.argv[1] if len(sys.argv) > 1 else "tests/fixtures/QY70_SGT.syx"

    confirm_shift_register(syx_path)
    extract_new_values(syx_path)
    compare_c2_c4_new_values(syx_path)
    cross_section_new_values(syx_path)
    decompose_f0(syx_path)
    full_derotated_structure(syx_path)
    test_alternative_widths(syx_path)
    header_chord_analysis(syx_path)
    raw_event_analysis(syx_path)
    header_event_correlation(syx_path)
