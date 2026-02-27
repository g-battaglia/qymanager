#!/usr/bin/env python3
"""
Note Field Cracker — Session 8 (continued)
============================================

KEY INSIGHT: The C2/C4 XOR after de-rotation falls at bits 35-42,
which straddles the F3/F4 boundary (F3=bits 27-35, F4=bits 36-44).
The note field likely spans this boundary.

APPROACH:
1. Compare C2 across sections (S0-S2=identical, S3/S4/S5=different chords)
2. Extract the straddling field and look for chord-tone correlations
3. Test if events encode "which chord tones to play" from the header
4. Decode F5 as timing/gate by checking bit patterns
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qymanager.formats.qy70.sysex_parser import SysExParser

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


def rot_right(val, shift, width=56):
    shift = shift % width
    return ((val >> shift) | (val << (width - shift))) & ((1 << width) - 1)


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
                evt = seg[13 + i * 7 : 13 + (i + 1) * 7]
                if len(evt) == 7:
                    events.append(evt)
            bars.append((header, events))
    return bars


def decode_header_notes(header_13):
    """Decode 13-byte header as 9-bit fields, return first 5 as chord notes."""
    val = int.from_bytes(header_13, "big")
    fields = []
    for fi in range(11):
        shift = 104 - (fi + 1) * 9
        if shift < 0:
            break
        fields.append((val >> shift) & 0x1FF)
    return fields


def derotate_event(evt_bytes, event_index, R=9):
    """De-rotate a single event and return the full 56-bit value."""
    val = int.from_bytes(evt_bytes, "big")
    return rot_right(val, event_index * R)


def extract_9bit(val, field_idx, total_width=56):
    shift = total_width - (field_idx + 1) * 9
    if shift < 0:
        return -1
    return (val >> shift) & 0x1FF


def hex_str(data):
    return " ".join(f"{b:02X}" for b in data)


# ============================================================================
# PART 1: Cross-Section Chord Comparison
# ============================================================================


def cross_section_chords(syx_path):
    """Compare C2 across sections where chord content differs.
    S0-S2 = identical, S3-S4 = fill variants, S5 = ending.
    """
    print("=" * 90)
    print("PART 1: CROSS-SECTION CHORD COMPARISON (C2)")
    print("S0-S2 identical | S3-S4 fills | S5 ending → different header chords")
    print("=" * 90)

    for section in range(6):
        data = get_track_data(syx_path, section, 4)  # C2 = track 4
        if not data or len(data) < 28:
            continue
        bars = get_all_bars(data)

        print(f"\n{'=' * 60}")
        print(f"  C2 Section {section} ({len(bars)} bars)")

        for bi, (header, events) in enumerate(bars):
            hdr_fields = decode_header_notes(header)
            hdr_notes = [nn(f) if f <= 127 else f">{f}" for f in hdr_fields[:5]]

            print(f"\n    Bar{bi}: chord={hdr_notes}")
            print(f"    Header hex: {hex_str(header)}")
            print(f"    Header 9-bit: {hdr_fields}")

            # De-rotate events and show all 6 fields
            for ei, evt in enumerate(events[:4]):
                derot = derotate_event(evt, ei)
                fields = [extract_9bit(derot, fi) for fi in range(6)]
                rem = derot & 0x3

                # Binary decomposition of F3 and F4
                f3_bin = format(fields[3], "09b")
                f4_bin = format(fields[4], "09b")

                # Straddling field: F3 lo4 + F4 hi5
                straddle = ((fields[3] & 0xF) << 5) | (fields[4] >> 4)
                straddle_note = nn(straddle) if straddle <= 127 else f">{straddle}"

                print(
                    f"      E{ei}: F0={fields[0]:3d} F3={fields[3]:3d}[{f3_bin}] "
                    f"F4={fields[4]:3d}[{f4_bin}] F5={fields[5]:3d} "
                    f"straddle={straddle:3d}({straddle_note})"
                )


# ============================================================================
# PART 2: F3 One-Hot Beat Pattern Verification
# ============================================================================


def verify_f3_onehot(syx_path):
    """F3 lo4 for C2 S0: 1000,0100,0010,0001 (one-hot beat counter).
    Verify this holds across ALL tracks and sections.
    """
    print()
    print("=" * 90)
    print("PART 2: F3 LO4 ONE-HOT BEAT PATTERN")
    print("C2 S0: lo4 = 1000→0100→0010→0001. Is this universal?")
    print("=" * 90)

    tracks = [(4, "C2"), (7, "C4"), (6, "C1"), (5, "C3")]

    for track_idx, track_name in tracks:
        print(f"\n--- {track_name} ---")
        for section in range(6):
            data = get_track_data(syx_path, section, track_idx)
            if not data:
                continue
            bars = get_all_bars(data)

            # Skip duplicate sections
            if section > 0 and track_name in ("C2",):
                prev = get_track_data(syx_path, 0, track_idx)
                if prev == data:
                    continue

            for bi, (header, events) in enumerate(bars[:3]):  # First 3 bars
                lo4_pattern = []
                mid3_pattern = []
                hi2_pattern = []

                for ei, evt in enumerate(events[:6]):
                    derot = derotate_event(evt, ei)
                    f3 = extract_9bit(derot, 3)
                    lo4 = f3 & 0xF
                    mid3 = (f3 >> 4) & 0x7
                    hi2 = (f3 >> 7) & 0x3
                    lo4_pattern.append(format(lo4, "04b"))
                    mid3_pattern.append(mid3)
                    hi2_pattern.append(hi2)

                is_onehot = all(bin(int(p, 2)).count("1") <= 1 for p in lo4_pattern)
                print(
                    f"  S{section}B{bi}: lo4=[{','.join(lo4_pattern)}] "
                    f"mid3={mid3_pattern} hi2={hi2_pattern} "
                    f"one-hot={'YES' if is_onehot else 'NO'}"
                )


# ============================================================================
# PART 3: F4 as Chord-Tone Mask
# ============================================================================


def test_chord_tone_mask(syx_path):
    """Hypothesis: F4 encodes which chord tones from the header to play.
    Header has 5 notes. If F4 is a 5-bit mask, only 32 possible values.
    """
    print()
    print("=" * 90)
    print("PART 3: F4 AS CHORD-TONE MASK")
    print("Header defines 5 chord notes. Does F4 select which ones to play?")
    print("=" * 90)

    for section in range(6):
        data = get_track_data(syx_path, section, 4)  # C2
        if not data:
            continue
        bars = get_all_bars(data)

        # Skip duplicates
        if section > 0:
            prev = get_track_data(syx_path, 0, 4)
            if prev == data:
                continue

        for bi, (header, events) in enumerate(bars[:2]):
            hdr_fields = decode_header_notes(header)
            hdr_notes = [nn(f) if f <= 127 else f">{f}" for f in hdr_fields[:5]]

            print(f"\n  C2 S{section} B{bi}: chord={hdr_notes}")

            for ei, evt in enumerate(events[:4]):
                derot = derotate_event(evt, ei)
                f4 = extract_9bit(derot, 4)

                # Try F4 as 5-bit mask + 4-bit parameter
                mask5 = (f4 >> 4) & 0x1F
                param4 = f4 & 0xF
                mask_bits = format(mask5, "05b")

                # Which chord tones are selected?
                selected = [hdr_fields[i] for i in range(5) if (mask5 >> (4 - i)) & 1]
                selected_names = [nn(n) if n <= 127 else f">{n}" for n in selected]

                # Also try 4-bit mask + 5-bit parameter
                mask4 = (f4 >> 5) & 0xF
                param5 = f4 & 0x1F
                mask4_bits = format(mask4, "04b")

                # And 3-bit + 6-bit
                top3 = (f4 >> 6) & 0x7
                mid6 = f4 & 0x3F

                print(
                    f"    E{ei}: F4={f4:3d} [{format(f4, '09b')}]  "
                    f"5mask={mask_bits}→{selected_names} param4={param4}  |  "
                    f"4mask={mask4_bits} param5={param5}  |  "
                    f"top3={top3} mid6={mid6}"
                )


# ============================================================================
# PART 4: RAW Byte-Level XOR Analysis
# ============================================================================


def raw_xor_analysis(syx_path):
    """Look at raw (non-derotated) XOR between C2 and C4 at all sections.
    The XOR pattern should reveal the note field position directly.
    """
    print()
    print("=" * 90)
    print("PART 4: RAW BYTE-LEVEL XOR (C2 vs C4, all sections)")
    print("=" * 90)

    for section in range(6):
        c2_data = get_track_data(syx_path, section, 4)
        c4_data = get_track_data(syx_path, section, 7)
        if not c2_data or not c4_data:
            continue
        c2_bars = get_all_bars(c2_data)
        c4_bars = get_all_bars(c4_data)

        # Skip if identical
        if c2_data == c4_data:
            continue

        for bi in range(min(len(c2_bars), len(c4_bars))):
            _, c2_evts = c2_bars[bi]
            _, c4_evts = c4_bars[bi]

            n_events = min(len(c2_evts), len(c4_evts), 4)
            if n_events == 0:
                continue

            print(f"\n  S{section} B{bi}:")
            for ei in range(n_events):
                xor = bytes(a ^ b for a, b in zip(c2_evts[ei], c4_evts[ei]))
                diff_bytes = [(i, c2_evts[ei][i], c4_evts[ei][i]) for i in range(7) if xor[i] != 0]
                xor_hex = hex_str(xor)
                xor_bits = "".join(format(b, "08b") for b in xor)
                diff_positions = [i for i, b in enumerate(xor_bits) if b == "1"]

                print(f"    E{ei}: XOR={xor_hex}  bits@{diff_positions}")
                for byte_idx, c2_val, c4_val in diff_bytes:
                    print(
                        f"      byte{byte_idx}: C2=0x{c2_val:02X} C4=0x{c4_val:02X} "
                        f"XOR=0x{xor[byte_idx]:02X}={format(xor[byte_idx], '08b')}"
                    )


# ============================================================================
# PART 5: F5 Bit Pattern Analysis
# ============================================================================


def analyze_f5_bits(syx_path):
    """F5 spacing is mostly +16 or +32 (powers of 2).
    Look at F5 binary patterns — maybe it's not a simple counter.
    """
    print()
    print("=" * 90)
    print("PART 5: F5 BIT PATTERN ANALYSIS")
    print("F5 increments by +16 or +32. What do the bits look like?")
    print("=" * 90)

    tracks = [(4, "C2"), (7, "C4"), (6, "C1")]

    for track_idx, track_name in tracks:
        print(f"\n--- {track_name} ---")
        for section in [0]:
            data = get_track_data(syx_path, section, track_idx)
            if not data:
                continue
            bars = get_all_bars(data)

            for bi, (header, events) in enumerate(bars[:3]):
                print(f"  S{section}B{bi}:")
                for ei, evt in enumerate(events[:4]):
                    derot = derotate_event(evt, ei)
                    f5 = extract_9bit(derot, 5)
                    f5_bin = format(f5, "09b")
                    # Decompose: top2 | mid4 | lo3
                    top2 = (f5 >> 7) & 0x3
                    mid4 = (f5 >> 3) & 0xF
                    lo3 = f5 & 0x7

                    # Also decompose: bit8 | 7-bit value
                    hi1 = (f5 >> 8) & 1
                    lo8 = f5 & 0xFF

                    print(
                        f"    E{ei}: F5={f5:3d} [{f5_bin}] "
                        f"top2={top2} mid4={mid4:2d}({format(mid4, '04b')}) lo3={lo3} "
                        f"| hi1={hi1} lo8={lo8:3d}({nn(lo8) if lo8 <= 127 else '>'})"
                    )


# ============================================================================
# PART 6: Adjacent Section Header Chord Comparison
# ============================================================================


def compare_section_headers(syx_path):
    """Compare header chord notes across sections for the SAME track.
    Look for sections with DIFFERENT chords to correlate events.
    """
    print()
    print("=" * 90)
    print("PART 6: HEADER CHORD NOTES ACROSS SECTIONS")
    print("=" * 90)

    tracks = [(4, "C2"), (7, "C4"), (6, "C1"), (5, "C3")]

    for track_idx, track_name in tracks:
        print(f"\n--- {track_name} ---")
        prev_hdr = None
        for section in range(6):
            data = get_track_data(syx_path, section, track_idx)
            if not data:
                continue
            bars = get_all_bars(data)

            for bi, (header, events) in enumerate(bars):
                hdr_fields = decode_header_notes(header)
                hdr_notes = [nn(f) if f <= 127 else f">{f}" for f in hdr_fields[:5]]
                is_dup = (header == prev_hdr) if prev_hdr is not None else False
                marker = " (SAME)" if is_dup else ""
                print(f"  S{section}B{bi}: {hdr_notes}  fields={hdr_fields[:5]}{marker}")
                prev_hdr = header


# ============================================================================
# PART 7: Decode C2 S3 vs C2 S0 (Different Chords)
# ============================================================================


def decode_cross_chord(syx_path):
    """C2 S0 and C2 S3 have DIFFERENT header chords.
    Compare their events field-by-field to find what changes.
    """
    print()
    print("=" * 90)
    print("PART 7: C2 S0 vs S3/S5 (DIFFERENT CHORD CONTENT)")
    print("=" * 90)

    sections_to_compare = [0, 3, 4, 5]

    section_data = {}
    for s in sections_to_compare:
        data = get_track_data(syx_path, s, 4)  # C2
        if data:
            bars = get_all_bars(data)
            section_data[s] = bars

    ref_section = 0
    if ref_section not in section_data:
        return

    ref_bars = section_data[ref_section]

    for comp_section in sections_to_compare:
        if comp_section == ref_section:
            continue
        if comp_section not in section_data:
            continue

        comp_bars = section_data[comp_section]
        print(f"\n{'=' * 60}")
        print(f"  C2 S{ref_section} vs S{comp_section}")

        for bi in range(min(len(ref_bars), len(comp_bars))):
            ref_hdr, ref_evts = ref_bars[bi]
            comp_hdr, comp_evts = comp_bars[bi]

            ref_hdr_fields = decode_header_notes(ref_hdr)
            comp_hdr_fields = decode_header_notes(comp_hdr)

            ref_notes = [nn(f) if f <= 127 else f">{f}" for f in ref_hdr_fields[:5]]
            comp_notes = [nn(f) if f <= 127 else f">{f}" for f in comp_hdr_fields[:5]]

            hdr_same = ref_hdr == comp_hdr
            print(f"\n    B{bi}: S{ref_section} chord={ref_notes}")
            print(
                f"         S{comp_section} chord={comp_notes}  "
                f"{'SAME' if hdr_same else 'DIFFERENT'}"
            )

            if not hdr_same:
                # Field-by-field diff
                hdr_diffs = [
                    comp_hdr_fields[i] - ref_hdr_fields[i]
                    for i in range(min(5, len(ref_hdr_fields), len(comp_hdr_fields)))
                ]
                print(f"         Header diffs: {hdr_diffs}")

            n_evts = min(len(ref_evts), len(comp_evts), 4)
            for ei in range(n_evts):
                ref_derot = derotate_event(ref_evts[ei], ei)
                comp_derot = derotate_event(comp_evts[ei], ei)

                ref_fields = [extract_9bit(ref_derot, fi) for fi in range(6)]
                comp_fields = [extract_9bit(comp_derot, fi) for fi in range(6)]

                diffs = [comp_fields[fi] - ref_fields[fi] for fi in range(6)]
                changed = [fi for fi in range(6) if diffs[fi] != 0]

                if changed:
                    print(f"      E{ei}: changed={changed}")
                    for fi in changed:
                        rv, cv = ref_fields[fi], comp_fields[fi]
                        print(
                            f"        F{fi}: S{ref_section}={rv:3d}[{format(rv, '09b')}] "
                            f"S{comp_section}={cv:3d}[{format(cv, '09b')}] "
                            f"diff={diffs[fi]:+d}"
                        )
                else:
                    print(f"      E{ei}: identical")


# ============================================================================
# PART 8: Full Event Table — All Fields, All Sections
# ============================================================================


def full_event_table(syx_path):
    """Compact table of all de-rotated fields for C2 across sections."""
    print()
    print("=" * 90)
    print("PART 8: FULL C2 EVENT TABLE (all sections, bar 0/1)")
    print("=" * 90)

    print(
        f"  {'Sec':>3s} {'Bar':>3s} {'Evt':>3s}  "
        f"{'F0':>5s} {'F1':>5s} {'F2':>5s} {'F3':>5s} {'F4':>5s} {'F5':>5s}  "
        f"{'F3bin':>11s} {'F4bin':>11s} {'F5bin':>11s}"
    )

    for section in range(6):
        data = get_track_data(syx_path, section, 4)  # C2
        if not data:
            continue
        bars = get_all_bars(data)

        for bi, (header, events) in enumerate(bars[:2]):
            for ei, evt in enumerate(events[:4]):
                derot = derotate_event(evt, ei)
                fields = [extract_9bit(derot, fi) for fi in range(6)]

                f3_bin = format(fields[3], "09b")
                f4_bin = format(fields[4], "09b")
                f5_bin = format(fields[5], "09b")

                print(
                    f"  S{section:1d}  B{bi:1d}  E{ei:1d}   "
                    f"{fields[0]:5d} {fields[1]:5d} {fields[2]:5d} "
                    f"{fields[3]:5d} {fields[4]:5d} {fields[5]:5d}  "
                    f"{f3_bin} {f4_bin} {f5_bin}"
                )
            print()


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    syx_path = sys.argv[1] if len(sys.argv) > 1 else SGT_PATH

    if not os.path.exists(syx_path):
        print(f"File not found: {syx_path}")
        sys.exit(1)

    print(f"Analyzing: {syx_path}\n")

    cross_section_chords(syx_path)
    verify_f3_onehot(syx_path)
    test_chord_tone_mask(syx_path)
    raw_xor_analysis(syx_path)
    analyze_f5_bits(syx_path)
    compare_section_headers(syx_path)
    decode_cross_chord(syx_path)
    full_event_table(syx_path)

    print("\n" + "=" * 90)
    print("NOTE FIELD CRACKING COMPLETE")
    print("=" * 90)
