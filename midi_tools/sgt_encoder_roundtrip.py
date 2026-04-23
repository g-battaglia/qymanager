#!/usr/bin/env python3
"""
Build SGT dense-factory encoder (inverse of per-event R table decoder).

Given: (track, events, R_table, body_bytes_original)
Apply encoder logic:
  For each position, use R from table to decode original byte → get note
  Use original byte encoding (pass-through for now since R table matches)
  → roundtrip: decode(body, R) → events → encode(events, R) → body should match

For fields we KNOW how to encode (note, gate, velocity, sub_pos), modify
and verify resulting bytes play correct notes.
"""

import json
import sys
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent.parent))

from qymanager.formats.qy70.sysex_parser import SysExParser

TABLES = Path(__file__).parent.parent / "data" / "sgt_R_tables.json"
SGT = Path(__file__).parent.parent / "tests" / "fixtures" / "QY70_SGT.syx"


def rot_right(v, s, w=56):
    s %= w
    return ((v >> s) | (v << (w - s))) & ((1 << w) - 1)


def rot_left(v, s, w=56):
    return rot_right(v, (-s) % w, w)


def decode_event(chunk, R):
    val = int.from_bytes(chunk, "big")
    derot = rot_right(val, R)
    f0 = (derot >> 47) & 0x1FF
    f5 = (derot >> 2) & 0x1FF
    f1 = (derot >> 38) & 0x1FF
    f2 = (derot >> 29) & 0x1FF
    f3 = (derot >> 20) & 0x1FF
    f4 = (derot >> 11) & 0x1FF
    rem = derot & 0x3
    note = f0 & 0x7F
    bit7 = (f0 >> 7) & 1
    bit8 = (f0 >> 8) & 1
    vel_code = (bit8 << 3) | (bit7 << 2) | rem
    return {
        "f0": f0, "f1": f1, "f2": f2, "f3": f3, "f4": f4, "f5": f5, "rem": rem,
        "note": note, "vel": max(1, 127 - vel_code * 8),
        "gate": f5, "vel_code": vel_code,
    }


def encode_event(fields: dict, R: int) -> bytes:
    """Encode event dict back to 7-byte chunk."""
    val = 0
    val |= (fields["f0"] & 0x1FF) << 47
    val |= (fields["f1"] & 0x1FF) << 38
    val |= (fields["f2"] & 0x1FF) << 29
    val |= (fields["f3"] & 0x1FF) << 20
    val |= (fields["f4"] & 0x1FF) << 11
    val |= (fields["f5"] & 0x1FF) << 2
    val |= (fields["rem"] & 0x3)
    stored = rot_left(val, R)
    return stored.to_bytes(7, "big")


def extract_track(al: int) -> bytes:
    parser = SysExParser()
    msgs = parser.parse_file(str(SGT))
    data = b""
    for m in msgs:
        if m.is_style_data and m.decoded_data and m.address_low == al:
            data += m.decoded_data
    return data


def main():
    tables = json.loads(TABLES.read_text())

    print("═══ SGT encoder roundtrip validation ═══\n")
    for trk_str, t in tables.items():
        trk = int(trk_str)
        body_full = extract_track(trk)
        body = body_full[28:]
        R_table = t["best_Rs"]
        N = t["best_N"]
        n_events = t["n_events"]

        # Decode + encode back
        matches_total = 0
        for i in range(n_events):
            original_chunk = body[i*7:(i+1)*7]
            R = R_table[i % N]
            fields = decode_event(original_chunk, R)
            encoded_chunk = encode_event(fields, R)
            if encoded_chunk == original_chunk:
                matches_total += 1
        pct = matches_total / n_events * 100 if n_events else 0
        print(f"  {t['name']:6s}: roundtrip {matches_total}/{n_events} ({pct:.1f}%)")

    print(f"\n═══ Conclusion ═══")
    print(f"If roundtrip 100% → decoder/encoder bit-exact over full field extraction")
    print(f"Mismatch indicates un-extracted bits or field overlap")


if __name__ == "__main__":
    main()
