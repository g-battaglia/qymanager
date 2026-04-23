#!/usr/bin/env python3
"""
Analyze track header bytes[14:24] across 13 slots to isolate voice encoding.

For each (track_type, byte_position), count distinct values across slots.
Bytes with few distinct values (per track) = structural/config.
Bytes with many distinct values = per-pattern voice/mix settings.

Also verify U10+U11 are paired halves (sections 0-2 + 3-5).
"""

import sys
from collections import defaultdict, Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from qymanager.formats.qy70.sysex_parser import SysExParser

SLOTS = Path(__file__).parent.parent / "data" / "stored_slots"
TRACK_NAMES = {0: "RHY1", 1: "RHY2", 2: "PAD", 3: "BASS",
               4: "CHD1", 5: "CHD2", 6: "PHR1", 7: "PHR2"}


def parse(path):
    parser = SysExParser()
    msgs = parser.parse_file(str(path))
    return [m for m in msgs
            if m.address_high == 0x02 and
            (m.address_mid <= 0x1F or m.address_mid == 0x7E)
            and m.decoded_data]


def build_tracks(msgs):
    tracks = defaultdict(bytes)
    for m in msgs:
        al = m.address_low
        if al == 0x7F:
            continue
        sec = al // 8
        trk = al % 8
        tracks[(sec, trk)] += m.decoded_data
    return dict(tracks)


def main():
    # Load all slots
    slot_data = {}
    for f in sorted(SLOTS.iterdir()):
        if f.name.startswith(("._", "edit")):
            continue
        if not f.name.startswith("slot_"):
            continue
        slot_data[f.name] = build_tracks(parse(f))

    print(f"Loaded {len(slot_data)} slots")

    # Per (sec=0, track_idx), bytes[14:24] per-position distinct values
    print(f"\n═══ Track header bytes[14:24] per-position entropy ═══")

    for trk_idx in range(8):
        rows = []
        for slot, tracks in slot_data.items():
            data = tracks.get((0, trk_idx))
            if not data or len(data) < 28:
                continue
            rows.append((slot, data[14:24], data[24:28]))
        if not rows:
            continue
        print(f"\n  Track {trk_idx} ({TRACK_NAMES[trk_idx]}) — {len(rows)} slots")

        # Count distinct per byte position
        n_rows = len(rows)
        distinct_per_pos = [len({row[1][i] for row in rows}) for i in range(10)]
        print(f"    Byte position:  14 15 16 17 18 19 20 21 22 23")
        print(f"    Distinct vals:  " + " ".join(f"{n:>2d}" for n in distinct_per_pos))

        # Show value freq per position
        for pos in range(10):
            vals = Counter(row[1][pos] for row in rows)
            if len(vals) > 1:
                top = ", ".join(f"0x{v:02x}:{c}" for v, c in vals.most_common(5))
                print(f"    B[{14+pos}]: {top}")

    # Compare U10 (sections 0-2) + U11 (sections 3-5) — is this a unified style?
    print(f"\n═══ U10 + U11 paired-style test ═══")
    u10 = slot_data.get("slot_U10_am09.syx", {})
    u11 = slot_data.get("slot_U11_am0a.syx", {})
    u10_secs = sorted({k[0] for k in u10.keys()})
    u11_secs = sorted({k[0] for k in u11.keys()})
    print(f"  U10 sections: {u10_secs}")
    print(f"  U11 sections: {u11_secs}")
    # Track 0 first 28B of U10 sec 0 vs U11 sec 3
    if (0, 0) in u10 and (3, 0) in u11:
        u10_t0 = u10[(0, 0)][:28]
        u11_t0 = u11[(3, 0)][:28]
        match = sum(1 for a, b in zip(u10_t0, u11_t0) if a == b)
        print(f"  U10 sec0/trk0 vs U11 sec3/trk0 first 28B: {match}/28 match")
        if match >= 20:
            print(f"  → LIKELY PAIRED HALVES of same style")

    # Preamble distribution per track type
    print(f"\n═══ Preamble distribution per track type ═══")
    preamble_by_track = defaultdict(Counter)
    for slot, tracks in slot_data.items():
        for (sec, trk), data in tracks.items():
            if len(data) < 28:
                continue
            pre = data[24:28].hex()
            preamble_by_track[trk][pre] += 1

    for trk in range(8):
        if preamble_by_track[trk]:
            total = sum(preamble_by_track[trk].values())
            top = ", ".join(f"{p}:{c}" for p, c in preamble_by_track[trk].most_common(5))
            print(f"  Track {trk} ({TRACK_NAMES[trk]}): total={total}, {top}")


if __name__ == "__main__":
    main()
