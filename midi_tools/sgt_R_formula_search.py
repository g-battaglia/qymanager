#!/usr/bin/env python3
"""
R8: Search for R formula per track that maximizes match.

Tests extensive R formulas:
  - Linear: R = (a*i + b) mod 56 for all a, b
  - Per-beat: R depends on (event_idx mod 4) — 4 R values
  - Per-N-event: R cycle of length N
  - Position-based: R = f(byte_offset)

For each formula, count events matching captured notes at correct time window.
"""

import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from qymanager.formats.qy70.sysex_parser import SysExParser


SGT = Path(__file__).parent.parent / "tests" / "fixtures" / "QY70_SGT.syx"
R1 = Path(__file__).parent.parent / "data" / "sgt_rounds" / "R1_4bar" / "playback.json"
OUT = Path(__file__).parent.parent / "data" / "sgt_rounds" / "R8_R_formula.json"

TRACK_NAMES = {0: "RHY1", 1: "RHY2", 2: "PAD", 3: "BASS",
               5: "CHD2", 6: "PHR1"}
TRACK_CH = {0: 9, 1: 10, 2: 11, 3: 12, 5: 14, 6: 15}

BPM = 151
BARS = 4


def rot_right(val, s, w=56):
    s %= w
    return ((val >> s) | (val << (w - s))) & ((1 << w) - 1)


def decode(val, R):
    derot = rot_right(val, R)
    f0 = (derot >> 47) & 0x1FF
    return f0 & 0x7F


def extract_tracks():
    parser = SysExParser()
    msgs = parser.parse_file(str(SGT))
    tracks = defaultdict(bytes)
    for m in msgs:
        if m.is_style_data and m.decoded_data and 0 <= m.address_low <= 7:
            tracks[m.address_low] += m.decoded_data
    return dict(tracks)


def test_formula(body: bytes, target_notes: set, R_fn) -> int:
    """Count events where R_fn(i) produces a target note."""
    matches = 0
    for i in range(len(body) // 7):
        off = i * 7
        chunk = body[off:off + 7]
        val = int.from_bytes(chunk, "big")
        R = R_fn(i)
        if decode(val, R) in target_notes:
            matches += 1
    return matches


def search_linear(body, target_notes, n_events):
    """Try R = (a*i + b) % 56 for all a, b."""
    best = []
    for a in range(56):
        for b in range(56):
            matches = test_formula(body, target_notes, lambda i, a=a, b=b: (a * i + b) % 56)
            best.append((matches, a, b))
    best.sort(reverse=True)
    return best[:5]


def search_per_N(body, target_notes, n_events, N: int):
    """Try R cycle of length N: R_0, R_1, ..., R_{N-1}, then repeats."""
    # Pick best R per position modulo N
    best_Rs = []
    for pos in range(N):
        best_R = 0
        best_count = 0
        for R in range(56):
            count = 0
            for i in range(pos, n_events, N):
                off = i * 7
                chunk = body[off:off + 7]
                val = int.from_bytes(chunk, "big")
                if decode(val, R) in target_notes:
                    count += 1
            if count > best_count:
                best_count = count
                best_R = R
        best_Rs.append(best_R)

    # Total match
    total = 0
    for i in range(n_events):
        off = i * 7
        chunk = body[off:off + 7]
        val = int.from_bytes(chunk, "big")
        R = best_Rs[i % N]
        if decode(val, R) in target_notes:
            total += 1

    return {"N": N, "best_Rs": best_Rs, "matches": total, "total": n_events}


def analyze_track(trk: int, body: bytes, captured: list):
    target_notes = {n["note"] for n in captured}
    n_events = len(body) // 7
    if not target_notes or n_events == 0:
        return {"skipped": True}

    print(f"\n═══ Track {trk} ({TRACK_NAMES.get(trk, '?')}) — {n_events} events, target notes {sorted(target_notes)} ═══")

    result = {
        "target_notes": sorted(target_notes),
        "n_events": n_events,
        "captured_count": len(captured),
    }

    # Linear formula search
    lin = search_linear(body, target_notes, n_events)
    result["linear_top5"] = [{"a": a, "b": b, "matches": m} for m, a, b in lin]
    print(f"  Linear R=a*i+b top5: {result['linear_top5'][:3]}")

    # Per-beat (N=4)
    for N in (2, 3, 4, 6, 8):
        r_n = search_per_N(body, target_notes, n_events, N)
        result[f"per_{N}"] = r_n
        print(f"  Per-{N} cycle: best_Rs={r_n['best_Rs']} → {r_n['matches']}/{n_events}")

    return result


def main():
    tracks = extract_tracks()
    r1 = json.loads(R1.read_text())
    captured_per_ch = defaultdict(list)
    for n in r1["note_ons"]:
        captured_per_ch[n["ch"]].append(n)

    result = {}
    for trk in (0, 1, 2, 3, 5, 6):
        if trk not in tracks:
            continue
        body = tracks[trk][28:]
        captured = captured_per_ch.get(TRACK_CH[trk], [])
        result[trk] = {
            "name": TRACK_NAMES[trk],
            "ch": TRACK_CH[trk],
            **analyze_track(trk, body, captured),
        }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2, default=str))
    print(f"\n═══ Saved → {OUT} ═══")


if __name__ == "__main__":
    main()
