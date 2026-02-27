#!/usr/bin/env python3
"""
Per-Message Encoding Analysis — Verify that DC alignment breaks are caused
by multi-message concatenation, then decode events within proper boundaries.

Key hypothesis: Each SysEx message is independently 7-bit encoded.
When we concatenate decoded data from multiple messages, the 7-byte groups
from different messages DON'T align. So DC alignment should be 100%
within each individual message.

Then: Use the confirmed 7-byte group structure to decode actual events.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qymanager.formats.qy70.sysex_parser import SysExParser
from qymanager.utils.yamaha_7bit import decode_7bit


TRACK_NAMES = {0: "D1", 1: "D2", 2: "BASS", 3: "C1", 4: "C2", 5: "PC", 6: "C3", 7: "C4/PHR"}

SECTION_NAMES = {0: "MAIN-A", 1: "MAIN-B", 2: "FILL-AB", 3: "INTRO", 4: "FILL-BA", 5: "ENDING"}


def analyze_per_message_dc(syx_path: str):
    """Verify DC alignment is 100% within each individual SysEx message."""
    parser = SysExParser()
    messages = parser.parse_file(syx_path)
    style_msgs = [m for m in messages if m.is_style_data]

    print("=" * 80)
    print("PART 1: DC ALIGNMENT PER INDIVIDUAL SYSEX MESSAGE")
    print("=" * 80)

    total_dc = 0
    aligned_dc = 0
    misaligned_dc = 0

    # Group messages by AL value
    from collections import defaultdict

    by_al = defaultdict(list)
    for m in style_msgs:
        by_al[m.address_low].append(m)

    for al in sorted(by_al.keys()):
        if al == 0x7F:
            continue
        section = al // 8
        track = al % 8
        name = TRACK_NAMES.get(track, f"T{track}")
        msgs = by_al[al]

        print(f"\n  S{section}/{name} (AL=0x{al:02X}): {len(msgs)} message(s)")

        for msg_idx, msg in enumerate(msgs):
            dec = msg.decoded_data
            dc_positions = [i for i, b in enumerate(dec) if b == 0xDC]

            for pos in dc_positions:
                total_dc += 1
                mod = pos % 7
                if mod == 0:
                    aligned_dc += 1
                else:
                    misaligned_dc += 1
                    print(f"    MSG {msg_idx}: DC@{pos} mod7={mod} *** MISALIGNED ***")

            if dc_positions:
                all_ok = all(p % 7 == 0 for p in dc_positions)
                status = "ALL ALIGNED" if all_ok else "HAS MISALIGNMENTS"
                print(f"    MSG {msg_idx}: {len(dec)} bytes, DC at {dc_positions} — {status}")
            else:
                print(f"    MSG {msg_idx}: {len(dec)} bytes, no DC delimiters")

    print(
        f"\n  SUMMARY: {total_dc} DC total, {aligned_dc} aligned ({aligned_dc / total_dc * 100:.1f}%), "
        f"{misaligned_dc} misaligned ({misaligned_dc / total_dc * 100:.1f}%)"
    )

    if misaligned_dc == 0:
        print("  CONCLUSION: DC is 100% aligned to 7-byte decoded groups within each message")
        print("  The 7-byte periodicity is REAL STRUCTURE, not an encoding artifact")
        print("  Previous misalignments were caused by concatenating multiple messages")
    return total_dc, aligned_dc


def decode_7byte_groups(syx_path: str):
    """Decode all tracks into 7-byte groups and analyze the group structure."""
    parser = SysExParser()
    messages = parser.parse_file(syx_path)
    style_msgs = [m for m in messages if m.is_style_data]

    print()
    print("=" * 80)
    print("PART 2: 7-BYTE GROUP DECOMPOSITION — ALL SECTION 0 TRACKS")
    print("=" * 80)

    from collections import defaultdict

    by_al = defaultdict(list)
    for m in style_msgs:
        by_al[m.address_low].append(m)

    # Analyze section 0 tracks (AL 0-7)
    for al in range(8):
        if al not in by_al:
            continue
        msgs = by_al[al]
        track = al % 8
        name = TRACK_NAMES.get(track, f"T{track}")

        print(f"\n{'=' * 80}")
        print(f"  TRACK: {name} (AL=0x{al:02X}), {len(msgs)} messages")
        print(f"{'=' * 80}")

        for msg_idx, msg in enumerate(msgs):
            dec = msg.decoded_data
            print(f"\n  --- Message {msg_idx} ({len(dec)} decoded bytes) ---")

            groups = []
            for i in range(0, len(dec), 7):
                group = dec[i : i + 7]
                groups.append(group)

            # First 3 groups are typically track header (24 bytes = 3 groups + 3 bytes)
            # Actually, header is 24 bytes, so groups 0-2 = header (21 bytes),
            # then group 3 starts at byte 21 (has 3 header bytes + 4 event bytes)
            # Wait, let's check: 24 / 7 = 3.43, so header spans groups 0-3

            for g_idx, group in enumerate(groups):
                offset = g_idx * 7
                hex_str = " ".join(f"{b:02X}" for b in group)
                bit7_str = "".join(str((b >> 7) & 1) for b in group)
                ascii_str = "".join(chr(b) if 32 <= b < 127 else "." for b in group)

                # Mark special bytes
                markers = []
                if 0xDC in group:
                    markers.append("DC")
                if all(b == 0x00 for b in group):
                    markers.append("ZERO")
                # Check for empty marker pattern
                empty_pat = bytes([0xBF, 0xDF, 0xEF, 0xF7, 0xFB, 0xFD, 0xFE])
                if group == empty_pat:
                    markers.append("EMPTY-MARKER")
                # Check for low empty marker
                low_empty = bytes([0x3F, 0x5F, 0x6F, 0x77, 0x7B, 0x7D, 0x7E])
                if group == low_empty:
                    markers.append("LOW-EMPTY")

                marker_str = f" [{', '.join(markers)}]" if markers else ""
                print(
                    f"    G{g_idx:2d} @{offset:3d}: {hex_str}  b7={bit7_str}  |{ascii_str}|{marker_str}"
                )


def analyze_c1_events_deep(syx_path: str):
    """Deep analysis of C1 chord track events across all sections."""
    parser = SysExParser()
    messages = parser.parse_file(syx_path)
    style_msgs = [m for m in messages if m.is_style_data]

    print()
    print("=" * 80)
    print("PART 3: C1 CHORD TRACK — DEEP EVENT ANALYSIS (ALL SECTIONS)")
    print("=" * 80)

    from collections import defaultdict

    by_al = defaultdict(list)
    for m in style_msgs:
        by_al[m.address_low].append(m)

    # C1 is track index 3, so AL = section*8 + 3
    for section in range(6):
        al = section * 8 + 3
        if al not in by_al:
            continue
        msg = by_al[al][0]
        dec = msg.decoded_data

        print(f"\n  Section {section} ({SECTION_NAMES[section]}), AL=0x{al:02X}")
        print(f"  Decoded: {len(dec)} bytes")

        # Split into 7-byte groups
        groups = []
        for i in range(0, len(dec), 7):
            groups.append(dec[i : i + 7])

        # Groups 0-2 = track header (bytes 0-20)
        # Group 3 starts at byte 21 (bytes 21-27) — last 3 header bytes + 4 event bytes
        # Actually let's just label by offset

        # Find DC positions
        dc_pos = [i for i, b in enumerate(dec) if b == 0xDC]
        print(f"  DC delimiters at: {dc_pos}")

        # Split into bars using DC
        bar_starts = [0]
        for dp in dc_pos:
            bar_starts.append(dp + 1)  # Bar starts after DC

        bars = []
        for i, start in enumerate(bar_starts):
            if i + 1 < len(bar_starts):
                end = dc_pos[i]  # Up to (not including) DC
            else:
                end = len(dec)
            bar_data = dec[start:end]
            bars.append((start, bar_data))

        for bar_idx, (bar_start, bar_data) in enumerate(bars):
            print(f"\n    Bar {bar_idx} (offset {bar_start}, {len(bar_data)} bytes):")

            # Show as 7-byte groups relative to message start
            for i in range(0, len(bar_data), 7):
                chunk = bar_data[i : i + 7]
                abs_offset = bar_start + i
                abs_group = abs_offset // 7

                hex_str = " ".join(f"{b:02X}" for b in chunk)
                bit7 = "".join(str((b >> 7) & 1) for b in chunk)
                low7 = [b & 0x7F for b in chunk]
                low7_str = " ".join(f"{v:3d}" for v in low7)

                print(
                    f"      @{abs_offset:3d} G{abs_group:2d}: {hex_str}  b7={bit7}  lo7=[{low7_str}]"
                )


def analyze_c2_events(syx_path: str):
    """C2 has the most DC delimiters (3) — analyze its repeating structure."""
    parser = SysExParser()
    messages = parser.parse_file(syx_path)
    style_msgs = [m for m in messages if m.is_style_data]

    print()
    print("=" * 80)
    print("PART 4: C2 TRACK — REPEATING BAR ANALYSIS (section 0)")
    print("=" * 80)

    from collections import defaultdict

    by_al = defaultdict(list)
    for m in style_msgs:
        by_al[m.address_low].append(m)

    al = 4  # C2, section 0
    if al not in by_al:
        print("  C2 not found")
        return

    msg = by_al[al][0]
    dec = msg.decoded_data
    dc_pos = [i for i, b in enumerate(dec) if b == 0xDC]
    print(f"  C2 section 0: {len(dec)} bytes, DC at {dc_pos}")

    # Split into segments by DC
    segments = []
    prev = 0
    for dp in dc_pos:
        segments.append(dec[prev:dp])
        prev = dp + 1
    segments.append(dec[prev:])

    for seg_idx, seg in enumerate(segments):
        label = (
            "HEADER+BAR0"
            if seg_idx == 0
            else f"BAR {seg_idx}"
            if seg_idx < len(segments) - 1
            else "TAIL"
        )
        print(f"\n    Segment {seg_idx} ({label}): {len(seg)} bytes")
        hex_str = " ".join(f"{b:02X}" for b in seg)
        print(f"      {hex_str}")

        # Show as 7-byte groups (aligned to message, not segment)
        for i in range(0, len(seg), 7):
            chunk = seg[i : i + 7]
            hex_c = " ".join(f"{b:02X}" for b in chunk)
            bit7 = "".join(str((b >> 7) & 1) for b in chunk)
            print(f"      chunk {i // 7}: {hex_c}  b7={bit7}")

    # Compare segments for identity
    print(f"\n    Segment comparisons:")
    for i in range(len(segments)):
        for j in range(i + 1, len(segments)):
            if segments[i] == segments[j]:
                print(f"      Segment {i} == Segment {j} (IDENTICAL)")
            else:
                # Count differences
                min_len = min(len(segments[i]), len(segments[j]))
                diffs = sum(
                    1 for a, b in zip(segments[i][:min_len], segments[j][:min_len]) if a != b
                )
                len_diff = abs(len(segments[i]) - len(segments[j]))
                print(f"      Segment {i} vs {j}: {diffs} byte diffs + {len_diff} length diff")


def analyze_event_fields(syx_path: str):
    """Try to decode individual event fields from the 7-byte groups."""
    parser = SysExParser()
    messages = parser.parse_file(syx_path)
    style_msgs = [m for m in messages if m.is_style_data]

    print()
    print("=" * 80)
    print("PART 5: EVENT FIELD HYPOTHESES")
    print("Test various bit-field decompositions on C1 events")
    print("=" * 80)

    from collections import defaultdict

    by_al = defaultdict(list)
    for m in style_msgs:
        by_al[m.address_low].append(m)

    # Collect all C1 event groups (after header, excluding DC and preamble)
    all_event_groups = []
    for section in range(6):
        al = section * 8 + 3
        if al not in by_al:
            continue
        msg = by_al[al][0]
        dec = msg.decoded_data

        # Skip track header (first 24 bytes = groups 0-2 full + 3 bytes of group 3)
        # Preamble is at bytes 24-27: XX XX 60 00
        # Events start at byte 28

        # Find DC positions
        dc_pos = [i for i, b in enumerate(dec) if b == 0xDC]

        # Extract event groups (7-byte aligned to message start)
        for g_start in range(0, len(dec), 7):
            group = dec[g_start : g_start + 7]
            if len(group) < 7:
                continue
            # Skip header groups (0-2) and preamble area
            if g_start < 28:
                continue
            # Skip if this group contains DC
            if 0xDC in group:
                continue
            # Skip groups that are all zeros
            if all(b == 0 for b in group):
                continue

            all_event_groups.append((section, g_start, group))

    print(f"  Collected {len(all_event_groups)} non-header, non-DC, non-zero groups from C1")
    print()

    # Hypothesis 1: bytes are [note, velocity, gate_hi, gate_lo, ?, ?, ?]
    # Hypothesis 2: bit fields with note in bits, velocity in bits
    # Hypothesis 3: The first byte's low 7 bits are note, but shifted

    # Let's look at byte-level statistics
    print("  Byte-level statistics (all C1 event groups):")
    for byte_pos in range(7):
        values = [g[byte_pos] for _, _, g in all_event_groups]
        unique = sorted(set(values))
        bit7_count = sum(1 for v in values if v & 0x80)
        lo7_values = [v & 0x7F for v in values]

        print(
            f"    Byte {byte_pos}: min=0x{min(values):02X} max=0x{max(values):02X} "
            f"unique={len(unique)} bit7_set={bit7_count}/{len(values)} "
            f"lo7_range=[{min(lo7_values)}-{max(lo7_values)}]"
        )

    # Try various note extraction methods
    print()
    print("  Hypothesis testing — extracted 'note' values:")
    print()

    # C1 is a chord track — we expect chords built from notes in the 48-72 range (C3-C5)
    # CMaj = 48,52,55 (C3,E3,G3) or 60,64,67 (C4,E4,G4)

    note_names = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

    def midi_note_name(n):
        if 0 <= n <= 127:
            return f"{note_names[n % 12]}{n // 12 - 1}"
        return f"?{n}"

    print("  H1: byte[0] & 0x7F as note")
    for section, offset, group in all_event_groups[:16]:
        note = group[0] & 0x7F
        vel = group[1] & 0x7F
        print(
            f"    S{section} @{offset}: note={note:3d} ({midi_note_name(note):4s}) vel={vel:3d}  "
            f"raw={' '.join(f'{b:02X}' for b in group)}"
        )

    print()
    print("  H2: byte[2] & 0x7F as note")
    for section, offset, group in all_event_groups[:16]:
        note = group[2] & 0x7F
        vel = group[3] & 0x7F
        print(
            f"    S{section} @{offset}: note={note:3d} ({midi_note_name(note):4s}) vel={vel:3d}  "
            f"raw={' '.join(f'{b:02X}' for b in group)}"
        )

    print()
    print("  H3: bits [7:14] as note (cross byte 0-1 boundary)")
    for section, offset, group in all_event_groups[:16]:
        # Take bits 7-13 (7 bits starting at bit 7)
        word = (group[0] << 8) | group[1]
        note = (word >> 1) & 0x7F
        print(
            f"    S{section} @{offset}: note={note:3d} ({midi_note_name(note):4s})  "
            f"raw={' '.join(f'{b:02X}' for b in group)}"
        )

    print()
    print("  H4: byte[1] as note (full 8 bits)")
    for section, offset, group in all_event_groups[:16]:
        note = group[1]
        print(
            f"    S{section} @{offset}: note={note:3d} ({midi_note_name(note):4s})  "
            f"raw={' '.join(f'{b:02X}' for b in group)}"
        )

    # Look for XG chord patterns
    print()
    print("  H5: (byte[0]&0x7F, byte[2]&0x7F, byte[4]&0x7F) as chord notes")
    for section, offset, group in all_event_groups[:16]:
        n1 = group[0] & 0x7F
        n2 = group[2] & 0x7F
        n3 = group[4] & 0x7F
        print(
            f"    S{section} @{offset}: ({midi_note_name(n1):4s},{midi_note_name(n2):4s},"
            f"{midi_note_name(n3):4s}) = ({n1},{n2},{n3})  "
            f"raw={' '.join(f'{b:02X}' for b in group)}"
        )

    # Let's also try: what if the event isn't 7 bytes but spans differently?
    # The "7-byte group" is just the encoding boundary — the actual event structure
    # could be anything within those 7 bytes.

    print()
    print("  H6: Look at just byte pairs (might be note+velocity pairs)")
    for section, offset, group in all_event_groups[:8]:
        pairs = [(group[i], group[i + 1]) for i in range(0, 6, 2)]
        pair_str = "  ".join(f"({a & 0x7F:3d},{b & 0x7F:3d})" for a, b in pairs)
        print(f"    S{section} @{offset}: {pair_str}  raw={' '.join(f'{b:02X}' for b in group)}")


def compare_tracks_across_sections(syx_path: str):
    """Compare the same track across all 6 sections to find which groups change."""
    parser = SysExParser()
    messages = parser.parse_file(syx_path)
    style_msgs = [m for m in messages if m.is_style_data]

    print()
    print("=" * 80)
    print("PART 6: CROSS-SECTION COMPARISON (C1, C3, BASS)")
    print("Which 7-byte groups change between sections?")
    print("=" * 80)

    from collections import defaultdict

    by_al = defaultdict(list)
    for m in style_msgs:
        by_al[m.address_low].append(m)

    for track_idx, track_name in [(3, "C1"), (6, "C3"), (2, "BASS")]:
        print(f"\n  --- {track_name} ---")

        section_groups = {}
        for section in range(6):
            al = section * 8 + track_idx
            if al not in by_al:
                continue
            msg = by_al[al][0]
            dec = msg.decoded_data
            groups = [dec[i : i + 7] for i in range(0, len(dec), 7)]
            section_groups[section] = groups

        if len(section_groups) < 2:
            print("    Only 1 section, can't compare")
            continue

        # Compare each group across sections
        num_groups = min(len(g) for g in section_groups.values())
        sections = sorted(section_groups.keys())

        for g_idx in range(num_groups):
            ref = section_groups[sections[0]][g_idx]
            all_same = all(section_groups[s][g_idx] == ref for s in sections[1:])

            if not all_same:
                print(f"    G{g_idx:2d} @{g_idx * 7:3d}: VARIES")
                for s in sections:
                    g = section_groups[s][g_idx]
                    hex_str = " ".join(f"{b:02X}" for b in g)
                    print(f"      S{s}: {hex_str}")
            else:
                hex_str = " ".join(f"{b:02X}" for b in ref)
                print(f"    G{g_idx:2d} @{g_idx * 7:3d}: SAME    {hex_str}")


if __name__ == "__main__":
    syx_path = sys.argv[1] if len(sys.argv) > 1 else "tests/fixtures/QY70_SGT.syx"
    analyze_per_message_dc(syx_path)
    decode_7byte_groups(syx_path)
    analyze_c1_events_deep(syx_path)
    analyze_c2_events(syx_path)
    analyze_event_fields(syx_path)
    compare_tracks_across_sections(syx_path)
