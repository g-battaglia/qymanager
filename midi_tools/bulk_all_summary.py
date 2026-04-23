#!/usr/bin/env python3
"""Summarize a BULK_ALL .syx file: list populated user-pattern slots.

The QY70 BULK OUT → All dumps ALL user patterns (AM=0x00-0x3F) into one .syx.
`qymanager info` only inspects edit buffer (AM=0x7E), so for a BULK_ALL file
it shows "Active Sections: 0 of 6". This script fills that gap.

Usage:
    uv run python3 midi_tools/bulk_all_summary.py path/to/bulk_all.syx
"""

import argparse
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from qymanager.formats.qy70.sysex_parser import SysExParser


def summarize_bulk(path: Path) -> int:
    p = SysExParser()
    msgs = p.parse_file(str(path))

    # Group by (AH, AM)
    groups: dict[tuple[int, int], list] = defaultdict(list)
    for m in msgs:
        groups[(m.address_high, m.address_mid)].append(m)

    # Separate pattern slots (AH=0x02, AM=0x00-0x3F) from song (AH=0x01) and system (AH=0x03)
    print(f"File: {path}")
    print(f"Total messages: {len(msgs)}")
    print()

    pattern_slots = sorted([(ah, am) for (ah, am) in groups if ah == 0x02 and am < 0x40])
    song_slots = sorted([(ah, am) for (ah, am) in groups if ah == 0x01])
    system_slots = sorted([(ah, am) for (ah, am) in groups if ah == 0x03])
    xg_slots = sorted([(ah, am) for (ah, am) in groups if ah == 0x08])
    edit_buffer = sorted([(ah, am) for (ah, am) in groups if ah == 0x02 and am == 0x7E])

    print(f"═══ Pattern slots populated: {len(pattern_slots)} / 64 ═══")
    if pattern_slots:
        print(f"{'Slot':>4} {'Name':20s} {'Tracks':20s} {'Sections':20s} {'Bytes':>10}")
        print("-" * 82)
        for ah, am in pattern_slots:
            ms = groups[(ah, am)]
            # Collect ALs
            als = sorted({m.address_low for m in ms if m.decoded_data})
            track_als = [al for al in als if al <= 0x2F]
            has_header = 0x7F in als
            tracks = sorted({al % 8 for al in track_als})
            sections = sorted({al // 8 for al in track_als})
            total_bytes = sum(len(m.decoded_data or b"") for m in ms)
            slot_name = f"U{am + 1:02d}" if am < 128 else f"P{am:02X}"
            tracks_str = ",".join(f"{t + 1}" for t in tracks) or "-"
            sections_str = ",".join(str(s + 1) for s in sections) or "-"
            header_tag = "[H]" if has_header else "   "
            print(f"{slot_name:>4} {header_tag}  {tracks_str:20s} {sections_str:20s} {total_bytes:>10}")

    if edit_buffer:
        print(f"\n═══ Edit buffer (AM=0x7E): {len(edit_buffer)} group(s) ═══")
        for ah, am in edit_buffer:
            ms = groups[(ah, am)]
            als = sorted({m.address_low for m in ms if m.decoded_data})
            print(f"  AM=7E ALs: {[hex(a) for a in als]} ({len(ms)} msgs)")

    if song_slots:
        print(f"\n═══ Song data (AH=0x01): {len(song_slots)} group(s) ═══")
        for ah, am in song_slots:
            ms = groups[(ah, am)]
            total = sum(len(m.decoded_data or b"") for m in ms)
            print(f"  AM={am:02X}: {len(ms)} msgs, {total} bytes")

    if system_slots:
        print(f"\n═══ System data (AH=0x03): {len(system_slots)} group(s) ═══")
        for ah, am in system_slots:
            ms = groups[(ah, am)]
            for m in ms:
                d = m.decoded_data or b""
                print(f"  AM={am:02X} AL={m.address_low:02X}: {len(d)} bytes: {d.hex()[:64]}...")

    if xg_slots:
        print(f"\n═══ XG data (AH=0x08): {len(xg_slots)} group(s) ═══")
        for ah, am in xg_slots:
            ms = groups[(ah, am)]
            print(f"  AM={am:02X}: {len(ms)} msgs")

    print()
    print(f"Summary:")
    print(f"  - User pattern slots with data: {len(pattern_slots)}")
    print(f"  - Song slots: {len(song_slots)}")
    print(f"  - Edit buffer: {'present' if edit_buffer else 'absent'}")
    print(f"  - System setup: {'present' if system_slots else 'absent'}")
    print(f"  - XG Multi Part: {'present (Model 4C)' if xg_slots else 'absent — voice info limited'}")

    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("file", type=Path, help="BULK_ALL .syx file")
    args = ap.parse_args()
    if not args.file.exists():
        print(f"ERROR: file not found: {args.file}", file=sys.stderr)
        return 1
    return summarize_bulk(args.file)


if __name__ == "__main__":
    sys.exit(main())
