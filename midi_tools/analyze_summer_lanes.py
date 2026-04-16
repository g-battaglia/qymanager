#!/usr/bin/env python3
"""
Deep bit-level analysis of Summer pattern instrument lanes.

Session 25 discovery: Dense drum patterns encode 4 events per bar as
instrument lanes (HH, Snare, HH2, Kick) with fixed per-position R values
[R=9, R=22, R=12, R=53].

This script:
1. Loads Summer .syx and extracts RHY1 bitstream
2. Loads ground truth MIDI capture
3. For each bar: decodes 4 lanes, extracts 6×9-bit fields
4. XORs corresponding lanes across bars to identify velocity bits
5. Maps velocity differences to bit differences
"""

import json
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qymanager.formats.qy70.sysex_parser import SysExParser
from midi_tools.event_decoder import (
    rot_right, extract_9bit, extract_bars, TRACK_NAMES
)

# --- Constants ---
LANE_NAMES = ["HH", "Snare", "HH2", "Kick"]
LANE_R = [9, 22, 12, 53]  # Fixed R per instrument lane
PPQN = 480
BAR_TICKS = PPQN * 4  # 4/4 time = 1920 ticks

# QY70 MIDI channel mapping for Pattern mode PATT OUT=9~16
# ch9=D1/RHY1, ch10=D2/RHY2, ch11=PC/PAD, ch12=BA/BASS
# ch13=C1/CHD1, ch14=C2/CHD2, ch15=C3/PHR1, ch16=C4/PHR2
CH_RHY1 = 9  # 0-indexed: data[0] & 0x0F = 8


def load_syx_track(syx_path: str, section: int = 0, track: int = 0) -> bytes:
    """Load decoded track data from .syx file."""
    parser = SysExParser()
    messages = parser.parse_file(syx_path)
    al = section * 8 + track
    data = b""
    for m in messages:
        if m.is_style_data and m.address_low == al:
            if m.decoded_data is not None:
                data += m.decoded_data
    return data


def load_ground_truth(json_path: str) -> dict:
    """Load ground truth capture and organize by channel and bar."""
    with open(json_path) as f:
        capture = json.load(f)

    # Find tempo from timing
    events = capture["events"]

    # Extract note-on events on RHY1 channel (ch9 = status 0x98 = 152)
    rhy1_notes = []
    for evt in events:
        d = evt["data"]
        if len(d) == 3:
            status = d[0]
            ch = status & 0x0F
            msg_type = status & 0xF0
            if ch == 8 and msg_type == 0x90 and d[2] > 0:  # ch9 (0-indexed=8), note-on
                rhy1_notes.append({
                    "t": evt["t"],
                    "note": d[1],
                    "velocity": d[2],
                })

    return rhy1_notes


def organize_gt_by_bar(notes: list, bpm: float = 120.0) -> dict:
    """Organize ground truth notes into bars.

    Returns: {bar_index: [{"note": n, "velocity": v, "beat": b, "tick_in_bar": t}, ...]}
    """
    bar_duration = 60.0 / bpm * 4  # 4 beats per bar in seconds

    # Find the first note time as bar 0 start
    if not notes:
        return {}
    t0 = notes[0]["t"]

    bars = {}
    for n in notes:
        dt = n["t"] - t0
        bar_idx = int(dt / bar_duration)
        tick_in_bar = (dt - bar_idx * bar_duration) / (60.0 / bpm) * PPQN
        beat = int(tick_in_bar / PPQN)

        if bar_idx not in bars:
            bars[bar_idx] = []
        bars[bar_idx].append({
            "note": n["note"],
            "velocity": n["velocity"],
            "beat": beat,
            "tick_in_bar": tick_in_bar,
            "t_abs": n["t"],
        })

    return bars


def organize_gt_by_instrument(bar_notes: list) -> dict:
    """Group notes in a bar by instrument (GM note number).

    Returns: {note_number: [velocity_list_in_order]}
    """
    instruments = {}
    for n in sorted(bar_notes, key=lambda x: x["tick_in_bar"]):
        nn = n["note"]
        if nn not in instruments:
            instruments[nn] = []
        instruments[nn].append(n["velocity"])
    return instruments


def decode_lane(evt_bytes: bytes, r_val: int) -> dict:
    """Decode a 7-byte event at a specific R value.

    Returns all 6 fields + remainder + raw 56-bit derotated value.
    """
    val = int.from_bytes(evt_bytes, "big")
    derot = rot_right(val, r_val)

    fields = {}
    for i in range(6):
        fields[f"f{i}"] = extract_9bit(derot, i)

    fields["remainder"] = derot & 0x3
    fields["derot_56"] = derot
    fields["raw_hex"] = evt_bytes.hex()

    # Velocity decode
    f0 = fields["f0"]
    bit8 = (f0 >> 8) & 1
    bit7 = (f0 >> 7) & 1
    note = f0 & 0x7F
    vel_code = (bit8 << 3) | (bit7 << 2) | fields["remainder"]
    velocity = max(1, 127 - vel_code * 8)

    fields["note"] = note
    fields["vel_code"] = vel_code
    fields["velocity"] = velocity

    # Timing
    f1 = fields["f1"]
    f2 = fields["f2"]
    beat = f1 >> 7
    clock = ((f1 & 0x7F) << 2) | (f2 >> 7)
    tick = beat * 480 + clock
    fields["beat"] = beat
    fields["clock"] = clock
    fields["tick"] = tick

    return fields


def bits56(val: int) -> str:
    """Format 56-bit value as binary string."""
    return format(val, "056b")


def xor_analysis(a_val: int, b_val: int) -> dict:
    """XOR two 56-bit values and analyze differences."""
    xor = a_val ^ b_val
    diff_bits = bin(xor).count("1")
    diff_positions = [55 - i for i in range(56) if (xor >> (55 - i)) & 1]

    # Map diff positions to fields
    field_diffs = {}
    for pos in diff_positions:
        # Field boundaries: F0=55-47, F1=46-38, F2=37-29, F3=28-20, F4=19-11, F5=10-2, rem=1-0
        if pos >= 47:
            field_diffs.setdefault("F0", []).append(pos)
        elif pos >= 38:
            field_diffs.setdefault("F1", []).append(pos)
        elif pos >= 29:
            field_diffs.setdefault("F2", []).append(pos)
        elif pos >= 20:
            field_diffs.setdefault("F3", []).append(pos)
        elif pos >= 11:
            field_diffs.setdefault("F4", []).append(pos)
        elif pos >= 2:
            field_diffs.setdefault("F5", []).append(pos)
        else:
            field_diffs.setdefault("rem", []).append(pos)

    return {
        "xor": xor,
        "diff_bits": diff_bits,
        "diff_positions": diff_positions,
        "field_diffs": field_diffs,
    }


def main():
    syx_path = "data/qy70_sysx/P -  Summer - 20231101.syx"
    gt_path = "midi_tools/captured/summer_playback_s25.json"

    if not os.path.exists(syx_path):
        print(f"ERROR: {syx_path} not found")
        return
    if not os.path.exists(gt_path):
        print(f"ERROR: {gt_path} not found")
        return

    # --- Load SysEx RHY1 data ---
    print("=" * 70)
    print("SUMMER PATTERN — INSTRUMENT LANE ANALYSIS")
    print("=" * 70)

    data = load_syx_track(syx_path, section=0, track=0)
    print(f"\nRHY1 decoded: {len(data)} bytes")

    preamble, bars = extract_bars(data)
    print(f"Preamble: {preamble.hex()}")
    print(f"Bars (segments): {len(bars)}")

    # --- Load ground truth ---
    gt_notes = load_ground_truth(gt_path)
    print(f"\nGround truth RHY1 notes: {len(gt_notes)}")

    gt_bars = organize_gt_by_bar(gt_notes, bpm=120.0)
    print(f"Ground truth bars: {sorted(gt_bars.keys())}")

    # Show GT summary per bar
    print("\n--- Ground Truth Summary ---")
    for bar_idx in sorted(gt_bars.keys()):
        notes = gt_bars[bar_idx]
        instruments = organize_gt_by_instrument(notes)
        inst_summary = []
        for nn, vels in sorted(instruments.items()):
            from midi_tools.event_decoder import nn as note_name
            inst_summary.append(f"{note_name(nn)}({nn}): {len(vels)} hits, vel={vels}")
        print(f"  Bar {bar_idx}: {len(notes)} notes — {', '.join(inst_summary[:4])}")
        if len(inst_summary) > 4:
            print(f"           + {', '.join(inst_summary[4:])}")

    # --- Decode each bar at 4 lane R values ---
    print("\n" + "=" * 70)
    print("LANE DECODING — Fixed R per instrument position")
    print("=" * 70)

    all_lanes = []  # [bar_idx][lane_idx] = decoded fields

    for bar_idx, (header, events) in enumerate(bars):
        print(f"\n--- Bar {bar_idx} (header: {header.hex()}) ---")
        print(f"  Events: {len(events)}")

        bar_lanes = {}
        for evt_idx, evt in enumerate(events):
            if evt_idx >= 4:
                # Only analyze first 4 events (instrument lanes)
                break

            lane_name = LANE_NAMES[evt_idx] if evt_idx < len(LANE_NAMES) else f"e{evt_idx}"
            r_val = LANE_R[evt_idx] if evt_idx < len(LANE_R) else 9

            decoded = decode_lane(evt, r_val)
            bar_lanes[evt_idx] = decoded

            print(f"  {lane_name:6s} R={r_val:2d}: "
                  f"note={decoded['note']:3d} vel={decoded['velocity']:3d} "
                  f"tick={decoded['tick']:4d} gate={decoded['f5']:3d} "
                  f"| F0={decoded['f0']:03x} F1={decoded['f1']:03x} "
                  f"F2={decoded['f2']:03x} F3={decoded['f3']:03x} "
                  f"F4={decoded['f4']:03x} F5={decoded['f5']:03x} r={decoded['remainder']}")

        all_lanes.append(bar_lanes)

    # --- Cross-bar XOR analysis per lane ---
    print("\n" + "=" * 70)
    print("CROSS-BAR XOR ANALYSIS — Which bits change between bars?")
    print("=" * 70)

    for lane_idx in range(4):
        lane_name = LANE_NAMES[lane_idx]
        print(f"\n{'='*40}")
        print(f"Lane: {lane_name} (R={LANE_R[lane_idx]})")
        print(f"{'='*40}")

        # Collect derotated values across bars
        bar_values = []
        for bar_idx, bar_lanes in enumerate(all_lanes):
            if lane_idx in bar_lanes:
                bar_values.append((bar_idx, bar_lanes[lane_idx]))

        if len(bar_values) < 2:
            print("  Not enough bars for comparison")
            continue

        # Show field values across all bars
        print(f"\n  {'Bar':>3} | {'F0':>5} {'F1':>5} {'F2':>5} {'F3':>5} "
              f"{'F4':>5} {'F5':>5} {'rem':>3} | {'note':>4} {'vel':>3} {'tick':>4}")
        print(f"  {'---':>3}-+-{'-'*5}-{'-'*5}-{'-'*5}-{'-'*5}-"
              f"{'-'*5}-{'-'*5}-{'-'*3}-+-{'-'*4}-{'-'*3}-{'-'*4}")
        for bar_idx, d in bar_values:
            print(f"  {bar_idx:3d} | {d['f0']:5d} {d['f1']:5d} {d['f2']:5d} "
                  f"{d['f3']:5d} {d['f4']:5d} {d['f5']:5d} {d['remainder']:3d} | "
                  f"{d['note']:4d} {d['vel_code']:3d} {d['tick']:4d}")

        # Identify STABLE fields (same across all bars)
        field_names = ["f0", "f1", "f2", "f3", "f4", "f5", "remainder"]
        stable = {}
        for fn in field_names:
            vals = set(d[fn] for _, d in bar_values)
            stable[fn] = len(vals) == 1
            if len(vals) == 1:
                print(f"  {fn}: STABLE = {bar_values[0][1][fn]}")
            else:
                print(f"  {fn}: VARIES = {[d[fn] for _, d in bar_values]}")

        # Pairwise XOR between consecutive bars
        print(f"\n  Pairwise XOR (consecutive bars):")
        for i in range(len(bar_values) - 1):
            a_idx, a_d = bar_values[i]
            b_idx, b_d = bar_values[i + 1]
            xor_result = xor_analysis(a_d["derot_56"], b_d["derot_56"])
            print(f"\n  Bar {a_idx} vs {b_idx}: {xor_result['diff_bits']} bits differ")
            if xor_result["diff_bits"] > 0:
                print(f"    XOR: {bits56(xor_result['xor'])}")
                for field, positions in sorted(xor_result["field_diffs"].items()):
                    print(f"    {field}: bits {positions}")

    # --- Ground truth velocity correlation ---
    print("\n" + "=" * 70)
    print("VELOCITY CORRELATION — GT vs Decoded")
    print("=" * 70)

    # Map GT instruments to lanes
    # Need to figure out which GM notes correspond to HH/Snare/HH2/Kick
    # From known_pattern: HH=42(HHclose), Snare=38(Snare1), HH2=46(HHopen), Kick=36(Kick1)
    # But Summer may use different instruments

    # First, find the notes decoded at each lane R
    for lane_idx in range(4):
        lane_name = LANE_NAMES[lane_idx]
        notes_at_lane = set()
        for bar_lanes in all_lanes:
            if lane_idx in bar_lanes:
                notes_at_lane.add(bar_lanes[lane_idx]["note"])
        print(f"\n  {lane_name} lane decoded notes: {sorted(notes_at_lane)}")

    # Then show what GT has per bar
    print("\n  GT instruments per bar:")
    all_gt_instruments = set()
    for bar_idx in sorted(gt_bars.keys()):
        instruments = organize_gt_by_instrument(gt_bars[bar_idx])
        all_gt_instruments.update(instruments.keys())

    for inst_note in sorted(all_gt_instruments):
        from midi_tools.event_decoder import nn as note_name
        vels_per_bar = []
        for bar_idx in sorted(gt_bars.keys()):
            instruments = organize_gt_by_instrument(gt_bars[bar_idx])
            if inst_note in instruments:
                vels_per_bar.append(instruments[inst_note])
            else:
                vels_per_bar.append([])
        print(f"  {note_name(inst_note):>4s}({inst_note:2d}): "
              + "  |  ".join(
                  ",".join(str(v) for v in vl) if vl else "---"
                  for vl in vels_per_bar[:8]
              ))

    # --- Attempt velocity field mapping ---
    print("\n" + "=" * 70)
    print("VELOCITY FIELD MAPPING — Can decoded vel_code predict GT velocities?")
    print("=" * 70)

    # For each lane, try to correlate decoded vel_code with GT velocities
    # The vel_code is 4-bit inverted: MIDI_vel = max(1, 127 - vel_code*8)
    # But GT velocities are often NOT multiples of 8, suggesting the
    # instrument lane doesn't encode individual hit velocities.
    #
    # Hypothesis: The lane encodes a TEMPLATE (which beats are active)
    # while individual velocities come from a per-beat velocity table
    # stored elsewhere in the bitstream (e.g., the bar header or
    # trailing bytes).

    print("\n  Lane vel_code consistency across bars:")
    for lane_idx in range(4):
        lane_name = LANE_NAMES[lane_idx]
        vel_codes = []
        velocities = []
        for bar_idx, bar_lanes in enumerate(all_lanes):
            if lane_idx in bar_lanes:
                vel_codes.append(bar_lanes[lane_idx]["vel_code"])
                velocities.append(bar_lanes[lane_idx]["velocity"])
        print(f"  {lane_name}: vel_codes={vel_codes}, decoded_vel={velocities}")

    # --- Deep: all 56 bits per lane across bars ---
    print("\n" + "=" * 70)
    print("RAW 56-BIT COMPARISON — Full binary per lane per bar")
    print("=" * 70)

    for lane_idx in range(4):
        lane_name = LANE_NAMES[lane_idx]
        print(f"\n  Lane: {lane_name} (R={LANE_R[lane_idx]})")
        print(f"  {'Bar':>3} | {'56-bit derotated (MSB→LSB)':56s} | hex")
        print(f"  {'---':>3}-+-{'-'*56}-+------")
        for bar_idx, bar_lanes in enumerate(all_lanes):
            if lane_idx in bar_lanes:
                d = bar_lanes[lane_idx]
                print(f"  {bar_idx:3d} | {bits56(d['derot_56'])} | {d['derot_56']:014x}")

    # --- Try alternative R values ---
    print("\n" + "=" * 70)
    print("R-VALUE SWEEP — Try all R for each event position")
    print("=" * 70)

    # For bar 0, try all R=0..55 on each event and find which give valid notes
    if all_lanes:
        bar0 = all_lanes[0]
        for evt_idx in range(min(4, len(bars[0][1]))):
            evt = bars[0][1][evt_idx]
            print(f"\n  Event e{evt_idx} ({LANE_NAMES[evt_idx]}) raw={evt.hex()}")
            valid_rs = []
            for r in range(56):
                decoded = decode_lane(evt, r)
                if 13 <= decoded["note"] <= 87:
                    valid_rs.append((r, decoded["note"], decoded["velocity"],
                                    decoded["tick"], decoded["f5"]))
            print(f"  Valid R values ({len(valid_rs)}):")
            for r, note, vel, tick, gate in valid_rs:
                marker = " <<<" if r == LANE_R[evt_idx] else ""
                from midi_tools.event_decoder import nn as note_name
                print(f"    R={r:2d}: note={note:3d} ({note_name(note):>4s}) "
                      f"vel={vel:3d} tick={tick:4d} gate={gate:3d}{marker}")

    print("\n" + "=" * 70)
    print("DONE")
    print("=" * 70)


if __name__ == "__main__":
    main()
