#!/usr/bin/env python3
"""Model F: skip-ctrl iterative + R=47 fallback.

Combines the best approaches:
- Model D: note-only iterative index (skip ctrl events)
- Model E: R=47 fallback when primary R gives invalid note

Also adds Model G: same but with R=9 constant as secondary fallback.
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
    56: 'Cowbell', 57: 'Crash2', 80: 'MuTriang', 81: 'OpTriang',
    82: 'Shaker', 83: 'JnglBell', 84: 'BellTree', 85: 'Castanets',
    86: 'MuSurdo', 87: 'OpSurdo',
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
        if len(seg) >= 13:
            header = seg[:13]
            events = []
            for i in range((len(seg) - 13) // 7):
                evt = seg[13 + i*7:13 + (i+1)*7]
                if len(evt) == 7:
                    events.append(evt)
            segments.append((header, events))
        prev = dp + 1
    seg = event_data[prev:]
    if len(seg) >= 13:
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
        "gate": fields[5], "f0": f0, "fields": fields, "rem": rem,
        "is_ctrl": note > 87, "valid_drum": 13 <= note <= 87,
    }


def model_F(segments):
    """Skip-ctrl iterative + R=47 fallback."""
    total = 0; valid = 0; ctrl = 0
    for si, (header, events) in enumerate(segments):
        note_idx = 0
        for ei, evt in enumerate(events):
            total += 1
            r = (9 * (note_idx + 1)) % 56
            d = decode_at_r(evt, r)
            if d["is_ctrl"]:
                ctrl += 1
                continue
            if d["valid_drum"]:
                valid += 1
            else:
                # R=47 fallback
                d2 = decode_at_r(evt, 47)
                if d2["valid_drum"]:
                    valid += 1
            note_idx += 1
    return valid, total - ctrl, ctrl


def model_G(segments):
    """Standard cumulative + skip-ctrl fallback + R=47 fallback."""
    total = 0; valid = 0; ctrl = 0
    for si, (header, events) in enumerate(segments):
        note_idx = 0
        for ei, evt in enumerate(events):
            total += 1
            # Primary: standard cumulative
            r_std = (9 * (ei + 1)) % 56
            d = decode_at_r(evt, r_std)
            if d["is_ctrl"]:
                ctrl += 1
                continue
            if d["valid_drum"]:
                valid += 1
                note_idx += 1
                continue
            # Fallback 1: skip-ctrl R
            r_skip = (9 * (note_idx + 1)) % 56
            if r_skip != r_std:
                d2 = decode_at_r(evt, r_skip)
                if d2["valid_drum"]:
                    valid += 1
                    note_idx += 1
                    continue
            # Fallback 2: R=47
            d3 = decode_at_r(evt, 47)
            if d3["valid_drum"]:
                valid += 1
            note_idx += 1
    return valid, total - ctrl, ctrl


def model_A(segments):
    """Standard cumulative (baseline)."""
    total = 0; valid = 0; ctrl = 0
    for si, (header, events) in enumerate(segments):
        for ei, evt in enumerate(events):
            total += 1
            r = (9 * (ei + 1)) % 56
            d = decode_at_r(evt, r)
            if d["is_ctrl"]:
                ctrl += 1
            elif d["valid_drum"]:
                valid += 1
    return valid, total - ctrl, ctrl


def model_D(segments):
    """Skip-ctrl iterative (no fallback)."""
    total = 0; valid = 0; ctrl = 0
    for si, (header, events) in enumerate(segments):
        note_idx = 0
        for ei, evt in enumerate(events):
            total += 1
            r = (9 * (note_idx + 1)) % 56
            d = decode_at_r(evt, r)
            if d["is_ctrl"]:
                ctrl += 1
                continue
            if d["valid_drum"]:
                valid += 1
            note_idx += 1
    return valid, total - ctrl, ctrl


def model_E(segments):
    """Standard cumulative + R=47 fallback."""
    total = 0; valid = 0; ctrl = 0
    for si, (header, events) in enumerate(segments):
        for ei, evt in enumerate(events):
            total += 1
            r = (9 * (ei + 1)) % 56
            d = decode_at_r(evt, r)
            if d["is_ctrl"]:
                ctrl += 1
            elif d["valid_drum"]:
                valid += 1
            else:
                d2 = decode_at_r(evt, 47)
                if d2["valid_drum"]:
                    valid += 1
    return valid, total - ctrl, ctrl


def detailed_model_G(segments, label):
    """Show per-event detail for Model G."""
    print(f"\n  DETAILED — {label} — Model G")
    for si, (header, events) in enumerate(segments):
        if not events:
            continue
        print(f"\n    Seg {si} ({len(events)} events):")
        note_idx = 0
        for ei, evt in enumerate(events):
            r_std = (9 * (ei + 1)) % 56
            r_skip = (9 * (note_idx + 1)) % 56
            d_std = decode_at_r(evt, r_std)

            if d_std["is_ctrl"]:
                print(f"      e{ei:2d} [CTRL] R={r_std:2d}: lo7={d_std['note']:3d}")
                continue

            n_std = d_std["note"]
            used_r = r_std
            source = "STD"

            if not d_std["valid_drum"]:
                if r_skip != r_std:
                    d_skip = decode_at_r(evt, r_skip)
                    if d_skip["valid_drum"]:
                        n_std = d_skip["note"]
                        used_r = r_skip
                        source = "SKIP"
                if not (13 <= n_std <= 87):
                    d47 = decode_at_r(evt, 47)
                    if d47["valid_drum"]:
                        n_std = d47["note"]
                        used_r = 47
                        source = "R47"

            name = GM_DRUMS.get(n_std, f"n{n_std}")
            v_ok = "OK" if 13 <= n_std <= 87 else "BAD"
            print(f"      e{ei:2d} [NOTE ni={note_idx}] R={used_r:2d}({source:4s}): "
                  f"{name:>10s} n={n_std:3d} [{v_ok}]")
            note_idx += 1


def main():
    files = [
        ("midi_tools/captured/user_style_live.syx", 0, "USER-RHY1"),
        ("midi_tools/captured/ground_truth_style.syx", 0, "SGT-RHY1"),
        ("midi_tools/captured/known_pattern.syx", 0, "KNOWN-PATTERN"),
    ]

    models = [
        ("A (std cumulative)", model_A),
        ("D (skip-ctrl)", model_D),
        ("E (std + R=47)", model_E),
        ("F (skip + R=47)", model_F),
        ("G (std→skip→R=47)", model_G),
    ]

    print(f"{'=' * 75}")
    print(f"  MODEL COMPARISON — ALL TRACKS")
    print(f"{'=' * 75}")

    for syx_path, al, label in files:
        data = get_track(syx_path, al)
        if not data:
            continue
        segments = get_segments(data)
        print(f"\n  {label} ({len(segments)} segs):")
        print(f"  {'Model':>22s} {'Valid':>8s} {'Pct':>5s} {'Ctrl':>5s}")

        for mname, mfunc in models:
            v, n, c = mfunc(segments)
            pct = f"{100*v//max(1,n)}%"
            print(f"  {mname:>22s} {v:>3d}/{n:<3d}  {pct:>5s} {c:>5d}")

    # Detailed output for best model
    for syx_path, al, label in files[:2]:
        data = get_track(syx_path, al)
        if data:
            segments = get_segments(data)
            detailed_model_G(segments, label)


if __name__ == "__main__":
    main()
