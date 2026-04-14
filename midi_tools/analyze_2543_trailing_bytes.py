#!/usr/bin/env python3
"""Deep analysis of trailing bytes in 2543 segments.

~50% of segments have 1-3 bytes between the last 7-byte event and the delimiter.
The pattern `d878` appears twice. Are these:
  A) A footer/CRC
  B) The start of a partial event
  C) Segment-level parameters (volume, transpose, etc.)
  D) Just the end of the event stream, not 7-byte aligned

Analyze trailing bytes across ALL tracks and ALL sections.
"""

import sys, os
from collections import Counter, defaultdict
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from qymanager.formats.qy70.sysex_parser import SysExParser


def get_all_segments(syx_path):
    """Get all segments from all sections/tracks."""
    parser = SysExParser()
    messages = parser.parse_file(syx_path)

    tracks = defaultdict(bytes)
    for m in messages:
        if m.is_style_data and m.decoded_data is not None:
            al = m.address_low
            tracks[al] += m.decoded_data

    results = []
    for al, data in sorted(tracks.items()):
        section = al // 8
        track = al % 8
        if len(data) < 28:
            continue
        event_data = data[28:]
        delim_pos = sorted(i for i, b in enumerate(event_data) if b in (0xDC, 0x9E))
        prev = 0
        for dp in delim_pos:
            seg = event_data[prev:dp]
            delim = event_data[dp]
            results.append((section, track, seg, delim))
            prev = dp + 1
        last_seg = event_data[prev:]
        results.append((section, track, last_seg, None))

    return results


def main():
    base = os.path.dirname(os.path.abspath(__file__))
    syx = os.path.join(base, "captured", "ground_truth_style.syx")
    all_segments = get_all_segments(syx)

    track_names = ["RHY1", "RHY2", "BASS", "CHD1", "CHD2", "PAD", "PHR1", "PHR2"]

    # ============================================================
    # 1. Catalog ALL trailing bytes
    # ============================================================
    print(f"{'='*80}")
    print(f"  ALL TRAILING BYTES (across all tracks/sections)")
    print(f"{'='*80}")

    trailing_catalog = Counter()
    trailing_by_track = defaultdict(list)
    segments_with_trail = 0
    segments_total = 0

    for section, track, seg, delim in all_segments:
        if len(seg) < 13:
            continue
        segments_total += 1
        trail = (len(seg) - 13) % 7
        if trail > 0:
            segments_with_trail += 1
            trail_bytes = seg[-trail:]
            trail_hex = trail_bytes.hex()
            trailing_catalog[trail_hex] += 1
            trailing_by_track[track].append(
                (section, len(seg), trail, trail_hex, delim))

    print(f"\n  Total segments with events: {segments_total}")
    print(f"  Segments with trailing bytes: {segments_with_trail}"
          f" ({100*segments_with_trail/segments_total:.0f}%)")

    print(f"\n  Trailing byte patterns (sorted by frequency):")
    for pattern, count in trailing_catalog.most_common():
        trail_len = len(pattern) // 2
        print(f"    {pattern:>10} ({trail_len}B) × {count}")

    # ============================================================
    # 2. Per-track trailing bytes
    # ============================================================
    print(f"\n{'='*80}")
    print(f"  TRAILING BYTES PER TRACK")
    print(f"{'='*80}")

    for track in range(8):
        entries = trailing_by_track.get(track, [])
        if not entries:
            continue
        print(f"\n  {track_names[track]}:")
        for section, seg_len, trail, trail_hex, delim in entries:
            section_names = ["MainA", "MainB", "FillAB", "Intro", "FillBA", "Ending"]
            sname = section_names[section] if section < len(section_names) else f"S{section}"
            dname = f"0x{delim:02X}" if delim is not None else "END"
            print(f"    {sname:>8} | seg={seg_len:>3}B | trail={trail}B:"
                  f" {trail_hex} | delim={dname}")

    # ============================================================
    # 3. Check if trailing bytes are related to event count
    # ============================================================
    print(f"\n{'='*80}")
    print(f"  TRAILING BYTES vs EVENT COUNT")
    print(f"{'='*80}")

    print(f"\n  {'Track':>5} {'Section':>8} {'SegLen':>6} {'Events':>6} {'Trail':>5}"
          f" {'TrailHex':>12} {'FirstHdr':>6}")

    for section, track, seg, delim in all_segments:
        if len(seg) < 20:
            continue
        trail = (len(seg) - 13) % 7
        nevts = (len(seg) - 13) // 7
        if trail > 0:
            trail_hex = seg[-trail:].hex()
            first_hdr = f"0x{seg[0]:02X}"
            section_names = ["MainA", "MainB", "FillAB", "Intro", "FillBA", "Ending"]
            sname = section_names[section] if section < len(section_names) else f"S{section}"
            print(f"  {track_names[track]:>5} {sname:>8} {len(seg):>6}"
                  f" {nevts:>6} {trail:>5}"
                  f" {trail_hex:>12} {first_hdr:>6}")

    # ============================================================
    # 4. Are trailing bytes a function of the LAST event?
    # ============================================================
    print(f"\n{'='*80}")
    print(f"  CORRELATION: trailing bytes vs last event bytes")
    print(f"{'='*80}")

    for section, track, seg, delim in all_segments:
        if len(seg) < 20:
            continue
        trail = (len(seg) - 13) % 7
        if trail == 0:
            continue
        nevts = (len(seg) - 13) // 7
        trail_bytes = seg[-trail:]
        last_event = seg[13 + (nevts - 1) * 7: 13 + nevts * 7]
        # Check if trailing bytes match end of last event
        if last_event[-trail:] == trail_bytes:
            match = "MATCH end of last event!"
        elif seg[13:13+trail] == trail_bytes:
            match = "MATCH start of first event area!"
        else:
            match = ""

        section_names = ["MainA", "MainB", "FillAB", "Intro", "FillBA", "Ending"]
        sname = section_names[section] if section < len(section_names) else f"S{section}"
        print(f"  {track_names[track]:>5} {sname:>8}:"
              f" trail={trail_bytes.hex()}"
              f"  last_evt={last_event.hex()}"
              f"  {match}")

    # ============================================================
    # 5. What if trailing bytes ARE the first bytes of next event?
    # ============================================================
    print(f"\n{'='*80}")
    print(f"  CROSS-SEGMENT: trailing bytes + start of next segment")
    print(f"{'='*80}")

    # Build ordered list of segments per track
    by_track_section = defaultdict(list)
    for section, track, seg, delim in all_segments:
        by_track_section[(section, track)].append((seg, delim))

    for (section, track), segs_list in sorted(by_track_section.items()):
        for i in range(len(segs_list) - 1):
            seg, delim = segs_list[i]
            next_seg, _ = segs_list[i + 1]
            if len(seg) < 13 or len(next_seg) < 7:
                continue
            trail = (len(seg) - 13) % 7
            if trail == 0:
                continue

            trail_bytes = seg[-trail:]
            next_start = next_seg[:7 - trail]  # bytes needed to complete 7
            combined = trail_bytes + next_start
            if len(combined) == 7:
                # Decode this "combined event"
                from analyze_2543_mixed_rotation import decode
                note, vel, gate, tick, vc, f0 = decode(combined, 9)  # try R=9
                valid = "✓" if 13 <= note <= 87 else "✗"

                section_names = ["MainA", "MainB", "FillAB", "Intro",
                                 "FillBA", "Ending"]
                sname = section_names[section] if section < len(section_names) else f"S{section}"
                print(f"  {track_names[track]:>5} {sname:>8} seg→seg+1:"
                      f" trail={trail_bytes.hex()} + next={next_start.hex()}"
                      f" → note={note} {valid}")

    # ============================================================
    # 6. RHY1 specific: raw hex dump of segments with trailing
    # ============================================================
    print(f"\n{'='*80}")
    print(f"  RHY1 RAW HEX DUMP (segments with trailing bytes)")
    print(f"{'='*80}")

    for section, track, seg, delim in all_segments:
        if track != 0 or section != 0:
            continue
        if len(seg) < 20:
            continue
        trail = (len(seg) - 13) % 7
        if trail == 0:
            continue

        nevts = (len(seg) - 13) // 7
        print(f"\n  Segment ({len(seg)} bytes, {nevts} events, {trail} trailing):")
        # Header
        print(f"    Header:  {seg[:13].hex()}")
        # Events
        for i in range(nevts):
            evt = seg[13 + i * 7: 13 + (i + 1) * 7]
            print(f"    Event {i}: {evt.hex()}")
        # Trailing
        trail_start = 13 + nevts * 7
        print(f"    Trail:   {seg[trail_start:].hex()}")
        # Delimiter
        dname = f"0x{delim:02X}" if delim is not None else "END"
        print(f"    Delim:   {dname}")


if __name__ == "__main__":
    main()
