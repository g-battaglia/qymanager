#!/usr/bin/env python3
"""
Map 56-bit lane data to ground truth velocity patterns.

Focus on bars where lane model works perfectly (seg 4, seg 5 from raw =
"Bar 3" and "Bar 4" from extract_bars).

Key question: Within the 56 derotated bits of an HH lane event, HOW are
the 8 per-beat velocities encoded?

Hypotheses:
A) 8 × 7-bit velocities (exactly 56 bits)
B) Beat pattern mask + template velocity
C) F3/F4 encode beat pattern, velocity is in F0+remainder
D) Entirely different decomposition
"""

import json
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qymanager.formats.qy70.sysex_parser import SysExParser
from midi_tools.event_decoder import rot_right, extract_9bit, nn


def load_syx_track(syx_path, section=0, track=0):
    parser = SysExParser()
    messages = parser.parse_file(syx_path)
    al = section * 8 + track
    data = b""
    for m in messages:
        if m.is_style_data and m.address_low == al:
            if m.decoded_data is not None:
                data += m.decoded_data
    return data


def load_gt_rhy1(json_path, bpm=120.0):
    """Load GT and organize by bar and instrument."""
    with open(json_path) as f:
        capture = json.load(f)

    rhy1_notes = []
    for evt in capture["events"]:
        d = evt["data"]
        if len(d) == 3:
            ch = d[0] & 0x0F
            msg = d[0] & 0xF0
            if ch == 8 and msg == 0x90 and d[2] > 0:
                rhy1_notes.append({"t": evt["t"], "note": d[1], "vel": d[2]})

    if not rhy1_notes:
        return {}

    bar_dur = 60.0 / bpm * 4
    t0 = rhy1_notes[0]["t"]

    bars = {}
    for n in rhy1_notes:
        dt = n["t"] - t0
        bar_idx = int(dt / bar_dur)
        tick = (dt - bar_idx * bar_dur) / (60.0 / bpm) * 480
        if bar_idx not in bars:
            bars[bar_idx] = []
        bars[bar_idx].append({"note": n["note"], "vel": n["vel"], "tick": tick})

    return bars


def decode_at_r(evt_bytes, r_val):
    val = int.from_bytes(evt_bytes, "big")
    derot = rot_right(val, r_val)
    fields = [extract_9bit(derot, i) for i in range(6)]
    rem = derot & 0x3
    return {"derot": derot, "fields": fields, "rem": rem,
            "note": fields[0] & 0x7F}


def bits56(val):
    return format(val, "056b")


def split_7bit(val_56bit):
    """Split 56-bit value into 8 × 7-bit values."""
    vals = []
    for i in range(8):
        shift = 56 - (i + 1) * 7
        vals.append((val_56bit >> shift) & 0x7F)
    return vals


def main():
    syx_path = "data/qy70_sysx/P -  Summer - 20231101.syx"
    gt_path = "midi_tools/captured/summer_playback_s25.json"

    data = load_syx_track(syx_path, section=0, track=0)

    # Parse raw segments
    event_data = data[28:]
    delim_pos = [i for i, b in enumerate(event_data) if b in (0xDC, 0x9E)]
    prev = 0
    segments = []
    for dp in delim_pos:
        segments.append(event_data[prev:dp])
        prev = dp + 1
    segments.append(event_data[prev:])

    # Filter to segments with real data
    real_segs = []
    for seg in segments:
        if len(seg) >= 20:
            header = seg[:13]
            evts = [seg[13+i*7:13+(i+1)*7] for i in range((len(seg)-13)//7)]
            real_segs.append((header, evts))

    print(f"Real segments: {len(real_segs)}")
    for i, (h, evts) in enumerate(real_segs):
        print(f"  Seg {i}: {len(evts)} events, header={h[:4].hex()}")

    gt_bars = load_gt_rhy1(gt_path)
    print(f"GT bars: {sorted(gt_bars.keys())}")

    # GT has period-4 repetition. Map GT bar patterns to segments.
    # Pattern 0: bars 0,4,8  → GT velocities are identical
    # Pattern 1: bars 1,5,9
    # Pattern 2: bars 2,6,10
    # Pattern 3: bars 3,7,11  → has 4 snare hits (fill variation)

    gt_patterns = {}
    for pattern_idx in range(4):
        # Average across repetitions
        example_bar = gt_bars.get(pattern_idx, [])
        instruments = {}
        for n in sorted(example_bar, key=lambda x: x["tick"]):
            instruments.setdefault(n["note"], []).append(n["vel"])
        gt_patterns[pattern_idx] = instruments

    print("\nGT patterns:")
    for pi, instr in gt_patterns.items():
        print(f"  Pattern {pi}:")
        for note, vels in sorted(instr.items()):
            print(f"    {nn(note)}({note}): {vels}")

    # LANE_R values for the 4 instrument positions
    LANE_R = [9, 22, 12, 53]
    LANE_NAMES = ["HH", "Snare", "HH2", "Kick"]

    # Focus on segments where lane model works: seg 3 and seg 4
    # (from raw: seg 4 and seg 5, which are "Bar 3" and "Bar 4" in extract_bars)
    working_segs = [3, 4]  # 0-indexed within real_segs

    print("\n" + "=" * 80)
    print("HYPOTHESIS A: 56 bits = 8 × 7-bit velocity values")
    print("=" * 80)

    for seg_idx in range(min(6, len(real_segs))):
        header, evts = real_segs[seg_idx]
        if len(evts) < 4:
            continue

        print(f"\n--- Segment {seg_idx} ---")
        for lane_idx in range(4):
            r = LANE_R[lane_idx]
            d = decode_at_r(evts[lane_idx], r)
            vals_7bit = split_7bit(d["derot"])

            print(f"  {LANE_NAMES[lane_idx]:6s} R={r:2d}: note={d['note']:3d} "
                  f"7bit-split={vals_7bit}")

    # For working segments, compare 7-bit splits with GT velocities
    print("\n" + "=" * 80)
    print("CORRELATION: 7-bit splits vs GT HH velocities")
    print("=" * 80)

    for seg_idx in working_segs:
        if seg_idx >= len(real_segs):
            continue
        header, evts = real_segs[seg_idx]
        if len(evts) < 4:
            continue

        # HH lane (R=9)
        d = decode_at_r(evts[0], 9)
        vals_7bit = split_7bit(d["derot"])

        print(f"\n  Seg {seg_idx} HH (R=9):")
        print(f"    7-bit split: {vals_7bit}")

        # Try to match to GT patterns
        for pi in range(4):
            gt_hh = gt_patterns[pi].get(42, [])
            if gt_hh:
                print(f"    GT pattern {pi} HH vel: {gt_hh}")

                # Try: direct mapping
                if len(gt_hh) == 8:
                    diffs = [abs(a - b) for a, b in zip(vals_7bit, gt_hh)]
                    print(f"      Direct diff: {diffs} (sum={sum(diffs)})")

                    # Try: 127 - x
                    inv = [127 - v for v in vals_7bit]
                    diffs_inv = [abs(a - b) for a, b in zip(inv, gt_hh)]
                    print(f"      Inverted:    {inv} diff={diffs_inv} (sum={sum(diffs_inv)})")

                    # Try: x + offset
                    if vals_7bit[0] != 0:
                        offset = gt_hh[0] - vals_7bit[0]
                        shifted = [v + offset for v in vals_7bit]
                        diffs_shift = [abs(a - b) for a, b in zip(shifted, gt_hh)]
                        print(f"      Shifted(+{offset}): {shifted} diff={diffs_shift} (sum={sum(diffs_shift)})")

    # Try different bit decompositions
    print("\n" + "=" * 80)
    print("HYPOTHESIS B: Different bit decompositions")
    print("=" * 80)

    for seg_idx in working_segs:
        if seg_idx >= len(real_segs):
            continue
        header, evts = real_segs[seg_idx]

        d = decode_at_r(evts[0], 9)
        val = d["derot"]
        print(f"\n  Seg {seg_idx} HH derotated: {bits56(val)}")
        print(f"  = 0x{val:014x}")

        # Try 4-bit nibbles (14 nibbles)
        nibbles = [(val >> (52 - i*4)) & 0xF for i in range(14)]
        print(f"  4-bit nibbles: {nibbles}")

        # Try 8-bit bytes (7 bytes)
        bytez = [(val >> (48 - i*8)) & 0xFF for i in range(7)]
        print(f"  8-bit bytes:   {bytez}")

        # Standard 9-bit fields
        fields = [extract_9bit(val, i) for i in range(6)]
        rem = val & 0x3
        print(f"  9-bit fields:  F0={fields[0]} F1={fields[1]} F2={fields[2]} "
              f"F3={fields[3]} F4={fields[4]} F5={fields[5]} rem={rem}")

        # Now check: do F3/F4 change between bars while F0/F1/F2/F5 stay stable?
        # This would suggest F3/F4 encode the varying data (velocity pattern)
        print(f"\n  Field stability across segments for HH (R=9):")
        for fn in range(6):
            vals = []
            for si in range(min(6, len(real_segs))):
                if len(real_segs[si][1]) >= 1:
                    d2 = decode_at_r(real_segs[si][1][0], 9)
                    vals.append(d2["fields"][fn])
            unique = len(set(vals))
            stable = "STABLE" if unique == 1 else f"VARIES ({unique} values)"
            print(f"    F{fn}: {vals} — {stable}")

    # Hypothesis C: Look at ALL events across ALL segments
    # and try to find if there's a "velocity table" somewhere
    print("\n" + "=" * 80)
    print("FULL 56-BIT ANALYSIS FOR HH LANE (R=9) ACROSS ALL SEGMENTS")
    print("=" * 80)

    print(f"\n  {'Seg':>3} | {'F0':>5} {'F1':>5} {'F2':>5} {'F3':>5} "
          f"{'F4':>5} {'F5':>5} {'r':>1} | {'n':>3} | 7-bit split")
    print(f"  {'---':>3} | {'-'*5} {'-'*5} {'-'*5} {'-'*5} "
          f"{'-'*5} {'-'*5} {'-':>1} | {'-'*3} | {'-'*30}")

    for si in range(min(6, len(real_segs))):
        if not real_segs[si][1]:
            continue
        d = decode_at_r(real_segs[si][1][0], 9)
        v7 = split_7bit(d["derot"])
        print(f"  {si:3d} | {d['fields'][0]:5d} {d['fields'][1]:5d} "
              f"{d['fields'][2]:5d} {d['fields'][3]:5d} "
              f"{d['fields'][4]:5d} {d['fields'][5]:5d} {d['rem']:1d} | "
              f"{d['note']:3d} | {v7}")

    # GT velocity comparison for each bar
    print(f"\n  GT HH velocities per bar pattern:")
    for pi in range(4):
        gt_hh = gt_patterns[pi].get(42, [])
        print(f"    Pattern {pi}: {gt_hh}")

    # Hypothesis D: Maybe the beat-level data IS the fields, and each
    # 9-bit field corresponds to TWO beats? 4 beats = F1+F2 pairs?
    print("\n" + "=" * 80)
    print("HYPOTHESIS D: F1-F4 encode 4 beat-pairs? (2 beats per field)")
    print("=" * 80)

    for seg_idx in working_segs:
        if seg_idx >= len(real_segs):
            continue
        header, evts = real_segs[seg_idx]
        if len(evts) < 4:
            continue

        print(f"\n  Seg {seg_idx}:")
        for lane_idx in range(4):
            d = decode_at_r(evts[lane_idx], LANE_R[lane_idx])
            f = d["fields"]
            # F1-F4: 4 × 9 bits = 36 bits = could encode 4 × 9-bit parameters
            # or 8 × 4.5 bits
            # F1 top bits = beat, F1 lower bits = position detail
            # What if each 9-bit field F1-F4 encodes velocity for 2 beats?
            # [4-bit vel beat A][4-bit vel beat B][1 spare bit]
            for fi in range(1, 5):
                hi4 = (f[fi] >> 5) & 0xF
                lo4 = (f[fi] >> 1) & 0xF
                spare = f[fi] & 1
                vel_hi = max(1, 127 - hi4 * 8)
                vel_lo = max(1, 127 - lo4 * 8)
                print(f"    {LANE_NAMES[lane_idx]} F{fi}={f[fi]:3d}: "
                      f"hi4={hi4:2d}(vel≈{vel_hi:3d}) lo4={lo4:2d}(vel≈{vel_lo:3d}) "
                      f"spare={spare}")

    # Hypothesis E: Maybe it's NOT per-beat velocity but a
    # RHYTHMIC PATTERN encoded in the lane
    print("\n" + "=" * 80)
    print("HYPOTHESIS E: Rhythmic pattern bits")
    print("=" * 80)
    print("If 8 HH hits per bar = 8 eighth notes, and we need:")
    print("  - 1 bit per eighth note (hit/rest) = 8 bits")
    print("  - 7 bits per velocity = 56 bits")
    print("Or: pattern + velocity template?")

    for seg_idx in working_segs:
        if seg_idx >= len(real_segs):
            continue
        header, evts = real_segs[seg_idx]

        d_hh = decode_at_r(evts[0], 9)
        print(f"\n  Seg {seg_idx} HH:")
        # Maybe F3+F4 = rhythmic pattern (18 bits), F5 = gate, F0 = note, F1+F2 = ???
        # 18 bits for rhythm: could encode 8 hits with some extra info
        f = d_hh["fields"]
        pattern_18 = ((f[3] & 0x1FF) << 9) | (f[4] & 0x1FF)
        print(f"    F3|F4 (18 bits): {pattern_18:018b} = {pattern_18}")
        # What if each pair of bits = one eighth note position?
        pairs = [(pattern_18 >> (16 - i*2)) & 3 for i in range(9)]
        print(f"    As 9×2-bit pairs: {pairs}")
        # Or 6×3-bit groups
        triples = [(pattern_18 >> (15 - i*3)) & 7 for i in range(6)]
        print(f"    As 6×3-bit groups: {triples}")

    # Final: Show the KNOWN correct bar (seg 4) in maximum detail
    print("\n" + "=" * 80)
    print("DETAILED ANATOMY OF WORKING BAR (Seg 3 = extract_bars Bar 3)")
    print("=" * 80)

    if len(real_segs) > 3:
        header, evts = real_segs[3]
        print(f"Header: {header.hex()}")

        # Decode header
        hval = int.from_bytes(header, "big")
        hfields = [(hval >> (104 - (i+1)*9)) & 0x1FF for i in range(11)]
        print(f"Header fields (11×9-bit): {hfields}")

        for lane_idx in range(min(4, len(evts))):
            r = LANE_R[lane_idx]
            raw = evts[lane_idx]
            d = decode_at_r(raw, r)
            f = d["fields"]

            print(f"\n  {LANE_NAMES[lane_idx]} (R={r}):")
            print(f"    Raw: {raw.hex()}")
            print(f"    Derotated: {bits56(d['derot'])}")
            print(f"    F0={f[0]:3d} (0x{f[0]:03x}) = note {d['note']}, "
                  f"bit8={(f[0]>>8)&1} bit7={(f[0]>>7)&1}")
            print(f"    F1={f[1]:3d} (0x{f[1]:03x}) = beat {f[1]>>7}, "
                  f"clock {((f[1]&0x7F)<<2)|(f[2]>>7)}")
            print(f"    F2={f[2]:3d} (0x{f[2]:03x})")
            print(f"    F3={f[3]:3d} (0x{f[3]:03x}) = "
                  f"{format(f[3],'09b')}")
            print(f"    F4={f[4]:3d} (0x{f[4]:03x}) = "
                  f"{format(f[4],'09b')}")
            print(f"    F5={f[5]:3d} (0x{f[5]:03x}) = gate?")
            print(f"    rem={d['rem']}")

            # GT for this lane
            inst_note = d["note"]
            gt = gt_patterns.get(0, {}).get(inst_note, [])
            if not gt:
                gt = gt_patterns.get(3, {}).get(inst_note, [])
            if gt:
                print(f"    GT velocities: {gt}")

    print("\nDone.")


if __name__ == "__main__":
    main()
