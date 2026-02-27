#!/usr/bin/env python3
"""
Bit-Field Cracking Analysis — Use C2/C4 minimal differences and
cross-track comparisons to identify the bit-field layout of QY70 events.

Key insight: C2 and C4 events differ by only 2-4 bits per 7-byte event.
If these tracks play similar chord voicings but differ by one note, we can
identify exactly which bits encode note values.

Strategy:
1. Map ALL bit-level differences between C2 and C4 events
2. Look at which bit positions encode the varying "note" field
3. Cross-reference with C3 (which has unique data in section 0 vs defaults)
4. Check if the "empty marker" pattern gives clues about field sizes
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qymanager.formats.qy70.sysex_parser import SysExParser
from qymanager.utils.yamaha_7bit import decode_7bit
from collections import defaultdict, Counter


TRACK_NAMES = {0: "D1", 1: "D2", 2: "BASS", 3: "C1", 4: "C2", 5: "PC", 6: "C3", 7: "C4/PHR"}

NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def midi_note(n):
    if 0 <= n <= 127:
        return f"{NOTE_NAMES[n % 12]}{n // 12 - 1}"
    return f"?{n}"


def get_track_data(syx_path, section, track):
    """Get decoded data for a specific section/track."""
    parser = SysExParser()
    messages = parser.parse_file(syx_path)
    al = section * 8 + track
    msgs = [m for m in messages if m.is_style_data and m.address_low == al]
    data = b""
    for m in msgs:
        data += m.decoded_data
    return data


def extract_events(data, skip_header=True):
    """Extract 7-byte event groups from track data.
    Returns list of (offset, group_bytes, is_dc, is_header) tuples.
    """
    events = []
    # Skip track header (24 bytes)
    start = 24 if skip_header else 0

    # The preamble is 4 bytes: XX XX 60 00
    if skip_header and len(data) > 28:
        preamble = data[24:28]
        events.append((24, preamble, False, True))
        start = 28

    # Find DC positions
    dc_pos = set(i for i, b in enumerate(data) if b == 0xDC and i >= start)

    # Extract segments between DCs
    segments = []
    seg_start = start
    for dp in sorted(dc_pos):
        if dp > seg_start:
            segments.append((seg_start, data[seg_start:dp]))
        segments.append((dp, bytes([0xDC])))
        seg_start = dp + 1
    if seg_start < len(data):
        segments.append((seg_start, data[seg_start:]))

    return segments


def bit_analysis_c2_c4(syx_path):
    """Detailed bit-level comparison of C2 vs C4 events."""
    print("=" * 80)
    print("PART 1: C2 vs C4 BIT-LEVEL DIFFERENCE MAPPING")
    print("=" * 80)

    c2 = get_track_data(syx_path, 0, 4)  # C2
    c4 = get_track_data(syx_path, 0, 7)  # C4/PHR

    print(f"C2: {len(c2)} bytes, C4: {len(c4)} bytes")

    # Both have DC at specific positions. Let's extract bars.
    # C2: DC at 42, 84, 126 → header+bar0=42, bar1=41, bar2=41, tail=1
    # C4: DC at 56, 98, 126 → header+bar0=56, bar1=41, bar2=27, tail=1

    # Compare the bars that are the same size (41 bytes each)
    # C2 bar1: bytes 43-83
    # C4 bar1: bytes 57-97

    c2_bar1 = c2[43:84]
    c4_bar1 = c4[57:98]

    print(f"\nC2 bar1: {len(c2_bar1)} bytes (offset 43-83)")
    print(f"C4 bar1: {len(c4_bar1)} bytes (offset 57-97)")

    # Both bars have: 13-byte header + 4 × 7-byte events
    c2_hdr = c2_bar1[:13]
    c4_hdr = c4_bar1[:13]

    print(f"\nBar headers:")
    print(f"  C2: {' '.join(f'{b:02X}' for b in c2_hdr)}")
    print(f"  C4: {' '.join(f'{b:02X}' for b in c4_hdr)}")
    xor_hdr = bytes(a ^ b for a, b in zip(c2_hdr, c4_hdr))
    diff_pos = [i for i, b in enumerate(xor_hdr) if b != 0]
    print(f"  XOR: {' '.join(f'{b:02X}' for b in xor_hdr)} (diffs at positions {diff_pos})")

    for di in diff_pos:
        print(f"    Byte {di}: C2={c2_hdr[di]:08b} C4={c4_hdr[di]:08b} XOR={xor_hdr[di]:08b}")

    # Event-by-event comparison
    print(f"\nEvent-by-event bit difference:")
    for evt_idx in range(4):
        c2_evt = c2_bar1[13 + evt_idx * 7 : 13 + (evt_idx + 1) * 7]
        c4_evt = c4_bar1[13 + evt_idx * 7 : 13 + (evt_idx + 1) * 7]
        xor_evt = bytes(a ^ b for a, b in zip(c2_evt, c4_evt))
        total_diff_bits = sum(bin(b).count("1") for b in xor_evt)

        print(f"\n  Event {evt_idx}:")
        print(
            f"    C2: {' '.join(f'{b:02X}' for b in c2_evt)}  = {' '.join(f'{b:08b}' for b in c2_evt)}"
        )
        print(
            f"    C4: {' '.join(f'{b:02X}' for b in c4_evt)}  = {' '.join(f'{b:08b}' for b in c4_evt)}"
        )
        print(
            f"    XOR: {' '.join(f'{b:02X}' for b in xor_evt)}  = {' '.join(f'{b:08b}' for b in xor_evt)}"
        )
        print(f"    Total differing bits: {total_diff_bits}")

        # Map differing bit positions (0-55, MSB first)
        diff_bits = []
        for byte_idx in range(7):
            for bit_idx in range(7, -1, -1):
                if (xor_evt[byte_idx] >> bit_idx) & 1:
                    global_bit = byte_idx * 8 + (7 - bit_idx)
                    diff_bits.append(global_bit)
        print(f"    Differing bit positions (MSB=0): {diff_bits}")

    # Now let's view the events as 56-bit numbers
    print(f"\n  Events as 56-bit integers:")
    for evt_idx in range(4):
        c2_evt = c2_bar1[13 + evt_idx * 7 : 13 + (evt_idx + 1) * 7]
        c4_evt = c4_bar1[13 + evt_idx * 7 : 13 + (evt_idx + 1) * 7]

        c2_val = int.from_bytes(c2_evt, "big")
        c4_val = int.from_bytes(c4_evt, "big")
        diff = c2_val ^ c4_val

        print(f"    E{evt_idx}: C2=0x{c2_val:014X} C4=0x{c4_val:014X} XOR=0x{diff:014X}")

    # Look at bar 0 too
    print(f"\n\n  C2 bar0 (header+events): bytes 28-41 ({14} bytes after header)")
    c2_bar0_events = c2[28:42]  # 14 bytes = 2 × 7-byte groups
    print(f"    {' '.join(f'{b:02X}' for b in c2_bar0_events)}")

    c4_bar0_events = c4[28:56]  # 28 bytes = 4 × 7-byte groups
    print(f"  C4 bar0: bytes 28-55 ({28} bytes after header)")
    print(f"    {' '.join(f'{b:02X}' for b in c4_bar0_events)}")

    # C2 bar0 is shorter (14 bytes = 2 groups), C4 bar0 is 28 bytes (4 groups)
    # So they have different amounts of data before the first bar delimiter


def analyze_empty_marker_structure(syx_path):
    """Analyze the empty marker pattern to understand field boundaries."""
    print()
    print("=" * 80)
    print("PART 2: EMPTY MARKER AS FIELD SIZE INDICATOR")
    print("=" * 80)

    # Empty marker: BF DF EF F7 FB FD FE
    # In binary:    10111111 11011111 11101111 11110111 11111011 11111101 11111110
    # Each byte has one bit clear: bit 6, 5, 4, 3, 2, 1, 0 (descending)
    # As a 56-bit number: 10111111_11011111_11101111_11110111_11111011_11111101_11111110

    empty = bytes([0xBF, 0xDF, 0xEF, 0xF7, 0xFB, 0xFD, 0xFE])
    empty_val = int.from_bytes(empty, "big")
    print(f"Empty marker: {' '.join(f'{b:08b}' for b in empty)}")
    print(f"As 56-bit:    0x{empty_val:014X}")
    print(f"Inverted:     {' '.join(f'{(~b & 0xFF):08b}' for b in empty)}")
    # Inverted = 01000000 00100000 00010000 00001000 00000100 00000010 00000001
    # Each has ONE bit set: bit 6, 5, 4, 3, 2, 1, 0
    # This is literally the bit position marker pattern!

    # Low empty: 3F 5F 6F 77 7B 7D 7E
    low_empty = bytes([0x3F, 0x5F, 0x6F, 0x77, 0x7B, 0x7D, 0x7E])
    print(f"\nLow empty:    {' '.join(f'{b:08b}' for b in low_empty)}")
    print(f"(Same but bit7 clear in all bytes)")

    # So the "empty" pattern has ALL bits set EXCEPT one per byte
    # This is like a "template" showing that each byte position has one special bit
    # Maybe the bit 7 is a "data present" flag, and bits 6-0 form a 7-element
    # field index?

    # Let's look at how actual events relate to this pattern
    c2 = get_track_data(syx_path, 0, 4)
    c2_evt0 = c2[56:63]  # First event in bar 1

    print(f"\nComparison: empty marker vs actual C2 event 0:")
    print(f"  Empty: {' '.join(f'{b:08b}' for b in empty)}")
    print(f"  C2 E0: {' '.join(f'{b:08b}' for b in c2_evt0)}")
    xor_e = bytes(a ^ b for a, b in zip(empty, c2_evt0))
    print(f"  XOR:   {' '.join(f'{b:08b}' for b in xor_e)}")
    diff_count = sum(bin(b).count("1") for b in xor_e)
    print(f"  Bits different: {diff_count}/56")


def analyze_all_chord_events(syx_path):
    """Extract and compare all chord events from C2, C3, C4 across sections."""
    print()
    print("=" * 80)
    print("PART 3: ALL CHORD TRACK EVENTS — FIELD EXTRACTION ATTEMPT")
    print("=" * 80)

    # In the SGT style, C2 and C4 have very similar events with small differences.
    # C3 section 0 has unique data while sections 1-5 have default/empty patterns.
    # Let's collect ALL unique events and try to extract fields.

    all_events = []

    for track_idx, track_name in [(3, "C1"), (4, "C2"), (6, "C3"), (7, "C4")]:
        for section in range(6):
            data = get_track_data(syx_path, section, track_idx)
            if len(data) < 28:
                continue

            # Skip header (24) + preamble (4)
            event_data = data[28:]

            # Find DC positions
            dc_pos = [i for i, b in enumerate(event_data) if b == 0xDC]

            # Split into bars
            segments = []
            prev = 0
            for dp in dc_pos:
                segments.append(event_data[prev:dp])
                prev = dp + 1
            segments.append(event_data[prev:])

            for bar_idx, seg in enumerate(segments):
                if len(seg) < 7:
                    continue
                # Extract 7-byte chunks
                for chunk_start in range(0, len(seg) - 6, 7):
                    chunk = seg[chunk_start : chunk_start + 7]
                    if len(chunk) < 7:
                        continue
                    # Skip all-zero chunks
                    if all(b == 0 for b in chunk):
                        continue
                    # Check if it's empty marker
                    empty = bytes([0xBF, 0xDF, 0xEF, 0xF7, 0xFB, 0xFD, 0xFE])
                    low_empty = bytes([0x3F, 0x5F, 0x6F, 0x77, 0x7B, 0x7D, 0x7E])
                    is_empty = chunk == empty or chunk == low_empty
                    if is_empty:
                        continue

                    bit7 = "".join(str((b >> 7) & 1) for b in chunk)
                    all_events.append(
                        {
                            "track": track_name,
                            "section": section,
                            "bar": bar_idx,
                            "offset": chunk_start,
                            "data": chunk,
                            "bit7": bit7,
                        }
                    )

    print(f"Collected {len(all_events)} non-empty events")

    # Group by bit7 pattern
    by_bit7 = defaultdict(list)
    for evt in all_events:
        by_bit7[evt["bit7"]].append(evt)

    print(f"\nBit-7 pattern distribution:")
    for pattern, events in sorted(by_bit7.items(), key=lambda x: -len(x[1])):
        tracks = set(e["track"] for e in events)
        print(f"  {pattern}: {len(events):3d} events from {tracks}")

    # Focus on the most common pattern: 1111100
    print(f"\n\n--- Analyzing events with bit7 pattern '1111100' ---")
    events_1111100 = by_bit7.get("1111100", [])
    if events_1111100:
        # Extract low-7-bit values for each byte position
        print(f"\n  Low-7-bit value distribution per byte position:")
        for pos in range(7):
            values = [e["data"][pos] & 0x7F for e in events_1111100]
            unique = sorted(set(values))
            print(f"    Byte {pos}: unique={len(unique):2d}  values={unique[:20]}")

        # Look for note-like values (MIDI notes in reasonable range)
        # For chord tracks, we'd expect notes around 48-72 (C3-C5)
        print(f"\n  Looking for MIDI note candidates:")
        for pos in range(7):
            values = [e["data"][pos] & 0x7F for e in events_1111100]
            in_range = [v for v in values if 36 <= v <= 84]
            if len(in_range) > len(values) * 0.3:
                print(
                    f"    Byte {pos}: {len(in_range)}/{len(values)} in MIDI note range "
                    f"({min(in_range)}-{max(in_range)} = {midi_note(min(in_range))}-{midi_note(max(in_range))})"
                )

    # Focus on 0111100 pattern (preamble/header related)
    print(f"\n\n--- Analyzing events with bit7 pattern '0111100' ---")
    events_0111100 = by_bit7.get("0111100", [])
    if events_0111100:
        for pos in range(7):
            values = [e["data"][pos] & 0x7F for e in events_0111100]
            unique = sorted(set(values))
            print(f"    Byte {pos}: unique={len(unique):2d}  values={unique[:20]}")

    # Look at other patterns too
    for pattern in ["0100000", "0111000", "1010000", "0110000"]:
        events_p = by_bit7.get(pattern, [])
        if events_p:
            print(f"\n\n--- Pattern '{pattern}' ({len(events_p)} events) ---")
            tracks = set(e["track"] for e in events_p)
            print(f"    From tracks: {tracks}")
            for pos in range(7):
                values = sorted(set(e["data"][pos] & 0x7F for e in events_p))
                print(f"    Byte {pos}: unique={len(values):2d}  values={values[:15]}")


def analyze_bit_field_positions(syx_path):
    """Try to identify which bit positions encode note values by analyzing
    the C2/C4 XOR patterns and their shifting positions."""
    print()
    print("=" * 80)
    print("PART 4: BIT-FIELD POSITION ANALYSIS")
    print("If note value shifts position in each event, it may be packed")
    print("=" * 80)

    c2 = get_track_data(syx_path, 0, 4)
    c4 = get_track_data(syx_path, 0, 7)

    c2_bar1 = c2[43:84]
    c4_bar1 = c4[57:98]

    # Map all 56 bit positions for each event
    print("\nBit-by-bit XOR map for each event (bit 0 = MSB of byte 0):")
    print("Byte:  |---0---|---1---|---2---|---3---|---4---|---5---|---6---|")
    print("Bit#:  0 1 2 3 4 5 6 7 0 1 2 3 4 5 6 7 0 1 2 3 4 5 6 7 ...")

    for evt_idx in range(4):
        c2_evt = c2_bar1[13 + evt_idx * 7 : 13 + (evt_idx + 1) * 7]
        c4_evt = c4_bar1[13 + evt_idx * 7 : 13 + (evt_idx + 1) * 7]
        xor = bytes(a ^ b for a, b in zip(c2_evt, c4_evt))

        # Build bit string
        bits_c2 = ""
        bits_c4 = ""
        bits_xor = ""
        for byte_idx in range(7):
            for bit_idx in range(7, -1, -1):
                bits_c2 += str((c2_evt[byte_idx] >> bit_idx) & 1)
                bits_c4 += str((c4_evt[byte_idx] >> bit_idx) & 1)
                bits_xor += str((xor[byte_idx] >> bit_idx) & 1)

        # Highlight diff bits
        xor_visual = ""
        for i, ch in enumerate(bits_xor):
            if ch == "1":
                xor_visual += "^"
            else:
                xor_visual += "."

        print(f"\n  E{evt_idx} C2:  {bits_c2}")
        print(f"  E{evt_idx} C4:  {bits_c4}")
        print(f"  E{evt_idx} XOR: {xor_visual}")

        # Find the bit positions that differ
        diff_positions = [i for i, ch in enumerate(bits_xor) if ch == "1"]
        print(f"  Diff at bit positions: {diff_positions}")

    # Now let's see if the diff positions form a pattern
    # E0: 4 bits differ
    # E1: 2 bits differ (byte 3, bits 2 and 7 in byte terms)
    # E2: 2 bits differ (byte 2, bits ?)
    # E3: 2 bits differ (byte 1, bits ?)

    # The diff positions shift LEFT by 8 bits between E1→E2→E3
    # This suggests a field that encodes at different positions per event,
    # OR a packed structure where the note field occupies a fixed bit range
    # within a conceptual "event slot"


def analyze_c3_s0_vs_default(syx_path):
    """C3 section 0 has unique musical data, while sections 1-5 have defaults.
    Compare to understand what 'musical content' looks like vs defaults."""
    print()
    print("=" * 80)
    print("PART 5: C3 SECTION 0 (UNIQUE) vs SECTIONS 1-5 (DEFAULT)")
    print("=" * 80)

    c3_s0 = get_track_data(syx_path, 0, 6)
    c3_s1 = get_track_data(syx_path, 1, 6)

    # Both are 128 bytes (single message)
    # C3 S0 has unique event data, S1 has default/empty

    # Skip track header (24 bytes)
    s0_events = c3_s0[24:]
    s1_events = c3_s1[24:]

    # Preamble
    print(f"S0 preamble: {' '.join(f'{b:02X}' for b in s0_events[:4])}")
    print(f"S1 preamble: {' '.join(f'{b:02X}' for b in s1_events[:4])}")

    # XOR the entire event regions
    min_len = min(len(s0_events), len(s1_events))
    total_same = sum(1 for a, b in zip(s0_events[:min_len], s1_events[:min_len]) if a == b)
    print(f"\nSame bytes: {total_same}/{min_len} ({total_same / min_len * 100:.1f}%)")

    # Show both side by side as 7-byte groups
    print(f"\nSide-by-side comparison:")
    for g in range(0, min_len, 7):
        s0_g = s0_events[g : g + 7]
        s1_g = s1_events[g : g + 7]
        if len(s0_g) < 7 or len(s1_g) < 7:
            break

        s0_hex = " ".join(f"{b:02X}" for b in s0_g)
        s1_hex = " ".join(f"{b:02X}" for b in s1_g)
        same = s0_g == s1_g
        marker = "  SAME" if same else " *DIFF"
        s0_b7 = "".join(str((b >> 7) & 1) for b in s0_g)
        s1_b7 = "".join(str((b >> 7) & 1) for b in s1_g)
        print(f"  G{g // 7:2d}: S0={s0_hex} (b7={s0_b7}) | S1={s1_hex} (b7={s1_b7}){marker}")


def analyze_d1_repeating_pairs(syx_path):
    """Analyze the frequently repeating byte pairs in D1 drum data."""
    print()
    print("=" * 80)
    print("PART 6: D1 DRUM REPEATING PATTERNS")
    print("=" * 80)

    data = get_track_data(syx_path, 0, 0)
    event_data = data[28:]  # Skip header + preamble

    # `28 0F` appears 11 times. Let's find all positions and look at context
    pattern_28_0f = []
    for i in range(len(event_data) - 1):
        if event_data[i] == 0x28 and event_data[i + 1] == 0x0F:
            pattern_28_0f.append(i)

    print(f"'28 0F' positions: {pattern_28_0f}")
    print(
        f"Intervals between: {[pattern_28_0f[i + 1] - pattern_28_0f[i] for i in range(len(pattern_28_0f) - 1)]}"
    )

    # Show context around each occurrence
    for pos in pattern_28_0f[:8]:
        start = max(0, pos - 4)
        end = min(len(event_data), pos + 10)
        ctx = event_data[start:end]
        hex_ctx = []
        for j, b in enumerate(ctx):
            offset = start + j
            if offset == pos or offset == pos + 1:
                hex_ctx.append(f"[{b:02X}]")
            else:
                hex_ctx.append(f" {b:02X} ")
        print(f"  @{pos:3d}: {''.join(hex_ctx)}")

    # `40 78` appears 8 times
    print()
    pattern_40_78 = []
    for i in range(len(event_data) - 1):
        if event_data[i] == 0x40 and event_data[i + 1] == 0x78:
            pattern_40_78.append(i)

    print(f"'40 78' positions: {pattern_40_78}")
    print(
        f"Intervals: {[pattern_40_78[i + 1] - pattern_40_78[i] for i in range(len(pattern_40_78) - 1)]}"
    )

    for pos in pattern_40_78[:8]:
        start = max(0, pos - 4)
        end = min(len(event_data), pos + 10)
        ctx = event_data[start:end]
        hex_ctx = []
        for j, b in enumerate(ctx):
            offset = start + j
            if offset == pos or offset == pos + 1:
                hex_ctx.append(f"[{b:02X}]")
            else:
                hex_ctx.append(f" {b:02X} ")
        print(f"  @{pos:3d}: {''.join(hex_ctx)}")

    # Look for the `28 0F 8D 03` 4-byte sequence (appeared 6 times in freq analysis)
    print()
    pattern_4 = []
    for i in range(len(event_data) - 3):
        if (
            event_data[i] == 0x28
            and event_data[i + 1] == 0x0F
            and event_data[i + 2] in (0x8C, 0x8D, 0x8F)
        ):
            pattern_4.append(i)

    print(f"'28 0F 8x' positions: {pattern_4}")
    print(f"Byte after '28 0F': {[f'0x{event_data[p + 2]:02X}' for p in pattern_4]}")
    # The third byte varies: 0x8C, 0x8D, 0x8F
    # In binary: 10001100, 10001101, 10001111
    # Low 7 bits: 12, 13, 15 — these are close together, could be a timing value

    # What comes before '28 0F'?
    print(
        f"Byte before '28 0F': {[f'0x{event_data[p - 1]:02X}' if p > 0 else 'START' for p in pattern_4]}"
    )


def analyze_bar_header_13bytes(syx_path):
    """The 13-byte bar header appears after each DC. What does it encode?"""
    print()
    print("=" * 80)
    print("PART 7: 13-BYTE BAR HEADERS (after DC)")
    print("=" * 80)

    # Collect all bar headers from chord tracks
    headers = []
    for track_idx, track_name in [(3, "C1"), (4, "C2"), (6, "C3"), (7, "C4")]:
        for section in range(6):
            data = get_track_data(syx_path, section, track_idx)
            if len(data) < 28:
                continue

            dc_pos = [i for i, b in enumerate(data) if b == 0xDC and i >= 28]
            for dp in dc_pos:
                # Header starts at dp+1, should be at least 13 bytes before next DC or end
                hdr_start = dp + 1
                if hdr_start + 13 <= len(data):
                    hdr = data[hdr_start : hdr_start + 13]
                    headers.append(
                        {
                            "track": track_name,
                            "section": section,
                            "dc_offset": dp,
                            "data": hdr,
                        }
                    )

    print(f"Collected {len(headers)} bar headers")

    # Group by track
    by_track = defaultdict(list)
    for h in headers:
        by_track[h["track"]].append(h)

    for track_name in ["C1", "C2", "C3", "C4"]:
        track_hdrs = by_track.get(track_name, [])
        if not track_hdrs:
            continue
        print(f"\n  {track_name}: {len(track_hdrs)} headers")
        unique_hdrs = set(h["data"].hex() for h in track_hdrs)
        print(f"  Unique headers: {len(unique_hdrs)}")
        for h in track_hdrs:
            hex_str = " ".join(f"{b:02X}" for b in h["data"])
            print(f"    S{h['section']} @{h['dc_offset']}: {hex_str}")


if __name__ == "__main__":
    syx_path = sys.argv[1] if len(sys.argv) > 1 else "tests/fixtures/QY70_SGT.syx"
    bit_analysis_c2_c4(syx_path)
    analyze_empty_marker_structure(syx_path)
    analyze_all_chord_events(syx_path)
    analyze_bit_field_positions(syx_path)
    analyze_c3_s0_vs_default(syx_path)
    analyze_d1_repeating_pairs(syx_path)
    analyze_bar_header_13bytes(syx_path)
