#!/usr/bin/env python3
"""
Compare exact MIDI onset times for RHY1 events with the same velocity pattern.

Hypothesis: bytes 1-3 may encode micro-timing (swing/humanization) rather
than velocity. Verify by checking timing deviation for events with
identical velocities but different bytes 1-3.
"""

import json
from collections import defaultdict

BPM = 120.0
BEAT_S = 60.0 / BPM
BAR_S = BEAT_S * 4


def main():
    with open("midi_tools/captured/summer_playback_s25.json") as f:
        data = json.load(f)

    # Extract all first-loop drum notes with timing
    notes = []
    for ev in data["events"]:
        d = ev["data"]
        if len(d) < 3:
            continue
        if d[0] != 0x98:
            continue
        if d[2] == 0:
            continue
        t = ev["t"]
        if t >= BAR_S * 5:
            break
        notes.append((t, d[1], d[2]))

    # For each (bar, beat), list strike onsets relative to beat start
    beat_onsets = defaultdict(list)
    for t, note, vel in notes:
        bar = int(t / BAR_S)
        bar_t = t - bar * BAR_S
        eighth = round(bar_t / (BEAT_S / 2))
        beat = eighth // 2
        sub = eighth % 2
        if beat >= 4:
            continue
        # Expected onset for this sub-note
        expected_t = bar * BAR_S + beat * BEAT_S + sub * (BEAT_S / 2)
        offset_ms = (t - expected_t) * 1000
        beat_onsets[(bar + 1, beat + 1)].append(
            (note, vel, sub, offset_ms, t)
        )

    # Load event bytes
    with open("midi_tools/captured/summer_ground_truth_full.json") as f:
        gt = json.load(f)
    events = gt["tracks"]["RHY1"]["events"]

    # Build lookup
    event_bytes = {(e["bar"], e["beat"]): e["event_hex"]
                   for e in events}

    print("=" * 72)
    print("MICRO-TIMING offset per strike (ms deviation from quantized position)")
    print("=" * 72)

    for key in sorted(beat_onsets):
        bar, beat = key
        strikes = beat_onsets[key]
        hex_bytes = event_bytes.get(key, "?")
        b = bytes.fromhex(hex_bytes)
        b1_3 = b[1:4].hex() if len(b) >= 4 else "?"
        b4_6 = b[4:7].hex() if len(b) >= 7 else "?"

        strike_info = []
        for note, vel, sub, off_ms, t in sorted(strikes, key=lambda x: x[4]):
            drum = {36: "K", 38: "S", 42: "H"}.get(note, f"N{note}")
            strike_info.append(f"{drum}s{sub}v{vel:3d}t{off_ms:+6.1f}ms")

        print(f"  bar{bar} beat{beat} | b0={b[0]:02x} b1-3={b1_3} b4-6={b4_6} | "
              + " | ".join(strike_info))


if __name__ == "__main__":
    main()
