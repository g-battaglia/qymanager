#!/usr/bin/env python3
"""
RHY2 deep analysis — simplest SGT track (only note 37 SideStk).

Ground truth: 39 captured notes in 4 bars @ 151 BPM.
Bitstream: 256B at AL=0x01 Section 0.

Goals:
  1. Identify event boundaries in 228B data area
  2. Correlate event positions with captured timing
  3. Test multiple rotation schemes (cumulative, per-beat, constant)
  4. Discover if RHY2 uses sparse or dense encoding
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from qymanager.formats.qy70.sysex_parser import SysExParser

SGT = Path(__file__).parent.parent / "tests" / "fixtures" / "QY70_SGT.syx"
R1 = Path(__file__).parent.parent / "data" / "sgt_rounds" / "R1_4bar" / "playback.json"


def rot_right(val, shift, width=56):
    shift %= width
    return ((val >> shift) | (val << (width - shift))) & ((1 << width) - 1)


def rot_left(val, shift, width=56):
    return rot_right(val, (-shift) % width, width)


def extract_rhy2():
    parser = SysExParser()
    msgs = parser.parse_file(str(SGT))
    data = b""
    for m in msgs:
        if m.is_style_data and m.decoded_data and m.address_low == 0x01:
            data += m.decoded_data
    return data


def load_captured():
    r1 = json.loads(R1.read_text())
    return [n for n in r1["note_ons"] if n["ch"] == 10]


def try_all_R(chunk: bytes) -> list:
    """For a 7-byte chunk, return all R values that yield note=37."""
    val = int.from_bytes(chunk, "big")
    results = []
    for R in range(56):
        derot = rot_right(val, R)
        f0 = (derot >> 47) & 0x1FF
        note = f0 & 0x7F
        if note == 37:
            vel_code = ((f0 >> 8) & 1) << 3 | ((f0 >> 7) & 1) << 2 | (derot & 0x3)
            midi_vel = max(1, 127 - vel_code * 8)
            f5 = (derot >> 2) & 0x1FF
            f1 = (derot >> 38) & 0x1FF
            results.append({"R": R, "vel": midi_vel, "gate": f5, "f1": f1})
    return results


def main():
    data = extract_rhy2()
    captured = load_captured()

    print(f"RHY2 bitstream: {len(data)} B")
    print(f"Captured: {len(captured)} notes, all note=37")

    body = data[28:]  # skip track header + preamble
    print(f"Data body: {len(body)}B")

    # Show hex
    print(f"\nFirst 128B of body:")
    for row in range(0, min(128, len(body)), 16):
        print(f"  {row:4d}: {body[row:row+16].hex(' ')}")

    # Scan for 7-byte events yielding note=37
    print(f"\n═══ 7-byte events giving note=37 at some R ═══")
    candidates = []
    for off in range(0, len(body) - 6):
        chunk = body[off:off + 7]
        Rs = try_all_R(chunk)
        if Rs:
            candidates.append({
                "offset": off,
                "chunk": chunk.hex(),
                "Rs": Rs,
            })

    print(f"Found {len(candidates)} offsets with at least one valid R for note=37")
    if len(candidates) < 50:
        print(f"  Top 20:")
        for c in candidates[:20]:
            rs_str = ", ".join(f"R={r['R']} v{r['vel']}" for r in c["Rs"][:5])
            print(f"    @{c['offset']:3d}: {c['chunk']}  [{rs_str}]")

    # Compare to captured velocity distribution
    from collections import Counter
    vel_counter = Counter(n["vel"] for n in captured)
    print(f"\nCaptured velocities: {dict(vel_counter.most_common())}")
    print(f"  Unique: {sorted(vel_counter.keys())}")

    # Check if all captured vels are same (127) — expected from "hard strike" sparse event
    if len(vel_counter) == 1 and 127 in vel_counter:
        print(f"  → ALL captured at vel=127, suggests binary on/off encoding per event")

    # Time analysis
    print(f"\n═══ Captured note timing ═══")
    first_10 = captured[:10]
    for n in first_10:
        print(f"  t={n['t']:.4f}s  vel={n['vel']}")
    # Intervals
    intervals = [captured[i+1]["t"] - captured[i]["t"] for i in range(min(10, len(captured)-1))]
    print(f"  Intervals (first 10): {[f'{iv:.3f}' for iv in intervals]}s")
    # Expected at 151 BPM: 1 beat = 60/151 = 0.397s, 1 eighth = 0.199s, 1 sixteenth = 0.099s

    # Hypothesis: 9.75 notes/bar = between 8 (eighth notes) and 16 (sixteenths)
    # 39 notes in 4 bars. Maybe variable density.

    # Try per-bar analysis
    bar_duration = 60 / 151 * 4  # = 1.589s
    notes_per_bar = [0] * 4
    for n in captured:
        bar = int(n["t"] / bar_duration)
        if 0 <= bar < 4:
            notes_per_bar[bar] += 1
    print(f"  Notes per bar: {notes_per_bar}  (total {sum(notes_per_bar)})")


if __name__ == "__main__":
    main()
