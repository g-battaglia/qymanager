#!/usr/bin/env python3
"""
Compare Summer (user) vs SGT (factory) RHY1 structural layout.

Summer is a 4-bar user pattern (single section). SGT is a 6-section factory
style with 692B shared prefix. Hypothesis:
  - User patterns: direct events, no codebook
  - Factory styles: 692B codebook + section overrides

Validate by diffing byte-level structure.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from qymanager.formats.qy70.sysex_parser import SysExParser


def extract_rhy1_by_section(syx_path: Path) -> dict[int, bytes]:
    parser = SysExParser()
    msgs = parser.parse_file(str(syx_path))
    data = {}
    for m in msgs:
        if not m.is_style_data or not m.decoded_data:
            continue
        al = m.address_low
        if al % 8 == 0:
            sec = al // 8
            data.setdefault(sec, b"")
            data[sec] += m.decoded_data
    return data


def rot_right(val, shift, width=56):
    shift %= width
    return ((val >> shift) | (val << (width - shift))) & ((1 << width) - 1)


def find_bar_headers(data: bytes, start: int = 28) -> list[int]:
    """Find 13B bar headers — typically start with 0x1A or 0xDE."""
    positions = []
    i = start
    while i < len(data) - 13:
        # Bar header markers
        if data[i] in (0x1A, 0xDE, 0x98):
            # Heuristic: next 12 bytes form a consistent header pattern
            positions.append(i)
            i += 13  # jump over header
        else:
            i += 1
    return positions


def decode_event(evt_bytes: bytes, idx: int) -> dict:
    """Decode event with cumulative R=9×(i+1)."""
    val = int.from_bytes(evt_bytes, "big")
    r = (9 * (idx + 1)) % 56
    derot = rot_right(val, r)
    f0 = (derot >> 47) & 0x1FF
    f5 = (derot >> 2) & 0x1FF
    rem = derot & 0x3
    note = f0 & 0x7F
    bit7 = (f0 >> 7) & 1
    bit8 = (f0 >> 8) & 1
    vel_code = (bit8 << 3) | (bit7 << 2) | rem
    return {
        "hex": evt_bytes.hex(),
        "R": r,
        "note": note,
        "vel_code": vel_code,
        "gate": f5,
        "valid": 13 <= note <= 87,
    }


def decode_segment(data: bytes, seg_start: int, seg_end: int) -> list[dict]:
    """Decode events in a segment with per-segment index reset."""
    results = []
    # Skip 13B bar header
    event_start = seg_start + 13
    idx = 0
    while event_start + 7 <= seg_end:
        evt = data[event_start:event_start + 7]
        r = decode_event(evt, idx)
        r["offset"] = event_start
        results.append(r)
        event_start += 7
        idx += 1
    return results


def main():
    summer_path = Path(__file__).parent / "captured" / "ground_truth_style.syx"
    sgt_path = Path(__file__).parent.parent / "tests" / "fixtures" / "QY70_SGT.syx"

    print("=" * 70)
    print("Summer (user) — ground_truth_style.syx")
    print("=" * 70)
    summer_data = extract_rhy1_by_section(summer_path)
    for sec, d in summer_data.items():
        print(f"\nSec{sec}: {len(d)}B")
        # First 80 bytes
        for row in range(0, min(80, len(d)), 16):
            print(f"  {row:4d}: {d[row:row+16].hex(' ')}")

        # Find bar delimiters 0xDC / 0x9E
        bar_delims = [i for i, b in enumerate(d) if b == 0xDC]
        sub_delims = [i for i, b in enumerate(d) if b == 0x9E]
        print(f"  0xDC at: {bar_delims[:15]}")
        print(f"  0x9E at: {sub_delims[:15]}")
        # Find bar header candidates
        bh_pos = find_bar_headers(d, start=28)
        print(f"  Bar header candidates (0x1A/0xDE/0x98): {bh_pos}")

    print("\n" + "=" * 70)
    print("SGT (factory) — QY70_SGT.syx")
    print("=" * 70)
    sgt_data = extract_rhy1_by_section(sgt_path)
    for sec in sorted(sgt_data.keys())[:2]:  # first 2 sections only
        d = sgt_data[sec]
        print(f"\nSec{sec}: {len(d)}B")
        for row in range(0, min(80, len(d)), 16):
            print(f"  {row:4d}: {d[row:row+16].hex(' ')}")
        bar_delims = [i for i, b in enumerate(d) if b == 0xDC]
        sub_delims = [i for i, b in enumerate(d) if b == 0x9E]
        print(f"  0xDC at: {bar_delims[:15]}")
        print(f"  0x9E at: {sub_delims[:15]}")
        bh_pos = find_bar_headers(d, start=28)
        print(f"  Bar header candidates (0x1A/0xDE/0x98): {bh_pos[:20]}")

    # Compare first 28 bytes (track header + preamble)
    summer_head = summer_data[0][:28]
    sgt_head = sgt_data[0][:28]
    print("\n" + "=" * 70)
    print("Track header + preamble (first 28B) comparison")
    print("=" * 70)
    print(f"Summer: {summer_head.hex()}")
    print(f"SGT:    {sgt_head.hex()}")
    diff = sum(1 for i in range(28) if summer_head[i] != sgt_head[i])
    print(f"Diff bytes: {diff}/28")
    print(f"  Byte-by-byte:")
    for i in range(28):
        marker = " " if summer_head[i] == sgt_head[i] else "*"
        print(f"    [{i:2d}] {summer_head[i]:02x} {sgt_head[i]:02x} {marker}")

    # Key question: does Summer have an analog of the 692B codebook?
    # Summer is 384B total. 384 - 28 = 356B of data.
    # If user patterns don't have a codebook, then all 356B is event+bar data.
    print("\n" + "=" * 70)
    print("Summer event decoding (per-segment R)")
    print("=" * 70)
    summer_sec0 = summer_data[0]
    # Find segments by 0xDC delimiters
    bar_delims = [i for i, b in enumerate(summer_sec0) if b == 0xDC]
    print(f"Summer bar delimiters: {bar_delims}")

    # Assume segments = (preamble, bar_header, events, DC)
    prev = 28  # after preamble
    seg_idx = 0
    for dc in bar_delims:
        print(f"\nSegment {seg_idx}: bytes {prev}-{dc} ({dc - prev}B)")
        if dc - prev < 13:
            print("  too short for bar header + events")
        else:
            # Skip bar header (13B), decode remaining as events
            bh = summer_sec0[prev:prev + 13]
            print(f"  Bar header (13B): {bh.hex()}")
            events_region = summer_sec0[prev + 13:dc]
            print(f"  Events region ({len(events_region)}B): {events_region.hex()}")
            n = len(events_region) // 7
            trail = len(events_region) % 7
            if trail:
                print(f"  Trailing {trail}B: {events_region[-trail:].hex()}")
                events_region = events_region[:-trail]
            for i in range(n):
                evt = events_region[i * 7:(i + 1) * 7]
                r = decode_event(evt, i)
                status = "✓" if r["valid"] else "✗"
                print(f"    e{i}: {evt.hex()} R={r['R']} → note={r['note']} "
                      f"vel_code={r['vel_code']} gate={r['gate']} {status}")
        prev = dc + 1
        seg_idx += 1


if __name__ == "__main__":
    main()
