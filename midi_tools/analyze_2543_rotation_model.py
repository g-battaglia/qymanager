#!/usr/bin/env python3
"""CRITICAL TEST: Constant vs Cumulative rotation for 2543 encoding.

Previous "proof" of constant rotation was INCONCLUSIVE:
- 9 byte-identical events were ALL at position e0 in their segments
- At e0, constant R=9 and cumulative R=9*(0+1)=9 give THE SAME RESULT
- The proof didn't actually distinguish between the two models

This script compares:
  Model A: Constant R=9 (same rotation for every event)
  Model B: Cumulative R=9*(i+1) (rotation increases with event index)
  Model C: Cumulative R=9*i (zero-based, e0 gets R=0)

Metrics: valid drum notes (13-87), tick monotonicity, musical coherence.
"""

import sys, os
from collections import Counter, defaultdict
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from qymanager.formats.qy70.sysex_parser import SysExParser

XG_RANGE = set(range(13, 88))
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
    82: "Shaker", 83: "JnglBell", 84: "BellTree", 85: "Castanets",
    86: "MuSurdo", 87: "OpSurdo",
}


def rot_right(val, shift, width=56):
    shift = shift % width
    return ((val >> shift) | (val << (width - shift))) & ((1 << width) - 1)

def f9(val, idx, total=56):
    shift = total - (idx + 1) * 9
    return (val >> shift) & 0x1FF if shift >= 0 else -1


def decode_with_r(evt_bytes, r_value):
    val = int.from_bytes(evt_bytes, "big")
    derot = rot_right(val, r_value)
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
    beat = f1 >> 7
    clock_9 = ((f1 & 0x7F) << 2) | (f2 >> 7)
    tick_9 = beat * 480 + clock_9
    return {
        'note': note, 'midi_vel': midi_vel, 'gate': f5, 'tick_9': tick_9,
        'f0': f0, 'f1': f1, 'f2': f2, 'f3': f3, 'f4': f4, 'f5': f5,
        'rem': rem, 'bit8': bit8, 'bit7': bit7,
        'vel_code': vel_code, 'beat': beat, 'clock_9': clock_9,
    }


def get_segments(syx_path, section, track):
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
    return segments


def evaluate_model(segments, r_func, model_name):
    """Evaluate a rotation model across all segments.
    r_func(event_index) returns the rotation value for that event.
    """
    total_events = 0
    valid_events = 0
    mono_pairs = 0
    mono_ok = 0
    all_decoded = []  # (seg_idx, evt_idx, decoded_dict)

    for seg_idx, seg in enumerate(segments):
        if len(seg) < 20:
            continue
        nevts = (len(seg) - 13) // 7
        seg_ticks = []
        for i in range(nevts):
            evt = seg[13 + i * 7: 13 + (i + 1) * 7]
            if len(evt) != 7:
                continue
            r_val = r_func(i)
            d = decode_with_r(evt, r_val)
            d['seg'] = seg_idx
            d['eidx'] = i
            all_decoded.append(d)
            total_events += 1
            if d['note'] in XG_RANGE:
                valid_events += 1
            seg_ticks.append(d['tick_9'])

        for i in range(len(seg_ticks) - 1):
            mono_pairs += 1
            if seg_ticks[i + 1] >= seg_ticks[i]:
                mono_ok += 1

    return {
        'name': model_name,
        'total': total_events,
        'valid': valid_events,
        'valid_pct': 100 * valid_events / total_events if total_events > 0 else 0,
        'mono_pct': 100 * mono_ok / mono_pairs if mono_pairs > 0 else 0,
        'decoded': all_decoded,
    }


def main():
    base = os.path.dirname(os.path.abspath(__file__))
    syx = os.path.join(base, "captured", "ground_truth_style.syx")
    segments = get_segments(syx, 0, 0)

    # ============================================================
    # 1. GLOBAL COMPARISON: 3 rotation models
    # ============================================================
    print(f"{'='*80}")
    print(f"  ROTATION MODEL COMPARISON (ground_truth_style.syx, RHY1)")
    print(f"{'='*80}")

    models = [
        ("Constant R=9", lambda i: 9),
        ("Cumulative R=9*(i+1)", lambda i: 9 * (i + 1)),
        ("Cumulative R=9*i", lambda i: 9 * i),
    ]

    results = []
    for name, r_func in models:
        result = evaluate_model(segments, r_func, name)
        results.append(result)
        print(f"\n  {name}:")
        print(f"    Events: {result['total']}")
        print(f"    Valid drum notes: {result['valid']}/{result['total']}"
              f" ({result['valid_pct']:.0f}%)")
        print(f"    Tick monotonicity: {result['mono_pct']:.0f}%")

    # Also test higher R values with cumulative
    for r_base in [7, 11, 13, 17, 23]:
        name = f"Cumulative R={r_base}*(i+1)"
        result = evaluate_model(segments, lambda i, r=r_base: r * (i + 1), name)
        print(f"\n  {name}:")
        print(f"    Valid: {result['valid']}/{result['total']} ({result['valid_pct']:.0f}%)"
              f"  Mono: {result['mono_pct']:.0f}%")

    # ============================================================
    # 2. PER-SEGMENT breakdown for top 2 models
    # ============================================================
    print(f"\n{'='*80}")
    print(f"  PER-SEGMENT BREAKDOWN: Constant vs Cumulative")
    print(f"{'='*80}")

    for seg_idx, seg in enumerate(segments):
        if len(seg) < 20:
            continue
        nevts = (len(seg) - 13) // 7
        if nevts == 0:
            continue

        const_valid = 0
        cum_valid = 0

        print(f"\n  Segment {seg_idx} ({nevts} events):")
        print(f"  {'idx':>3} | {'Constant R=9':>20} | {'Cumulative R=9*(i+1)':>24} | {'Winner':>8}")

        for i in range(nevts):
            evt = seg[13 + i * 7: 13 + (i + 1) * 7]
            if len(evt) != 7:
                continue
            dc = decode_with_r(evt, 9)
            dm = decode_with_r(evt, 9 * (i + 1))

            name_c = GM_DRUMS.get(dc['note'], 'n' + str(dc['note']))
            name_m = GM_DRUMS.get(dm['note'], 'n' + str(dm['note']))
            vc = dc['note'] in XG_RANGE
            vm = dm['note'] in XG_RANGE

            if vc:
                const_valid += 1
            if vm:
                cum_valid += 1

            if vc and not vm:
                winner = "CONST"
            elif vm and not vc:
                winner = "CUM"
            elif vc and vm:
                winner = "both"
            else:
                winner = "neither"

            print(f"  {i:>3} | {dc['note']:>3} {name_c:>10}"
                  f" {'✓' if vc else '✗'} |"
                  f" {dm['note']:>3} {name_m:>10}"
                  f" {'✓' if vm else '✗'} | {winner}")

        print(f"  Score: Constant {const_valid}/{nevts},"
              f" Cumulative {cum_valid}/{nevts}")

    # ============================================================
    # 3. Detailed cumulative decode — is it musically coherent?
    # ============================================================
    print(f"\n{'='*80}")
    print(f"  FULL CUMULATIVE DECODE — Sorted by position")
    print(f"{'='*80}")

    cum_result = results[1]  # Cumulative R=9*(i+1)
    by_seg = defaultdict(list)
    for d in cum_result['decoded']:
        by_seg[d['seg']].append(d)

    for seg_idx in sorted(by_seg.keys()):
        evts = by_seg[seg_idx]
        sorted_evts = sorted(evts, key=lambda d: (d['tick_9'], d['note']))

        print(f"\n  Segment {seg_idx} ({len(evts)} events):")
        print(f"  {'Beat':>4} {'Clock':>5} {'Tick':>5} | {'Note':>4} {'Drum':>10}"
              f" | {'Vel':>3} {'Gate':>4} | {'raw_order':>9}")

        for d in sorted_evts:
            name = GM_DRUMS.get(d['note'], 'n' + str(d['note']))[:10]
            valid = " " if d['note'] in XG_RANGE else "*"
            print(f"  {d['beat']:>4} {d['clock_9']:>5} {d['tick_9']:>5}"
                  f" | {d['note']:>4} {name:>10}"
                  f" | {d['midi_vel']:>3} {d['gate']:>4}"
                  f" | e{d['eidx']}{valid}")

    # ============================================================
    # 4. Check: simultaneous events (same tick) in cumulative model
    # ============================================================
    print(f"\n{'='*80}")
    print(f"  SIMULTANEOUS EVENTS (cumulative model)")
    print(f"{'='*80}")

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
                    GM_DRUMS.get(d['note'], 'n' + str(d['note']))
                    + f"(v{d['midi_vel']},g{d['gate']})"
                    for d in ds
                )
                print(f"    tick {tick}: {notes}")

    # ============================================================
    # 5. Velocity consistency check in cumulative model
    # ============================================================
    print(f"\n{'='*80}")
    print(f"  VELOCITY DISTRIBUTION (cumulative model)")
    print(f"{'='*80}")

    note_vels = defaultdict(list)
    for d in cum_result['decoded']:
        if d['note'] in XG_RANGE:
            name = GM_DRUMS.get(d['note'], 'n' + str(d['note']))
            note_vels[name].append(d['midi_vel'])

    for name in sorted(note_vels.keys()):
        vels = note_vels[name]
        print(f"  {name:>10}: {sorted(set(vels))}")

    # ============================================================
    # 6. ALL TRACKS with cumulative rotation
    # ============================================================
    print(f"\n{'='*80}")
    print(f"  ALL TRACKS: cumulative R=9*(i+1) validation")
    print(f"{'='*80}")

    track_names = ["RHY1", "RHY2", "BASS", "CHD1", "CHD2", "PAD", "PHR1", "PHR2"]
    for section in range(4):
        section_names = ["Main A", "Main B", "Fill AA", "Fill BB"]
        for track in range(8):
            segs = get_segments(syx, section, track)
            if not segs:
                continue
            # Constant
            rc = evaluate_model(segs, lambda i: 9, "const")
            # Cumulative
            rm = evaluate_model(segs, lambda i: 9 * (i + 1), "cum")
            if rc['total'] > 0:
                label = f"{section_names[section]} {track_names[track]}"
                delta = rm['valid'] - rc['valid']
                delta_str = f"+{delta}" if delta > 0 else str(delta)
                print(f"  {label:>15}: const={rc['valid']:>2}/{rc['total']}"
                      f" ({rc['valid_pct']:>3.0f}%)"
                      f"  cum={rm['valid']:>2}/{rm['total']}"
                      f" ({rm['valid_pct']:>3.0f}%)"
                      f"  Δ={delta_str}"
                      f"  mono: {rc['mono_pct']:.0f}% → {rm['mono_pct']:.0f}%")


if __name__ == "__main__":
    main()
