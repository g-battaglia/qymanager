#!/usr/bin/env python3
"""Deep analysis of the 9 events (15%) that fail BOTH cumulative and constant
rotation in the mixed model.

For each failing event:
1. Show raw bytes and context (segment, position, neighbors)
2. Try ALL 56 rotations — which give valid notes?
3. Check if the event is near a trailing-byte boundary
4. Test: could the event be a non-note event (control/metadata)?
5. Check if reinterpreting with different field widths helps
"""

import sys, os
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

def decode(evt, r_val):
    val = int.from_bytes(evt, "big")
    derot = rot_right(val, r_val)
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
    clock = ((f1 & 0x7F) << 2) | (f2 >> 7)
    tick = beat * 480 + clock
    return note, midi_vel, f5, tick, vel_code, f0, f1, f2, f3, f4, rem


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


def main():
    base = os.path.dirname(os.path.abspath(__file__))
    syx = os.path.join(base, "captured", "ground_truth_style.syx")
    segments = get_segments(syx, 0, 0)

    # ============================================================
    # 1. Identify all failing events
    # ============================================================
    print(f"{'='*80}")
    print(f"  FAILING EVENTS IN MIXED MODEL (cumulative + constant R=9)")
    print(f"{'='*80}")

    failing = []
    all_events = []

    for seg_idx, seg in enumerate(segments):
        if len(seg) < 20:
            continue
        nevts = (len(seg) - 13) // 7
        trail = (len(seg) - 13) % 7

        for i in range(nevts):
            evt = seg[13 + i * 7: 13 + (i + 1) * 7]
            if len(evt) != 7:
                continue

            r_cum = 9 * (i + 1)
            note_c, *rest_c = decode(evt, r_cum)
            ok_c = note_c in XG_RANGE

            note_k, *rest_k = decode(evt, 9)
            ok_k = note_k in XG_RANGE

            info = {
                'seg': seg_idx, 'pos': i, 'nevts': nevts, 'trail': trail,
                'evt': evt, 'r_cum': r_cum,
                'note_cum': note_c, 'note_const': note_k,
                'ok_cum': ok_c, 'ok_const': ok_k,
            }
            all_events.append(info)

            if not ok_c and not ok_k:
                failing.append(info)

    print(f"\n  Total events: {len(all_events)}")
    print(f"  Failing (neither cumulative nor constant): {len(failing)}")

    # ============================================================
    # 2. Detailed analysis of each failing event
    # ============================================================
    print(f"\n{'='*80}")
    print(f"  DETAILED FAILING EVENT ANALYSIS")
    print(f"{'='*80}")

    for f in failing:
        evt = f['evt']
        seg_idx = f['seg']
        pos = f['pos']
        seg = segments[seg_idx]
        trail = f['trail']

        print(f"\n  === Seg {seg_idx}, e{pos} ===")
        print(f"  Raw bytes: {evt.hex()}")
        print(f"  Binary: {' '.join(f'{b:08b}' for b in evt)}")
        print(f"  Segment: {f['nevts']} events, {trail} trailing bytes")
        print(f"  Position: event {pos} of {f['nevts']} (last={pos==f['nevts']-1})")

        # Is this near the trailing bytes?
        events_end = 13 + f['nevts'] * 7
        trail_start = events_end
        is_last = (pos == f['nevts'] - 1)
        next_to_last = (pos == f['nevts'] - 2)
        print(f"  Near trailing: is_last={is_last}, next_to_last={next_to_last}")

        if trail > 0:
            trail_bytes = seg[-trail:]
            print(f"  Trailing bytes: {trail_bytes.hex()}")

        # Cumulative and constant decode
        for label, r_val in [("Cumulative", 9*(pos+1)), ("Constant", 9)]:
            note, vel, gate, tick, vc, f0, f1, f2, f3, f4, rem = decode(evt, r_val)
            name = GM_DRUMS.get(note, f'n{note}')
            print(f"  {label:>12} R={r_val:>3}: note={note:>3}({name:>10})"
                  f"  vel={vel:>3} gate={gate:>3} tick={tick:>5}"
                  f"  F0={f0:03X} F1={f1:03X} F2={f2:03X}"
                  f"  F3={f3:03X} F4={f4:03X} rem={rem}")

        # All valid rotations
        valid_rotations = []
        for r_test in range(56):
            nt, *_ = decode(evt, r_test)
            if nt in XG_RANGE:
                note_t, vel_t, gate_t, tick_t, vc_t, f0_t, *_ = decode(evt, r_test)
                name_t = GM_DRUMS.get(note_t, f'n{note_t}')
                valid_rotations.append((r_test, note_t, name_t, vel_t, gate_t, tick_t))

        print(f"  Valid rotations ({len(valid_rotations)}/56):")
        for r, n, nm, v, g, t in valid_rotations:
            # Is this a "natural" R value?
            natural = ""
            for mult in range(0, 7):
                if r == 9 * mult:
                    natural = f" ← 9×{mult}"
                    break
            print(f"    R={r:>2}: note={n:>3}({nm:>10}) vel={v:>3} gate={g:>3}"
                  f" tick={t:>5}{natural}")

        # Context: neighboring events
        print(f"  Neighbors:")
        for di in [-2, -1, 1, 2]:
            ni = pos + di
            if 0 <= ni < f['nevts']:
                nevt = seg[13 + ni * 7: 13 + (ni + 1) * 7]
                r_n = 9 * (ni + 1)
                nt_n, vel_n, gate_n, tick_n, *_ = decode(nevt, r_n)
                name_n = GM_DRUMS.get(nt_n, f'n{nt_n}')
                valid_n = "✓" if nt_n in XG_RANGE else "✗"
                print(f"    e{ni} R={r_n}: {nt_n}({name_n}) {valid_n}"
                      f" vel={vel_n} tick={tick_n}")

    # ============================================================
    # 3. Pattern analysis: what do failing events have in common?
    # ============================================================
    print(f"\n{'='*80}")
    print(f"  FAILING EVENT PATTERNS")
    print(f"{'='*80}")

    # Position distribution
    positions = [f['pos'] for f in failing]
    last_flags = [f['pos'] == f['nevts'] - 1 for f in failing]
    trail_flags = [f['trail'] > 0 for f in failing]
    seg_sizes = [f['nevts'] for f in failing]

    print(f"\n  Positions: {positions}")
    print(f"  Is last event: {last_flags}")
    print(f"  Has trailing bytes: {trail_flags}")
    print(f"  Segment sizes: {seg_sizes}")
    print(f"  Segments containing failures: {sorted(set(f['seg'] for f in failing))}")

    # Check: cumulative note values (how far from XG range?)
    cum_notes = [f['note_cum'] for f in failing]
    const_notes = [f['note_const'] for f in failing]
    print(f"\n  Cumulative notes: {cum_notes}")
    print(f"  Constant notes:   {const_notes}")
    print(f"  Above range (>87): cum={sum(1 for n in cum_notes if n>87)}, "
          f"const={sum(1 for n in const_notes if n>87)}")
    print(f"  Below range (<13): cum={sum(1 for n in cum_notes if n<13)}, "
          f"const={sum(1 for n in const_notes if n<13)}")

    # ============================================================
    # 4. Test: what if failing events use R = 9*(pos+2)?
    # ============================================================
    print(f"\n{'='*80}")
    print(f"  ALTERNATIVE FORMULAS FOR FAILING EVENTS")
    print(f"{'='*80}")

    for offset in range(-2, 8):
        valid = 0
        for f in failing:
            r_val = 9 * (f['pos'] + offset)
            if r_val < 0:
                continue
            nt, *_ = decode(f['evt'], r_val)
            if nt in XG_RANGE:
                valid += 1
        if valid > 0:
            print(f"  R=9*(pos+{offset:+d}): {valid}/{len(failing)} valid")

    # ============================================================
    # 5. Test: could trailing bytes be prepended to the next event?
    # ============================================================
    print(f"\n{'='*80}")
    print(f"  SHIFTED ALIGNMENT: include trailing bytes in event stream")
    print(f"{'='*80}")

    for seg_idx, seg in enumerate(segments):
        if len(seg) < 20:
            continue
        trail = (len(seg) - 13) % 7
        if trail == 0:
            continue

        nevts_std = (len(seg) - 13) // 7
        # Shift events by trail bytes: start at 13+trail instead of 13
        nevts_shifted = (len(seg) - 13 - trail) // 7
        if nevts_shifted < 1:
            continue

        # Standard alignment
        std_valid = 0
        for i in range(nevts_std):
            evt = seg[13 + i * 7: 13 + (i + 1) * 7]
            if len(evt) != 7:
                continue
            r_cum = 9 * (i + 1)
            note, *_ = decode(evt, r_cum)
            if note in XG_RANGE:
                std_valid += 1

        # Shifted: trail bytes at front, events start after them
        shift_valid = 0
        offset = 13 + trail
        nevts_s = (len(seg) - offset) // 7
        for i in range(nevts_s):
            evt = seg[offset + i * 7: offset + (i + 1) * 7]
            if len(evt) != 7:
                continue
            r_cum = 9 * (i + 1)
            note, *_ = decode(evt, r_cum)
            if note in XG_RANGE:
                shift_valid += 1

        if std_valid != shift_valid or trail > 0:
            print(f"  Seg {seg_idx}: trail={trail}B | "
                  f"standard={std_valid}/{nevts_std} | "
                  f"shifted={shift_valid}/{nevts_s}")

    # ============================================================
    # 6. R values that work for ALL events per segment
    # ============================================================
    print(f"\n{'='*80}")
    print(f"  PER-SEGMENT: R values giving 100% valid notes")
    print(f"{'='*80}")

    for seg_idx, seg in enumerate(segments):
        if len(seg) < 20:
            continue
        nevts = (len(seg) - 13) // 7
        if nevts < 3:
            continue

        # For each R_base, check if R=R_base*(i+1) gives all valid
        best_bases = []
        for base_r in range(1, 56):
            all_valid = True
            for i in range(nevts):
                evt = seg[13 + i * 7: 13 + (i + 1) * 7]
                if len(evt) != 7:
                    continue
                r_val = base_r * (i + 1)
                note, *_ = decode(evt, r_val)
                if note not in XG_RANGE:
                    all_valid = False
                    break
            if all_valid:
                best_bases.append(base_r)

        seg_has_fail = any(f['seg'] == seg_idx for f in failing)
        mark = " ← HAS FAILURES" if seg_has_fail else ""
        if best_bases:
            print(f"  Seg {seg_idx} ({nevts} events): "
                  f"R_base={best_bases}{mark}")
        else:
            print(f"  Seg {seg_idx} ({nevts} events): "
                  f"NO R_base gives 100%{mark}")


if __name__ == "__main__":
    main()
