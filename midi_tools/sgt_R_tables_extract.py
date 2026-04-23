#!/usr/bin/env python3
"""
Extract complete per-track R lookup tables for SGT Section 0.

For each track, find optimal N and R table [R_0..R_{N-1}] that maximizes
target-note matches.
"""

import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from qymanager.formats.qy70.sysex_parser import SysExParser

SGT = Path(__file__).parent.parent / "tests" / "fixtures" / "QY70_SGT.syx"
R1 = Path(__file__).parent.parent / "data" / "sgt_rounds" / "R1_4bar" / "playback.json"
OUT = Path(__file__).parent.parent / "data" / "sgt_R_tables.json"

TRACK_CH = {0: 9, 1: 10, 2: 11, 3: 12, 5: 14, 6: 15}
TRACK_NAMES = {0: "RHY1", 1: "RHY2", 2: "PAD", 3: "BASS", 5: "CHD2", 6: "PHR1"}


def rot_right(v, s, w=56):
    s %= w
    return ((v >> s) | (v << (w - s))) & ((1 << w) - 1)


def decode(val, R):
    derot = rot_right(val, R)
    return (derot >> 47) & 0x7F


def extract_tracks():
    parser = SysExParser()
    msgs = parser.parse_file(str(SGT))
    tracks = defaultdict(bytes)
    for m in msgs:
        if m.is_style_data and m.decoded_data and 0 <= m.address_low <= 7:
            tracks[m.address_low] += m.decoded_data
    return dict(tracks)


def find_best_table(body: bytes, target_notes: set):
    n_events = len(body) // 7
    best = {"score": 0, "N": 1, "Rs": []}
    for N in range(1, min(n_events + 1, 64)):
        best_Rs = []
        total = 0
        for pos in range(N):
            best_R = 0
            best_count = 0
            for R in range(56):
                count = 0
                for i in range(pos, n_events, N):
                    chunk = body[i*7:(i+1)*7]
                    val = int.from_bytes(chunk, "big")
                    if decode(val, R) in target_notes:
                        count += 1
                if count > best_count:
                    best_count = count
                    best_R = R
            best_Rs.append(best_R)
            total += best_count
        if total > best["score"]:
            best = {"score": total, "N": N, "Rs": best_Rs, "events": n_events}
    return best


def main():
    tracks = extract_tracks()
    r1 = json.loads(R1.read_text())
    captured_per_ch = defaultdict(list)
    for n in r1["note_ons"]:
        captured_per_ch[n["ch"]].append(n)

    tables = {}
    for trk, ch in TRACK_CH.items():
        body = tracks[trk][28:]
        target = {n["note"] for n in captured_per_ch.get(ch, [])}
        if not target:
            continue
        best = find_best_table(body, target)
        # Also decode all events with this table
        decoded_notes = []
        for i in range(best["events"]):
            chunk = body[i*7:(i+1)*7]
            val = int.from_bytes(chunk, "big")
            R = best["Rs"][i % best["N"]]
            derot = rot_right(val, R)
            f0 = (derot >> 47) & 0x1FF
            f5 = (derot >> 2) & 0x1FF
            rem = derot & 0x3
            note = f0 & 0x7F
            bit7 = (f0 >> 7) & 1
            bit8 = (f0 >> 8) & 1
            vel_code = (bit8 << 3) | (bit7 << 2) | rem
            midi_vel = max(1, 127 - vel_code * 8)
            decoded_notes.append({"i": i, "R": R, "note": note, "vel": midi_vel, "gate": f5})

        tables[str(trk)] = {
            "name": TRACK_NAMES[trk],
            "ch": ch,
            "target_notes": sorted(target),
            "n_events": best["events"],
            "best_N": best["N"],
            "best_Rs": best["Rs"],
            "score": best["score"],
            "coverage": round(best["score"] / best["events"], 3),
            "decoded_first_16": decoded_notes[:16],
            "all_decoded_notes": [d["note"] for d in decoded_notes],
        }
        print(f"\n═══ {TRACK_NAMES[trk]} ch{ch} ═══")
        print(f"  N={best['N']}, score={best['score']}/{best['events']} ({best['score']/best['events']*100:.1f}%)")
        print(f"  R table: {best['Rs']}")
        # Count decoded unique notes
        unique = set(d["note"] for d in decoded_notes if d["note"] in target)
        print(f"  Unique target notes decoded: {sorted(unique)}")
        print(f"  First 16 decoded: {[d['note'] for d in decoded_notes[:16]]}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(tables, indent=2, default=str))
    print(f"\n═══ Saved → {OUT} ═══")


if __name__ == "__main__":
    main()
