#!/usr/bin/env python3
"""Deep field-structure analysis for 2543 drum encoding.

Tests:
1. Joint R optimization: which R maximizes BOTH valid drum notes AND beat counter?
2. Alternative field widths: is it really 6×9+2, or some other partition?
3. Position encoding in F1-F4: how do events order within a bar?
4. F5 as gate time: physical reasonableness check
"""

import sys
import os
from collections import Counter, defaultdict
from typing import List, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from qymanager.formats.qy70.sysex_parser import SysExParser

GM_DRUM_NAMES = {
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


def rot_right(val, shift, width=56):
    shift = shift % width
    return ((val >> shift) | (val << (width - shift))) & ((1 << width) - 1)


def extract_field(val, start_bit, width, total=56):
    """Extract a field starting at start_bit (0=MSB) with given width."""
    shift = total - start_bit - width
    if shift < 0:
        return -1
    return (val >> shift) & ((1 << width) - 1)


def get_all_events(syx_path, section=0, track=0):
    """Get all raw 7-byte events from a track."""
    parser = SysExParser()
    messages = parser.parse_file(syx_path)
    al = section * 8 + track
    data = b""
    for m in messages:
        if m.is_style_data and m.address_low == al:
            if m.decoded_data is not None:
                data += m.decoded_data
    if len(data) < 28:
        return [], b""
    preamble = data[24:28]
    event_data = data[28:]

    delim_pos = sorted(i for i, b in enumerate(event_data) if b in (0xDC, 0x9E))
    segments = []
    prev = 0
    for dp in delim_pos:
        segments.append(event_data[prev:dp])
        prev = dp + 1
    segments.append(event_data[prev:])

    all_events = []
    for seg_idx, seg in enumerate(segments):
        if len(seg) >= 20:
            header = seg[:13]
            for i in range((len(seg) - 13) // 7):
                evt = seg[13 + i * 7: 13 + (i + 1) * 7]
                if len(evt) == 7:
                    all_events.append((seg_idx, i, evt, header))
    return all_events, preamble


def main():
    base = os.path.dirname(os.path.abspath(__file__))
    style_syx = os.path.join(base, "captured", "ground_truth_style.syx")

    events, preamble = get_all_events(style_syx, section=0, track=0)
    if not events:
        print("No events found")
        return
    print(f"Loaded {len(events)} events from Style RHY1")

    # ============================================================
    # TEST 1: Joint R optimization
    # ============================================================
    print(f"\n{'='*70}")
    print("  TEST 1: JOINT R OPTIMIZATION")
    print(f"{'='*70}")
    print(f"\n  For each R (0-55), check:")
    print(f"  - drum_pct: F0 lo7 in GM range 35-81")
    print(f"  - beat_pct: F3 lo4 is valid one-hot (0,1,2,4,8)")
    print(f"  - joint = drum_pct × beat_pct")

    best_joint = 0
    best_r = -1
    results = []
    for r in range(56):
        gm_hits = 0
        beat_hits = 0
        for _, _, evt, _ in events:
            val = int.from_bytes(evt, "big")
            derot = rot_right(val, r)
            f0 = extract_field(derot, 0, 9)
            f3 = extract_field(derot, 27, 9)
            lo7 = f0 & 0x7F
            lo4 = f3 & 0xF
            if 35 <= lo7 <= 81:
                gm_hits += 1
            if lo4 in (0, 1, 2, 4, 8):
                beat_hits += 1
        dp = gm_hits / len(events)
        bp = beat_hits / len(events)
        joint = dp * bp
        if joint > best_joint:
            best_joint = joint
            best_r = r
        results.append((r, dp, bp, joint))

    # Show top 10
    results.sort(key=lambda x: -x[3])
    print(f"\n  {'R':>3} {'Drum%':>7} {'Beat%':>7} {'Joint':>7}")
    for r, dp, bp, j in results[:15]:
        marker = " <<<" if r == best_r else ""
        print(f"  {r:>3} {dp*100:>6.1f}% {bp*100:>6.1f}% {j*100:>6.1f}%{marker}")

    # ============================================================
    # TEST 2: Alternative field widths with R=9
    # ============================================================
    print(f"\n{'='*70}")
    print("  TEST 2: ALTERNATIVE FIELD WIDTHS (R=9)")
    print(f"{'='*70}")

    layouts = [
        ("6×9+2", [9, 9, 9, 9, 9, 9, 2]),
        ("7+7+12+12+7+9+2", [7, 7, 12, 12, 7, 9, 2]),
        ("8+8+10+10+10+8+2", [8, 8, 10, 10, 10, 8, 2]),
        ("7+7+7+12+12+7+4", [7, 7, 7, 12, 12, 7, 4]),
        ("9+12+12+12+9+2", [9, 12, 12, 12, 9, 2]),
        ("9+11+12+12+10+2", [9, 11, 12, 12, 10, 2]),
        ("8+12+12+12+12", [8, 12, 12, 12, 12]),
        ("7+12+12+12+7+6", [7, 12, 12, 12, 7, 6]),
    ]

    for name, widths in layouts:
        print(f"\n  Layout: {name} (sum={sum(widths)})")
        # Extract first field for each event and check drum validity
        gm_hits = 0
        vel_reasonable = 0
        for _, _, evt, _ in events:
            val = int.from_bytes(evt, "big")
            derot = rot_right(val, 9)
            pos = 0
            fields = []
            for w in widths:
                f = extract_field(derot, pos, w)
                fields.append(f)
                pos += w
            # First field = note candidate
            note_field = fields[0]
            max_note = (1 << widths[0]) - 1
            if widths[0] <= 7:
                lo7 = note_field
            elif widths[0] <= 8:
                lo7 = note_field & 0x7F
            else:
                lo7 = note_field & 0x7F
            if 35 <= lo7 <= 81:
                gm_hits += 1
            # Last substantial field = velocity/gate candidate
            last_field = fields[-1] if widths[-1] >= 7 else fields[-2]
            last_w = widths[-1] if widths[-1] >= 7 else widths[-2]
            if 1 <= (last_field & 0x7F) <= 127:
                vel_reasonable += 1

        print(f"    F0 lo7 in GM drums: {gm_hits}/{len(events)} ({100*gm_hits/len(events):.0f}%)")
        print(f"    Last field lo7 reasonable: {vel_reasonable}/{len(events)}")

        # Show first 3 events decoded
        for idx in range(min(3, len(events))):
            _, _, evt, _ = events[idx]
            val = int.from_bytes(evt, "big")
            derot = rot_right(val, 9)
            pos = 0
            fields = []
            for w in widths:
                f = extract_field(derot, pos, w)
                fields.append(f)
                pos += w
            print(f"    evt[{idx}]: {' '.join(f'{f:>{max(3,w//3+2)}}' for f, w in zip(fields, widths))}")

    # ============================================================
    # TEST 3: Position ordering within bars
    # ============================================================
    print(f"\n{'='*70}")
    print("  TEST 3: EVENT ORDERING WITHIN SEGMENTS (R=9)")
    print(f"{'='*70}")

    # For each segment, show events in order with their F1-F4 "position fingerprint"
    segs = defaultdict(list)
    for seg_idx, evt_idx, evt, header in events:
        val = int.from_bytes(evt, "big")
        derot = rot_right(val, 9)
        f0 = extract_field(derot, 0, 9)
        f1 = extract_field(derot, 9, 9)
        f2 = extract_field(derot, 18, 9)
        f3 = extract_field(derot, 27, 9)
        f4 = extract_field(derot, 36, 9)
        f5 = extract_field(derot, 45, 9)
        rem = derot & 0x3
        segs[seg_idx].append((evt_idx, f0, f1, f2, f3, f4, f5, rem))

    for seg_idx in sorted(segs.keys())[:5]:
        evts = segs[seg_idx]
        print(f"\n  Segment {seg_idx} ({len(evts)} events):")
        print(f"  {'#':>2} {'F0':>5} {'Note':>10} {'F1':>4} {'F2':>4} {'F3':>4} {'F4':>4} {'F5':>4} {'R':>1}")
        for evt_idx, f0, f1, f2, f3, f4, f5, rem in evts:
            lo7 = f0 & 0x7F
            name = GM_DRUM_NAMES.get(lo7, f"n{lo7}")[:10]
            print(f"  {evt_idx:>2} {f0:>5} {name:>10} {f1:>4} {f2:>4} {f3:>4} {f4:>4} {f5:>4} {rem:>1}")

    # ============================================================
    # TEST 4: F5 as gate time — physical check
    # ============================================================
    print(f"\n{'='*70}")
    print("  TEST 4: F5 AS GATE TIME (ticks @ 480ppq)")
    print(f"{'='*70}")

    # Collect F5 by note lo7
    note_f5 = defaultdict(list)
    for _, _, evt, _ in events:
        val = int.from_bytes(evt, "big")
        derot = rot_right(val, 9)
        f0 = extract_field(derot, 0, 9)
        f5 = extract_field(derot, 45, 9)
        lo7 = f0 & 0x7F
        note_f5[lo7].append(f5)

    bpm = 155  # SGT style tempo
    tick_ms = 60000 / bpm / 480  # ms per tick
    print(f"\n  Assuming {bpm} BPM → 1 tick = {tick_ms:.2f}ms, 1 beat = {60000/bpm:.0f}ms")
    print(f"\n  {'Note':>12} {'lo7':>4} {'F5 avg':>7} {'F5 min':>7} {'F5 max':>7} "
          f"{'ms avg':>7} {'Physical?':>10}")

    for note in sorted(note_f5.keys()):
        vals = note_f5[note]
        name = GM_DRUM_NAMES.get(note, f"n{note}")[:12]
        avg = sum(vals) / len(vals)
        mn = min(vals)
        mx = max(vals)
        ms_avg = avg * tick_ms
        # Physical reasonableness
        if note in (35, 36):  # Kick
            phys = "OK" if 200 < ms_avg < 800 else "?"
        elif note in (42, 44):  # HH closed/pedal
            phys = "OK" if 5 < ms_avg < 100 else "?"
        elif note in (46,):  # HH open
            phys = "OK" if 20 < ms_avg < 300 else "?"
        elif note in (38, 40):  # Snare
            phys = "OK" if 50 < ms_avg < 400 else "?"
        elif note in (49, 51, 57):  # Cymbal
            phys = "OK" if 5 < ms_avg < 600 else "?"
        else:
            phys = "-"
        print(f"  {name:>12} {note:>4} {avg:>7.1f} {mn:>7} {mx:>7} {ms_avg:>7.1f} {phys:>10}")

    # ============================================================
    # TEST 5: Try bit-reversed or nibble-swapped field extraction
    # ============================================================
    print(f"\n{'='*70}")
    print("  TEST 5: POSITION ENCODING — BIT PATTERNS")
    print(f"{'='*70}")

    # For events known to be at beat 1 (first event in bar), check F1-F4 bit patterns
    # versus events later in the bar
    print(f"\n  Comparing 'beat 1' events (first in segment) vs 'later' events:")
    beat1_f1f4 = []
    later_f1f4 = []
    for seg_idx, evt_idx, evt, _ in events:
        val = int.from_bytes(evt, "big")
        derot = rot_right(val, 9)
        f1 = extract_field(derot, 9, 9)
        f2 = extract_field(derot, 18, 9)
        f3 = extract_field(derot, 27, 9)
        f4 = extract_field(derot, 36, 9)
        if evt_idx == 0:
            beat1_f1f4.append((f1, f2, f3, f4))
        else:
            later_f1f4.append((f1, f2, f3, f4))

    # Average values
    if beat1_f1f4:
        avg1 = [sum(x[i] for x in beat1_f1f4)/len(beat1_f1f4) for i in range(4)]
        print(f"  Beat1 avg: F1={avg1[0]:.1f} F2={avg1[1]:.1f} F3={avg1[2]:.1f} F4={avg1[3]:.1f}")
    if later_f1f4:
        avg2 = [sum(x[i] for x in later_f1f4)/len(later_f1f4) for i in range(4)]
        print(f"  Later avg: F1={avg2[0]:.1f} F2={avg2[1]:.1f} F3={avg2[2]:.1f} F4={avg2[3]:.1f}")

    # ============================================================
    # TEST 6: Are events actually sorted by some combined key?
    # ============================================================
    print(f"\n{'='*70}")
    print("  TEST 6: EVENT SORT ORDER — COMBINED KEYS")
    print(f"{'='*70}")

    # Try various combined keys to see if events are sorted
    for seg_idx in sorted(segs.keys())[:3]:
        evts = segs[seg_idx]
        print(f"\n  Segment {seg_idx}:")

        # Key 1: F1*512+F2 (first 18 bits of position)
        k1 = [f1*512+f2 for _, _, f1, f2, f3, f4, f5, rem in evts]
        mono1 = sum(1 for i in range(len(k1)-1) if k1[i+1] >= k1[i])

        # Key 2: F3*512+F4 (second 18 bits of position)
        k2 = [f3*512+f4 for _, _, f1, f2, f3, f4, f5, rem in evts]
        mono2 = sum(1 for i in range(len(k2)-1) if k2[i+1] >= k2[i])

        # Key 3: Just F5
        k3 = [f5 for _, _, f1, f2, f3, f4, f5, rem in evts]
        mono3 = sum(1 for i in range(len(k3)-1) if k3[i+1] >= k3[i])

        # Key 4: F0 (note order)
        k4 = [f0 for _, f0, f1, f2, f3, f4, f5, rem in evts]
        mono4 = sum(1 for i in range(len(k4)-1) if k4[i+1] >= k4[i])

        n = len(evts) - 1 if len(evts) > 1 else 1
        print(f"    F1F2 monotonic: {mono1}/{n}")
        print(f"    F3F4 monotonic: {mono2}/{n}")
        print(f"    F5 monotonic:   {mono3}/{n}")
        print(f"    F0 monotonic:   {mono4}/{n}")

    # ============================================================
    # TEST 7: Does the HEADER encode velocity for each event?
    # ============================================================
    print(f"\n{'='*70}")
    print("  TEST 7: HEADER ANALYSIS — VELOCITY TABLE?")
    print(f"{'='*70}")

    # For each segment, decode header as various field widths
    seen_headers = {}
    for seg_idx, evt_idx, evt, header in events:
        if seg_idx not in seen_headers:
            seen_headers[seg_idx] = (header, 0)
        seen_headers[seg_idx] = (header, seen_headers[seg_idx][1] + 1)

    for seg_idx, (header, nevt) in sorted(seen_headers.items())[:5]:
        hval = int.from_bytes(header, "big")
        # 13 bytes = 104 bits → 11×9+5 or 8×13 or 13×8
        h9 = [(hval >> (104 - (i+1)*9)) & 0x1FF for i in range(11)]
        # Try 8-bit fields: 13 bytes = 13 values
        h8 = list(header)
        # Try 7-bit fields (like MIDI SysEx encoding): 104/7 = 14.8
        h7 = [(hval >> (104 - (i+1)*7)) & 0x7F for i in range(14)]

        print(f"\n  Segment {seg_idx} ({nevt} events):")
        print(f"    Raw:  {header.hex()}")
        print(f"    8-bit: {h8}")
        print(f"    9-bit: {h9}")
        print(f"    7-bit: {h7}")

        # Check if header bytes 1-N correlate with event count
        # (a velocity table would have one entry per event)


if __name__ == "__main__":
    main()
