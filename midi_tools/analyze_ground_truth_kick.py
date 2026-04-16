#!/usr/bin/env python3
"""
Analyze the ground truth Pattern C capture: solo kick (note 36) on beat 1, 4 bars.

This is the simplest possible drum pattern. By examining how the QY70 encodes it,
we can isolate the encoding rules for dense drum data without the complexity of
multiple instruments or groove humanization.

Expected content:
  - RHY1: 1 event per bar (kick on beat 1), 4 bars
  - All other tracks: empty
  - Tempo: 120 BPM
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qymanager.formats.qy70.sysex_parser import SysExParser


def analyze_capture(syx_path):
    parser = SysExParser()
    messages = parser.parse_file(syx_path)

    print(f"File: {syx_path}")
    print(f"Total messages parsed: {len(messages)}")
    print()

    # De-duplicate by raw content (QY70 sends full pattern for each track request)
    seen_raw = set()
    unique_msgs = []
    for m in messages:
        if not m.is_bulk_dump:
            continue
        if m.address_high != 0x02:
            continue
        key = m.raw.hex() if m.raw else m.data.hex()
        if key not in seen_raw:
            seen_raw.add(key)
            unique_msgs.append(m)

    print(f"Unique bulk dump messages (AH=0x02): {len(unique_msgs)}")

    # Group by track (AL)
    tracks = {}
    for m in unique_msgs:
        al = m.address_low
        tracks.setdefault(al, []).append(m)

    TRACK_NAMES = {
        0: "RHY1", 1: "RHY2", 2: "BASS", 3: "CHD1",
        4: "CHD2", 5: "PHR1", 6: "PHR2", 7: "PHR3",
        0x7F: "HEADER"
    }

    print("\n" + "=" * 70)
    print("TRACK SUMMARY")
    print("=" * 70)
    for al in sorted(tracks.keys()):
        name = TRACK_NAMES.get(al, f"UNK_{al:02X}")
        msgs = tracks[al]
        total_decoded = sum(len(m.decoded_data) for m in msgs if m.decoded_data)
        total_raw = sum(len(m.raw) for m in msgs if m.raw)
        print(f"  AL=0x{al:02X} ({name:6s}): {len(msgs)} msgs, "
              f"{total_decoded} decoded bytes, {total_raw} raw bytes")

    # Analyze each track in detail
    for al in sorted(tracks.keys()):
        name = TRACK_NAMES.get(al, f"UNK_{al:02X}")
        msgs = tracks[al]

        print(f"\n{'=' * 70}")
        print(f"TRACK: {name} (AL=0x{al:02X})")
        print(f"{'=' * 70}")

        # Concatenate decoded data
        decoded = b""
        for m in msgs:
            if m.decoded_data is not None:
                decoded += m.decoded_data

        if not decoded:
            print("  (no decoded data)")
            continue

        print(f"  Total decoded: {len(decoded)} bytes")

        # Show first 64 bytes as hex
        print(f"\n  First 64 bytes (hex):")
        for row in range(min(4, (len(decoded) + 15) // 16)):
            offset = row * 16
            hex_str = " ".join(f"{b:02X}" for b in decoded[offset:offset+16])
            ascii_str = "".join(
                chr(b) if 32 <= b < 127 else "." for b in decoded[offset:offset+16]
            )
            print(f"    {offset:04X}: {hex_str:<48s}  {ascii_str}")

        if al == 0x7F:
            # Header analysis
            analyze_header(decoded)
        elif al < 8:
            # Track data analysis
            analyze_track(decoded, name, al)


def analyze_header(data):
    """Analyze header track (AL=0x7F)."""
    print(f"\n  --- Header Analysis ---")
    print(f"  Total bytes: {len(data)}")

    # First message usually contains tempo and global settings
    if len(data) >= 10:
        print(f"\n  First 10 bytes: {' '.join(f'{b:02X}' for b in data[:10])}")

    # Look for pattern name (usually ASCII near the end or at known offset)
    # Try to find ASCII strings
    ascii_runs = []
    current = ""
    start = 0
    for i, b in enumerate(data):
        if 32 <= b < 127:
            if not current:
                start = i
            current += chr(b)
        else:
            if len(current) >= 3:
                ascii_runs.append((start, current))
            current = ""
    if len(current) >= 3:
        ascii_runs.append((start, current))

    if ascii_runs:
        print(f"\n  ASCII strings found:")
        for offset, s in ascii_runs:
            print(f"    @0x{offset:03X}: '{s}'")


def analyze_track(data, name, al):
    """Analyze a track's data looking for events and structure."""
    print(f"\n  --- Track Structure ---")

    if len(data) < 28:
        print(f"  Too short ({len(data)} bytes) - likely empty")
        # Show all bytes anyway
        print(f"  All bytes: {data.hex()}")
        return

    # First 24 bytes = metadata (preamble, etc.)
    metadata = data[:24]
    preamble = data[24:28]
    event_area = data[28:]

    print(f"  Metadata (24 bytes): {metadata.hex()}")
    print(f"  Preamble (4 bytes): {preamble.hex()}")
    print(f"  Event area: {len(event_area)} bytes")

    # Show preamble as hex
    print(f"\n  Preamble decoded: 0x{int.from_bytes(preamble, 'big'):08X}")

    if not event_area:
        print("  (no events)")
        return

    # Find delimiters (0xDC = segment end, 0x9E = track end)
    print(f"\n  --- Segment Analysis ---")
    segments = []
    prev = 0
    for i, b in enumerate(event_area):
        if b in (0xDC, 0x9E):
            seg = event_area[prev:i]
            delim = "DC" if b == 0xDC else "9E"
            segments.append((seg, delim))
            prev = i + 1

    if prev < len(event_area):
        seg = event_area[prev:]
        if seg:
            segments.append((seg, "END"))

    print(f"  Found {len(segments)} segments")

    for si, (seg, delim) in enumerate(segments):
        print(f"\n  Segment {si} ({len(seg)} bytes, delim=0x{delim}):")
        if not seg:
            print("    (empty)")
            continue

        # Show raw hex
        hex_str = seg.hex()
        print(f"    Raw: {hex_str}")

        if len(seg) >= 13:
            # First 13 bytes = bar header
            header = seg[:13]
            events_raw = seg[13:]

            print(f"    Bar header (13B): {header.hex()}")

            # Decode header as 9-bit fields
            hval = int.from_bytes(header, "big")
            hfields = []
            for i in range(11):
                shift = 104 - 9 * (i + 1)
                if shift >= 0:
                    hfields.append((hval >> shift) & 0x1FF)
            print(f"    Header 9-bit fields: {hfields[:6]}")
            print(f"    Header fields hi7:   {[f & 0x7F for f in hfields[:6]]}")

            if events_raw:
                n_events = len(events_raw) // 7
                trailing = len(events_raw) % 7
                print(f"    Events: {n_events} × 7-byte + {trailing} trailing")

                for ei in range(n_events):
                    evt = events_raw[ei*7:(ei+1)*7]
                    val = int.from_bytes(evt, "big")
                    print(f"      e{ei}: {evt.hex()} = 0x{val:014X} = {val}")

                    # Try all rotations and show which ones give note 36 (kick)
                    from midi_tools.event_decoder import rot_right, extract_9bit
                    kick_rs = []
                    for r in range(56):
                        derot = rot_right(val, r)
                        f0 = extract_9bit(derot, 0)
                        note = f0 & 0x7F
                        if note == 36:
                            kick_rs.append(r)

                    if kick_rs:
                        print(f"        note=36 (kick) at R={kick_rs}")

                        # Show full field decode at known R=9
                        for r in [9] + [r2 for r2 in kick_rs if r2 != 9][:2]:
                            derot = rot_right(val, r)
                            fields = [extract_9bit(derot, i) for i in range(6)]
                            rem = derot & 0x3
                            print(f"        R={r:2d}: F0={fields[0]:3d}({fields[0]&0x7F:3d}) "
                                  f"F1={fields[1]:3d} F2={fields[2]:3d} "
                                  f"F3={fields[3]:3d} F4={fields[4]:3d} "
                                  f"F5={fields[5]:3d} rem={rem}")
                    else:
                        print(f"        note=36 NOT found at any R!")
                        # Show what notes ARE possible
                        note_set = set()
                        for r in range(56):
                            derot = rot_right(val, r)
                            f0 = extract_9bit(derot, 0)
                            note_set.add(f0 & 0x7F)
                        print(f"        Possible notes: {sorted(note_set)}")

                if trailing:
                    trail = events_raw[n_events*7:]
                    print(f"      Trailing: {trail.hex()}")
        else:
            print(f"    (short segment, raw hex shown above)")

    # Also check for zero-filled regions
    zero_count = sum(1 for b in data if b == 0)
    print(f"\n  Zero bytes: {zero_count}/{len(data)} ({100*zero_count/len(data):.1f}%)")


if __name__ == "__main__":
    path = "midi_tools/captured/ground_truth_C_kick.syx"
    if len(sys.argv) > 1:
        path = sys.argv[1]
    analyze_capture(path)
