#!/usr/bin/env python3
"""
Verify Summer tempo = 155 BPM against GT capture timing.

If tempo is 155 BPM:
- Quarter note = 60/155 = 0.387 sec
- Bar (4 beats) = 1.548 sec
- 4 bars = 6.194 sec

Check if GT note timing aligns with 155 BPM bars.
"""

import json
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from midi_tools.event_decoder import nn


def main():
    gt_path = "midi_tools/captured/summer_playback_s25.json"
    if not os.path.exists(gt_path):
        print(f"GT file not found: {gt_path}")
        return

    with open(gt_path) as f:
        capture = json.load(f)

    # Extract note-on events by channel
    channels = {}
    for evt in capture["events"]:
        d = evt["data"]
        if len(d) == 3:
            ch = (d[0] & 0x0F) + 1
            msg = d[0] & 0xF0
            if msg == 0x90 and d[2] > 0:
                channels.setdefault(ch, []).append({
                    "t": evt["t"], "note": d[1], "vel": d[2]
                })

    # Test both 110 and 155 BPM
    for bpm in [110, 120, 133, 155]:
        beat_dur = 60.0 / bpm
        bar_dur = beat_dur * 4

        print(f"\n{'='*70}")
        print(f"BPM = {bpm} (bar = {bar_dur:.3f}s, beat = {beat_dur:.3f}s)")
        print(f"{'='*70}")

        # Use CHD1 (ch13) — has clear chord changes on bar boundaries
        ch13 = channels.get(13, [])
        if not ch13:
            print("  No ch13 data")
            continue

        t0 = ch13[0]["t"]
        print(f"  CHD1: {len(ch13)} notes, first at t={t0:.3f}s")

        # Group by bar
        bars = {}
        for n in ch13:
            dt = n["t"] - t0
            bar_idx = int(dt / bar_dur)
            beat_pos = (dt - bar_idx * bar_dur) / beat_dur
            bars.setdefault(bar_idx, []).append({
                "note": n["note"], "vel": n["vel"],
                "beat": beat_pos, "dt": dt
            })

        # Check: do notes land on clean beat positions?
        total_deviation = 0
        note_count = 0
        for bi in sorted(bars.keys())[:8]:
            notes = bars[bi]
            for n in notes:
                # Quantize to nearest 8th note
                eighth = round(n["beat"] * 2) / 2
                deviation = abs(n["beat"] - eighth) * beat_dur * 1000  # ms
                total_deviation += deviation
                note_count += 1

            notes_str = [f"{nn(n['note'])} @beat={n['beat']:.2f}" for n in notes]
            print(f"    Bar {bi} ({len(notes)} notes): {', '.join(notes_str)}")

        avg_dev = total_deviation / note_count if note_count else 0
        print(f"\n  Average deviation from 8th-note grid: {avg_dev:.1f} ms")

        # Check bar periodicity: notes in bar N should repeat in bar N+4
        if len(bars) >= 8:
            matches = 0
            total = 0
            for bi in range(4):
                if bi in bars and bi + 4 in bars:
                    notes_a = sorted([n["note"] for n in bars[bi]])
                    notes_b = sorted([n["note"] for n in bars[bi + 4]])
                    if notes_a == notes_b:
                        matches += 1
                    total += 1
            if total > 0:
                print(f"  Bar periodicity (bars 0-3 vs 4-7): {matches}/{total} match")

        # Check: how many notes per bar? (should be consistent)
        counts = [len(bars.get(bi, [])) for bi in range(min(8, max(bars.keys()) + 1))]
        print(f"  Notes per bar (first 8): {counts}")

    # RHY1 timing analysis — drums have very precise timing
    ch9 = channels.get(9, [])
    if ch9:
        t0 = ch9[0]["t"]
        # Find inter-note intervals
        intervals = [ch9[i+1]["t"] - ch9[i]["t"] for i in range(min(30, len(ch9)-1))]

        print(f"\n{'='*70}")
        print(f"RHY1 (ch9) TIMING ANALYSIS")
        print(f"{'='*70}")
        print(f"  First 20 intervals: {[f'{x:.3f}' for x in intervals[:20]]}")

        # The shortest repeating interval should be the 8th-note duration
        # At 155 BPM: 8th = 0.194s, at 110: 0.273s, at 133: 0.226s
        from collections import Counter
        rounded = [round(x, 2) for x in intervals]
        c = Counter(rounded)
        print(f"\n  Most common intervals:")
        for val, count in c.most_common(10):
            # What BPM does this correspond to if it's an 8th note?
            if val > 0:
                bpm_8th = 60.0 / (val * 2)
                bpm_beat = 60.0 / val
                print(f"    {val:.3f}s × {count}: "
                      f"if 8th={bpm_8th:.0f} BPM, if beat={bpm_beat:.0f} BPM")

    print("\nDone.")


if __name__ == "__main__":
    main()
