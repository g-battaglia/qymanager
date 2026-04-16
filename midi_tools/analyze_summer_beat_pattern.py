#!/usr/bin/env python3
"""
Test beat-pattern hypothesis for Summer RHY1 dense drum encoding.

HYPOTHESIS: Each 7-byte event encodes a full-bar beat pattern for ONE instrument.
The instrument is identified by EVENT POSITION (not F0 note field):
  e0 = HH (note 42), e1 = Snare (note 38), e2 = HH2 (variant), e3 = Kick (note 36)

The 56 bits, after derotation, contain 8 × 7-bit velocity values (one per 8th-note).
Velocity 0 = no hit, 1-127 = hit at that velocity.

This model DOESN'T require note 38 to be extractable from F0.
The R value is just a de-obfuscation key, and the note comes from position.

If this is true, the derotated 56 bits for e0 at R=9 should produce 8 velocities
that correlate with GT HH velocities.
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
    with open(json_path) as f:
        capture = json.load(f)
    bar_dur = 60.0 / bpm * 4
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
    t0 = rhy1_notes[0]["t"]
    bars = {}
    for n in rhy1_notes:
        dt = n["t"] - t0
        bar_idx = int(dt / bar_dur)
        eighth = round((dt - bar_idx * bar_dur) / (60.0 / bpm) * 2) / 2
        pos = int(eighth * 2)  # 0-7 for 8 eighth-note positions
        bars.setdefault(bar_idx, {}).setdefault(n["note"], {})[pos] = n["vel"]
    return bars


def extract_segments(data):
    event_data = data[28:]
    segments = []
    prev = 0
    for i, b in enumerate(event_data):
        if b in (0xDC, 0x9E):
            segments.append(event_data[prev:i])
            prev = i + 1
    if prev < len(event_data):
        segments.append(event_data[prev:])
    return segments


def split_7bit(val_56bit):
    """Split 56-bit value into 8 × 7-bit groups (MSB first)."""
    groups = []
    for i in range(8):
        shift = 49 - i * 7
        groups.append((val_56bit >> shift) & 0x7F)
    return groups


def split_8bit(val_56bit):
    """Split 56-bit value into 7 × 8-bit groups (MSB first)."""
    groups = []
    for i in range(7):
        shift = 48 - i * 8
        groups.append((val_56bit >> shift) & 0xFF)
    return groups


def correlate(a, b):
    """Simple correlation between two lists of numbers."""
    if len(a) != len(b) or len(a) < 2:
        return 0
    n = len(a)
    mean_a = sum(a) / n
    mean_b = sum(b) / n
    num = sum((a[i] - mean_a) * (b[i] - mean_b) for i in range(n))
    den_a = sum((a[i] - mean_a) ** 2 for i in range(n)) ** 0.5
    den_b = sum((b[i] - mean_b) ** 2 for i in range(n)) ** 0.5
    if den_a == 0 or den_b == 0:
        return 0
    return num / (den_a * den_b)


def main():
    syx_path = "data/qy70_sysx/P -  Summer - 20231101.syx"
    gt_path = "midi_tools/captured/summer_playback_s25.json"

    data = load_syx_track(syx_path, section=0, track=0)
    gt_bars = load_gt_rhy1(gt_path, bpm=120.0)
    segments = extract_segments(data)

    # Instrument mapping by event position
    LANE_NOTES = {0: 42, 1: 38, 2: 42, 3: 36}  # HH, Snare, HH(variant), Kick
    LANE_NAMES = {0: "HH", 1: "Snare", 2: "HH2", 3: "Kick"}

    print("=" * 80)
    print("BEAT PATTERN HYPOTHESIS TEST")
    print("56 bits = 8 × 7-bit velocity values for one instrument per bar")
    print("=" * 80)

    # =========================================================
    # TEST 1: Split derotated 56 bits into 8×7-bit groups
    # Compare against GT velocities
    # =========================================================
    print("\n--- TEST 1: 8×7-bit split at known R values ---")
    print("R values tested: [9, 22, 12, 53]")

    LANE_R = [9, 22, 12, 53]

    for seg_idx, seg in enumerate(segments):
        if len(seg) < 20:
            continue

        header = seg[:13]
        event_bytes = seg[13:]
        n_events = len(event_bytes) // 7

        gt_bar = seg_idx - 1
        gt = gt_bars.get(gt_bar, {})

        if not gt:
            print(f"\n  Seg {seg_idx} (GT bar {gt_bar}): no GT data")
            continue

        print(f"\n  Seg {seg_idx} (GT bar {gt_bar}):")

        for ei in range(min(4, n_events)):
            evt = event_bytes[ei*7:(ei+1)*7]
            val = int.from_bytes(evt, "big")
            r = LANE_R[ei]
            inst_note = LANE_NOTES[ei]
            lane_name = LANE_NAMES[ei]
            derot = rot_right(val, r)

            # Split into 8×7-bit
            vels_7bit = split_7bit(derot)

            # GT velocities for this instrument
            gt_inst = gt.get(inst_note, {})
            gt_vels = [gt_inst.get(pos, 0) for pos in range(8)]

            # Correlate
            corr = correlate(vels_7bit, gt_vels) if any(gt_vels) else 0

            print(f"    {lane_name:6s} e{ei} R={r:2d}: "
                  f"7bit={vels_7bit}")
            print(f"    {'':6s}        GT:  vel={gt_vels}")
            print(f"    {'':6s}        corr={corr:+.3f}")

    # =========================================================
    # TEST 2: Try ALL R values 0-55, find which gives best
    # correlation with GT for each event
    # =========================================================
    print("\n" + "=" * 80)
    print("TEST 2: Best R per event (maximize correlation with GT)")
    print("=" * 80)

    for seg_idx, seg in enumerate(segments):
        if len(seg) < 20:
            continue

        header = seg[:13]
        event_bytes = seg[13:]
        n_events = len(event_bytes) // 7

        gt_bar = seg_idx - 1
        gt = gt_bars.get(gt_bar, {})
        if not gt:
            continue

        print(f"\n  Seg {seg_idx} (GT bar {gt_bar}):")

        for ei in range(min(4, n_events)):
            evt = event_bytes[ei*7:(ei+1)*7]
            val = int.from_bytes(evt, "big")
            inst_note = LANE_NOTES[ei]
            lane_name = LANE_NAMES[ei]

            gt_inst = gt.get(inst_note, {})
            gt_vels = [gt_inst.get(pos, 0) for pos in range(8)]

            if not any(gt_vels):
                print(f"    {lane_name:6s} e{ei}: no GT hits, skipping")
                continue

            best_r = None
            best_corr = -2
            best_vels = None

            for r in range(56):
                derot = rot_right(val, r)
                vels = split_7bit(derot)
                c = correlate(vels, gt_vels)
                if c > best_corr:
                    best_corr = c
                    best_r = r
                    best_vels = vels

            print(f"    {lane_name:6s} e{ei}: best R={best_r:2d} corr={best_corr:+.3f}")
            print(f"    {'':6s}      7bit={best_vels}")
            print(f"    {'':6s}      GT  ={gt_vels}")

    # =========================================================
    # TEST 3: Try EACH instrument for EACH event
    # Maybe the lane-to-instrument mapping varies per bar
    # =========================================================
    print("\n" + "=" * 80)
    print("TEST 3: Best instrument assignment per event (free R + free instrument)")
    print("=" * 80)

    for seg_idx, seg in enumerate(segments):
        if len(seg) < 20:
            continue

        header = seg[:13]
        event_bytes = seg[13:]
        n_events = len(event_bytes) // 7

        gt_bar = seg_idx - 1
        gt = gt_bars.get(gt_bar, {})
        if not gt:
            continue

        print(f"\n  Seg {seg_idx} (GT bar {gt_bar}):")

        for ei in range(min(4, n_events)):
            evt = event_bytes[ei*7:(ei+1)*7]
            val = int.from_bytes(evt, "big")

            best_overall = None
            for inst_note in [36, 38, 42]:
                gt_inst = gt.get(inst_note, {})
                gt_vels = [gt_inst.get(pos, 0) for pos in range(8)]
                if not any(gt_vels):
                    continue

                for r in range(56):
                    derot = rot_right(val, r)
                    vels = split_7bit(derot)
                    c = correlate(vels, gt_vels)
                    if best_overall is None or c > best_overall[0]:
                        best_overall = (c, r, inst_note, vels, gt_vels)

            if best_overall:
                c, r, note, vels, gt_vels = best_overall
                print(f"    e{ei}: best={nn(note)} R={r:2d} corr={c:+.3f}")
                print(f"      decoded: {vels}")
                print(f"      GT:      {gt_vels}")
            else:
                print(f"    e{ei}: no GT match found")

    # =========================================================
    # TEST 4: Alternative: NOT 8×7 but 6×9-bit fields contain
    # per-beat data in a different way
    # =========================================================
    print("\n" + "=" * 80)
    print("TEST 4: 9-bit fields as beat data (F1-F5 = 5 beat groups?)")
    print("=" * 80)

    for seg_idx, seg in enumerate(segments):
        if len(seg) < 20:
            continue
        event_bytes = seg[13:]
        n_events = len(event_bytes) // 7
        gt_bar = seg_idx - 1
        gt = gt_bars.get(gt_bar, {})
        if not gt or seg_idx < 1 or seg_idx > 5:
            continue

        print(f"\n  Seg {seg_idx} (GT bar {gt_bar}):")

        for ei in range(min(4, n_events)):
            evt = event_bytes[ei*7:(ei+1)*7]
            val = int.from_bytes(evt, "big")

            for r in LANE_R:
                derot = rot_right(val, r)
                fields = [extract_9bit(derot, i) for i in range(6)]
                rem = derot & 0x3

                # F0 = note/identifier, F1-F4 = beat data, F5 = control, rem = flags
                # Or: F0 = note, F1-F2 = timing, F3-F4 = velocity/gate, F5 = position
                print(f"    e{ei} R={r:2d}: F0={fields[0]:3d}(={fields[0] & 0x7F:3d}) "
                      f"F1={fields[1]:3d} F2={fields[2]:3d} "
                      f"F3={fields[3]:3d} F4={fields[4]:3d} "
                      f"F5={fields[5]:3d} r={rem}")
            print()

    # =========================================================
    # TEST 5: Raw byte split — maybe encoding is byte-level
    # =========================================================
    print("\n" + "=" * 80)
    print("TEST 5: Byte-level analysis (no rotation)")
    print("=" * 80)

    print("  Direct bytes of e1 (expected snare) per bar:")
    for seg_idx, seg in enumerate(segments):
        if len(seg) < 27:
            continue
        evt = seg[13+7:13+14]  # e1
        bytes_list = list(evt)
        gt_bar = seg_idx - 1
        gt = gt_bars.get(gt_bar, {})
        snare_vel = gt.get(38, {})
        print(f"  Seg{seg_idx}: {evt.hex()} = {bytes_list} "
              f"GT snare={dict(snare_vel)}")

    print("\n  XOR of e1 between consecutive bars:")
    prev_e1 = None
    for seg_idx, seg in enumerate(segments):
        if len(seg) < 27:
            continue
        evt = seg[13+7:13+14]
        if prev_e1 is not None:
            xor = bytes(a ^ b for a, b in zip(evt, prev_e1))
            diff_bits = sum(bin(b).count("1") for b in xor)
            print(f"  Seg{seg_idx-1}→Seg{seg_idx}: {xor.hex()} ({diff_bits} bits)")
        prev_e1 = evt

    print("\nDone.")


if __name__ == "__main__":
    main()
