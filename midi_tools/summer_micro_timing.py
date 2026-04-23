#!/usr/bin/env python3
"""
Extract Summer micro-timing from high-res playback capture.

For each captured note-on, compute:
  - Actual tick = t × BPM/60 × 480
  - Quantized 8th tick (closest 240 tick multiple)
  - Micro-offset = actual - quantized

Then per (bar, beat, strike), correlate with remaining variable bits
from bitstream events.
"""

import json
from pathlib import Path
from collections import defaultdict

PB = Path(__file__).parent / "captured" / "summer_playback_s25.json"
GT = Path(__file__).parent / "captured" / "summer_ground_truth.json"


def main():
    pb = json.loads(PB.read_text())
    gt = json.loads(GT.read_text())
    events = pb["events"]

    BPM = 120  # Summer default
    TICKS_PER_BEAT = 480
    TICKS_PER_BAR = TICKS_PER_BEAT * 4

    # Extract RHY1 channel (ch9) note-ons
    rhy1_notes = []
    for e in events:
        data = e["data"]
        if len(data) >= 3 and (data[0] & 0xF0) == 0x90 and data[2] > 0:
            ch = (data[0] & 0x0F) + 1
            if ch == 9:
                t = e["t"]
                tick = t * BPM / 60 * TICKS_PER_BEAT
                rhy1_notes.append({"t": t, "tick": tick, "note": data[1], "vel": data[2]})

    print(f"Summer RHY1 captured notes (raw): {len(rhy1_notes)}")

    # Group by bar + beat + subdivision_8th
    # subdivision_8th 0 = on beat, 1 = + half beat (tick 240)
    grouped = defaultdict(list)
    for n in rhy1_notes:
        bar = int(n["tick"] // TICKS_PER_BAR) + 1
        tick_in_bar = n["tick"] - (bar - 1) * TICKS_PER_BAR
        beat = int(tick_in_bar // TICKS_PER_BEAT) + 1
        tick_in_beat = tick_in_bar - (beat - 1) * TICKS_PER_BEAT
        sub = 0 if tick_in_beat < 240 else 1
        quantized = beat * TICKS_PER_BEAT - TICKS_PER_BEAT + sub * 240
        offset = tick_in_beat - sub * 240  # offset within quarter-note half
        grouped[(bar, beat, sub)].append({
            "note": n["note"], "vel": n["vel"], "actual_tick": n["tick"],
            "quantized": quantized, "offset_ticks": offset, "t_ms": n["t"] * 1000,
        })

    # Show micro-timing per bar/beat/sub
    print(f"\n═══ Per-bar-beat-sub micro-timing ═══\n")
    for key in sorted(grouped.keys())[:20]:
        bar, beat, sub = key
        notes = grouped[key]
        for n in notes:
            print(f"  bar{bar} beat{beat} sub{sub}  n{n['note']:>3} v{n['vel']:>3}  "
                  f"offset={n['offset_ticks']:+.2f}t  ({n['t_ms']:.2f}ms)")

    # Correlate with bitstream events
    # For each bitstream event (bar, beat), collect the 3 strikes' offsets
    print(f"\n═══ Bitstream events with captured micro-offsets ═══")
    for bs_event in gt["events"]:
        bar = bs_event["bar"]
        beat = bs_event["beat"]
        event_hex = bs_event["event_hex"]
        # Summer is 5 bars but captured playback is 30s = 18.75 bars @ 120 BPM
        # Pattern loops every 4 bars (main) + 1 fill?
        # Match strikes
        matched = []
        for s in bs_event["expected_strikes"]:
            sub = s["subdivision_8th"]
            # Look in grouped for the closest note
            key = (bar, beat, sub)
            if key in grouped:
                # Find note with matching note number
                candidates = [n for n in grouped[key] if n["note"] == s["note"]]
                if candidates:
                    matched.append({
                        "note": s["note"],
                        "gt_vel": s["velocity"],
                        "actual_vel": candidates[0]["vel"],
                        "offset_ticks": candidates[0]["offset_ticks"],
                    })
        if matched:
            offsets = [m["offset_ticks"] for m in matched]
            print(f"  bar{bar} beat{beat} {event_hex}: "
                  f"offsets={['%+.1f' % o for o in offsets]}  strikes={matched}")


if __name__ == "__main__":
    main()
