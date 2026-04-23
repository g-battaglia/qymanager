#!/usr/bin/env python3
"""
Unified SGT decoder using per-event R tables.

Decode pipeline:
  1. Parse SysEx bulk messages
  2. Extract per-track body bytes
  3. Skip 28B track header + preamble
  4. For each event (7-byte), decode with R_table[track_type][i mod N]
  5. Emit MIDI events

Test: apply to 13 stored slots. Measure decoded-note count vs captured (where available).
"""

import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from qymanager.formats.qy70.sysex_parser import SysExParser

TABLES = Path(__file__).parent.parent / "data" / "sgt_R_tables.json"
SLOTS = Path(__file__).parent.parent / "data" / "stored_slots"
OUT = Path(__file__).parent.parent / "data" / "unified_decoder_results.json"


def rot_right(v, s, w=56):
    s %= w
    return ((v >> s) | (v << (w - s))) & ((1 << w) - 1)


def decode_event(chunk: bytes, R: int) -> dict:
    val = int.from_bytes(chunk, "big")
    derot = rot_right(val, R)
    f0 = (derot >> 47) & 0x1FF
    f5 = (derot >> 2) & 0x1FF
    f1 = (derot >> 38) & 0x1FF
    rem = derot & 0x3
    note = f0 & 0x7F
    bit7 = (f0 >> 7) & 1
    bit8 = (f0 >> 8) & 1
    vel_code = (bit8 << 3) | (bit7 << 2) | rem
    return {
        "note": note,
        "vel": max(1, 127 - vel_code * 8),
        "gate": f5,
        "f1_top2": f1 >> 7,
    }


def parse_slot(path: Path):
    parser = SysExParser()
    msgs = parser.parse_file(str(path))
    tracks = defaultdict(bytes)
    for m in msgs:
        if not (m.address_high == 0x02 and
                (m.address_mid <= 0x1F or m.address_mid == 0x7E)
                and m.decoded_data):
            continue
        if m.address_low == 0x7F:
            continue
        sec = m.address_low // 8
        trk = m.address_low % 8
        tracks[(sec, trk)] += m.decoded_data
    return dict(tracks)


def decode_track(body: bytes, R_table: list) -> list:
    body = body[28:]
    n_events = len(body) // 7
    N = len(R_table)
    decoded = []
    for i in range(n_events):
        chunk = body[i*7:(i+1)*7]
        R = R_table[i % N]
        dec = decode_event(chunk, R)
        dec["idx"] = i
        decoded.append(dec)
    return decoded


def main():
    tables = json.loads(TABLES.read_text())

    results = {"tables_used": {}, "slots_decoded": {}}
    for trk_str, t in tables.items():
        results["tables_used"][trk_str] = {
            "name": t["name"], "N": t["best_N"], "coverage": t["coverage"]
        }

    # Apply decoder to all slots
    print("═══ Applying per-event R decoder to 13 slots ═══\n")

    for f in sorted(SLOTS.iterdir()):
        if f.name.startswith(("._", "edit")) or not f.name.startswith("slot_"):
            continue
        tracks = parse_slot(f)
        slot_result = {}
        for (sec, trk_idx), body in tracks.items():
            if str(trk_idx) not in tables:
                continue
            table = tables[str(trk_idx)]
            R_table = table["best_Rs"]
            target = set(table["target_notes"])
            decoded = decode_track(body, R_table)
            # Filter to valid drum/target range
            valid = [d for d in decoded if 13 <= d["note"] <= 127]
            target_matches = [d for d in decoded if d["note"] in target]
            slot_result[f"sec{sec}_trk{trk_idx}"] = {
                "track_name": table["name"],
                "total_events": len(decoded),
                "valid_range_notes": len(valid),
                "target_matches": len(target_matches),
                "unique_notes": sorted({d["note"] for d in valid})[:15],
            }
        results["slots_decoded"][f.name] = slot_result

        print(f"{f.name}:")
        for key, info in sorted(slot_result.items()):
            print(f"  {key} {info['track_name']:6s}: "
                  f"{info['valid_range_notes']:>3d}/{info['total_events']:>3d} valid, "
                  f"{info['target_matches']:>3d} target matches, "
                  f"notes={info['unique_notes'][:8]}")

    OUT.write_text(json.dumps(results, indent=2, default=str))
    print(f"\nSaved → {OUT}")


if __name__ == "__main__":
    main()
