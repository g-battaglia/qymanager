#!/usr/bin/env python3
"""
Find R-per-event pattern for RHY2 (only note=37).

If encoding is deterministic per-event-position, we can extract R values
and look for linear/modular/cyclic pattern.
"""

import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from qymanager.formats.qy70.sysex_parser import SysExParser


SGT = Path(__file__).parent.parent / "tests" / "fixtures" / "QY70_SGT.syx"


def rot_right(val, s, w=56):
    s %= w
    return ((val >> s) | (val << (w - s))) & ((1 << w) - 1)


def main():
    parser = SysExParser()
    msgs = parser.parse_file(str(SGT))
    data = b""
    for m in msgs:
        if m.is_style_data and m.decoded_data and m.address_low == 0x01:
            data += m.decoded_data
    body = data[28:]  # skip track header + preamble
    print(f"RHY2 body: {len(body)}B")

    # Try starts 0-7 and report R-per-event
    TARGET = 37
    for start in range(0, 14):
        events = []
        for off in range(start, len(body) - 6, 7):
            chunk = body[off:off + 7]
            val = int.from_bytes(chunk, "big")
            valid_Rs = []
            for R in range(56):
                derot = rot_right(val, R)
                f0 = (derot >> 47) & 0x1FF
                note = f0 & 0x7F
                if note == TARGET:
                    vel_code = ((f0 >> 8) & 1) << 3 | ((f0 >> 7) & 1) << 2 | (derot & 0x3)
                    midi_vel = max(1, 127 - vel_code * 8)
                    f5 = (derot >> 2) & 0x1FF
                    valid_Rs.append({"R": R, "v": midi_vel, "g": f5})
            events.append({
                "idx": len(events),
                "off": off,
                "hex": chunk.hex(),
                "valid_Rs": valid_Rs,
            })
        n_events = len(events)
        n_with_target = sum(1 for e in events if e["valid_Rs"])
        print(f"\n═══ start={start:2d}: {n_events} events, {n_with_target} with note={TARGET} at some R ═══")

        if n_with_target < n_events * 0.5:
            continue

        # Print first 16 events
        for e in events[:16]:
            if e["valid_Rs"]:
                Rs = [r["R"] for r in e["valid_Rs"][:8]]
                vels = [r["v"] for r in e["valid_Rs"][:3]]
                print(f"  e{e['idx']:2d} @{e['off']:3d} {e['hex']}: Rs={Rs}  vels={vels}")
            else:
                print(f"  e{e['idx']:2d} @{e['off']:3d} {e['hex']}: no R gives note={TARGET}")

        # For events with valid R, check if there's a common pattern
        # Try R = cumulative formula
        for offset_R in [0, 9, 18, 27, 47]:
            matches = 0
            for i, e in enumerate(events):
                expected_R = (offset_R + 9 * i) % 56
                if any(r["R"] == expected_R for r in e["valid_Rs"]):
                    matches += 1
            print(f"    Linear R={offset_R}+9i: {matches}/{n_events} events match")

        # Try R = constant
        for const_R in [0, 9, 18, 27, 47]:
            matches = 0
            for e in events:
                if any(r["R"] == const_R for r in e["valid_Rs"]):
                    matches += 1
            print(f"    Constant R={const_R}: {matches}/{n_events} events match")

        # Build R-count histogram across all events
        R_counter = defaultdict(int)
        for e in events:
            if e["valid_Rs"]:
                for r in e["valid_Rs"]:
                    R_counter[r["R"]] += 1
        common_Rs = sorted(R_counter.items(), key=lambda x: -x[1])[:10]
        print(f"    Most common Rs across all events: {common_Rs}")


if __name__ == "__main__":
    main()
