#!/usr/bin/env python3
"""Test GLOBAL event index for R=9*(i+1) on USER-RHY1.

known_pattern.syx proves R=9*(i+1) with PERFECT 7/7 match.
The USER-RHY1 has multiple segments — test if the event index is
GLOBAL (continuing across DC delimiters) rather than per-segment.
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
EXPECTED = {36, 38, 42}


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
    fields = [extract_9bit(derot, i) for i in range(6)]
    rem = derot & 0x3
    f0 = fields[0]
    note = f0 & 0x7F
    bit8 = (f0 >> 8) & 1
    bit7 = (f0 >> 7) & 1
    vel_code = (bit8 << 3) | (bit7 << 2) | rem
    velocity = max(1, 127 - vel_code * 8)
    f1 = fields[1]
    f2 = fields[2]
    beat = f1 >> 7
    clock = ((f1 & 0x7F) << 2) | (f2 >> 7)
    tick = beat * 480 + clock
    return {
        "note": note, "velocity": velocity, "tick": tick,
        "gate": fields[5], "f0": f0, "valid": 13 <= note <= 87,
    }


def decode_track(syx_path, al, label, index_mode):
    """Decode with specified index mode: 'global', 'per_segment', 'per_segment_plus_header'."""
    data = get_track(syx_path, al)
    if not data:
        print(f"  {label}: not found")
        return

    segments = get_segments(data)
    print(f"\n{'='*70}")
    print(f"  {label} — index_mode={index_mode}")
    print(f"  {len(data)}B, {len(segments)} segments")
    print(f"{'='*70}")

    global_idx = 0
    total_expected = 0
    total_valid = 0
    total_events = 0

    for si, (header, events) in enumerate(segments):
        print(f"\n  Segment {si} ({len(events)} events):")

        for ei, evt in enumerate(events):
            if index_mode == "global":
                idx = global_idx
            elif index_mode == "per_segment":
                idx = ei
            elif index_mode == "per_segment_plus_header":
                # Header counts as some events
                idx = ei + 1  # or some offset
            elif index_mode == "global_plus_headers":
                # Each segment's header counts as ~2 events
                idx = global_idx
            else:
                idx = ei

            r = (9 * (idx + 1)) % 56
            d = decode_at_r(evt, r)
            n = d["note"]
            v = d["velocity"]
            t = d["tick"]
            g = d["gate"]
            nname = GM_DRUMS.get(n, f"n{n}")
            valid = "OK" if d["valid"] else "BAD"
            exp = "***" if n in EXPECTED else "   "
            gidx_str = f"G={global_idx}" if index_mode.startswith("global") else ""
            print(f"    e{ei} (i={idx:2d} R={r:2d}): {nname:>10s} n={n:3d} v={v:3d} "
                  f"t={t:4d} g={g:3d} [{valid}] {exp} {gidx_str}")

            total_events += 1
            if d["valid"]:
                total_valid += 1
            if n in EXPECTED:
                total_expected += 1

            global_idx += 1

        # For "global_plus_headers" mode, add header offset
        if index_mode == "global_plus_headers":
            global_idx += 2  # assume header "consumes" 2 event indices

    print(f"\n  TOTAL: {total_events} events, {total_valid} valid, "
          f"{total_expected} expected hits")


def main():
    syx = "midi_tools/captured/user_style_live.syx"

    # Test all index modes
    for mode in ["per_segment", "global", "global_plus_headers"]:
        decode_track(syx, 0, f"USER-RHY1", mode)

    # Also test on SGT-RHY1
    sgt_syx = "midi_tools/captured/ground_truth_style.syx"
    for mode in ["per_segment", "global"]:
        decode_track(sgt_syx, 0, f"SGT-RHY1", mode)


if __name__ == "__main__":
    main()
