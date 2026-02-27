#!/usr/bin/env python3
"""
Focused Hypothesis Testing — Session 8
========================================

KEY OBSERVATIONS from comprehensive_decoder.py:
1. R=9 is UNIVERSAL (confirmed for BASS too, avg 16.5 bits differ)
2. F0/F1/F2 is a 3-deep shift register (F1[n]=F0[n-1], F2[n]=F1[n-1])
3. F5 for C2 S0 bar1: [94, 110, 126, 126] — monotonically increasing, then plateau
4. C2 vs C4: F3 differs by +1, F4 differs by large amounts, F5 identical
5. C3 S0 has 30 events with varying content — our best dataset
6. DC delimiters absent from D2 (drums) — DC is chord-specific
7. Bar headers encode chord notes as 9-bit MIDI values

THIS SCRIPT TESTS:
A) Is F5 a timing accumulator? (monotonic increase within bar = beat position)
B) Is F3 a note/velocity field? (correlates with header chord notes)
C) Is F4 a packed note+octave? (large jumps suggest multi-field encoding)
D) What do F3/F4/F5 look like in C3 S0 (30 events, unique data)?
E) Can we find note-to-field mapping by comparing bars with different chords?
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


def nn(n):
    if 0 <= n <= 127:
        return f"{NOTE_NAMES[n % 12]}{n // 12 - 1}"
    return f"?{n}"


def rot_left(val, shift, width=56):
    shift = shift % width
    return ((val << shift) | (val >> (width - shift))) & ((1 << width) - 1)


def rot_right(val, shift, width=56):
    return rot_left(val, width - shift, width)


def extract_9bit(val, field_idx, total_width=56):
    """Extract 9-bit field at position field_idx (0=MSB)."""
    shift = total_width - (field_idx + 1) * 9
    if shift < 0:
        return -1
    return (val >> shift) & 0x1FF


def hex_str(data):
    return " ".join(f"{b:02X}" for b in data)


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
    """Extract bars from decoded track data. Returns [(header_13, [evt_7bytes,...])...]"""
    if len(data) < 28:
        return []
    event_data = data[28:]  # Skip 24-byte track header + 4-byte preamble
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
                evt = seg[13 + i * 7 : 13 + (i + 1) * 7]
                if len(evt) == 7:
                    events.append(evt)
            bars.append((header, events))
    return bars


def derotate_events(events, R=9):
    """De-rotate events and extract 9-bit fields."""
    result = []
    for ei, evt in enumerate(events):
        if len(evt) != 7:
            continue
        val = int.from_bytes(evt, "big")
        derot = rot_right(val, ei * R)
        fields = [extract_9bit(derot, fi) for fi in range(6)]
        rem = derot & 0x3
        result.append(fields)
    return result


def decode_header_9bit(header_13):
    """Decode 13-byte header as 9-bit fields (104 bits → 11 fields + 5 rem)."""
    val = int.from_bytes(header_13, "big")
    fields = []
    for fi in range(11):
        shift = 104 - (fi + 1) * 9
        if shift < 0:
            break
        fields.append((val >> shift) & 0x1FF)
    rem = val & 0x1F  # 104 - 99 = 5 remainder bits
    return fields, rem


# ============================================================================
# TEST A: F5 as Timing Accumulator
# ============================================================================


def test_f5_timing(syx_path):
    """Is F5 a timing accumulator (beat position within bar)?
    If so, F5 should increase monotonically within each bar.
    """
    print("=" * 80)
    print("TEST A: F5 AS TIMING ACCUMULATOR")
    print("Hypothesis: F5 increases monotonically within each bar (beat position)")
    print("=" * 80)

    tracks = [
        (4, "C2", 0),
        (7, "C4", 0),
        (6, "C1", 0),
        (5, "C3", 0),
        (5, "C3", 1),  # C3 S1 = default pattern
    ]

    for track_idx, track_name, section in tracks:
        data = get_track_data(syx_path, section, track_idx)
        if not data:
            continue
        bars = get_all_bars(data)

        print(f"\n--- {track_name} S{section} ({len(bars)} bars) ---")
        for bi, (header, events) in enumerate(bars):
            fields_list = derotate_events(events)
            f5_values = [f[5] for f in fields_list if len(f) > 5]
            is_monotonic = all(f5_values[i] <= f5_values[i + 1] for i in range(len(f5_values) - 1))
            diffs = [f5_values[i + 1] - f5_values[i] for i in range(len(f5_values) - 1)]
            print(f"  Bar{bi}: F5={f5_values}  monotonic={is_monotonic}  diffs={diffs}")

    # Also check BASS
    data = get_track_data(syx_path, 0, 3)
    if data:
        bars = get_all_bars(data)
        print(f"\n--- BASS S0 ({len(bars)} bars) ---")
        for bi, (header, events) in enumerate(bars):
            fields_list = derotate_events(events)
            f5_values = [f[5] for f in fields_list if len(f) > 5]
            is_mono = (
                all(f5_values[i] <= f5_values[i + 1] for i in range(len(f5_values) - 1))
                if len(f5_values) > 1
                else True
            )
            print(
                f"  Bar{bi}: F5={f5_values[:10]}{'...' if len(f5_values) > 10 else ''}"
                f"  monotonic={is_mono}"
            )


# ============================================================================
# TEST B: F3 Field Analysis — Note or Velocity?
# ============================================================================


def test_f3_note_velocity(syx_path):
    """F3 differs by +1 between C2/C4 (one semitone transposition?).
    Test: Does F3 lo7 correlate with header chord notes?
    """
    print()
    print("=" * 80)
    print("TEST B: F3 — NOTE OR VELOCITY?")
    print("F3 differs by +1 between C2/C4. Checking if it maps to chord notes.")
    print("=" * 80)

    # C3 S0 has different chords per bar — perfect test case
    data = get_track_data(syx_path, 0, 5)  # C3 = track 5
    if not data:
        return
    bars = get_all_bars(data)

    print(f"\n--- C3 S0: {len(bars)} bars with varying chord content ---")
    for bi, (header, events) in enumerate(bars):
        hdr_fields, hdr_rem = decode_header_9bit(header)
        hdr_notes = [nn(f) if f <= 127 else f">{f}" for f in hdr_fields[:5]]
        fields_list = derotate_events(events)

        print(f"\n  Bar{bi}: header_notes={hdr_notes}")
        for ei, fields in enumerate(fields_list[:6]):  # Limit output
            f3_lo7 = fields[3] & 0x7F
            f3_hi2 = (fields[3] >> 7) & 0x3
            print(
                f"    E{ei}: F3={fields[3]:3d} (lo7={f3_lo7}={nn(f3_lo7)}, hi2={f3_hi2})"
                f"  F0={fields[0]:3d}"
            )

    # Compare C2 vs C4 F3 values (same bar)
    print(f"\n--- C2 vs C4 F3 Comparison (S0) ---")
    c2_data = get_track_data(syx_path, 0, 4)
    c4_data = get_track_data(syx_path, 0, 7)
    c2_bars = get_all_bars(c2_data) if c2_data else []
    c4_bars = get_all_bars(c4_data) if c4_data else []

    for bi in range(min(len(c2_bars), len(c4_bars))):
        c2_fields = derotate_events(c2_bars[bi][1])
        c4_fields = derotate_events(c4_bars[bi][1])
        print(f"  Bar{bi}:")
        for ei in range(min(len(c2_fields), len(c4_fields))):
            c2_f3, c4_f3 = c2_fields[ei][3], c4_fields[ei][3]
            diff = c4_f3 - c2_f3
            # Decompose F3 into hi2 + lo7
            c2_lo7, c4_lo7 = c2_f3 & 0x7F, c4_f3 & 0x7F
            c2_hi2, c4_hi2 = c2_f3 >> 7, c4_f3 >> 7
            print(
                f"    E{ei}: C2_F3={c2_f3:3d}(hi2={c2_hi2},lo7={c2_lo7}={nn(c2_lo7)}) "
                f"C4_F3={c4_f3:3d}(hi2={c4_hi2},lo7={c4_lo7}={nn(c4_lo7)}) "
                f"diff={diff:+d}"
            )


# ============================================================================
# TEST C: F4 Decomposition — Packed Note+Octave?
# ============================================================================


def test_f4_decomposition(syx_path):
    """F4 has large jumps between C2/C4 (+244, -16, +248, +248).
    Try decomposing as different sub-field combinations.
    """
    print()
    print("=" * 80)
    print("TEST C: F4 DECOMPOSITION — PACKED FIELDS?")
    print("F4 values: C2=[172,188,188,186] C4=[416,172,436,434]")
    print("Differences: [+244,-16,+248,+248] — too large for simple transposition")
    print("=" * 80)

    c2_data = get_track_data(syx_path, 0, 4)
    c4_data = get_track_data(syx_path, 0, 7)
    c2_bars = get_all_bars(c2_data) if c2_data else []
    c4_bars = get_all_bars(c4_data) if c4_data else []

    if not c2_bars or not c4_bars:
        print("  No data")
        return

    # Get bar1 events
    c2_fields = derotate_events(c2_bars[1][1]) if len(c2_bars) > 1 else []
    c4_fields = derotate_events(c4_bars[1][1]) if len(c4_bars) > 1 else []

    # Try different decompositions of the 9-bit F4 field
    decompositions = [
        ("1+8 (flag+value)", [(0, 1), (1, 8)]),
        ("2+7 (type+note)", [(0, 2), (2, 7)]),
        ("3+6 (oct+note)", [(0, 3), (3, 6)]),
        ("4+5 (oct+note)", [(0, 4), (4, 5)]),
        ("5+4 (note+gate)", [(0, 5), (5, 4)]),
        ("1+4+4 (flag+hi+lo)", [(0, 1), (1, 4), (5, 4)]),
        ("2+3+4 (type+oct+note)", [(0, 2), (2, 3), (5, 4)]),
        ("1+1+7 (flag+oct+note)", [(0, 1), (1, 1), (2, 7)]),
    ]

    for name, slices in decompositions:
        print(f"\n  --- {name} ---")
        for ei in range(min(len(c2_fields), len(c4_fields), 4)):
            c2_f4 = c2_fields[ei][4]
            c4_f4 = c4_fields[ei][4]

            c2_parts = []
            c4_parts = []
            for start, width in slices:
                c2_parts.append((c2_f4 >> (9 - start - width)) & ((1 << width) - 1))
                c4_parts.append((c4_f4 >> (9 - start - width)) & ((1 << width) - 1))

            diffs = [c4_parts[j] - c2_parts[j] for j in range(len(c2_parts))]
            print(f"    E{ei}: C2={c2_parts} C4={c4_parts} diff={diffs}")


# ============================================================================
# TEST D: C3 S0 Full Decode (30 events, unique data)
# ============================================================================


def test_c3_full_decode(syx_path):
    """C3 S0 has ~30 events with varying musical content.
    This is our richest dataset for pattern detection.
    """
    print()
    print("=" * 80)
    print("TEST D: C3 S0 FULL DECODE (Unique Musical Content)")
    print("=" * 80)

    data = get_track_data(syx_path, 0, 5)  # C3 = track 5
    if not data:
        print("  No C3 data")
        return

    bars = get_all_bars(data)
    print(f"  {len(bars)} bars")

    all_f0 = []
    all_f3 = []
    all_f4 = []
    all_f5 = []

    for bi, (header, events) in enumerate(bars):
        hdr_fields, hdr_rem = decode_header_9bit(header)
        hdr_notes_5 = [nn(f) if f <= 127 else f">{f}" for f in hdr_fields[:5]]
        fields_list = derotate_events(events)

        print(f"\n  Bar{bi} ({len(events)} events): header_chord={hdr_notes_5}")
        print(f"    Header 9-bit fields: {hdr_fields}")
        print(
            f"    {'Evt':>3s}  {'F0':>5s}  {'F1':>5s}  {'F2':>5s}  "
            f"{'F3':>5s} {'F3_note':>8s}  {'F4':>5s} {'F4_note':>8s}  "
            f"{'F5':>5s} {'F5_note':>8s}"
        )

        for ei, fields in enumerate(fields_list):
            f0, f1, f2, f3, f4, f5 = fields[:6]
            all_f0.append(f0)
            all_f3.append(f3)
            all_f4.append(f4)
            all_f5.append(f5)

            f3_lo7 = f3 & 0x7F
            f4_lo7 = f4 & 0x7F
            f5_lo7 = f5 & 0x7F
            print(
                f"    E{ei:2d}  {f0:5d}  {f1:5d}  {f2:5d}  "
                f"{f3:5d} {nn(f3_lo7):>8s}  {f4:5d} {nn(f4_lo7):>8s}  "
                f"{f5:5d} {nn(f5_lo7):>8s}"
            )

    # Statistical analysis
    print(f"\n  --- Field Statistics ---")
    for name, values in [("F0", all_f0), ("F3", all_f3), ("F4", all_f4), ("F5", all_f5)]:
        if not values:
            continue
        uniq = sorted(set(values))
        print(
            f"  {name}: {len(values)} values, {len(uniq)} unique, "
            f"range [{min(values)}-{max(values)}]"
        )
        # Check bit decomposition
        lo7_uniq = sorted(set(v & 0x7F for v in values))
        hi2_uniq = sorted(set((v >> 7) & 0x3 for v in values))
        print(
            f"    lo7: {len(lo7_uniq)} unique = {lo7_uniq[:15]}{'...' if len(lo7_uniq) > 15 else ''}"
        )
        print(f"    hi2: {hi2_uniq}")
        # Check if lo7 values are valid MIDI notes
        valid_notes = [v for v in lo7_uniq if 24 <= v <= 96]
        if valid_notes:
            print(f"    Musical lo7 notes (C1-C7): {[nn(v) for v in valid_notes]}")


# ============================================================================
# TEST E: Header Chord ↔ Event Field Correlation
# ============================================================================


def test_header_event_correlation(syx_path):
    """Compare bars with DIFFERENT header chords to find which event fields change.
    C3 S0 has unique headers per bar — perfect for correlation.
    """
    print()
    print("=" * 80)
    print("TEST E: HEADER CHORD ↔ EVENT FIELD CORRELATION")
    print("Which event fields change when the header chord changes?")
    print("=" * 80)

    # Compare C3 S0 (unique chords) vs C3 S1 (default chord)
    c3_s0 = get_track_data(syx_path, 0, 5)
    c3_s1 = get_track_data(syx_path, 1, 5)

    if not c3_s0 or not c3_s1:
        print("  No C3 data")
        return

    s0_bars = get_all_bars(c3_s0)
    s1_bars = get_all_bars(c3_s1)

    print(f"  C3 S0: {len(s0_bars)} bars (unique)")
    print(f"  C3 S1: {len(s1_bars)} bars (default)")

    # For each bar pair, compare fields
    for bi in range(min(len(s0_bars), len(s1_bars))):
        s0_hdr, s0_evts = s0_bars[bi]
        s1_hdr, s1_evts = s1_bars[bi]

        s0_hdr_fields, _ = decode_header_9bit(s0_hdr)
        s1_hdr_fields, _ = decode_header_9bit(s1_hdr)

        s0_fields = derotate_events(s0_evts)
        s1_fields = derotate_events(s1_evts)

        hdr_same = s0_hdr == s1_hdr
        s0_notes = [nn(f) if f <= 127 else f">{f}" for f in s0_hdr_fields[:5]]
        s1_notes = [nn(f) if f <= 127 else f">{f}" for f in s1_hdr_fields[:5]]

        print(f"\n  Bar{bi}: header {'SAME' if hdr_same else 'DIFFERENT'}")
        if not hdr_same:
            print(f"    S0 chord: {s0_notes}")
            print(f"    S1 chord: {s1_notes}")
            # Show field-by-field header diff
            hdr_diffs = [
                s0_hdr_fields[i] - s1_hdr_fields[i]
                for i in range(min(len(s0_hdr_fields), len(s1_hdr_fields)))
            ]
            print(f"    Header field diffs (S0-S1): {hdr_diffs}")

        # Compare event fields
        for ei in range(min(len(s0_fields), len(s1_fields), 4)):
            diffs = [s0_fields[ei][fi] - s1_fields[ei][fi] for fi in range(6)]
            changed = [fi for fi in range(6) if diffs[fi] != 0]
            if changed:
                print(f"    E{ei}: changed fields={changed}  diffs={diffs}")
                for fi in changed:
                    print(
                        f"      F{fi}: S0={s0_fields[ei][fi]:3d} S1={s1_fields[ei][fi]:3d} "
                        f"diff={diffs[fi]:+d}"
                    )


# ============================================================================
# TEST F: Binary Decomposition of F3 and F4
# ============================================================================


def test_binary_decomposition(syx_path):
    """Look at F3 and F4 bit patterns across all events.
    Key insight: F3 values cluster around multiples of 128 (bit 7 boundary).
    """
    print()
    print("=" * 80)
    print("TEST F: BINARY DECOMPOSITION OF F3 AND F4")
    print("=" * 80)

    tracks = [(4, "C2"), (7, "C4"), (6, "C1"), (5, "C3")]

    for track_idx, track_name in tracks:
        data = get_track_data(syx_path, 0, track_idx)
        if not data:
            continue
        bars = get_all_bars(data)

        print(f"\n--- {track_name} S0 ---")
        for bi, (header, events) in enumerate(bars[:3]):  # First 3 bars
            fields_list = derotate_events(events)
            for ei, fields in enumerate(fields_list[:4]):
                f3_bin = format(fields[3], "09b")
                f4_bin = format(fields[4], "09b")
                f5_bin = format(fields[5], "09b")
                # Also show as bit groups
                f3_grp = f"{f3_bin[:2]}|{f3_bin[2:5]}|{f3_bin[5:]}"
                f4_grp = f"{f4_bin[:2]}|{f4_bin[2:5]}|{f4_bin[5:]}"
                f5_grp = f"{f5_bin[:2]}|{f5_bin[2:5]}|{f5_bin[5:]}"
                print(
                    f"  B{bi}E{ei}: F3={fields[3]:3d} {f3_grp}  "
                    f"F4={fields[4]:3d} {f4_grp}  "
                    f"F5={fields[5]:3d} {f5_grp}"
                )


# ============================================================================
# TEST G: Event-to-Event Transition Analysis
# ============================================================================


def test_transitions(syx_path):
    """Analyze how F3/F4/F5 change between consecutive events within a bar.
    Look for velocity/note patterns.
    """
    print()
    print("=" * 80)
    print("TEST G: EVENT-TO-EVENT TRANSITIONS (within bars)")
    print("How do F3/F4/F5 change between beats?")
    print("=" * 80)

    tracks = [(4, "C2"), (7, "C4"), (5, "C3")]

    for track_idx, track_name in tracks:
        data = get_track_data(syx_path, 0, track_idx)
        if not data:
            continue
        bars = get_all_bars(data)

        print(f"\n--- {track_name} S0 ---")
        for bi, (header, events) in enumerate(bars[:3]):
            fields_list = derotate_events(events)
            if len(fields_list) < 2:
                continue

            print(f"  Bar{bi} ({len(fields_list)} events):")
            for ei in range(len(fields_list) - 1):
                curr = fields_list[ei]
                nxt = fields_list[ei + 1]
                d3 = nxt[3] - curr[3]
                d4 = nxt[4] - curr[4]
                d5 = nxt[5] - curr[5]
                print(f"    E{ei}→E{ei + 1}: ΔF3={d3:+4d}  ΔF4={d4:+4d}  ΔF5={d5:+4d}")


# ============================================================================
# TEST H: F5 Value Spacing Analysis
# ============================================================================


def test_f5_spacing(syx_path):
    """F5 for C2 bar1: [94, 110, 126, 126] — spacing is [16, 16, 0].
    Is 16 a beat-spacing constant? Check across all tracks/bars.
    """
    print()
    print("=" * 80)
    print("TEST H: F5 VALUE SPACING ANALYSIS")
    print("C2 bar1 F5=[94,110,126,126], spacing=[16,16,0]")
    print("Is 16 the beat spacing? Does F5 encode beat position?")
    print("=" * 80)

    tracks = [(4, "C2"), (7, "C4"), (6, "C1"), (5, "C3")]

    all_spacings = []

    for track_idx, track_name in tracks:
        for section in range(6):
            data = get_track_data(syx_path, section, track_idx)
            if not data:
                continue
            bars = get_all_bars(data)

            for bi, (header, events) in enumerate(bars):
                fields_list = derotate_events(events)
                f5_vals = [f[5] for f in fields_list]
                if len(f5_vals) < 2:
                    continue

                spacings = [f5_vals[i + 1] - f5_vals[i] for i in range(len(f5_vals) - 1)]
                all_spacings.extend(spacings)

                # Only print if spacing is interesting
                if track_name == "C2" and section == 0:
                    print(f"  {track_name} S{section} B{bi}: F5={f5_vals}  spacing={spacings}")
                elif track_name == "C3" and section == 0:
                    if bi < 3:  # First 3 bars of C3 S0
                        print(
                            f"  {track_name} S{section} B{bi}: F5={f5_vals[:8]}{'...' if len(f5_vals) > 8 else ''}"
                        )
                        print(f"    spacing={spacings[:8]}{'...' if len(spacings) > 8 else ''}")

    # Spacing distribution
    print(f"\n  --- F5 Spacing Distribution (all tracks/sections) ---")
    spacing_counter = Counter(all_spacings)
    for val, count in spacing_counter.most_common(15):
        bar = "█" * min(count, 40)
        print(f"    {val:+5d}: {count:3d}x  {bar}")


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    syx_path = sys.argv[1] if len(sys.argv) > 1 else SGT_PATH

    if not os.path.exists(syx_path):
        print(f"File not found: {syx_path}")
        sys.exit(1)

    print(f"Analyzing: {syx_path}\n")

    test_f5_timing(syx_path)
    test_f3_note_velocity(syx_path)
    test_f4_decomposition(syx_path)
    test_c3_full_decode(syx_path)
    test_header_event_correlation(syx_path)
    test_binary_decomposition(syx_path)
    test_transitions(syx_path)
    test_f5_spacing(syx_path)

    print("\n" + "=" * 80)
    print("HYPOTHESIS TESTING COMPLETE")
    print("=" * 80)
