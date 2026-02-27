#!/usr/bin/env python3
"""
Ground Truth Decoder — Use D1 drum track (known note values: kick=36, snare=38,
hihat=42/44/46) and Q7P decoded events as ground truth to crack the QY70 bitstream.

STRATEGY:
1. Decode Q7P event data from T01.Q7P to understand reference format (byte-oriented)
2. Analyze D1 drum track from SGT.syx as continuous bitstream
3. Search for known drum note numbers in D1 bitstream
4. Use findings to build a general bitstream decoder

KEY KNOWN DRUM NOTES (GM/XG Standard Kit):
  35=Kick2, 36=Kick1, 38=Snare1, 40=Snare2
  42=HiHatClosed, 44=HiHatPedal, 46=HiHatOpen
  49=Crash, 51=Ride, 53=RideBell
  41=LowTom, 43=MidTom, 45=HighTom, 47=MidTom2, 48=HighTom2
"""

import sys
import os
import struct

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
    """Extract field of 'width' bits starting at position 'msb' (0=MSB)."""
    shift = total_width - msb - width
    if shift < 0:
        return -1
    return (val >> shift) & ((1 << width) - 1)


# ============================================================================
# PART 1: Q7P Event Data Decoding (reference format)
# ============================================================================


def decode_q7p_events(q7p_path):
    """Decode Q7P event data to understand the reference format."""
    print("=" * 80)
    print("PART 1: Q7P EVENT DATA DECODING (T01.Q7P)")
    print("=" * 80)

    with open(q7p_path, "rb") as f:
        data = f.read()

    print(f"File size: {len(data)} bytes")

    # Section config starts at 0x100
    # Phrase/sequence data region: 0x100-0x87F (variable)
    # The section pointers are at 0x100+

    # Let's find the actual event data
    # In T01, section 0 is active. Section pointer at 0x100
    ptr_offset = 0x100
    section_data = data[ptr_offset:]

    # Show raw bytes around section data start
    print(f"\nSection data region (0x100-0x180):")
    for row in range(0, 128, 16):
        offset = 0x100 + row
        chunk = data[offset : offset + 16]
        hex_str = " ".join(f"{b:02X}" for b in chunk)
        ascii_str = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
        print(f"  0x{offset:04X}: {hex_str}  |{ascii_str}|")

    # Parse Q7P event commands
    print(f"\nParsing Q7P event commands starting at 0x100:")
    pos = 0x100
    max_pos = 0x876  # Before pattern name
    event_count = 0

    while pos < max_pos and pos < len(data):
        cmd = data[pos]

        if cmd == 0xF2:
            print(f"  0x{pos:04X}: F2 — END OF SECTION")
            pos += 1
            event_count += 1
            continue

        if cmd == 0xF0:
            # Section header
            if pos + 8 < len(data):
                block = data[pos : pos + 9]
                hex_str = " ".join(f"{b:02X}" for b in block)
                print(f"  0x{pos:04X}: {hex_str} — SECTION HEADER")
                pos += 9
                event_count += 1
                continue

        if cmd == 0xFE:
            # Fill byte
            # Count consecutive 0xFE
            count = 0
            while pos + count < len(data) and data[pos + count] == 0xFE:
                count += 1
            if count > 2:
                print(f"  0x{pos:04X}: FE × {count} — FILL")
                pos += count
                continue
            else:
                pos += 1
                continue

        if cmd == 0xF1:
            # F1 = inline data record
            # Find length — scan until we hit something recognizable
            end = pos + 1
            while end < max_pos and data[end] not in (0xF0, 0xF2, 0xFE) and end - pos < 100:
                end += 1
            block = data[pos:end]
            hex_str = " ".join(f"{b:02X}" for b in block[:20])
            if len(block) > 20:
                hex_str += f" ... ({len(block)} bytes)"
            print(f"  0x{pos:04X}: {hex_str} — F1 RECORD")
            pos = end
            event_count += 1
            continue

        if 0xD0 <= cmd <= 0xDF:
            # Drum note event: D0 nn vv xx
            if pos + 3 < len(data):
                note = data[pos + 1]
                vel = data[pos + 2]
                extra = data[pos + 3]
                drum_name = GM_DRUM_NAMES.get(note, nn(note))
                print(
                    f"  0x{pos:04X}: D0 {note:02X} {vel:02X} {extra:02X} — "
                    f"DRUM note={note}({drum_name}) vel={vel} x={extra}"
                )
                pos += 4
                event_count += 1
                continue

        if 0xE0 <= cmd <= 0xEF:
            # Melody note: E0 nn vv xx
            if pos + 3 < len(data):
                note = data[pos + 1]
                vel = data[pos + 2]
                extra = data[pos + 3]
                print(
                    f"  0x{pos:04X}: E0 {note:02X} {vel:02X} {extra:02X} — "
                    f"MELODY note={note}({nn(note)}) vel={vel} x={extra}"
                )
                pos += 4
                event_count += 1
                continue

        if 0xA0 <= cmd <= 0xA7:
            # Delta time: A0-A7 dd
            ticks_hi = cmd & 0x07
            ticks_lo = data[pos + 1] if pos + 1 < len(data) else 0
            ticks = (ticks_hi << 8) | ticks_lo
            print(f"  0x{pos:04X}: {cmd:02X} {ticks_lo:02X} — DELTA {ticks} ticks")
            pos += 2
            event_count += 1
            continue

        if cmd == 0xBE:
            # Note off
            if pos + 1 < len(data):
                val = data[pos + 1]
                print(f"  0x{pos:04X}: BE {val:02X} — NOTE OFF ({val})")
                pos += 2
                event_count += 1
                continue

        if cmd == 0xC0:
            # Bar count
            if pos + 1 < len(data):
                bars = data[pos + 1]
                print(f"  0x{pos:04X}: C0 {bars:02X} — BAR COUNT ({bars})")
                pos += 2
                event_count += 1
                continue

        # Unknown command
        print(f"  0x{pos:04X}: {cmd:02X} — UNKNOWN CMD")
        pos += 1
        event_count += 1

        if event_count > 200:
            print("  ... (truncated)")
            break

    print(f"\nTotal events parsed: {event_count}")


# ============================================================================
# PART 2: D1 Drum Track Bitstream Analysis
# ============================================================================


def analyze_d1_bitstream(syx_path):
    """Treat D1 drum track as a continuous bitstream and search for
    known drum note values."""
    print()
    print("=" * 80)
    print("PART 2: D1 DRUM TRACK BITSTREAM ANALYSIS")
    print("Searching for known drum note values in bitstream")
    print("=" * 80)

    d1 = get_track_data(syx_path, 0, 0)
    print(f"D1 total: {len(d1)} bytes")
    print(f"Track header: {' '.join(f'{b:02X}' for b in d1[:24])}")
    print(f"Preamble: {' '.join(f'{b:02X}' for b in d1[24:28])}")

    # Event data starts at byte 28
    event_data = d1[28:]
    print(f"Event data: {len(event_data)} bytes")

    # Convert to bitstream
    total_bits = len(event_data) * 8
    bitstream = int.from_bytes(event_data, "big")

    # Key drum notes to search for
    target_notes = {
        36: "Kick1",
        38: "Snare1",
        42: "HHClosed",
        44: "HHPedal",
        46: "HHOpen",
        49: "Crash1",
        51: "Ride1",
        53: "RideBell",
        41: "LowTom2",
        43: "LowTom1",
        45: "MidTom2",
        37: "SideStick",
    }

    # Search for 7-bit encoded drum notes at regular intervals
    # A typical drum pattern has 16 or 32 subdivisions per bar
    # With 740 event bytes for 2 bars, that's ~370 bytes/bar

    # Try different field widths and intervals
    for field_width in [7, 8, 9]:
        print(f"\n--- Searching for {field_width}-bit drum notes ---")

        # Scan the entire bitstream
        note_positions = defaultdict(list)

        for bit_pos in range(total_bits - field_width):
            val = extract_field(bitstream, bit_pos, field_width, total_bits)
            if val in target_notes:
                note_positions[val].append(bit_pos)

        # Report findings
        for note, positions in sorted(note_positions.items()):
            if len(positions) > 2:  # Only show notes that appear multiple times
                # Calculate intervals between occurrences
                intervals = [
                    positions[i + 1] - positions[i] for i in range(min(len(positions) - 1, 10))
                ]
                consistent = len(set(intervals)) <= 3  # Few unique intervals
                marker = " *** REGULAR" if consistent and len(intervals) > 3 else ""
                name = target_notes[note]
                print(
                    f"  Note {note:3d} ({name:10s}): {len(positions):3d} occurrences, "
                    f"first intervals: {intervals[:8]}{marker}"
                )

    # Also try: look for byte patterns that correlate with '28 0F' markers
    print(f"\n--- Context around '28 0F' markers (D1 beat markers) ---")
    markers_28_0f = []
    for i in range(len(event_data) - 1):
        if event_data[i] == 0x28 and event_data[i + 1] == 0x0F:
            markers_28_0f.append(i)

    print(f"Found {len(markers_28_0f)} '28 0F' markers at: {markers_28_0f}")

    # Extract data between markers and analyze
    for i, pos in enumerate(markers_28_0f[:6]):
        end = markers_28_0f[i + 1] if i + 1 < len(markers_28_0f) else len(event_data)
        segment = event_data[pos:end]
        hex_str = " ".join(f"{b:02X}" for b in segment[:20])
        if len(segment) > 20:
            hex_str += f"... ({len(segment)} bytes)"
        print(f"  Marker {i} @{pos}: {hex_str}")

        # Show as 7-byte groups
        for g in range(0, min(len(segment), 35), 7):
            chunk = segment[g : g + 7]
            if len(chunk) == 7:
                bit7 = "".join(str((b >> 7) & 1) for b in chunk)
                lo7 = [b & 0x7F for b in chunk]
                print(
                    f"    G{g // 7} @{g}: {' '.join(f'{b:02X}' for b in chunk)}  "
                    f"b7={bit7}  lo7={lo7}"
                )


# ============================================================================
# PART 3: D1 Event Byte Frequency and Structure
# ============================================================================


def d1_byte_analysis(syx_path):
    """Analyze D1 event data byte-by-byte looking for structure."""
    print()
    print("=" * 80)
    print("PART 3: D1 BYTE-LEVEL STRUCTURE ANALYSIS")
    print("=" * 80)

    d1 = get_track_data(syx_path, 0, 0)
    event_data = d1[28:]

    # DC positions
    dc_pos = [i for i, b in enumerate(event_data) if b == 0xDC]
    print(f"DC positions: {dc_pos}")

    # Split into bars
    bar0 = event_data[: dc_pos[0]] if dc_pos else event_data
    bar1 = event_data[dc_pos[0] + 1 :] if dc_pos else b""

    print(f"Bar 0: {len(bar0)} bytes")
    print(f"Bar 1: {len(bar1)} bytes")

    # Byte frequency analysis per bar
    for bar_name, bar_data in [("Bar0", bar0), ("Bar1", bar1)]:
        print(f"\n  {bar_name} byte frequency (top 20):")
        freq = Counter(bar_data)
        for byte_val, count in freq.most_common(20):
            pct = count / len(bar_data) * 100
            lo7 = byte_val & 0x7F
            drum = GM_DRUM_NAMES.get(lo7, "")
            print(
                f"    0x{byte_val:02X} ({byte_val:3d}): {count:3d}× ({pct:4.1f}%) "
                f"lo7={lo7:3d} {drum}"
            )

    # Look for the '40 78' pattern too
    print(f"\n  '40 78' positions in event data:")
    for i in range(len(event_data) - 1):
        if event_data[i] == 0x40 and event_data[i + 1] == 0x78:
            ctx = event_data[max(0, i - 3) : min(len(event_data), i + 6)]
            print(f"    @{i}: {' '.join(f'{b:02X}' for b in ctx)}")

    # Try treating D1 as having 9-bit groups
    print(f"\n  D1 bar0 as 9-bit values (first 50):")
    bar0_bits = int.from_bytes(bar0, "big")
    bar0_total = len(bar0) * 8
    for i in range(min(50, bar0_total // 9)):
        val = extract_field(bar0_bits, i * 9, 9, bar0_total)
        lo7 = val & 0x7F
        drum = GM_DRUM_NAMES.get(lo7, "")
        drum2 = GM_DRUM_NAMES.get(val, "") if val <= 127 else ""
        marker = f" <<< {drum2}" if drum2 else ""
        print(f"    F{i:2d} @{i * 9:3d}: {val:3d} (0b{val:09b}) lo7={lo7:3d} {drum}{marker}")


# ============================================================================
# PART 4: Look for note patterns in D1 using the '28 0F' structure
# ============================================================================


def d1_structural_decode(syx_path):
    """Use '28 0F' as beat markers and try to decode D1 events between them."""
    print()
    print("=" * 80)
    print("PART 4: D1 STRUCTURAL DECODE USING '28 0F' MARKERS")
    print("=" * 80)

    d1 = get_track_data(syx_path, 0, 0)
    event_data = d1[28:]

    # Find '28 0F' markers
    markers = []
    for i in range(len(event_data) - 1):
        if event_data[i] == 0x28 and event_data[i + 1] == 0x0F:
            markers.append(i)

    print(f"Markers: {len(markers)} at positions {markers}")
    intervals = [markers[i + 1] - markers[i] for i in range(len(markers) - 1)]
    print(f"Intervals: {intervals}")
    print(f"Average interval: {sum(intervals) / len(intervals):.1f} bytes")

    # For each inter-marker segment, try to decode as drum events
    for i in range(min(len(markers), 8)):
        start = markers[i]
        end = markers[i + 1] if i + 1 < len(markers) else len(event_data)
        segment = event_data[start:end]

        print(f"\n  Segment {i} ({start}-{end}, {len(segment)} bytes):")
        hex_str = " ".join(f"{b:02X}" for b in segment)
        print(f"    Raw: {hex_str}")

        # The first 2 bytes are the marker '28 0F'
        # Byte 2 is typically 0x8C, 0x8D, or 0x8F
        if len(segment) > 2:
            b2 = segment[2]
            b2_lo7 = b2 & 0x7F
            print(f"    Byte 2: 0x{b2:02X} (lo7={b2_lo7}, b7={b2 >> 7})")

        # Try interpreting remaining bytes as note events
        # Hypothesis: each drum hit is encoded in some compact format
        # Let's look at 3-byte and 4-byte groupings after the 3-byte header

        remaining = segment[3:]
        print(f"    After header ({len(remaining)} bytes):")

        # Show as various groupings
        for group_size in [3, 4]:
            groups = []
            for g in range(0, len(remaining) - group_size + 1, group_size):
                chunk = remaining[g : g + group_size]
                groups.append(chunk)

            if groups:
                print(f"      As {group_size}-byte groups:")
                for gi, g in enumerate(groups[:8]):
                    hex_g = " ".join(f"{b:02X}" for b in g)
                    lo7s = [b & 0x7F for b in g]
                    drums = [GM_DRUM_NAMES.get(v, "") for v in lo7s]
                    drum_str = " ".join(f"{d:10s}" for d in drums if d)
                    print(f"        G{gi}: {hex_g}  lo7={lo7s}  {drum_str}")


# ============================================================================
# PART 5: Cross-reference D1 with Q7P drum events
# ============================================================================


def cross_reference_drums(syx_path, q7p_path):
    """If T01.Q7P has drum events, compare note distribution with D1."""
    print()
    print("=" * 80)
    print("PART 5: Q7P DRUM EVENTS vs QY70 D1 COMPARISON")
    print("=" * 80)

    with open(q7p_path, "rb") as f:
        q7p_data = f.read()

    # Parse Q7P events to find drum notes
    q7p_drums = []
    pos = 0x100
    while pos < 0x876:
        cmd = q7p_data[pos]

        if cmd == 0xF2:
            pos += 1
            continue
        if cmd == 0xFE:
            pos += 1
            continue
        if cmd == 0xF0:
            pos += 9
            continue
        if cmd == 0xF1:
            # Skip F1 record
            end = pos + 1
            while end < 0x876 and q7p_data[end] not in (0xF0, 0xF2, 0xFE, 0xC0):
                end += 1
            pos = end
            continue
        if 0xD0 <= cmd <= 0xDF:
            if pos + 3 < len(q7p_data):
                note = q7p_data[pos + 1]
                vel = q7p_data[pos + 2]
                q7p_drums.append((note, vel))
            pos += 4
            continue
        if 0xE0 <= cmd <= 0xEF:
            pos += 4
            continue
        if 0xA0 <= cmd <= 0xA7:
            pos += 2
            continue
        if cmd == 0xBE:
            pos += 2
            continue
        if cmd == 0xC0:
            pos += 2
            continue
        pos += 1

    print(f"Q7P drum events: {len(q7p_drums)}")

    if q7p_drums:
        # Drum note distribution
        note_freq = Counter(note for note, vel in q7p_drums)
        print(f"\nQ7P drum note distribution:")
        for note, count in note_freq.most_common():
            name = GM_DRUM_NAMES.get(note, nn(note))
            print(f"  Note {note:3d} ({name:12s}): {count:3d}×")

        # Velocity distribution
        vel_freq = Counter(vel for note, vel in q7p_drums)
        print(f"\nQ7P drum velocity distribution:")
        for vel, count in vel_freq.most_common(10):
            print(f"  Vel {vel:3d}: {count:3d}×")

    # Now analyze D1 from QY70
    d1 = get_track_data(syx_path, 0, 0)
    event_data = d1[28:]

    # D1 byte-level frequency of lo7 values
    d1_lo7_freq = Counter(b & 0x7F for b in event_data)
    d1_byte_freq = Counter(event_data)

    print(f"\nQY70 D1 lo7 frequency (matching drum notes):")
    for lo7, count in d1_lo7_freq.most_common(30):
        name = GM_DRUM_NAMES.get(lo7, "")
        pct = count / len(event_data) * 100
        is_drum = " <<<" if name else ""
        print(f"  lo7={lo7:3d} (0x{lo7:02X}): {count:3d}× ({pct:4.1f}%) {name}{is_drum}")


# ============================================================================
# PART 6: Systematic 9-bit sliding window on D1 with drum correlation
# ============================================================================


def d1_9bit_drum_correlation(syx_path):
    """Use 9-bit sliding window and correlate with expected drum patterns."""
    print()
    print("=" * 80)
    print("PART 6: D1 9-BIT SLIDING WINDOW DRUM CORRELATION")
    print("=" * 80)

    d1 = get_track_data(syx_path, 0, 0)
    event_data = d1[28:]

    # Split by DC
    dc_pos = [i for i, b in enumerate(event_data) if b == 0xDC]
    bar0 = event_data[: dc_pos[0]] if dc_pos else event_data

    total_bits = len(bar0) * 8
    bar0_int = int.from_bytes(bar0, "big")

    # For each possible starting bit offset (0-8), extract 9-bit values
    # and check which offset produces the most drum note values
    drum_notes = set(GM_DRUM_NAMES.keys())

    print(f"Bar 0: {len(bar0)} bytes = {total_bits} bits")
    print(f"Testing 9-bit extraction at different phase offsets:")

    for phase in range(9):
        values = []
        for i in range(phase, total_bits - 8, 9):
            val = extract_field(bar0_int, i, 9, total_bits)
            values.append(val)

        # Count how many values are valid drum notes
        drum_hits = sum(1 for v in values if v in drum_notes)
        drum_7bit = sum(1 for v in values if (v & 0x7F) in drum_notes)
        in_range = sum(1 for v in values if 35 <= v <= 81)

        print(
            f"  Phase {phase}: {len(values)} values, "
            f"{drum_hits} exact drum notes, "
            f"{drum_7bit} lo7 drum notes, "
            f"{in_range} in drum range"
        )

        # Show the first 20 values
        val_str = ", ".join(f"{v}" for v in values[:20])
        print(f"    First 20: [{val_str}]")

        # Show which are drum notes
        drum_found = [(i, v, GM_DRUM_NAMES[v]) for i, v in enumerate(values) if v in drum_notes]
        if drum_found:
            for idx, val, name in drum_found[:10]:
                print(f"    @slot {idx}: {val} = {name}")

    # Also try 7-bit extraction
    print(f"\nTesting 7-bit extraction at different phase offsets:")
    for phase in range(7):
        values = []
        for i in range(phase, total_bits - 6, 7):
            val = extract_field(bar0_int, i, 7, total_bits)
            values.append(val)

        drum_hits = sum(1 for v in values if v in drum_notes)
        in_range = sum(1 for v in values if 35 <= v <= 81)

        if drum_hits > 5:
            print(
                f"  Phase {phase}: {len(values)} values, "
                f"{drum_hits} drum notes, {in_range} in drum range"
            )
            drum_found = [(i, v, GM_DRUM_NAMES[v]) for i, v in enumerate(values) if v in drum_notes]
            for idx, val, name in drum_found[:10]:
                print(f"    @slot {idx}: {val} = {name}")


# ============================================================================
# PART 7: Explore if D1 uses the SAME header+events structure as chord tracks
# ============================================================================


def d1_structure_comparison(syx_path):
    """Compare D1 structure to chord tracks to find commonalities."""
    print()
    print("=" * 80)
    print("PART 7: D1 vs CHORD TRACK STRUCTURAL COMPARISON")
    print("=" * 80)

    track_names = {0: "D1", 1: "D2", 2: "BASS", 3: "C1", 4: "C2", 5: "PC", 6: "C3", 7: "C4"}

    for track_idx in range(8):
        data = get_track_data(syx_path, 0, track_idx)
        if len(data) < 28:
            continue

        # Track header
        header = data[:24]
        preamble = data[24:28]
        event_data = data[28:]

        # Count DCs
        dc_count = sum(1 for b in event_data if b == 0xDC)
        dc_pos = [i for i, b in enumerate(event_data) if b == 0xDC]

        # Count 7-byte group aligned segments
        name = track_names.get(track_idx, f"T{track_idx}")
        print(
            f"\n  {name}: {len(data)} bytes total, "
            f"{len(event_data)} event bytes, "
            f"{dc_count} DCs at {dc_pos}"
        )

        # Show preamble
        print(f"    Preamble: {' '.join(f'{b:02X}' for b in preamble)}")

        # Show first 7 bytes of event data after preamble (first group)
        if len(event_data) >= 7:
            first_group = event_data[:7]
            bit7 = "".join(str((b >> 7) & 1) for b in first_group)
            print(f"    First 7B: {' '.join(f'{b:02X}' for b in first_group)}  b7={bit7}")

        # Show voice bytes from track header
        voice = header[14:16]
        note_range = header[16:18]
        track_type = header[18:21]
        pan = header[21:23]
        print(
            f"    Voice: {voice[0]:02X} {voice[1]:02X}  "
            f"NoteRange: {note_range[0]:02X} {note_range[1]:02X}  "
            f"Type: {' '.join(f'{b:02X}' for b in track_type)}  "
            f"Pan: {pan[0]:02X} {pan[1]:02X}"
        )


# ============================================================================
# PART 8: Look for note values in D2 track (second drum track)
# ============================================================================


def analyze_d2_track(syx_path):
    """D2 is the second drum track — may have simpler patterns."""
    print()
    print("=" * 80)
    print("PART 8: D2 (SECOND DRUM) TRACK ANALYSIS")
    print("=" * 80)

    d2 = get_track_data(syx_path, 0, 1)
    if len(d2) < 28:
        print("  D2 has no data")
        return

    event_data = d2[28:]
    print(f"D2 event data: {len(event_data)} bytes")

    # Show as 7-byte groups
    dc_pos = [i for i, b in enumerate(event_data) if b == 0xDC]
    print(f"DC positions: {dc_pos}")

    # Show all data
    for g in range(0, len(event_data), 7):
        chunk = event_data[g : g + 7]
        hex_str = " ".join(f"{b:02X}" for b in chunk)
        if len(chunk) == 7:
            bit7 = "".join(str((b >> 7) & 1) for b in chunk)
            lo7 = [b & 0x7F for b in chunk]
            drums = [GM_DRUM_NAMES.get(v, "") for v in lo7]
            drum_str = "  ".join(f"{d}" for d in drums if d)
            dc_marker = (
                " <<DC"
                if any(
                    event_data[g + j] == 0xDC for j in range(min(7, len(chunk))) if g + j in dc_pos
                )
                else ""
            )
            print(f"  G{g // 7:2d} @{g}: {hex_str}  b7={bit7}  {drum_str}{dc_marker}")
        else:
            print(f"  G{g // 7:2d} @{g}: {hex_str}")


# ============================================================================
# PART 9: BASS track analysis (melodic, simpler than chords)
# ============================================================================


def analyze_bass_track(syx_path):
    """BASS track plays single notes — easier to decode than chords."""
    print()
    print("=" * 80)
    print("PART 9: BASS TRACK ANALYSIS")
    print("=" * 80)

    bass = get_track_data(syx_path, 0, 2)
    if len(bass) < 28:
        print("  BASS has no data")
        return

    header = bass[:24]
    preamble = bass[24:28]
    event_data = bass[28:]

    print(f"BASS total: {len(bass)} bytes")
    print(f"Track header: {' '.join(f'{b:02X}' for b in header)}")
    print(f"Preamble: {' '.join(f'{b:02X}' for b in preamble)}")
    print(f"Event data: {len(event_data)} bytes")

    # Voice info
    voice = header[14:16]
    note_range = header[16:18]
    print(f"Voice: {voice[0]:02X} {voice[1]:02X} (bank={voice[0]}, prog={voice[1]})")
    print(f"Note range: {note_range[0]:02X} {note_range[1]:02X}")

    # DC positions
    dc_pos = [i for i, b in enumerate(event_data) if b == 0xDC]
    print(f"DC positions: {dc_pos}")

    # Show as 7-byte groups
    for g in range(0, len(event_data), 7):
        chunk = event_data[g : g + 7]
        hex_str = " ".join(f"{b:02X}" for b in chunk)
        if len(chunk) == 7:
            bit7 = "".join(str((b >> 7) & 1) for b in chunk)
            lo7 = [b & 0x7F for b in chunk]
            notes = [nn(v) for v in lo7 if 24 <= v <= 72]
            note_str = " ".join(notes) if notes else ""
            print(f"  G{g // 7:2d} @{g}: {hex_str}  b7={bit7}  lo7={lo7}  {note_str}")
        else:
            print(f"  G{g // 7:2d} @{g}: {hex_str}")

    # Try 9-bit extraction
    total_bits = len(event_data) * 8
    bs = int.from_bytes(event_data, "big")

    print(f"\n  9-bit values (first 30):")
    for i in range(min(30, total_bits // 9)):
        val = extract_field(bs, i * 9, 9, total_bits)
        lo7 = val & 0x7F
        if 0 <= lo7 <= 127:
            note = nn(lo7)
        else:
            note = ""
        bass_range = "<<< BASS" if 24 <= lo7 <= 60 else ""
        print(f"    F{i:2d}: {val:3d} (0b{val:09b})  lo7={lo7:3d} ({note}) {bass_range}")


if __name__ == "__main__":
    syx_path = sys.argv[1] if len(sys.argv) > 1 else "tests/fixtures/QY70_SGT.syx"
    q7p_path = "tests/fixtures/T01.Q7P"

    decode_q7p_events(q7p_path)
    analyze_d1_bitstream(syx_path)
    d1_byte_analysis(syx_path)
    d1_structural_decode(syx_path)
    cross_reference_drums(syx_path, q7p_path)
    d1_9bit_drum_correlation(syx_path)
    d1_structure_comparison(syx_path)
    analyze_d2_track(syx_path)
    analyze_bass_track(syx_path)
