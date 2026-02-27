#!/usr/bin/env python3
"""
Note Field Cracking — Use the C2/C4 XOR shift pattern and the
consistent bit-7 patterns to determine the exact bit-field layout
of QY70 chord events.

KEY INSIGHTS FROM PREVIOUS ANALYSIS:
1. C2 vs C4: XOR diffs at [9,14], [18,23], [26,31], [35,36,41,42]
   - Shifts by ~8-9 bits per event slot
   - 2 bits differ in E1/E2/E3, 4 bits in E0
2. Pattern `1111100`: bytes 0-4 have bit7 set, bytes 5-6 don't
3. Bytes 5-6 nearly constant: 0x61/0x71 and 0x78
4. The 4 events in a bar likely represent 4 beats, each with a chord

HYPOTHESIS: The 56-bit event word encodes a chord using relative
note offsets from a root, with the root note in the bar header.

ALTERNATIVE: The 7 bytes are NOT a single event — they might be
7 parallel channels/voices, one byte each, where each byte encodes
a note in the chord for that beat.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qymanager.formats.qy70.sysex_parser import SysExParser
from collections import defaultdict


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


def extract_bar_events(data):
    """Extract bars from track data. Returns list of (header, events) tuples."""
    if len(data) < 28:
        return []

    # Skip track header (24 bytes) + preamble (4 bytes)
    event_data = data[28:]

    # Split by DC
    dc_pos = [i for i, b in enumerate(event_data) if b == 0xDC]

    bars = []
    prev = 0
    for dp in dc_pos:
        segment = event_data[prev:dp]
        if len(segment) >= 7:
            bars.append(segment)
        prev = dp + 1
    # Tail segment
    tail = event_data[prev:]
    if len(tail) >= 7:
        bars.append(tail)

    return bars


def analyze_56bit_fields(syx_path):
    """Try all possible 7-bit field extractions from 56-bit event words."""
    print("=" * 80)
    print("PART 1: SYSTEMATIC 7-BIT FIELD EXTRACTION FROM 56-BIT EVENTS")
    print("=" * 80)

    # Get C2 and C4 bar 1 events (both have 41-byte bars with 13-byte header + 4×7 events)
    c2 = get_track_data(syx_path, 0, 4)
    c4 = get_track_data(syx_path, 0, 7)

    # C2 bar 1: bytes 43-83 (after first DC at 42)
    c2_bar = c2[43:84]
    # C4 bar 1: bytes 57-97 (after first DC at 56)
    c4_bar = c4[57:98]

    c2_header = c2_bar[:13]
    c4_header = c4_bar[:13]
    c2_events = [c2_bar[13 + i * 7 : 13 + (i + 1) * 7] for i in range(4)]
    c4_events = [c4_bar[13 + i * 7 : 13 + (i + 1) * 7] for i in range(4)]

    # Also get C2 bar 0 for comparison
    # C2: header+preamble=28 bytes, then event data until DC at 42
    # So bar 0 event data is data[28:42] = 14 bytes = 2 × 7-byte groups
    c2_bar0_groups = [c2[28:35], c2[35:42]]

    # Try extracting 7-bit fields at every possible bit offset (0-49)
    print("\nExtracting 7-bit fields at various bit offsets from C2 bar1 events:")
    print("Looking for fields that produce values in MIDI note range (36-96)")
    print()

    for bit_offset in range(50):
        values = []
        for evt in c2_events:
            # Convert to 56-bit integer
            val = int.from_bytes(evt, "big")
            # Extract 7 bits starting at bit_offset (MSB=0)
            field = (val >> (56 - bit_offset - 7)) & 0x7F
            values.append(field)

        # Check if all values are in MIDI note range
        all_in_range = all(36 <= v <= 96 for v in values)
        any_in_range = any(36 <= v <= 96 for v in values)

        # Also check C4 values
        c4_values = []
        for evt in c4_events:
            val = int.from_bytes(evt, "big")
            field = (val >> (56 - bit_offset - 7)) & 0x7F
            c4_values.append(field)

        c4_all_in_range = all(36 <= v <= 96 for v in c4_values)

        if all_in_range or c4_all_in_range:
            notes_c2 = [nn(v) for v in values]
            notes_c4 = [nn(v) for v in c4_values]
            marker = " ***" if all_in_range and c4_all_in_range else ""
            print(f"  bit_offset={bit_offset:2d}: C2={values} ({notes_c2})")
            print(f"                   C4={c4_values} ({notes_c4}){marker}")

    # Try 8-bit fields too
    print("\n\nExtracting 8-bit fields at byte boundaries:")
    for byte_pos in range(7):
        c2_vals = [evt[byte_pos] for evt in c2_events]
        c4_vals = [evt[byte_pos] for evt in c4_events]
        lo7_c2 = [v & 0x7F for v in c2_vals]
        lo7_c4 = [v & 0x7F for v in c4_vals]

        in_range_c2 = all(36 <= v <= 96 for v in lo7_c2)
        in_range_c4 = all(36 <= v <= 96 for v in lo7_c4)

        if in_range_c2 or in_range_c4:
            notes_c2 = [nn(v) for v in lo7_c2]
            notes_c4 = [nn(v) for v in lo7_c4]
            print(f"  byte {byte_pos}: C2_lo7={lo7_c2} ({notes_c2}) C4_lo7={lo7_c4} ({notes_c4})")


def analyze_interleaved_notes(syx_path):
    """Test hypothesis: maybe the 7 bytes encode 7 interleaved voices/notes,
    one per byte, and the 4 events are 4 beats."""
    print()
    print("=" * 80)
    print("PART 2: INTERLEAVED VOICES HYPOTHESIS")
    print("Each byte = one voice/note, 7 bytes = up to 7 simultaneous notes")
    print("=" * 80)

    c2 = get_track_data(syx_path, 0, 4)
    c2_bar = c2[43:84]
    c2_events = [c2_bar[13 + i * 7 : 13 + (i + 1) * 7] for i in range(4)]

    # In XG, a chord track would play maybe 3-5 notes simultaneously
    # If each byte maps to a voice, bytes 5-6 being constant could mean
    # "voice 5 and 6 are fixed" (maybe bass note and root)

    # What if the 7 bytes are: [v0 v1 v2 v3 v4 timing gate]
    # Where v0-v4 are chord note values with bit7 as "active" flag?

    print("\nHypothesis: bytes 0-4 = notes (bit7=active), bytes 5-6 = timing")
    for i, evt in enumerate(c2_events):
        notes = []
        for j in range(5):
            active = (evt[j] >> 7) & 1
            note = evt[j] & 0x7F
            if active:
                notes.append(f"{nn(note):5s} ({note})")
            else:
                notes.append(f"  -   ({note})")
        timing = evt[5]
        gate = evt[6]
        print(f"  Beat {i}: notes=[{', '.join(notes)}] timing=0x{timing:02X} gate=0x{gate:02X}")


def analyze_relative_encoding(syx_path):
    """Test hypothesis: notes encoded as offsets from the bar header's root note."""
    print()
    print("=" * 80)
    print("PART 3: RELATIVE NOTE ENCODING FROM BAR HEADER")
    print("=" * 80)

    c2 = get_track_data(syx_path, 0, 4)
    c4 = get_track_data(syx_path, 0, 7)

    # C2 bar header: 1F 8F 47 63 71 21 3E 9F 8F C7 62 42 70
    # C4 bar header: 1F 8F 47 63 71 23 3E 9F 8F 47 62 46 60

    c2_hdr = c2[43:56]
    c4_hdr = c4[57:70]

    print(f"C2 header: {' '.join(f'{b:02X}' for b in c2_hdr)}")
    print(f"C4 header: {' '.join(f'{b:02X}' for b in c4_hdr)}")

    # Header diffs at bytes 5, 9, 11, 12
    # Byte 5: C2=0x21(33) C4=0x23(35) → diff=2
    # Byte 9: C2=0xC7(199) C4=0x47(71) → bit7 differs (128 diff)
    # Byte 11: C2=0x42(66) C4=0x46(70) → diff=4
    # Byte 12: C2=0x70(112) C4=0x60(96) → diff=16

    print(f"\nHeader byte differences:")
    for i in range(13):
        if c2_hdr[i] != c4_hdr[i]:
            c2v = c2_hdr[i]
            c4v = c4_hdr[i]
            diff = c2v - c4v
            print(
                f"  Byte {i:2d}: C2=0x{c2v:02X}({c2v:3d}) C4=0x{c4v:02X}({c4v:3d}) "
                f"diff={diff:+4d} (lo7: {c2v & 0x7F} vs {c4v & 0x7F}, "
                f"diff={c2v & 0x7F - (c4v & 0x7F):+d})"
            )


def analyze_pitch_class_encoding(syx_path):
    """Test: maybe the lo7 values encode pitch class (0-11) + octave."""
    print()
    print("=" * 80)
    print("PART 4: PITCH CLASS ANALYSIS")
    print("=" * 80)

    c2 = get_track_data(syx_path, 0, 4)
    c2_events = [c2[43 + 13 + i * 7 : 43 + 13 + (i + 1) * 7] for i in range(4)]

    for i, evt in enumerate(c2_events):
        print(f"\n  Event {i}: {' '.join(f'{b:02X}' for b in evt)}")
        for j in range(7):
            val = evt[j]
            lo7 = val & 0x7F
            hi = (val >> 7) & 1
            # Try pitch class
            pc = lo7 % 12
            octave = lo7 // 12
            print(
                f"    byte {j}: 0x{val:02X} = b7={hi} lo7={lo7:3d} "
                f"pc={pc:2d}({NOTE_NAMES[pc]:2s}) oct={octave}"
            )


def analyze_bit_rotation(syx_path):
    """The XOR pattern shifts by varying amounts per event.
    Let's check if the DATA itself shows a consistent bit rotation."""
    print()
    print("=" * 80)
    print("PART 5: BIT ROTATION / BARREL SHIFT ANALYSIS")
    print("Each event might be the same chord data, rotated by N bits")
    print("=" * 80)

    c2 = get_track_data(syx_path, 0, 4)
    c2_events = [c2[43 + 13 + i * 7 : 43 + 13 + (i + 1) * 7] for i in range(4)]

    # Convert each event to 56-bit integer
    vals = [int.from_bytes(evt, "big") for evt in c2_events]

    print("Event values (56-bit):")
    for i, v in enumerate(vals):
        print(f"  E{i}: 0x{v:014X} = {v:056b}")

    # Check if any rotation of E0 produces E1, E2, or E3
    print("\nRotation analysis (left rotate E0):")
    e0 = vals[0]
    for rot in range(1, 56):
        rotated = ((e0 << rot) | (e0 >> (56 - rot))) & ((1 << 56) - 1)
        for j in range(1, 4):
            if rotated == vals[j]:
                print(f"  E0 rotated left {rot} = E{j} !!!")
            # Also check XOR similarity
            xor = rotated ^ vals[j]
            diff_bits = bin(xor).count("1")
            if diff_bits <= 4:
                print(
                    f"  E0 rotated left {rot} vs E{j}: {diff_bits} bits differ (XOR=0x{xor:014X})"
                )

    # Check sequential rotations between events
    print("\nSequential rotation check (E[i] → E[i+1]):")
    for i in range(3):
        best_rot = -1
        best_diff = 56
        for rot in range(1, 56):
            rotated = ((vals[i] << rot) | (vals[i] >> (56 - rot))) & ((1 << 56) - 1)
            xor = rotated ^ vals[i + 1]
            diff_bits = bin(xor).count("1")
            if diff_bits < best_diff:
                best_diff = diff_bits
                best_rot = rot
        print(f"  E{i}→E{i + 1}: best rotation={best_rot} bits, {best_diff} bits differ")


def analyze_c3_unique_events(syx_path):
    """C3 section 0 has unique musical data. Compare its events to
    the default pattern to understand what changes."""
    print()
    print("=" * 80)
    print("PART 6: C3 SECTION 0 (UNIQUE) EVENT ANALYSIS")
    print("C3 S0 has different musical content — extract its notes")
    print("=" * 80)

    c3_s0 = get_track_data(syx_path, 0, 6)  # C3 section 0 (unique)
    c3_s1 = get_track_data(syx_path, 1, 6)  # C3 section 1 (default)

    bars_s0 = extract_bar_events(c3_s0)
    bars_s1 = extract_bar_events(c3_s1)

    print(f"C3 S0: {len(bars_s0)} bars")
    print(f"C3 S1: {len(bars_s1)} bars")

    # C3 S0 has DC at 56 and 98 (relative to event data start at byte 28)
    # So: bar0=28 bytes, bar1=41 bytes, bar2=? and more from message 2

    # For C3 S0, show events as 7-byte groups
    for bar_idx, bar_data in enumerate(bars_s0[:5]):
        print(f"\n  Bar {bar_idx}: {len(bar_data)} bytes")

        # Check if it has the 13-byte header + 7-byte events structure
        if len(bar_data) >= 20:
            # First, try to find where events start
            # Look for the bit-7 transition from header to events
            for offset in [0, 6, 7, 13, 14]:
                if offset + 7 <= len(bar_data):
                    chunk = bar_data[offset : offset + 7]
                    bit7 = "".join(str((b >> 7) & 1) for b in chunk)
                    hex_str = " ".join(f"{b:02X}" for b in chunk)
                    print(f"    @{offset}: {hex_str}  b7={bit7}")

        # Show all groups
        for g in range(0, len(bar_data), 7):
            chunk = bar_data[g : g + 7]
            if len(chunk) < 7:
                hex_str = " ".join(f"{b:02X}" for b in chunk)
                print(f"    G{g // 7} @{g}: {hex_str}")
                continue
            hex_str = " ".join(f"{b:02X}" for b in chunk)
            bit7 = "".join(str((b >> 7) & 1) for b in chunk)
            lo7 = [b & 0x7F for b in chunk]
            print(f"    G{g // 7} @{g}: {hex_str}  b7={bit7}  lo7={lo7}")


def analyze_differential_encoding(syx_path):
    """Test: maybe each event is encoded as a difference from the previous one."""
    print()
    print("=" * 80)
    print("PART 7: DIFFERENTIAL ENCODING BETWEEN EVENTS")
    print("=" * 80)

    c2 = get_track_data(syx_path, 0, 4)
    c2_events = [c2[43 + 13 + i * 7 : 43 + 13 + (i + 1) * 7] for i in range(4)]

    print("C2 bar 1 events — byte-level differences:")
    for i in range(3):
        diffs = []
        for j in range(7):
            diff = (c2_events[i + 1][j] - c2_events[i][j]) & 0xFF
            signed = diff if diff < 128 else diff - 256
            diffs.append(signed)
        print(f"  E{i}→E{i + 1}: {diffs}")
        lo7_diffs = [(c2_events[i + 1][j] & 0x7F) - (c2_events[i][j] & 0x7F) for j in range(7)]
        print(f"           lo7: {lo7_diffs}")

    # Also look at C3 S0 events which have different musical content
    c3 = get_track_data(syx_path, 0, 6)
    bars = extract_bar_events(c3)
    if len(bars) > 1 and len(bars[1]) >= 41:
        bar1 = bars[1]
        events = [
            bar1[13 + i * 7 : 13 + (i + 1) * 7] for i in range(4) if 13 + (i + 1) * 7 <= len(bar1)
        ]
        if len(events) >= 2:
            print(f"\nC3 S0 bar 1 events — byte-level differences:")
            for i in range(len(events) - 1):
                if len(events[i]) == 7 and len(events[i + 1]) == 7:
                    diffs = [(events[i + 1][j] - events[i][j]) & 0xFF for j in range(7)]
                    signed = [d if d < 128 else d - 256 for d in diffs]
                    print(f"  E{i}→E{i + 1}: {signed}")


def analyze_combined_56bit_as_notes(syx_path):
    """The 13-byte bar header + 4 events = 13 + 28 = 41 bytes = 328 bits.
    Maybe the whole 41-byte bar encodes a measure of music as one block."""
    print()
    print("=" * 80)
    print("PART 8: FULL BAR AS SINGLE ENCODING BLOCK")
    print("Try extracting note values from the full 41-byte bar")
    print("=" * 80)

    c2 = get_track_data(syx_path, 0, 4)
    c4 = get_track_data(syx_path, 0, 7)

    c2_bar = c2[43:84]  # 41 bytes
    c4_bar = c4[57:98]  # 41 bytes

    # Convert full bars to bit strings
    c2_bits = "".join(f"{b:08b}" for b in c2_bar)
    c4_bits = "".join(f"{b:08b}" for b in c4_bar)

    # XOR to find all differing positions
    diff_positions = [i for i, (a, b) in enumerate(zip(c2_bits, c4_bits)) if a != b]
    print(f"Total differing bits between C2 and C4 bar: {len(diff_positions)}")
    print(f"Positions: {diff_positions}")

    # Group diff positions by proximity
    groups = []
    current_group = [diff_positions[0]]
    for p in diff_positions[1:]:
        if p - current_group[-1] <= 2:
            current_group.append(p)
        else:
            groups.append(current_group)
            current_group = [p]
    groups.append(current_group)

    print(f"\nDifference groups (contiguous or near-contiguous):")
    for g in groups:
        byte_start = g[0] // 8
        bit_in_byte = g[0] % 8
        c2_field = int(c2_bits[g[0] : g[-1] + 1], 2)
        c4_field = int(c4_bits[g[0] : g[-1] + 1], 2)
        width = g[-1] - g[0] + 1
        print(
            f"  Bits {g[0]}-{g[-1]} (byte {byte_start}+{bit_in_byte}, width={width}): "
            f"C2={c2_field} C4={c4_field} diff={c2_field - c4_field}"
        )

    # Map each difference group to a potential musical interval
    print(f"\nMusical interval interpretation:")
    for g in groups:
        c2_field = int(c2_bits[g[0] : g[-1] + 1], 2)
        c4_field = int(c4_bits[g[0] : g[-1] + 1], 2)
        diff = c4_field - c2_field
        if abs(diff) <= 24:
            print(f"  Bits {g[0]}-{g[-1]}: interval = {diff:+d} semitones")


if __name__ == "__main__":
    syx_path = sys.argv[1] if len(sys.argv) > 1 else "tests/fixtures/QY70_SGT.syx"
    analyze_56bit_fields(syx_path)
    analyze_interleaved_notes(syx_path)
    analyze_relative_encoding(syx_path)
    analyze_pitch_class_encoding(syx_path)
    analyze_bit_rotation(syx_path)
    analyze_c3_unique_events(syx_path)
    analyze_differential_encoding(syx_path)
    analyze_combined_56bit_as_notes(syx_path)
