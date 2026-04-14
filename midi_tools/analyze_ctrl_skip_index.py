#!/usr/bin/env python3
"""Test if skipping control events fixes the cumulative index in multi-segment tracks.

Hypothesis: the cumulative rotation index R=9*(i+1) counts only NOTE events,
not control events. When a control event appears, it doesn't consume an index slot.

Test on:
1. USER-RHY1 (user_style_live.syx) — multi-segment with known control events
2. SGT-RHY1 (ground_truth_style.syx) — multi-segment reference
3. known_pattern.syx — single segment, no control events (baseline)

For each track, compare:
A. Standard cumulative: R = 9*(event_position+1) % 56  (all events count)
B. Skip-ctrl cumulative: R = 9*(note_count+1) % 56  (only note events count)
C. Two-pass: first identify ctrl at standard R, then re-decode notes with skip index
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

EXPECTED_DRUMS = {36, 38, 42}  # Kick, Snare, HH (from playback capture)


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
        "is_ctrl": note > 87,
        "valid_drum": 13 <= note <= 87,
    }


def is_control_at_r(evt_bytes, r_value):
    """Check if event is a control event at given R."""
    val = int.from_bytes(evt_bytes, "big")
    derot = rot_right(val, r_value)
    f0 = extract_9bit(derot, 0)
    lo7 = f0 & 0x7F
    return lo7 > 87


def test_model_A(segments, label):
    """Model A: standard cumulative R=9*(i+1), per-segment index reset."""
    print(f"\n  MODEL A — Standard cumulative (all events count)")
    total = 0
    valid = 0
    expected = 0
    ctrl = 0

    for si, (header, events) in enumerate(segments):
        for ei, evt in enumerate(events):
            r = (9 * (ei + 1)) % 56
            d = decode_at_r(evt, r)
            total += 1
            if d["is_ctrl"]:
                ctrl += 1
            elif d["valid_drum"]:
                valid += 1
                if d["note"] in EXPECTED_DRUMS:
                    expected += 1

    note_total = total - ctrl
    print(f"    Events: {total} total, {ctrl} ctrl, {note_total} note")
    print(f"    Valid drums: {valid}/{note_total} ({100*valid//max(1,note_total)}%)")
    print(f"    Expected hits: {expected}/{note_total}")
    return valid, note_total, expected


def test_model_B(segments, label):
    """Model B: two-pass — identify ctrl at cumulative R, then re-index notes only."""
    print(f"\n  MODEL B — Two-pass: identify ctrl, then skip-index for notes")
    total = 0
    valid = 0
    expected = 0
    ctrl = 0

    for si, (header, events) in enumerate(segments):
        # Pass 1: identify control events using standard cumulative R
        is_ctrl = []
        for ei, evt in enumerate(events):
            r = (9 * (ei + 1)) % 56
            is_ctrl.append(is_control_at_r(evt, r))

        # Pass 2: decode note events with skip-ctrl index
        note_idx = 0
        for ei, evt in enumerate(events):
            total += 1
            if is_ctrl[ei]:
                ctrl += 1
                continue

            # Note event: use note_idx for rotation
            r = (9 * (note_idx + 1)) % 56
            d = decode_at_r(evt, r)
            note_idx += 1

            if d["valid_drum"]:
                valid += 1
                if d["note"] in EXPECTED_DRUMS:
                    expected += 1

    note_total = total - ctrl
    print(f"    Events: {total} total, {ctrl} ctrl, {note_total} note")
    print(f"    Valid drums: {valid}/{note_total} ({100*valid//max(1,note_total)}%)")
    print(f"    Expected hits: {expected}/{note_total}")
    return valid, note_total, expected


def test_model_C(segments, label):
    """Model C: ctrl events use DIFFERENT R than notes.
    Hypothesis: ctrl at cumulative-including-all, notes at cumulative-notes-only.
    """
    print(f"\n  MODEL C — Mixed: ctrl at all-cumulative, notes at note-only-cumulative")
    total = 0
    valid = 0
    expected = 0
    ctrl = 0

    for si, (header, events) in enumerate(segments):
        # For each event, try standard R first; if ctrl, skip for note index
        note_idx = 0
        for ei, evt in enumerate(events):
            total += 1
            # First: check if ctrl at standard cumulative R
            r_all = (9 * (ei + 1)) % 56
            if is_control_at_r(evt, r_all):
                ctrl += 1
                continue

            # Not ctrl at standard R — try note-only index
            r_note = (9 * (note_idx + 1)) % 56
            d = decode_at_r(evt, r_note)
            note_idx += 1

            if d["valid_drum"]:
                valid += 1
                if d["note"] in EXPECTED_DRUMS:
                    expected += 1

    note_total = total - ctrl
    print(f"    Events: {total} total, {ctrl} ctrl, {note_total} note")
    print(f"    Valid drums: {valid}/{note_total} ({100*valid//max(1,note_total)}%)")
    print(f"    Expected hits: {expected}/{note_total}")
    return valid, note_total, expected


def test_model_D(segments, label):
    """Model D: ctrl events also skip-indexed; ALL events use note-only-cumulative.
    Every event uses R=9*(note_count_before_it + 1).
    Ctrl events are identified by lo7>87 AFTER decoding.
    """
    print(f"\n  MODEL D — All events use note-only index (iterative)")
    total = 0
    valid = 0
    expected = 0
    ctrl = 0

    for si, (header, events) in enumerate(segments):
        note_idx = 0
        for ei, evt in enumerate(events):
            total += 1
            r = (9 * (note_idx + 1)) % 56
            d = decode_at_r(evt, r)

            if d["is_ctrl"]:
                ctrl += 1
                # Don't increment note_idx for ctrl events
                continue

            note_idx += 1
            if d["valid_drum"]:
                valid += 1
                if d["note"] in EXPECTED_DRUMS:
                    expected += 1

    note_total = total - ctrl
    print(f"    Events: {total} total, {ctrl} ctrl, {note_total} note")
    print(f"    Valid drums: {valid}/{note_total} ({100*valid//max(1,note_total)}%)")
    print(f"    Expected hits: {expected}/{note_total}")
    return valid, note_total, expected


def test_model_E(segments, label):
    """Model E: ALL events (incl ctrl) use standard cumulative,
    but ctrl events still increment the counter.
    Notes that fail at cumulative R get tried at R=47 fallback.
    """
    print(f"\n  MODEL E — Standard cumulative + R=47 fallback for failures")
    total = 0
    valid = 0
    expected = 0
    ctrl = 0

    for si, (header, events) in enumerate(segments):
        for ei, evt in enumerate(events):
            total += 1
            r = (9 * (ei + 1)) % 56
            d = decode_at_r(evt, r)

            if d["is_ctrl"]:
                ctrl += 1
                continue

            if d["valid_drum"]:
                valid += 1
                if d["note"] in EXPECTED_DRUMS:
                    expected += 1
            else:
                # Try R=47 fallback
                d2 = decode_at_r(evt, 47)
                if d2["valid_drum"]:
                    valid += 1
                    if d2["note"] in EXPECTED_DRUMS:
                        expected += 1

    note_total = total - ctrl
    print(f"    Events: {total} total, {ctrl} ctrl, {note_total} note")
    print(f"    Valid drums: {valid}/{note_total} ({100*valid//max(1,note_total)}%)")
    print(f"    Expected hits: {expected}/{note_total}")
    return valid, note_total, expected


def detailed_decode(segments, label, model_func):
    """Show per-segment detail for a specific model."""
    print(f"\n  DETAILED DECODE — {label}")

    for si, (header, events) in enumerate(segments):
        print(f"\n    Segment {si} ({len(events)} events):")

        # Two-pass like model B
        ctrl_flags = []
        for ei, evt in enumerate(events):
            r = (9 * (ei + 1)) % 56
            ctrl_flags.append(is_control_at_r(evt, r))

        note_idx = 0
        for ei, evt in enumerate(events):
            if ctrl_flags[ei]:
                r = (9 * (ei + 1)) % 56
                d = decode_at_r(evt, r)
                print(f"      e{ei} [CTRL] R={r:2d}: lo7={d['note']:3d} "
                      f"f0=0x{d['f0']:03X}")
            else:
                # Try both standard and skip-ctrl R
                r_std = (9 * (ei + 1)) % 56
                r_skip = (9 * (note_idx + 1)) % 56
                d_std = decode_at_r(evt, r_std)
                d_skip = decode_at_r(evt, r_skip)

                n_std = d_std["note"]
                n_skip = d_skip["note"]
                name_std = GM_DRUMS.get(n_std, f"n{n_std}")
                name_skip = GM_DRUMS.get(n_skip, f"n{n_skip}")

                exp_std = "***" if n_std in EXPECTED_DRUMS else "   "
                exp_skip = "***" if n_skip in EXPECTED_DRUMS else "   "
                valid_std = "OK" if 13 <= n_std <= 87 else "BAD"
                valid_skip = "OK" if 13 <= n_skip <= 87 else "BAD"

                match = "SAME" if r_std == r_skip else "DIFF"
                print(f"      e{ei} [NOTE ni={note_idx}] "
                      f"stdR={r_std:2d}→{name_std:>10s}({n_std:3d})[{valid_std}]{exp_std} | "
                      f"skipR={r_skip:2d}→{name_skip:>10s}({n_skip:3d})[{valid_skip}]{exp_skip} "
                      f"[{match}]")

                note_idx += 1


def main():
    files = [
        ("midi_tools/captured/user_style_live.syx", 0, "USER-RHY1"),
        ("midi_tools/captured/ground_truth_style.syx", 0, "SGT-RHY1"),
        ("midi_tools/captured/known_pattern.syx", 0, "KNOWN-PATTERN"),
    ]

    for syx_path, al, label in files:
        data = get_track(syx_path, al)
        if not data:
            print(f"\n{label}: not found")
            continue

        segments = get_segments(data)
        print(f"\n{'=' * 75}")
        print(f"  {label}: {len(data)}B, {len(segments)} segments")
        print(f"{'=' * 75}")

        results = {}
        for name, test_fn in [
            ("A", test_model_A),
            ("B", test_model_B),
            ("C", test_model_C),
            ("D", test_model_D),
            ("E", test_model_E),
        ]:
            v, n, e = test_fn(segments, label)
            results[name] = (v, n, e)

        # Summary
        print(f"\n  SUMMARY — {label}:")
        print(f"  {'Model':>8s} {'Valid':>6s} {'Pct':>5s} {'Expected':>8s}")
        for name in "ABCDE":
            v, n, e = results[name]
            pct = f"{100*v//max(1,n)}%" if n > 0 else "N/A"
            print(f"  {name:>8s} {v:>3d}/{n:<3d} {pct:>5s} {e:>8d}")

    # Detailed decode for USER-RHY1
    data = get_track("midi_tools/captured/user_style_live.syx", 0)
    if data:
        segments = get_segments(data)
        detailed_decode(segments, "USER-RHY1", test_model_B)


if __name__ == "__main__":
    main()
