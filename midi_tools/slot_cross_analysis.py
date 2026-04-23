#!/usr/bin/env python3
"""
Cross-slot structural analysis of 13 extracted user patterns.

For each slot:
  - Parse SysEx bulk dump messages
  - Extract per-track body bytes (AL = section*8 + track)
  - Identify preamble encoding per track
  - Count DC delimiters (bar boundaries)
  - Sum decoded bytes

Then cross-slot:
  - Compare track header bytes (first 28B) across slots for SAME track
  - Find invariant byte positions (structural) vs variable (content)
  - Byte frequency per track type
"""

import sys
from collections import defaultdict, Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from qymanager.formats.qy70.sysex_parser import SysExParser

SLOTS_DIR = Path(__file__).parent.parent / "data" / "stored_slots"

TRACK_NAMES = {0: "RHY1", 1: "RHY2", 2: "PAD", 3: "BASS",
               4: "CHD1", 5: "CHD2", 6: "PHR1", 7: "PHR2"}


def parse_slot(path: Path) -> dict:
    parser = SysExParser()
    msgs = parser.parse_file(str(path))
    # Accept AH=0x02 AM=0x00-0x1F (user pattern slots) + 0x7E (edit buffer)
    style_msgs = [m for m in msgs
                  if m.address_high == 0x02 and
                  (m.address_mid <= 0x1F or m.address_mid == 0x7E)
                  and m.decoded_data]

    tracks = defaultdict(bytes)
    header_data = b""
    for m in style_msgs:
        al = m.address_low
        if al == 0x7F:
            header_data += m.decoded_data
        elif al <= 0x2F:
            sec = al // 8
            trk = al % 8
            tracks[(sec, trk)] += m.decoded_data

    result = {
        "path": path.name,
        "total_msgs": len(style_msgs),
        "header_bytes": len(header_data),
        "header_first_16": header_data[:16].hex() if header_data else "",
        "sections": sorted({k[0] for k in tracks.keys()}),
        "tracks_per_section": defaultdict(list),
        "track_details": {},
    }

    for (sec, trk), data in sorted(tracks.items()):
        result["tracks_per_section"][sec].append(trk)
        track_info = {
            "bytes": len(data),
            "header_16": data[:16].hex() if len(data) >= 16 else data.hex(),
            "preamble": data[24:28].hex() if len(data) >= 28 else "",
            "track_header_bytes_14_23": data[14:24].hex() if len(data) >= 24 else "",
            "dc_count": data[28:].count(b"\xdc") if len(data) > 28 else 0,
            "sub_count": data[28:].count(b"\x9e") if len(data) > 28 else 0,
        }
        result["track_details"][f"sec{sec}_trk{trk}"] = track_info

    return result


def main():
    slot_files = sorted(SLOTS_DIR.glob("slot_U*.syx"))
    print(f"Analyzing {len(slot_files)} slots\n")

    all_slots = []
    for sf in slot_files:
        info = parse_slot(sf)
        all_slots.append(info)
        sections = info["sections"]
        n_tracks_total = sum(len(v) for v in info["tracks_per_section"].values())
        print(f"{sf.name:35s}: {info['total_msgs']:>3d} msgs, "
              f"sections={sections}, total_tracks={n_tracks_total}, "
              f"header={info['header_bytes']}B")

    # Cross-slot per-track header comparison (first section only)
    print(f"\n═══ Cross-slot track[14:24] (voice info) by track ═══")
    per_track = defaultdict(list)
    for info in all_slots:
        for trk in range(8):
            key = f"sec0_trk{trk}"
            if key in info["track_details"]:
                per_track[trk].append((info["path"], info["track_details"][key]))

    for trk in range(8):
        print(f"\n  Track {trk} ({TRACK_NAMES[trk]}):")
        entries = per_track[trk]
        if not entries:
            print(f"    (no data)")
            continue
        bytes_14_23_set = {ti["track_header_bytes_14_23"] for _, ti in entries}
        print(f"    Unique byte[14:24] patterns across {len(entries)} slots: {len(bytes_14_23_set)}")
        for path, ti in entries[:8]:
            print(f"      {path:30s}: B[14-23]={ti['track_header_bytes_14_23']} "
                  f"preamble={ti['preamble']} dc={ti['dc_count']}")
        if len(entries) > 8:
            print(f"      ... +{len(entries)-8} more")

    # Preamble distribution per track type
    print(f"\n═══ Preamble distribution per track ═══")
    for trk in range(8):
        preamble_counter = Counter(
            ti["preamble"] for _, ti in per_track[trk]
        )
        print(f"  Track {trk} ({TRACK_NAMES[trk]}): {dict(preamble_counter.most_common())}")

    # Bytes[14:16] "voice" field analysis — might encode (bank, program) compact
    print(f"\n═══ Bytes[14:16] per track (candidate voice encoding) ═══")
    for trk in range(8):
        pairs = Counter(
            ti["track_header_bytes_14_23"][:4]  # hex string first 2 bytes
            for _, ti in per_track[trk]
        )
        print(f"  Track {trk}: {dict(pairs.most_common(6))}")


if __name__ == "__main__":
    main()
