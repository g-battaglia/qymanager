#!/usr/bin/env python3
"""
D1 Drum Track Deep Analysis — Concatenate all 6 messages and analyze
the complete drum event stream. Also analyze Q7P events for comparison.

D1 is the primary drum track with 6 messages = 768 decoded bytes.
Drum events should map to known GM/GS drum notes:
  36=Kick, 38=Snare, 42=HiHat Closed, 46=HiHat Open, etc.
"""

import sys
import os
import struct

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qymanager.formats.qy70.sysex_parser import SysExParser
from qymanager.utils.yamaha_7bit import decode_7bit
from collections import defaultdict, Counter


TRACK_NAMES = {0: "D1", 1: "D2", 2: "BASS", 3: "C1", 4: "C2", 5: "PC", 6: "C3", 7: "C4/PHR"}


def concatenate_track_data(syx_path: str, section: int, track: int) -> bytes:
    """Get all decoded data for a track, concatenated from multiple messages."""
    parser = SysExParser()
    messages = parser.parse_file(syx_path)

    al = section * 8 + track
    track_msgs = sorted(
        [m for m in messages if m.is_style_data and m.address_low == al],
        key=lambda m: messages.index(m),  # Keep file order
    )

    data = b""
    for m in track_msgs:
        data += m.decoded_data
    return data


def analyze_d1_full_stream(syx_path: str):
    """Analyze the full D1 drum track data stream."""
    data = concatenate_track_data(syx_path, 0, 0)

    print("=" * 80)
    print(f"D1 FULL STREAM: {len(data)} decoded bytes from section 0")
    print("=" * 80)

    # Find all DC positions in the concatenated stream
    dc_pos = [i for i, b in enumerate(data) if b == 0xDC]
    print(f"DC positions in full stream: {dc_pos}")

    # Show track header
    print(f"\nTrack header (bytes 0-23):")
    for i in range(0, 24, 8):
        chunk = data[i : min(i + 8, 24)]
        hex_str = " ".join(f"{b:02X}" for b in chunk)
        print(f"  {i:3d}: {hex_str}")

    # Preamble
    print(f"\nPreamble (bytes 24-27): {' '.join(f'{b:02X}' for b in data[24:28])}")

    # Event data starts at byte 28
    event_data = data[28:]
    print(f"\nEvent data: {len(event_data)} bytes")

    # Find DC in event data
    dc_ev = [i for i, b in enumerate(event_data) if b == 0xDC]
    print(f"DC in event data at: {dc_ev}")

    # Split by DC
    segments = []
    prev = 0
    for dp in dc_ev:
        segments.append(event_data[prev:dp])
        prev = dp + 1
    segments.append(event_data[prev:])

    print(f"\nSegments (bars): {len(segments)}")
    for seg_idx, seg in enumerate(segments):
        is_last = seg_idx == len(segments) - 1
        label = f"Bar {seg_idx}" if not is_last else "TAIL"
        print(f"\n  {label}: {len(seg)} bytes")
        # Show first 56 bytes max
        for i in range(0, min(len(seg), 84), 7):
            chunk = seg[i : i + 7]
            hex_str = " ".join(f"{b:02X}" for b in chunk)
            bit7 = "".join(str((b >> 7) & 1) for b in chunk)
            lo7 = [b & 0x7F for b in chunk]
            lo7_str = " ".join(f"{v:3d}" for v in lo7)
            print(f"    {i:3d}: {hex_str}  b7={bit7}  lo7=[{lo7_str}]")
        if len(seg) > 84:
            print(f"    ... ({len(seg) - 84} more bytes)")

    # Compare segment sizes
    sizes = [len(s) for s in segments]
    print(f"\nSegment sizes: {sizes}")

    # Compare segments for similarity
    print(f"\nSegment similarity matrix:")
    for i in range(len(segments)):
        for j in range(i + 1, len(segments)):
            min_len = min(len(segments[i]), len(segments[j]))
            if min_len == 0:
                continue
            matches = sum(1 for a, b in zip(segments[i][:min_len], segments[j][:min_len]) if a == b)
            pct = matches / min_len * 100
            if pct > 50:
                print(f"  Seg {i} vs {j}: {pct:.0f}% match ({matches}/{min_len} bytes)")


def analyze_q7p_events(q7p_path: str):
    """Analyze Q7P event format for cross-reference."""
    with open(q7p_path, "rb") as f:
        data = f.read()

    print()
    print("=" * 80)
    print(f"Q7P EVENT DATA ANALYSIS: {q7p_path}")
    print(f"File size: {len(data)} bytes")
    print("=" * 80)

    # Q7P section pointers are at various offsets
    # For 3072-byte files, section data starts around 0x100
    # Phrase/sequence data is at the end

    # Let's look at the phrase data area (typically starts around 0x300-0x380)
    # Section config at 0x120+

    # First, let's find all Q7P event commands in the data
    # Q7P commands: D0 nn vv xx (drum), E0 nn vv xx (melody), A0-A7 dd (delta), F2 (end), etc.

    print("\nScanning for Q7P event commands in phrase data area (0x300-end):")

    event_area = data[0x300:]
    i = 0
    events = []
    while i < len(event_area):
        byte = event_area[i]
        offset = 0x300 + i

        if byte == 0xD0:  # Drum note
            if i + 3 < len(event_area):
                note = event_area[i + 1]
                vel = event_area[i + 2]
                gate = event_area[i + 3]
                events.append(("DRUM", offset, note, vel, gate))
                i += 4
                continue
        elif byte == 0xE0:  # Melody note
            if i + 3 < len(event_area):
                note = event_area[i + 1]
                vel = event_area[i + 2]
                gate = event_area[i + 3]
                events.append(("NOTE", offset, note, vel, gate))
                i += 4
                continue
        elif 0xA0 <= byte <= 0xA7:  # Delta time
            if i + 1 < len(event_area):
                delta = event_area[i + 1]
                events.append(("DELTA", offset, byte - 0xA0, delta, 0))
                i += 2
                continue
        elif byte == 0xBE:  # Note off
            if i + 1 < len(event_area):
                events.append(("OFF", offset, event_area[i + 1], 0, 0))
                i += 2
                continue
        elif byte == 0xF2:  # End marker
            events.append(("END", offset, 0, 0, 0))
            i += 1
            continue
        elif byte == 0xFE:  # Fill byte
            i += 1
            continue

        i += 1

    print(f"Found {len(events)} events")

    # Show first events
    note_names = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

    def nn(n):
        if 0 <= n <= 127:
            return f"{note_names[n % 12]}{n // 12 - 1}"
        return f"?{n}"

    drum_names = {
        35: "Kick2",
        36: "Kick1",
        37: "SStick",
        38: "Snare1",
        39: "Clap",
        40: "Snare2",
        41: "LTom2",
        42: "HHClose",
        43: "LTom1",
        44: "HHPedal",
        45: "MTom2",
        46: "HHOpen",
        47: "MTom1",
        48: "HTom2",
        49: "Crash1",
        50: "HTom1",
        51: "Ride1",
        52: "China",
        53: "RideBell",
        54: "Tamb",
        55: "Splash",
        56: "Cowbell",
    }

    for evt in events[:60]:
        cmd, offset, p1, p2, p3 = evt
        if cmd == "DRUM":
            dname = drum_names.get(p1, nn(p1))
            print(f"  0x{offset:03X}: DRUM  note={p1:3d} ({dname:10s}) vel={p2:3d} gate=0x{p3:02X}")
        elif cmd == "NOTE":
            print(f"  0x{offset:03X}: NOTE  note={p1:3d} ({nn(p1):6s}) vel={p2:3d} gate=0x{p3:02X}")
        elif cmd == "DELTA":
            print(f"  0x{offset:03X}: DELTA channel={p1} value={p2:3d}")
        elif cmd == "OFF":
            print(f"  0x{offset:03X}: OFF   ref=0x{p1:02X}")
        elif cmd == "END":
            print(f"  0x{offset:03X}: END")

    # Statistics
    print(f"\nEvent type counts:")
    type_counts = Counter(e[0] for e in events)
    for t, c in type_counts.most_common():
        print(f"  {t}: {c}")

    if type_counts.get("DRUM", 0) > 0:
        print(f"\nDrum note distribution:")
        drum_notes = Counter(e[2] for e in events if e[0] == "DRUM")
        for note, count in drum_notes.most_common():
            dname = drum_names.get(note, nn(note))
            print(f"  {note:3d} ({dname:10s}): {count}")

    if type_counts.get("DRUM", 0) > 0:
        print(f"\nDrum velocity distribution:")
        vels = [e[3] for e in events if e[0] == "DRUM"]
        vel_counts = Counter(vels)
        for v, c in vel_counts.most_common(10):
            print(f"  vel={v:3d}: {c}")


def analyze_byte_frequency(syx_path: str):
    """Analyze byte frequency in QY70 event data to find structural patterns."""
    parser = SysExParser()
    messages = parser.parse_file(syx_path)
    style_msgs = [m for m in messages if m.is_style_data]

    by_al = defaultdict(list)
    for m in style_msgs:
        by_al[m.address_low].append(m)

    print()
    print("=" * 80)
    print("BYTE FREQUENCY IN EVENT DATA (section 0, all tracks)")
    print("=" * 80)

    for track in range(8):
        al = track
        if al not in by_al:
            continue
        name = TRACK_NAMES.get(track, f"T{track}")

        # Concatenate all messages for this track
        data = b""
        for m in by_al[al]:
            data += m.decoded_data

        # Skip header (24 bytes) and preamble (4 bytes)
        event_data = data[28:]

        # Remove DC delimiters
        event_bytes = bytes(b for b in event_data if b != 0xDC)

        # Byte frequency
        freq = Counter(event_bytes)
        total = len(event_bytes)

        # Top 10 most common bytes
        top = freq.most_common(10)
        top_str = ", ".join(f"0x{b:02X}({c})" for b, c in top)
        print(f"\n  {name}: {total} event bytes, {len(freq)} unique values")
        print(f"    Top 10: {top_str}")

        # How many bytes have bit 7 set?
        hi_count = sum(1 for b in event_bytes if b & 0x80)
        print(f"    Bit 7 set: {hi_count}/{total} ({hi_count / total * 100:.1f}%)")

        # Bytes in MIDI note range (36-84)
        note_range = sum(1 for b in event_bytes if 36 <= b <= 84)
        print(f"    In drum range (36-84): {note_range}/{total} ({note_range / total * 100:.1f}%)")


def analyze_xor_patterns(syx_path: str):
    """XOR consecutive 7-byte groups within C2 bars to find changing fields."""
    data = concatenate_track_data(syx_path, 0, 4)  # C2

    print()
    print("=" * 80)
    print("C2 BAR EVENT XOR ANALYSIS")
    print("=" * 80)

    # C2 has DC at 42, 84, 126
    # Bar 0: bytes 28-41 (14 bytes after header)
    # Bar 1: bytes 43-83 (41 bytes)
    # Bar 2: bytes 85-125 (41 bytes) — identical to bar 1

    bar1 = data[43:84]
    print(f"Bar 1 ({len(bar1)} bytes):")
    print(f"  {' '.join(f'{b:02X}' for b in bar1)}")

    # The 4 events (after 13-byte header):
    header = bar1[:13]
    events = [bar1[13 + i * 7 : 13 + (i + 1) * 7] for i in range(4)]

    print(f"\n  Bar header (13 bytes): {' '.join(f'{b:02X}' for b in header)}")
    print(f"  In binary:")
    for i, b in enumerate(header):
        print(f"    byte {i:2d}: {b:08b} (0x{b:02X}, dec {b})")

    for i, evt in enumerate(events):
        print(f"\n  Event {i}: {' '.join(f'{b:02X}' for b in evt)}")
        for j, b in enumerate(evt):
            print(f"    byte {j}: {b:08b} (0x{b:02X}, dec {b}, lo7={b & 0x7F})")

    # XOR pairs
    print(f"\n  Event XOR analysis:")
    for i in range(4):
        for j in range(i + 1, 4):
            xor = bytes(a ^ b for a, b in zip(events[i], events[j]))
            diff_bits = sum(bin(b).count("1") for b in xor)
            print(
                f"    E{i} XOR E{j}: {' '.join(f'{b:02X}' for b in xor)} ({diff_bits} bits differ)"
            )

    # Now look at C4/PHR which also has repeating patterns
    data4 = concatenate_track_data(syx_path, 0, 7)  # C4/PHR
    print()
    print("=" * 80)
    print("C4/PHR BAR EVENT XOR ANALYSIS")
    print("=" * 80)

    # C4/PHR has DC at 56, 98, 126
    # Bar 0: bytes 28-55 (28 bytes after header)
    # Bar 1: bytes 57-97 (41 bytes)
    # Bar 2: bytes 99-125 (27 bytes)
    # Tail: byte 127 (1 byte = 00)

    bar0_data = data4[28:56]
    bar1_data = data4[57:98]
    bar2_data = data4[99:126]

    print(f"Bar 0: {len(bar0_data)} bytes")
    print(f"  {' '.join(f'{b:02X}' for b in bar0_data)}")
    print(f"Bar 1: {len(bar1_data)} bytes")
    print(f"  {' '.join(f'{b:02X}' for b in bar1_data)}")
    print(f"Bar 2: {len(bar2_data)} bytes")
    print(f"  {' '.join(f'{b:02X}' for b in bar2_data)}")

    # Bar 0 is 28 bytes = 4 × 7. Let's see if it has the same structure
    print(f"\nBar 0 as 7-byte groups:")
    for i in range(0, len(bar0_data), 7):
        chunk = bar0_data[i : i + 7]
        bit7 = "".join(str((b >> 7) & 1) for b in chunk)
        print(f"  G{i // 7}: {' '.join(f'{b:02X}' for b in chunk)}  b7={bit7}")

    if len(bar1_data) >= 41:
        header1 = bar1_data[:13]
        events1 = [bar1_data[13 + i * 7 : 13 + (i + 1) * 7] for i in range(4)]
        print(f"\nBar 1 header: {' '.join(f'{b:02X}' for b in header1)}")
        for i, evt in enumerate(events1):
            bit7 = "".join(str((b >> 7) & 1) for b in evt)
            print(f"  Event {i}: {' '.join(f'{b:02X}' for b in evt)}  b7={bit7}")

        # XOR C2 events with C4 events
        print(f"\nC2 vs C4 event comparison (bar 1):")
        c2_events = [data[43 + 13 + i * 7 : 43 + 13 + (i + 1) * 7] for i in range(4)]
        for i in range(4):
            xor = bytes(a ^ b for a, b in zip(c2_events[i], events1[i]))
            diff_bits = sum(bin(b).count("1") for b in xor)
            print(f"  C2_E{i}: {' '.join(f'{b:02X}' for b in c2_events[i])}")
            print(f"  C4_E{i}: {' '.join(f'{b:02X}' for b in events1[i])}")
            print(f"   XOR:   {' '.join(f'{b:02X}' for b in xor)} ({diff_bits} bits)")
            print()


def analyze_concatenated_d1_bars(syx_path: str):
    """Analyze D1 with proper multi-message handling."""
    parser = SysExParser()
    messages = parser.parse_file(syx_path)
    style_msgs = [m for m in messages if m.is_style_data]

    by_al = defaultdict(list)
    for m in style_msgs:
        by_al[m.address_low].append(m)

    # For D1, we need to handle message boundaries carefully
    # Each message is independently encoded, so we concatenate decoded data
    al = 0  # D1, section 0
    msgs = by_al[al]

    print()
    print("=" * 80)
    print(f"D1 CONCATENATED ANALYSIS — {len(msgs)} messages")
    print("=" * 80)

    full_data = b""
    for m in msgs:
        full_data += m.decoded_data

    print(f"Total decoded: {len(full_data)} bytes")

    # Header (24 bytes) + preamble (4 bytes) = 28 bytes
    event_data = full_data[28:]
    print(f"Event data: {len(event_data)} bytes")

    # Find all DC
    dc_pos = [i for i, b in enumerate(event_data) if b == 0xDC]
    print(f"DC positions in event data: {dc_pos}")

    # If only 1 DC (based on earlier analysis), split
    if len(dc_pos) == 0:
        print("No DC delimiters — entire event data is one bar or continuous")
        # Look for 0x00 terminator at the end
        trail = event_data[-10:]
        print(f"Last 10 bytes: {' '.join(f'{b:02X}' for b in trail)}")
    elif len(dc_pos) == 1:
        bar0 = event_data[: dc_pos[0]]
        bar1 = event_data[dc_pos[0] + 1 :]
        print(f"Bar 0: {len(bar0)} bytes")
        print(f"Bar 1: {len(bar1)} bytes")

        # Show bar 0 structure
        print(f"\nBar 0 (first 112 bytes):")
        for i in range(0, min(len(bar0), 112), 7):
            chunk = bar0[i : i + 7]
            hex_str = " ".join(f"{b:02X}" for b in chunk)
            bit7 = "".join(str((b >> 7) & 1) for b in chunk)
            print(f"  {i:3d}: {hex_str}  b7={bit7}")

        # Look for repeating patterns in bar 0
        print(f"\nSearching for repeating patterns in bar 0:")
        for period in range(6, 15):
            matches = 0
            total = 0
            for i in range(0, len(bar0) - period, period):
                chunk1 = bar0[i : i + period]
                for j in range(i + period, len(bar0) - period + 1, period):
                    chunk2 = bar0[j : j + period]
                    total += 1
                    if chunk1 == chunk2:
                        matches += 1
            if total > 0 and matches > 0:
                print(f"  Period {period}: {matches} exact pattern repeats")

        # Look for 2-byte patterns (like command bytes)
        print(f"\n2-byte pair frequency (top 15):")
        pairs = Counter()
        for i in range(len(bar0) - 1):
            pair = (bar0[i], bar0[i + 1])
            pairs[pair] += 1
        for pair, count in pairs.most_common(15):
            print(f"  {pair[0]:02X} {pair[1]:02X}: {count}")

        # Look for specific Q7P-like command bytes
        print(f"\nPotential command byte frequency:")
        cmd_bytes = Counter()
        for b in bar0:
            cmd_bytes[b] += 1
        for b, c in cmd_bytes.most_common(15):
            print(f"  0x{b:02X} ({b:3d}): {c}")


if __name__ == "__main__":
    syx_path = sys.argv[1] if len(sys.argv) > 1 else "tests/fixtures/QY70_SGT.syx"
    q7p_path = "tests/fixtures/T01.Q7P"

    analyze_d1_full_stream(syx_path)
    analyze_q7p_events(q7p_path)
    analyze_byte_frequency(syx_path)
    analyze_xor_patterns(syx_path)
    analyze_concatenated_d1_bars(syx_path)
