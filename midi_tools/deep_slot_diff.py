#!/usr/bin/env python3
"""
Deep byte-level diff across 13 slots.

For each pair of slots with SAME TRACK, diff their bitstream bytes
to identify event encoding patterns.

Focus: tracks with compatible preamble (same encoding scheme).
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
    p = SysExParser()
    msgs = p.parse_file(str(path))
    tracks = defaultdict(bytes)
    for m in msgs:
        if not (m.address_high == 0x02 and
                (m.address_mid <= 0x1F or m.address_mid == 0x7E)
                and m.decoded_data):
            continue
        al = m.address_low
        if al == 0x7F:
            continue
        sec = al // 8
        trk = al % 8
        tracks[(sec, trk)] += m.decoded_data
    return dict(tracks)


def find_event_boundaries(data: bytes) -> list:
    """Find segment boundaries (DC delimiters)."""
    body = data[28:]
    positions = [i + 28 for i, b in enumerate(body) if b in (0xDC, 0x9E)]
    return positions


def main():
    slot_data = {}
    for f in sorted(SLOTS.iterdir()):
        if f.name.startswith(("._", "edit")):
            continue
        if not f.name.startswith("slot_"):
            continue
        slot_data[f.name] = parse(f)

    # Group slots by track preamble
    print("═══ Track 0 (RHY1) cross-slot body analysis ═══")
    # Get all slots' RHY1 sec0 data
    rhy1_by_slot = {}
    for slot, tracks in slot_data.items():
        data = tracks.get((0, 0))
        if data and len(data) > 28:
            preamble = data[24:28].hex()
            rhy1_by_slot[slot] = {
                "preamble": preamble,
                "full_bytes": data,
                "body_bytes": data[28:],
                "body_len": len(data) - 28,
                "bar_delims": [i for i, b in enumerate(data[28:]) if b == 0xDC],
                "sub_delims": [i for i, b in enumerate(data[28:]) if b == 0x9E],
            }

    # Group by preamble
    by_pre = defaultdict(list)
    for slot, info in rhy1_by_slot.items():
        by_pre[info["preamble"]].append(slot)

    for pre, slots in by_pre.items():
        print(f"\n  Preamble {pre}: {len(slots)} slots")
        for s in slots[:6]:
            info = rhy1_by_slot[s]
            print(f"    {s}: body={info['body_len']}B  bar_delims={info['bar_delims'][:8]}  sub={len(info['sub_delims'])}")

    # Pair-wise diff for 2543 preamble slots (most common)
    pre_25 = by_pre.get("25436000", [])
    if len(pre_25) >= 2:
        print(f"\n═══ 25436000 pair diff ({len(pre_25)} slots) ═══")
        # Compare all pairs, byte by byte, count positional diffs
        # Take first pair
        for i, sa in enumerate(pre_25[:3]):
            for sb in pre_25[i+1:i+4]:
                a = rhy1_by_slot[sa]["body_bytes"]
                b = rhy1_by_slot[sb]["body_bytes"]
                min_len = min(len(a), len(b))
                diffs = [i for i in range(min_len) if a[i] != b[i]]
                print(f"\n  {sa} vs {sb}: {len(diffs)}/{min_len} byte diffs (len a={len(a)}, b={len(b)})")
                # First 5 diff positions
                for d in diffs[:5]:
                    print(f"    byte {d}: 0x{a[d]:02x} vs 0x{b[d]:02x}  XOR=0x{a[d]^b[d]:02x}")

    # Compare sec0/trk3 (BASS) across slots — look for different voices
    print(f"\n═══ Track 3 (BASS) preamble distribution + first event ═══")
    bass = {}
    for slot, tracks in slot_data.items():
        data = tracks.get((0, 3))
        if data and len(data) > 41:
            pre = data[24:28].hex()
            bar_header = data[28:41].hex()
            first_event = data[41:48].hex()
            bass[slot] = {"pre": pre, "bh": bar_header, "e0": first_event}

    for slot, info in bass.items():
        print(f"  {slot:30s}: pre={info['pre']} bh={info['bh']} e0={info['e0']}")

    # Summary encoding sizes per track per slot
    print(f"\n═══ Track body sizes per slot ═══")
    slots_ordered = sorted(slot_data.keys())
    print(f"  {'Slot':<30s} " + " ".join(f"{TRACK_NAMES[t][:4]:>4s}" for t in range(8)))
    for s in slots_ordered:
        sizes = []
        for t in range(8):
            d = slot_data[s].get((0, t))
            sizes.append(len(d) if d else 0)
        print(f"  {s:<30s} " + " ".join(f"{sz:>4d}" for sz in sizes))


if __name__ == "__main__":
    main()
