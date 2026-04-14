#!/usr/bin/env python3
"""Test MIXED rotation: cumulative R=9*(i+1) for each event, but try R=9
for events that fail the cumulative model.

Hypothesis: maybe some events ARE constant-rotated (like header echoes
or repeated patterns) while most use cumulative rotation.

Also test: what if the event_index resets at certain positions
(e.g., after simultaneous events)?
"""

import sys, os
from collections import defaultdict
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


def decode(evt, r_val):
    val = int.from_bytes(evt, "big")
    derot = rot_right(val, r_val)
    f0 = f9(derot, 0)
    f1 = f9(derot, 1)
    f2 = f9(derot, 2)
    f5 = f9(derot, 5)
    rem = derot & 0x3
    note = f0 & 0x7F
    bit8 = (f0 >> 8) & 1
    bit7 = (f0 >> 7) & 1
    vel_code = (bit8 << 3) | (bit7 << 2) | rem
    midi_vel = max(1, 127 - vel_code * 8)
    beat = f1 >> 7
    clock = ((f1 & 0x7F) << 2) | (f2 >> 7)
    tick = beat * 480 + clock
    return note, midi_vel, f5, tick, vel_code, f0


def main():
    base = os.path.dirname(os.path.abspath(__file__))
    syx = os.path.join(base, "captured", "ground_truth_style.syx")
    segments = get_segments(syx, 0, 0)

    # ============================================================
    # 1. Mixed model: cumulative first, constant R=9 as fallback
    # ============================================================
    print(f"{'='*80}")
    print(f"  MIXED MODEL: cumulative R=9*(i+1), fallback to constant R=9")
    print(f"{'='*80}")

    total = 0
    valid_cum = 0
    valid_const = 0
    valid_mixed = 0
    valid_best = 0  # best R per event

    for seg_idx, seg in enumerate(segments):
        if len(seg) < 20:
            continue
        nevts = (len(seg) - 13) // 7

        print(f"\n  Seg {seg_idx} ({nevts} events):")
        for i in range(nevts):
            evt = seg[13 + i * 7: 13 + (i + 1) * 7]
            if len(evt) != 7:
                continue
            total += 1

            # Cumulative
            r_cum = 9 * (i + 1)
            note_c, vel_c, gate_c, tick_c, vc_c, f0_c = decode(evt, r_cum)
            ok_c = note_c in XG_RANGE
            if ok_c:
                valid_cum += 1

            # Constant
            note_k, vel_k, gate_k, tick_k, vc_k, f0_k = decode(evt, 9)
            ok_k = note_k in XG_RANGE
            if ok_k:
                valid_const += 1

            # Mixed: prefer cumulative, fallback to constant
            if ok_c:
                valid_mixed += 1
                note_m, vel_m, gate_m, tick_m = note_c, vel_c, gate_c, tick_c
                model = "CUM"
            elif ok_k:
                valid_mixed += 1
                note_m, vel_m, gate_m, tick_m = note_k, vel_k, gate_k, tick_k
                model = "CST"
            else:
                note_m, vel_m, gate_m, tick_m = note_c, vel_c, gate_c, tick_c
                model = "???"

            # Best R (any R 0-55 that gives valid note)
            found_any = False
            for r_test in range(56):
                nt, *_ = decode(evt, r_test)
                if nt in XG_RANGE:
                    found_any = True
                    break
            if found_any:
                valid_best += 1

            name = GM_DRUMS.get(note_m, 'n' + str(note_m))
            status = f"{'✓' if model != '???' else '✗'} {model}"
            print(f"    e{i}: {status} note={note_m:>3}({name:>10})"
                  f" vel={vel_m:>3} gate={gate_m:>3} tick={tick_m:>5}")

    print(f"\n{'='*80}")
    print(f"  SUMMARY")
    print(f"{'='*80}")
    print(f"  Total events: {total}")
    print(f"  Constant R=9:   {valid_const}/{total} ({100*valid_const/total:.0f}%)")
    print(f"  Cumulative:     {valid_cum}/{total} ({100*valid_cum/total:.0f}%)")
    print(f"  Mixed (cum+cst):{valid_mixed}/{total} ({100*valid_mixed/total:.0f}%)")
    print(f"  Best any R:     {valid_best}/{total} ({100*valid_best/total:.0f}%)")

    # ============================================================
    # 2. Test: what if event index counts from 1 not 0?
    #    R = 9*(i+1) same as R = 9*(i) + 9 = 9*i + 9
    #    vs R = 9*i (different: e0 gets R=0)
    #    vs R = 9*(i+2) (e0 gets R=18)
    # ============================================================
    print(f"\n{'='*80}")
    print(f"  INDEX OFFSET TEST: R = 9*(i+offset)")
    print(f"{'='*80}")

    for offset in range(0, 7):
        total = 0
        valid = 0
        for seg in segments:
            if len(seg) < 20:
                continue
            nevts = (len(seg) - 13) // 7
            for i in range(nevts):
                evt = seg[13 + i * 7: 13 + (i + 1) * 7]
                if len(evt) != 7:
                    continue
                total += 1
                r_val = 9 * (i + offset)
                note, *_ = decode(evt, r_val)
                if note in XG_RANGE:
                    valid += 1
        print(f"  offset={offset}: R=9*(i+{offset})"
              f"  valid={valid}/{total} ({100*valid/total:.0f}%)")

    # ============================================================
    # 3. What if simultaneous events share the same R?
    # ============================================================
    print(f"\n{'='*80}")
    print(f"  SHARED R FOR SIMULTANEOUS EVENTS")
    print(f"{'='*80}")

    # In cumulative model, if 3 events are at same position,
    # do they all use the same R (like position-based instead of index-based)?
    # Test: for each segment, group events by constant-R position,
    # then try assigning same R to groups

    for seg_idx, seg in enumerate(segments):
        if len(seg) < 20:
            continue
        nevts = (len(seg) - 13) // 7
        if nevts < 3:
            continue

        # Get constant-R ticks to identify simultaneous events
        events = []
        for i in range(nevts):
            evt = seg[13 + i * 7: 13 + (i + 1) * 7]
            if len(evt) == 7:
                note_k, vel_k, gate_k, tick_k, *_ = decode(evt, 9)
                events.append((i, evt, tick_k))

        # Group by approximate tick (within 20)
        groups = []
        current_group = [events[0]]
        for ev in events[1:]:
            if abs(ev[2] - current_group[-1][2]) < 20:
                current_group.append(ev)
            else:
                groups.append(current_group)
                current_group = [ev]
        groups.append(current_group)

        if any(len(g) > 1 for g in groups):
            print(f"\n  Seg {seg_idx}: {len(groups)} position groups"
                  f" (from {nevts} events)")
            group_idx = 0
            for grp in groups:
                group_idx += 1
                if len(grp) > 1:
                    r_shared = 9 * group_idx
                    notes_shared = []
                    for idx, evt, _ in grp:
                        n, v, g, t, *_ = decode(evt, r_shared)
                        name = GM_DRUMS.get(n, 'n' + str(n))
                        valid = "✓" if n in XG_RANGE else "✗"
                        notes_shared.append(f"e{idx}:{name}({n}){valid}")
                    print(f"    Group {group_idx} (R={r_shared}):"
                          f" {', '.join(notes_shared)}")

    # ============================================================
    # 4. DEFINITIVE TEST: use event_decoder.py's cumulative formula
    # ============================================================
    print(f"\n{'='*80}")
    print(f"  EVENT_DECODER FORMULA CHECK")
    print(f"{'='*80}")

    # The existing event_decoder uses shift = (event_index * 9) % 56
    # This is R = 9*i, NOT R = 9*(i+1)
    # Check if event_decoder's formula (R=9*i) was already cumulative
    # and the ACTUAL proved rotation for 1FA3 chord encoding

    print(f"\n  Formula comparison (first 10 indices):")
    print(f"  {'idx':>4} | R=9*(i+1) | R=9*i | R=9 const")
    for i in range(10):
        r1 = (9 * (i + 1)) % 56
        r0 = (9 * i) % 56
        print(f"  {i:>4} | R={r1:>5} | R={r0:>4} | R=9")

    print(f"\n  Note: R=9*(i+1) at i=0 gives R=9 (matches constant)")
    print(f"        R=9*i at i=0 gives R=0 (no rotation)")
    print(f"        R=9*i at i=1 gives R=9 (one-off from cumulative)")


if __name__ == "__main__":
    main()
