#!/usr/bin/env python3
"""Iter 6: exhaustive per-N cycle R search for SGT tracks."""

import json
import sys
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent.parent))

from qymanager.formats.qy70.sysex_parser import SysExParser

SGT = Path(__file__).parent.parent / "tests" / "fixtures" / "QY70_SGT.syx"
R1 = Path(__file__).parent.parent / "data" / "sgt_rounds" / "R1_4bar" / "playback.json"
TRACK_CH = {0: 9, 1: 10, 2: 11, 3: 12, 5: 14, 6: 15}
TRACK_NAMES = {0: "RHY1", 1: "RHY2", 2: "PAD", 3: "BASS", 5: "CHD2", 6: "PHR1"}


def rot_right(v, s, w=56):
    s %= w
    return ((v >> s) | (v << (w - s))) & ((1 << w) - 1)


def extract_tracks():
    parser = SysExParser()
    msgs = parser.parse_file(str(SGT))
    tracks = defaultdict(bytes)
    for m in msgs:
        if m.is_style_data and m.decoded_data and 0 <= m.address_low <= 7:
            tracks[m.address_low] += m.decoded_data
    return dict(tracks)


def decode(val, R):
    derot = rot_right(val, R)
    return (derot >> 47) & 0x7F


def score_per_N(body, target_notes, N):
    n_events = len(body) // 7
    # Best R per position mod N
    best_Rs = []
    for pos in range(N):
        best_R, best_count = 0, 0
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
    # Total matches
    total = 0
    for i in range(n_events):
        chunk = body[i*7:(i+1)*7]
        val = int.from_bytes(chunk, "big")
        R = best_Rs[i % N]
        if decode(val, R) in target_notes:
            total += 1
    return total, n_events, best_Rs


def main():
    tracks = extract_tracks()
    r1 = json.loads(R1.read_text())
    captured_per_ch = defaultdict(list)
    for n in r1["note_ons"]:
        captured_per_ch[n["ch"]].append(n)

    for trk, ch in TRACK_CH.items():
        body = tracks[trk][28:]
        target = {n["note"] for n in captured_per_ch.get(ch, [])}
        if not target:
            continue
        print(f"\n═══ {TRACK_NAMES[trk]} (ch{ch}) — {len(body)}B, {len(body)//7} events, target {sorted(target)} ═══")

        best_score = 0
        best_N = 0
        best_Rs_out = []
        for N in range(1, 33):
            matches, total, Rs = score_per_N(body, target, N)
            pct = matches / total * 100
            if pct > best_score:
                best_score = pct
                best_N = N
                best_Rs_out = Rs
            if pct > 40:  # show meaningful ones
                print(f"  N={N:2d}: {matches:3d}/{total} ({pct:5.1f}%)  Rs={Rs[:12]}{'...' if len(Rs)>12 else ''}")
        print(f"  → BEST: N={best_N} at {best_score:.1f}%")


if __name__ == "__main__":
    main()
