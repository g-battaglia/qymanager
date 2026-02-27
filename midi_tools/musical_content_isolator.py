#!/usr/bin/env python3
"""
Musical Content Isolator — Identify exactly which bits encode musical content
by comparing tracks with different musical data but identical structure.

KEY STRATEGY:
1. C3 S0 has unique musical content, C3 S1-5 have default/template data
2. By XOR-ing S0 vs S1, we isolate EXACTLY which bits change with music
3. Map those bits to field positions within the 7-byte event structure
4. Cross-validate with C2/C4 XOR (different voicing, same rhythm)
5. Check if the identified fields produce valid MIDI note values

ALSO: Investigate why BASS track has drum voice flags (40 80 / 87 F8 / 80 8E 83)
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


def get_track_data(syx_path, section, track):
    parser = SysExParser()
    messages = parser.parse_file(syx_path)
    al = section * 8 + track
    data = b""
    for m in messages:
        if m.is_style_data and m.address_low == al:
            data += m.decoded_data
    return data


def extract_field(val, msb, width, total_width):
    shift = total_width - msb - width
    if shift < 0:
        return -1
    return (val >> shift) & ((1 << width) - 1)


def rot_left(val, shift, width=56):
    shift = shift % width
    return ((val << shift) | (val >> (width - shift))) & ((1 << width) - 1)


def rot_right(val, shift, width=56):
    return rot_left(val, width - shift, width)


def popcount(val):
    return bin(val).count("1")


# ============================================================================
# PART 1: C3 S0 vs S1 — Musical content isolation
# ============================================================================


def isolate_musical_content(syx_path):
    """Compare C3 S0 (unique music) with C3 S1 (default) byte-by-byte."""
    print("=" * 80)
    print("PART 1: MUSICAL CONTENT ISOLATION (C3 S0 vs S1)")
    print("=" * 80)

    c3_s0 = get_track_data(syx_path, 0, 6)
    c3_s1 = get_track_data(syx_path, 1, 6)

    print(f"C3 S0: {len(c3_s0)} bytes")
    print(f"C3 S1: {len(c3_s1)} bytes")

    # Track header comparison (first 24 bytes)
    print(f"\nTrack header:")
    print(f"  S0: {' '.join(f'{b:02X}' for b in c3_s0[:24])}")
    print(f"  S1: {' '.join(f'{b:02X}' for b in c3_s1[:24])}")
    hdr_same = c3_s0[:24] == c3_s1[:24]
    print(f"  Headers identical: {hdr_same}")

    # Preamble comparison
    print(f"\nPreamble:")
    print(f"  S0: {' '.join(f'{b:02X}' for b in c3_s0[24:28])}")
    print(f"  S1: {' '.join(f'{b:02X}' for b in c3_s1[24:28])}")

    # Event data comparison
    s0_events = c3_s0[28:]
    s1_events = c3_s1[28:]

    # Find DC positions in both
    s0_dc = [i for i, b in enumerate(s0_events) if b == 0xDC]
    s1_dc = [i for i, b in enumerate(s1_events) if b == 0xDC]
    print(f"\nDC positions: S0={s0_dc}, S1={s1_dc}")

    # Overall similarity
    min_len = min(len(s0_events), len(s1_events))
    same_count = sum(1 for a, b in zip(s0_events[:min_len], s1_events[:min_len]) if a == b)
    print(f"Same bytes: {same_count}/{min_len} ({same_count / min_len * 100:.1f}%)")

    # Byte-by-byte XOR map
    print(f"\nByte-by-byte XOR (. = same, X = different):")
    xor_data = bytes(a ^ b for a, b in zip(s0_events[:min_len], s1_events[:min_len]))

    for row in range(0, min_len, 28):
        end = min(row + 28, min_len)
        # Show as 7-byte groups
        xor_line = ""
        s0_hex = ""
        s1_hex = ""
        for i in range(row, end):
            if i > row and (i - row) % 7 == 0:
                xor_line += "|"
                s0_hex += "|"
                s1_hex += "|"
            xor_line += "X" if xor_data[i] != 0 else "."
            s0_hex += f"{s0_events[i]:02X}"
            s1_hex += f"{s1_events[i]:02X}"

        # Mark DCs
        dc_markers = ""
        for i in range(row, end):
            if i in s0_dc or i in s1_dc:
                dc_markers += "D"
            else:
                dc_markers += " "

        print(f"  @{row:3d}: {xor_line}  S0={s0_hex}")
        print(f"         {''.join(dc_markers)}  S1={s1_hex}")

    # Now split by DC and compare bar-by-bar
    print(f"\n\nBar-by-bar comparison:")

    def split_bars(data, dc_positions):
        bars = []
        prev = 0
        for dp in dc_positions:
            bars.append(data[prev:dp])
            prev = dp + 1
        bars.append(data[prev:])
        return bars

    s0_bars = split_bars(s0_events, s0_dc)
    s1_bars = split_bars(s1_events, s1_dc)

    print(f"  S0 bars: {len(s0_bars)} with lengths {[len(b) for b in s0_bars]}")
    print(f"  S1 bars: {len(s1_bars)} with lengths {[len(b) for b in s1_bars]}")

    # For bars with matching length, do detailed comparison
    for bi in range(min(len(s0_bars), len(s1_bars))):
        b0 = s0_bars[bi]
        b1 = s1_bars[bi]
        if len(b0) != len(b1):
            print(f"\n  Bar {bi}: DIFFERENT LENGTHS (S0={len(b0)}, S1={len(b1)})")
            continue

        if b0 == b1:
            print(f"\n  Bar {bi}: IDENTICAL ({len(b0)} bytes)")
            continue

        xor_bar = bytes(a ^ b for a, b in zip(b0, b1))
        diff_count = sum(1 for x in xor_bar if x != 0)
        diff_bits = sum(popcount(x) for x in xor_bar)

        print(f"\n  Bar {bi}: {diff_count}/{len(b0)} bytes differ ({diff_bits} bits)")

        # If bar has 13-byte header + events structure
        if len(b0) >= 20:
            hdr0 = b0[:13]
            hdr1 = b1[:13]
            hdr_xor = bytes(a ^ b for a, b in zip(hdr0, hdr1))
            hdr_diff = sum(1 for x in hdr_xor if x != 0)

            print(f"    Header: {hdr_diff}/13 bytes differ")
            if hdr_diff > 0:
                print(f"      S0: {' '.join(f'{b:02X}' for b in hdr0)}")
                print(f"      S1: {' '.join(f'{b:02X}' for b in hdr1)}")
                for i in range(13):
                    if hdr_xor[i] != 0:
                        print(
                            f"      Byte {i}: S0=0x{hdr0[i]:02X}({hdr0[i]:3d}) "
                            f"S1=0x{hdr1[i]:02X}({hdr1[i]:3d}) "
                            f"XOR=0x{hdr_xor[i]:02X} diff={hdr0[i] - hdr1[i]:+d}"
                        )

            # Compare events
            n_events = (len(b0) - 13) // 7
            for ei in range(n_events):
                e0 = b0[13 + ei * 7 : 13 + (ei + 1) * 7]
                e1 = b1[13 + ei * 7 : 13 + (ei + 1) * 7]
                if e0 == e1:
                    print(f"    Event {ei}: IDENTICAL")
                else:
                    xor_e = bytes(a ^ b for a, b in zip(e0, e1))
                    bits_diff = sum(popcount(x) for x in xor_e)
                    print(f"    Event {ei}: {bits_diff} bits differ")
                    print(f"      S0: {' '.join(f'{b:02X}' for b in e0)}")
                    print(f"      S1: {' '.join(f'{b:02X}' for b in e1)}")

                    # Show which bit positions differ
                    diff_positions = []
                    for byte_idx in range(7):
                        for bit_idx in range(7, -1, -1):
                            if (xor_e[byte_idx] >> bit_idx) & 1:
                                global_bit = byte_idx * 8 + (7 - bit_idx)
                                diff_positions.append(global_bit)
                    print(f"      Diff bit positions: {diff_positions}")

                    # De-rotate and show diff positions
                    v0 = int.from_bytes(e0, "big")
                    v1 = int.from_bytes(e1, "big")
                    v0_derot = rot_right(v0, ei * 9)
                    v1_derot = rot_right(v1, ei * 9)
                    xor_derot = v0_derot ^ v1_derot
                    derot_positions = [b for b in range(56) if (xor_derot >> (55 - b)) & 1]
                    print(f"      De-rotated diff positions (R=9): {derot_positions}")


# ============================================================================
# PART 2: Track header analysis across ALL tracks and sections
# ============================================================================


def analyze_all_track_headers(syx_path):
    """Check if track headers vary across sections."""
    print()
    print("=" * 80)
    print("PART 2: TRACK HEADER COMPARISON ACROSS SECTIONS")
    print("=" * 80)

    track_names = {0: "D1", 1: "D2", 2: "BASS", 3: "C1", 4: "C2", 5: "PC", 6: "C3", 7: "C4"}

    for track_idx in range(8):
        headers = []
        for section in range(6):
            data = get_track_data(syx_path, section, track_idx)
            if len(data) >= 24:
                headers.append(data[:24])

        if not headers:
            continue

        name = track_names.get(track_idx, f"T{track_idx}")
        all_same = all(h == headers[0] for h in headers)
        print(f"\n  {name} (track {track_idx}): {'ALL IDENTICAL' if all_same else 'VARIES'}")
        print(f"    S0: {' '.join(f'{b:02X}' for b in headers[0])}")

        if not all_same:
            for si, h in enumerate(headers[1:], 1):
                if h != headers[0]:
                    diffs = [i for i in range(24) if h[i] != headers[0][i]]
                    print(f"    S{si}: differs at bytes {diffs}")
                    for d in diffs:
                        print(f"      byte {d}: S0=0x{headers[0][d]:02X} S{si}=0x{h[d]:02X}")


# ============================================================================
# PART 3: Preamble analysis — what do the first 2 bytes encode?
# ============================================================================


def analyze_preambles(syx_path):
    """The preamble bytes XX XX 60 00 vary by track type. Decode them."""
    print()
    print("=" * 80)
    print("PART 3: PREAMBLE BYTE ANALYSIS")
    print("=" * 80)

    track_names = {0: "D1", 1: "D2", 2: "BASS", 3: "C1", 4: "C2", 5: "PC", 6: "C3", 7: "C4"}

    preamble_map = defaultdict(list)

    for track_idx in range(8):
        for section in range(6):
            data = get_track_data(syx_path, section, track_idx)
            if len(data) >= 28:
                preamble = data[24:28]
                event_data = data[28:]
                event_len = len(event_data)
                dc_count = sum(1 for b in event_data if b == 0xDC)
                name = track_names.get(track_idx, f"T{track_idx}")

                preamble_map[(preamble[0], preamble[1])].append(
                    {
                        "track": name,
                        "section": section,
                        "event_len": event_len,
                        "dc_count": dc_count,
                        "preamble": preamble,
                    }
                )

    for (p0, p1), entries in sorted(preamble_map.items()):
        tracks = set(e["track"] for e in entries)
        event_lens = set(e["event_len"] for e in entries)
        print(f"\n  Preamble 0x{p0:02X} 0x{p1:02X}:")
        print(f"    Tracks: {tracks}")
        print(f"    Event data lengths: {event_lens}")
        print(f"    DC counts: {set(e['dc_count'] for e in entries)}")

        # Are preamble bytes encoding length?
        for e in entries[:1]:
            p = e["preamble"]
            el = e["event_len"]
            # Try various decodings
            val16 = (p[0] << 8) | p[1]
            val_lo7 = ((p[0] & 0x7F) << 7) | (p[1] & 0x7F)
            print(
                f"    As 16-bit: {val16} (event_len={el}, ratio={el / val16:.2f})"
                if val16 > 0
                else ""
            )
            print(f"    As 14-bit (lo7): {val_lo7} (event_len={el})")
            # Binary representation
            print(f"    Binary: {p[0]:08b} {p[1]:08b}")


# ============================================================================
# PART 4: C2 event field analysis with bar header as context
# ============================================================================


def c2_field_analysis(syx_path):
    """Extract fields from C2 events using the bar header as context."""
    print()
    print("=" * 80)
    print("PART 4: C2 BAR HEADER + EVENTS FIELD EXTRACTION")
    print("Focus on the 13-byte header's 9-bit fields as potential chord data")
    print("=" * 80)

    c2 = get_track_data(syx_path, 0, 4)
    c4 = get_track_data(syx_path, 0, 7)

    # C2 bar 1
    c2_bar = c2[43:84]  # 41 bytes after first DC+1
    c4_bar = c4[57:98]  # 41 bytes after first DC+1

    c2_hdr = c2_bar[:13]
    c4_hdr = c4_bar[:13]

    # Decode header as 9-bit fields (13 bytes = 104 bits = 11 × 9 + 5)
    c2_hdr_val = int.from_bytes(c2_hdr, "big")
    c4_hdr_val = int.from_bytes(c4_hdr, "big")

    print("Header as 9-bit fields:")
    print(
        f"  {'Field':>5} {'Start':>5} {'C2':>5} {'C4':>5} {'Diff':>5} "
        f"{'C2 Note':>8} {'C4 Note':>8} {'C2 lo7':>6} {'C4 lo7':>6}"
    )

    for i in range(11):
        start = i * 9
        c2_val = extract_field(c2_hdr_val, start, 9, 104)
        c4_val = extract_field(c4_hdr_val, start, 9, 104)
        diff = c4_val - c2_val
        c2_note = nn(c2_val) if 0 <= c2_val <= 127 else str(c2_val)
        c4_note = nn(c4_val) if 0 <= c4_val <= 127 else str(c4_val)
        c2_lo7 = c2_val & 0x7F
        c4_lo7 = c4_val & 0x7F
        marker = " <<<" if diff != 0 else ""
        print(
            f"  F{i:2d}   @{start:3d}   {c2_val:3d}   {c4_val:3d}   {diff:+4d}   "
            f"{c2_note:>8} {c4_note:>8}   {c2_lo7:>4}   {c4_lo7:>4}{marker}"
        )

    # Also try 7-bit fields (13 bytes = 104 bits = 14 × 7 + 6)
    print("\nHeader as 7-bit fields:")
    for i in range(14):
        start = i * 7
        c2_val = extract_field(c2_hdr_val, start, 7, 104)
        c4_val = extract_field(c4_hdr_val, start, 7, 104)
        diff = c4_val - c2_val
        c2_note = nn(c2_val) if 0 <= c2_val <= 127 else str(c2_val)
        c4_note = nn(c4_val) if 0 <= c4_val <= 127 else str(c4_val)
        marker = " <<<" if diff != 0 else ""
        if diff != 0 or 24 <= c2_val <= 96:
            print(
                f"  F{i:2d}   @{start:3d}   {c2_val:3d}   {c4_val:3d}   {diff:+4d}   "
                f"{c2_note:>8} {c4_note:>8}{marker}"
            )

    # Now extract events and decode
    print("\n\nC2 Events (bar 1, de-rotated R=9):")
    for ei in range(4):
        evt = c2_bar[13 + ei * 7 : 13 + (ei + 1) * 7]
        val = int.from_bytes(evt, "big")
        derot = rot_right(val, ei * 9)

        print(f"\n  E{ei}: raw={' '.join(f'{b:02X}' for b in evt)}")
        print(f"       derot=0x{derot:014X}")

        # Extract 7-bit fields from de-rotated value
        print(f"       7-bit fields: ", end="")
        for fi in range(8):
            fval = extract_field(derot, fi * 7, 7, 56)
            note = nn(fval) if 36 <= fval <= 96 else f"{fval:3d}"
            print(f"[{fval:3d}={note}]", end=" ")
        print()

        # Extract 9-bit fields from de-rotated value
        print(f"       9-bit fields: ", end="")
        for fi in range(6):
            fval = extract_field(derot, fi * 9, 9, 56)
            lo7 = fval & 0x7F
            note = nn(lo7) if 36 <= lo7 <= 96 else f"{lo7:3d}"
            print(f"[{fval:3d}={note}]", end=" ")
        print()


# ============================================================================
# PART 5: C3 S0 bar headers — are they chord progressions?
# ============================================================================


def c3_bar_header_chords(syx_path):
    """C3 S0 has 6 bars with different musical content.
    Extract 9-bit fields from each bar header and see if they form chords."""
    print()
    print("=" * 80)
    print("PART 5: C3 S0 BAR HEADERS AS CHORD PROGRESSIONS")
    print("=" * 80)

    c3_s0 = get_track_data(syx_path, 0, 6)
    event_data = c3_s0[28:]
    dc_pos = [i for i, b in enumerate(event_data) if b == 0xDC]

    # Split into bars
    bars = []
    prev = 0
    for dp in dc_pos:
        bars.append(event_data[prev:dp])
        prev = dp + 1
    bars.append(event_data[prev:])

    print(f"C3 S0: {len(bars)} bars")

    for bi, bar_data in enumerate(bars):
        if len(bar_data) < 13:
            print(f"\n  Bar {bi}: too short ({len(bar_data)} bytes)")
            continue

        hdr = bar_data[:13]
        hdr_val = int.from_bytes(hdr, "big")
        n_events = (len(bar_data) - 13) // 7

        print(f"\n  Bar {bi}: {len(bar_data)} bytes, {n_events} events")
        print(f"    Header: {' '.join(f'{b:02X}' for b in hdr)}")

        # 9-bit fields from header
        print(f"    9-bit fields: ", end="")
        notes_9 = []
        for fi in range(11):
            start = fi * 9
            val = extract_field(hdr_val, start, 9, 104)
            lo7 = val & 0x7F
            notes_9.append(val)
            note = nn(val) if 0 <= val <= 127 else str(val)
            print(f"[{val:3d}={note}]", end=" ")
        print()

        # 7-bit fields
        print(f"    7-bit fields: ", end="")
        for fi in range(14):
            start = fi * 7
            val = extract_field(hdr_val, start, 7, 104)
            note = nn(val) if 24 <= val <= 96 else f"{val:3d}"
            print(f"[{val:3d}={note}]", end=" ")
        print()

        # Show events
        for ei in range(min(n_events, 4)):
            evt = bar_data[13 + ei * 7 : 13 + (ei + 1) * 7]
            if len(evt) < 7:
                break
            val = int.from_bytes(evt, "big")
            derot = rot_right(val, ei * 9)
            print(f"    E{ei}: {' '.join(f'{b:02X}' for b in evt)}  derot=0x{derot:014X}")


# ============================================================================
# PART 6: Compare bar headers between C2, C3, C4 for same section
# ============================================================================


def compare_bar_headers(syx_path):
    """Compare bar headers between tracks that play different parts
    (C2=chord2, C3=chord3, C4=chord4) to see what varies."""
    print()
    print("=" * 80)
    print("PART 6: BAR HEADER COMPARISON BETWEEN CHORD TRACKS")
    print("=" * 80)

    for section in range(2):
        print(f"\n--- Section {section} ---")

        for track_idx, track_name in [(3, "C1"), (4, "C2"), (6, "C3"), (7, "C4")]:
            data = get_track_data(syx_path, section, track_idx)
            if len(data) < 28:
                continue

            event_data = data[28:]
            dc_pos = [i for i, b in enumerate(event_data) if b == 0xDC]

            # Get first bar header after first DC (bar 1, the main one)
            if dc_pos:
                bar_start = dc_pos[0] + 1
                if bar_start + 13 <= len(event_data):
                    hdr = event_data[bar_start : bar_start + 13]
                    hdr_val = int.from_bytes(hdr, "big")

                    print(f"\n  {track_name} bar1 header: {' '.join(f'{b:02X}' for b in hdr)}")

                    # 9-bit fields (first 5 only — these match MIDI notes)
                    fields_9 = []
                    for fi in range(5):
                        val = extract_field(hdr_val, fi * 9, 9, 104)
                        fields_9.append(val)
                    notes = [nn(v) if 0 <= v <= 127 else str(v) for v in fields_9]
                    print(f"    9-bit F0-F4: {fields_9} = {notes}")

                    # Byte-level lo7
                    lo7 = [b & 0x7F for b in hdr]
                    print(f"    lo7: {lo7}")


# ============================================================================
# PART 7: BASS track deep dive — find the note encoding
# ============================================================================


def bass_deep_analysis(syx_path):
    """Analyze BASS track focusing on finding note values."""
    print()
    print("=" * 80)
    print("PART 7: BASS TRACK DEEP DIVE")
    print("=" * 80)

    # Compare BASS across sections
    bass_data = []
    for section in range(6):
        data = get_track_data(syx_path, section, 2)
        bass_data.append(data)
        print(f"  S{section}: {len(data)} bytes")

    # Check if BASS varies across sections
    all_same = all(d == bass_data[0] for d in bass_data)
    print(f"  All sections identical: {all_same}")

    if not all_same:
        for si in range(1, 6):
            if bass_data[si] != bass_data[0]:
                event0 = bass_data[0][28:]
                event_si = bass_data[si][28:]
                min_l = min(len(event0), len(event_si))
                diff_count = sum(1 for a, b in zip(event0[:min_l], event_si[:min_l]) if a != b)
                print(f"  S{si} differs from S0: {diff_count}/{min_l} bytes")

    # For S0, analyze in detail
    bass = bass_data[0]
    event_data = bass[28:]

    print(f"\n  Event data: {len(event_data)} bytes")

    # BASS has no DCs, so the entire event data is one bar
    # Show the data looking for patterns

    # Look at the last bytes — do they have empty markers?
    print(f"\n  Last 21 bytes (3 groups):")
    for g in range(-3, 0):
        start = len(event_data) + g * 7
        if start >= 0:
            chunk = event_data[start : start + 7]
            bit7 = "".join(str((b >> 7) & 1) for b in chunk)
            lo7 = [b & 0x7F for b in chunk]
            print(f"    @{start}: {' '.join(f'{b:02X}' for b in chunk)}  b7={bit7}  lo7={lo7}")

    # Check if the ending matches the empty pattern
    empty = bytes([0x10, 0x88, 0x04, 0x02, 0x01])
    print(f"\n  Checking for repeated end pattern:")
    for g in range(len(event_data) // 7):
        chunk = event_data[g * 7 : (g + 1) * 7]
        if len(chunk) == 7:
            # Check if it starts with the repeated 10 88 pattern
            if chunk[0] == 0x10 and chunk[1] == 0x88:
                print(
                    f"    G{g} @{g * 7}: {' '.join(f'{b:02X}' for b in chunk)}  "
                    f"lo7={[b & 0x7F for b in chunk]}"
                )

    # The BASS data has a distinct pattern where later groups are
    # 10 88 XX XX XX XX XX — this might be the "empty" marker for BASS
    # Let's find where the "real" data ends
    print(f"\n  Finding 'real' data boundary:")
    for g in range(len(event_data) // 7):
        chunk = event_data[g * 7 : (g + 1) * 7]
        if len(chunk) == 7 and chunk[0] == 0x10 and chunk[1] == 0x88:
            print(f"    Template starts at G{g} (@{g * 7})")
            real_data = event_data[: g * 7]
            template = event_data[g * 7 :]
            print(f"    Real data: {len(real_data)} bytes")
            print(f"    Template: {len(template)} bytes")

            # Analyze real data
            print(f"\n  Real BASS data ({len(real_data)} bytes):")
            for gi in range(len(real_data) // 7):
                chunk = real_data[gi * 7 : (gi + 1) * 7]
                if len(chunk) == 7:
                    bit7 = "".join(str((b >> 7) & 1) for b in chunk)
                    lo7 = [b & 0x7F for b in chunk]
                    bass_notes = [nn(v) for v in lo7 if 24 <= v <= 60]
                    print(
                        f"    G{gi}: {' '.join(f'{b:02X}' for b in chunk)}  "
                        f"b7={bit7}  lo7={lo7}  bass={bass_notes}"
                    )
            break


# ============================================================================
# PART 8: Try the entire bar as a 7-bit packed bitstream (lo7 only)
# ============================================================================


def lo7_bitstream_analysis(syx_path):
    """Since QY70 uses 7-bit encoding everywhere, maybe the event data
    should be read as 7-bit values (ignoring bit 7 flags)."""
    print()
    print("=" * 80)
    print("PART 8: LO7 BITSTREAM ANALYSIS")
    print("Treat event bytes as 7-bit values (ignore bit 7)")
    print("=" * 80)

    c2 = get_track_data(syx_path, 0, 4)
    c4 = get_track_data(syx_path, 0, 7)

    # C2 bar 1 events
    c2_bar = c2[43:84]
    c4_bar = c4[57:98]

    # Extract lo7 values
    c2_lo7 = [b & 0x7F for b in c2_bar]
    c4_lo7 = [b & 0x7F for b in c4_bar]

    # Treat as 7-bit packed stream
    c2_stream = 0
    c4_stream = 0
    for v in c2_lo7:
        c2_stream = (c2_stream << 7) | v
    for v in c4_lo7:
        c4_stream = (c4_stream << 7) | v

    total_bits = 41 * 7  # 287 bits

    print(f"Lo7 stream: {total_bits} bits")

    # Extract 7-bit fields from the lo7 stream
    print(f"\n7-bit fields from lo7 stream:")
    print(f"  {'F':>3} {'Start':>5} {'C2':>5} {'C4':>5} {'Diff':>5} {'C2 Note':>8} {'C4 Note':>8}")

    for fi in range(total_bits // 7):
        start = fi * 7
        c2_val = extract_field(c2_stream, start, 7, total_bits)
        c4_val = extract_field(c4_stream, start, 7, total_bits)
        diff = c4_val - c2_val
        c2_note = nn(c2_val) if 24 <= c2_val <= 96 else f"{c2_val:3d}"
        c4_note = nn(c4_val) if 24 <= c4_val <= 96 else f"{c4_val:3d}"
        marker = " <<<" if diff != 0 else ""

        # Only show fields in note range or with differences
        if diff != 0 or 24 <= c2_val <= 96:
            print(
                f"  F{fi:2d}  @{start:3d}   {c2_val:3d}   {c4_val:3d}   {diff:+4d}   "
                f"{c2_note:>8} {c4_note:>8}{marker}"
            )

    # XOR to find all differing lo7 field positions
    xor_stream = c2_stream ^ c4_stream
    diff_bits = [b for b in range(total_bits) if (xor_stream >> (total_bits - 1 - b)) & 1]
    print(f"\nDiffering bit positions in lo7 stream: {diff_bits}")
    print(f"Total: {len(diff_bits)} bits")

    # Group diff positions
    groups = []
    if diff_bits:
        current = [diff_bits[0]]
        for p in diff_bits[1:]:
            if p - current[-1] <= 2:
                current.append(p)
            else:
                groups.append(current)
                current = [p]
        groups.append(current)

    print(f"Diff groups: {groups}")
    for g in groups:
        width = g[-1] - g[0] + 1
        c2_val = extract_field(c2_stream, g[0], width, total_bits)
        c4_val = extract_field(c4_stream, g[0], width, total_bits)
        print(
            f"  Bits {g[0]}-{g[-1]} (width={width}): C2={c2_val} C4={c4_val} "
            f"diff={c4_val - c2_val:+d}"
        )


# ============================================================================
# PART 9: Check if preamble encodes data length
# ============================================================================


def preamble_length_correlation(syx_path):
    """Check if preamble bytes correlate with event data length or structure."""
    print()
    print("=" * 80)
    print("PART 9: PREAMBLE-LENGTH CORRELATION")
    print("=" * 80)

    track_names = {0: "D1", 1: "D2", 2: "BASS", 3: "C1", 4: "C2", 5: "PC", 6: "C3", 7: "C4"}

    entries = []
    for track_idx in range(8):
        data = get_track_data(syx_path, 0, track_idx)
        if len(data) >= 28:
            p0 = data[24]
            p1 = data[25]
            event_len = len(data) - 28
            name = track_names.get(track_idx, f"T{track_idx}")
            entries.append((name, p0, p1, event_len))

    print(
        f"  {'Track':>6} {'P0':>4} {'P1':>4} {'P0_b':>10} {'P1_b':>10} "
        f"{'EvLen':>6} {'P0*8':>6} {'P1_lo7':>6}"
    )
    for name, p0, p1, elen in entries:
        print(
            f"  {name:>6} 0x{p0:02X} 0x{p1:02X} {p0:08b} {p1:08b} "
            f"{elen:6d} {p0 * 8:6d} {p1 & 0x7F:6d}"
        )


if __name__ == "__main__":
    syx_path = sys.argv[1] if len(sys.argv) > 1 else "tests/fixtures/QY70_SGT.syx"

    isolate_musical_content(syx_path)
    analyze_all_track_headers(syx_path)
    analyze_preambles(syx_path)
    c2_field_analysis(syx_path)
    c3_bar_header_chords(syx_path)
    compare_bar_headers(syx_path)
    bass_deep_analysis(syx_path)
    lo7_bitstream_analysis(syx_path)
    preamble_length_correlation(syx_path)
