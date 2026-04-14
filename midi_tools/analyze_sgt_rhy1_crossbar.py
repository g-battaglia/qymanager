#!/usr/bin/env python3
"""Apply cross-bar brute-force analysis to SGT-RHY1 (ground_truth_style.syx).

Same methodology as USER-RHY1: for each event position, find R values
that give consistent notes across bars. Then compare R patterns.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qymanager.formats.qy70.sysex_parser import SysExParser
from midi_tools.event_decoder import rot_right, extract_9bit

GM_DRUMS = {
    35: 'Kick2', 36: 'Kick1', 37: 'SStick', 38: 'Snare1', 39: 'Clap',
    40: 'ElSnare', 41: 'LFlrTom', 42: 'HHclose', 43: 'HFlrTom',
    44: 'HHpedal', 45: 'LowTom', 46: 'HHopen', 47: 'LMidTom',
    48: 'HiMidTom', 49: 'Crash1', 50: 'HiTom', 51: 'Ride1',
    52: 'Chinese', 53: 'RideBell', 54: 'Tamb', 55: 'Splash',
    56: 'Cowbell', 57: 'Crash2',
}


def get_track(syx_path, al_target):
    parser = SysExParser()
    messages = parser.parse_file(syx_path)
    data = b''
    for m in messages:
        if m.is_style_data and m.decoded_data and m.address_low == al_target:
            data += m.decoded_data
    return data


def get_segments(data):
    event_data = data[28:]
    delim_pos = [i for i, b in enumerate(event_data) if b in (0xDC, 0x9E)]
    segments = []
    prev = 0
    for dp in delim_pos:
        seg = event_data[prev:dp]
        if len(seg) >= 20:
            header = seg[:13]
            events = []
            for i in range((len(seg) - 13) // 7):
                evt = seg[13 + i*7:13 + (i+1)*7]
                if len(evt) == 7:
                    events.append(evt)
            segments.append((header, events))
        prev = dp + 1
    seg = event_data[prev:]
    if len(seg) >= 20:
        header = seg[:13]
        events = []
        for i in range((len(seg) - 13) // 7):
            evt = seg[13 + i*7:13 + (i+1)*7]
            if len(evt) == 7:
                events.append(evt)
        segments.append((header, events))
    return segments


def decode_at_r(evt_bytes, r_value):
    val = int.from_bytes(evt_bytes, "big")
    derot = rot_right(val, r_value)
    f0 = extract_9bit(derot, 0)
    note = f0 & 0x7F
    bit8 = (f0 >> 8) & 1
    bit7 = (f0 >> 7) & 1
    rem = derot & 0x3
    vel_code = (bit8 << 3) | (bit7 << 2) | rem
    velocity = max(1, 127 - vel_code * 8)
    f1 = extract_9bit(derot, 1)
    f2 = extract_9bit(derot, 2)
    beat = f1 >> 7
    clock = ((f1 & 0x7F) << 2) | (f2 >> 7)
    tick = beat * 480 + clock
    return {"note": note, "velocity": velocity, "tick": tick,
            "f0": f0, "valid": 13 <= note <= 87}


def main():
    data = get_track("midi_tools/captured/ground_truth_style.syx", 0)
    if not data:
        print("SGT-RHY1 not found")
        return

    segments = get_segments(data)
    print(f"SGT-RHY1: {len(data)}B, {len(segments)} segments")

    # Overview
    print(f"\n{'='*70}")
    print(f"  SEGMENT OVERVIEW")
    print(f"{'='*70}")
    for si, (header, events) in enumerate(segments):
        print(f"  Seg {si}: {len(events)} events, header={header[:4].hex()}")

    # Cross-bar analysis: for each position, find most consistent note per R
    print(f"\n{'='*70}")
    print(f"  CROSS-BAR CONSISTENCY")
    print(f"{'='*70}")

    # Group events by position across ALL segments
    max_events = max(len(evts) for _, evts in segments)
    for ei in range(min(6, max_events)):
        events_at_pos = []
        for si, (_, evts) in enumerate(segments):
            if ei < len(evts):
                events_at_pos.append((si, evts[ei]))

        if not events_at_pos:
            continue

        print(f"\n  Event position {ei} ({len(events_at_pos)} bars):")

        # Find R with most consistent note
        best_results = []
        for r in range(56):
            note_counts = {}
            for si, evt in events_at_pos:
                d = decode_at_r(evt, r)
                if d["valid"]:
                    n = d["note"]
                    note_counts[n] = note_counts.get(n, 0) + 1

            for n, cnt in note_counts.items():
                if cnt >= max(2, len(events_at_pos) // 3):
                    nname = GM_DRUMS.get(n, f"n{n}")
                    best_results.append((cnt, r, n, nname))

        # Sort by count descending
        best_results.sort(key=lambda x: (-x[0], x[1]))
        shown = set()
        for cnt, r, n, nname in best_results[:10]:
            if n not in shown:
                shown.add(n)
                pct = cnt * 100 // len(events_at_pos)
                print(f"    R={r:2d}: {nname:>10s} n={n:3d} in {cnt}/{len(events_at_pos)} "
                      f"bars ({pct}%)")

    # Now decode with USER-RHY1 R values to see if they work
    print(f"\n{'='*70}")
    print(f"  DECODE WITH USER-RHY1 R VALUES (9,22,12,53)")
    print(f"{'='*70}")

    user_r = {0: 9, 1: 22, 2: 12, 3: 53, 4: 33, 5: 37}

    for si, (header, events) in enumerate(segments):
        print(f"\n  Segment {si} ({len(events)} events):")
        for ei, evt in enumerate(events):
            r = user_r.get(ei, 9)
            d = decode_at_r(evt, r)
            n = d["note"]
            nname = GM_DRUMS.get(n, f"n{n}")
            valid = "OK" if d["valid"] else "BAD"
            print(f"    e{ei}: R={r:2d} → {nname:>10s} n={n:3d} v={d['velocity']:3d} "
                  f"t={d['tick']:4d} [{valid}]")

    # Also: find OPTIMAL R per position for SGT
    print(f"\n{'='*70}")
    print(f"  OPTIMAL R PER POSITION (SGT-specific)")
    print(f"{'='*70}")

    for ei in range(min(6, max_events)):
        events_at_pos = []
        for si, (_, evts) in enumerate(segments):
            if ei < len(evts):
                events_at_pos.append((si, evts[ei]))

        if not events_at_pos:
            continue

        best_r = -1
        best_score = 0
        best_note = -1

        for r in range(56):
            note_counts = {}
            for si, evt in events_at_pos:
                d = decode_at_r(evt, r)
                if d["valid"]:
                    n = d["note"]
                    note_counts[n] = note_counts.get(n, 0) + 1
            for n, cnt in note_counts.items():
                if cnt > best_score:
                    best_score = cnt
                    best_r = r
                    best_note = n

        nname = GM_DRUMS.get(best_note, f"n{best_note}")
        print(f"  e{ei}: Best R={best_r:2d} → {nname}({best_note}) "
              f"({best_score}/{len(events_at_pos)} bars)")


if __name__ == "__main__":
    main()
