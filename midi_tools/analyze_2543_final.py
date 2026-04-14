#!/usr/bin/env python3
"""Final 2543 decoding verification with corrected position formula.

Confirmed field map:
- F0 [bit8:bit7] + remainder = 4-bit inverted velocity (0=fff, 15=pppp)
- F0 lo7 = MIDI note number
- F1 top 2 bits = beat (0-3)
- F1 lower 7 bits + F2 top bits = clock within beat
- F5 = gate time in ticks

Test 9-bit clock: pos_clock = ((F1 & 0x7F) << 2) | (F2 >> 7)  [9 bits, 0-511]
vs 10-bit clock: pos_clock = ((F1 & 0x7F) << 3) | (F2 >> 6)  [10 bits, 0-1023]
"""

import sys, os
from collections import defaultdict
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from qymanager.formats.qy70.sysex_parser import SysExParser

GM_DRUMS = {
    35: "Kick2", 36: "Kick1", 37: "SideStk", 38: "Snare1", 39: "Clap",
    40: "Snare2", 41: "LoFlTom", 42: "HHclose", 43: "HiFlTom", 44: "HHpedal",
    45: "LoTom", 46: "HHopen", 47: "MidLoTom", 48: "HiMidTom", 49: "Crash1",
    50: "HiTom", 51: "Ride1", 52: "Chinese", 53: "RideBell", 54: "Tamb",
    55: "Splash", 56: "Cowbell", 57: "Crash2", 58: "Vibslap", 59: "Ride2",
    60: "HiBongo", 61: "LoBongo", 62: "MuHConga", 63: "OpHConga", 64: "LoConga",
    65: "HiTimbal", 66: "LoTimbal", 67: "HiAgogo", 68: "LoAgogo", 69: "Cabasa",
    70: "Maracas", 71: "ShWhistl", 72: "LgWhistl", 73: "ShGuiro", 74: "LgGuiro",
    75: "Claves", 76: "HiWBlock", 77: "LoWBlock", 78: "MuCuica", 79: "OpCuica",
    80: "MuTriang", 81: "OpTriang",
}

R = 9

def rot_right(val, shift, width=56):
    shift = shift % width
    return ((val >> shift) | (val << (width - shift))) & ((1 << width) - 1)

def f9(val, idx, total=56):
    shift = total - (idx + 1) * 9
    return (val >> shift) & 0x1FF if shift >= 0 else -1

def get_events(syx_path, section=0, track=0):
    parser = SysExParser()
    messages = parser.parse_file(syx_path)
    al = section * 8 + track
    data = b""
    for m in messages:
        if m.is_style_data and m.address_low == al:
            if m.decoded_data is not None:
                data += m.decoded_data
    if len(data) < 28:
        return []
    event_data = data[28:]
    delim_pos = sorted(i for i, b in enumerate(event_data) if b in (0xDC, 0x9E))
    segments = []
    prev = 0
    for dp in delim_pos:
        segments.append(event_data[prev:dp])
        prev = dp + 1
    segments.append(event_data[prev:])

    events = []
    for seg_idx, seg in enumerate(segments):
        if len(seg) >= 20:
            for i in range((len(seg) - 13) // 7):
                evt = seg[13 + i * 7: 13 + (i + 1) * 7]
                if len(evt) == 7:
                    events.append((seg_idx, i, evt))
    return events


def decode_event(evt):
    val = int.from_bytes(evt, "big")
    derot = rot_right(val, R)
    f0 = f9(derot, 0)
    f1 = f9(derot, 1)
    f2 = f9(derot, 2)
    f3 = f9(derot, 3)
    f4 = f9(derot, 4)
    f5 = f9(derot, 5)
    rem = derot & 0x3

    note = f0 & 0x7F
    bit8 = (f0 >> 8) & 1
    bit7 = (f0 >> 7) & 1
    vel_code = (bit8 << 3) | (bit7 << 2) | rem
    midi_vel = max(1, 127 - vel_code * 8)
    gate = f5

    beat = f1 >> 7  # top 2 bits of F1

    # Try different clock extractions
    clock_9 = ((f1 & 0x7F) << 2) | (f2 >> 7)  # 9-bit
    clock_10 = ((f1 & 0x7F) << 3) | (f2 >> 6)  # 10-bit

    tick_9 = beat * 480 + clock_9
    tick_10 = beat * 480 + (clock_10 % 480) if clock_10 >= 480 else beat * 480 + clock_10

    return {
        'note': note, 'vel_code': vel_code, 'midi_vel': midi_vel,
        'gate': gate, 'beat': beat,
        'clock_9': clock_9, 'clock_10': clock_10,
        'tick_9': tick_9, 'tick_10': tick_10,
        'f1': f1, 'f2': f2, 'f3': f3, 'f4': f4, 'f5': f5, 'rem': rem,
    }


def main():
    base = os.path.dirname(os.path.abspath(__file__))
    syx = os.path.join(base, "captured", "ground_truth_style.syx")
    raw_events = get_events(syx, 0, 0)

    # ============================================================
    # Compare 9-bit vs 10-bit clock monotonicity
    # ============================================================
    print(f"{'='*70}")
    print(f"  POSITION MONOTONICITY: 9-bit vs 10-bit clock")
    print(f"{'='*70}")

    by_seg = defaultdict(list)
    for seg_idx, evt_idx, evt in raw_events:
        d = decode_event(evt)
        d['seg'] = seg_idx
        d['eidx'] = evt_idx
        by_seg[seg_idx].append(d)

    total_mono_9 = 0
    total_mono_10 = 0
    total_pairs = 0

    for seg_idx in sorted(by_seg.keys()):
        evts = by_seg[seg_idx]
        n = len(evts) - 1
        if n <= 0:
            continue
        # Unique positions only (remove duplicates at same position)
        seen_9 = {}
        seen_10 = {}
        for d in evts:
            if d['tick_9'] not in seen_9:
                seen_9[d['tick_9']] = d
            if d['tick_10'] not in seen_10:
                seen_10[d['tick_10']] = d

        # Check if unique positions are in event order
        ticks_9 = [d['tick_9'] for d in evts]
        ticks_10 = [d['tick_10'] for d in evts]

        mono_9 = sum(1 for i in range(n) if ticks_9[i+1] >= ticks_9[i])
        mono_10 = sum(1 for i in range(n) if ticks_10[i+1] >= ticks_10[i])

        # Check if sorted unique positions match event order
        unique_9 = sorted(set(ticks_9))
        unique_10 = sorted(set(ticks_10))

        total_mono_9 += mono_9
        total_mono_10 += mono_10
        total_pairs += n

    print(f"\n  9-bit clock monotonic:  {total_mono_9}/{total_pairs}"
          f" ({100*total_mono_9/total_pairs:.0f}%)")
    print(f"  10-bit clock monotonic: {total_mono_10}/{total_pairs}"
          f" ({100*total_mono_10/total_pairs:.0f}%)")

    # ============================================================
    # Full decode with 9-bit clock, sorted by position
    # ============================================================
    print(f"\n{'='*70}")
    print(f"  FULL DECODE — Sorted by position (9-bit clock)")
    print(f"{'='*70}")

    for seg_idx in sorted(by_seg.keys()):
        evts = by_seg[seg_idx]
        sorted_evts = sorted(evts, key=lambda d: (d['tick_9'], d['note']))

        print(f"\n  Segment {seg_idx} ({len(evts)} events):")
        print(f"  {'Beat':>4} {'Clock':>5} {'Tick':>5} | {'Note':>4} {'Drum':>10}"
              f" | {'Vel':>3} {'Gate':>4} | {'raw_order':>9}")

        for d in sorted_evts:
            name = GM_DRUMS.get(d['note'], f"n{d['note']}")[:10]
            print(f"  {d['beat']:>4} {d['clock_9']:>5} {d['tick_9']:>5}"
                  f" | {d['note']:>4} {name:>10}"
                  f" | {d['midi_vel']:>3} {d['gate']:>4}"
                  f" | e{d['eidx']}")

    # ============================================================
    # Check if "simultaneous" events at same tick have same vel/gate
    # ============================================================
    print(f"\n{'='*70}")
    print(f"  SIMULTANEOUS EVENTS (same tick position)")
    print(f"{'='*70}")

    for seg_idx in sorted(by_seg.keys()):
        evts = by_seg[seg_idx]
        by_tick = defaultdict(list)
        for d in evts:
            by_tick[d['tick_9']].append(d)

        multis = {t: ds for t, ds in by_tick.items() if len(ds) > 1}
        if multis:
            print(f"\n  Segment {seg_idx}:")
            for tick, ds in sorted(multis.items()):
                notes = ", ".join(
                    f"{GM_DRUMS.get(d['note'], 'n' + str(d['note']))}"
                    f"(v{d['midi_vel']},g{d['gate']})"
                    for d in ds
                )
                print(f"    tick {tick}: {notes}")

    # ============================================================
    # Position validation: does tick 240 = beat 1 onset?
    # ============================================================
    print(f"\n{'='*70}")
    print(f"  POSITION CALIBRATION")
    print(f"{'='*70}")

    # Common positions (tick_9 values that appear in >3 segments)
    tick_segs = defaultdict(set)
    for seg_idx in by_seg:
        for d in by_seg[seg_idx]:
            tick_segs[d['tick_9']].add(seg_idx)

    common_ticks = sorted((t, len(segs)) for t, segs in tick_segs.items() if len(segs) >= 2)
    print(f"\n  Tick positions appearing in 2+ segments:")
    print(f"  {'Tick':>5} {'Beat.Clk':>8} {'Segs':>4} {'Notes at this position'}")
    for tick, nseg in sorted(common_ticks, key=lambda x: -x[1])[:15]:
        notes = set()
        for seg_idx in tick_segs[tick]:
            for d in by_seg[seg_idx]:
                if d['tick_9'] == tick:
                    notes.add(GM_DRUMS.get(d['note'], f"n{d['note']}"))
        beat = tick // 480
        clock = tick % 480
        print(f"  {tick:>5} {beat}.{clock:03d}    {nseg:>4}  {', '.join(sorted(notes))}")

    # ============================================================
    # Grid analysis: what timing grid do events fall on?
    # ============================================================
    print(f"\n{'='*70}")
    print(f"  GRID ANALYSIS (480ppq)")
    print(f"{'='*70}")

    all_clocks = [d['clock_9'] for evts in by_seg.values() for d in evts]
    grid_counts = {
        "whole note (1920)": sum(1 for c in all_clocks if c % 480 == 0),
        "half note (960)": sum(1 for c in all_clocks if c % 240 == 0),
        "quarter (480)": sum(1 for c in all_clocks if c % 120 == 0),
        "8th (240)": sum(1 for c in all_clocks if c % 60 == 0),
        "16th (120)": sum(1 for c in all_clocks if c % 30 == 0),
        "32nd (60)": sum(1 for c in all_clocks if c % 15 == 0),
    }
    for grid, cnt in grid_counts.items():
        print(f"  On {grid}: {cnt}/{len(all_clocks)} ({100*cnt/len(all_clocks):.0f}%)")


if __name__ == "__main__":
    main()
