#!/usr/bin/env python3
"""Test 6-byte header hypothesis for 2543 segments.

Observation: the 13-byte "header" might actually be:
  - 6 bytes of bar parameters
  - 7 bytes = first event at R=0 (rotation index 0)

Then subsequent events (what we called e0, e1...) are at indices 1, 2, 3...
with R = index * 9 — the SAME formula as 1FA3 chord encoding.

Seg 11 strongly supports this: header bytes 6-12 = 538cfa0bc3a26d
closely match the ODD events (538fda0bc3a26d etc.).

At R=0, 538cfa0bc3a26d → note 39 (Clap) — a valid drum note!

This test:
1. Extracts the "header event" (bytes 6-12) at R=0
2. Checks if it decodes to a valid drum note
3. Compares with the 1FA3 unified formula R = index * 9
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

def decode(evt_bytes, r_val):
    val = int.from_bytes(evt_bytes, "big")
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
    return note, midi_vel, f5, tick, vel_code, f0, f1, f2


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
    # 1. Extract header events (bytes 6-12) at R=0
    # ============================================================
    print(f"{'='*80}")
    print(f"  HEADER EVENT EXTRACTION (bytes 6-12, R=0)")
    print(f"{'='*80}")

    for seg_idx, seg in enumerate(segments):
        if len(seg) < 13:
            continue
        hdr_evt = seg[6:13]  # bytes 6-12 = potential event at R=0
        hdr_params = seg[:6]  # bytes 0-5 = bar parameters

        note, vel, gate, tick, vc, f0, f1, f2 = decode(hdr_evt, 0)
        name = GM_DRUMS.get(note, 'n' + str(note))
        valid = "✓" if note in XG_RANGE else "✗"

        print(f"\n  Seg {seg_idx}: params={hdr_params.hex()} evt={hdr_evt.hex()}")
        print(f"    R=0: note={note:>3}({name:>10}) {valid}"
              f"  vel={vel:>3} gate={gate:>3} tick={tick:>5}")

        # Also try R=9 for comparison
        note9, vel9, gate9, tick9, *_ = decode(hdr_evt, 9)
        name9 = GM_DRUMS.get(note9, 'n' + str(note9))
        valid9 = "✓" if note9 in XG_RANGE else "✗"
        print(f"    R=9: note={note9:>3}({name9:>10}) {valid9}"
              f"  vel={vel9:>3} gate={gate9:>3} tick={tick9:>5}")

    # ============================================================
    # 2. Full decode with 6-byte header + unified R=index*9
    # ============================================================
    print(f"\n{'='*80}")
    print(f"  UNIFIED MODEL: 6-byte header + R=index*9 (0-based)")
    print(f"{'='*80}")

    total_events = 0
    valid_events = 0
    mono_ok = 0
    mono_pairs = 0

    for seg_idx, seg in enumerate(segments):
        if len(seg) < 13:
            continue

        # All events start at byte 6, with 7 bytes each
        # Index 0 = bytes 6-12 (header event)
        # Index 1 = bytes 13-19 (first event after header)
        # Index 2 = bytes 20-26...

        total_bytes = len(seg) - 6
        nevts = total_bytes // 7
        trail = total_bytes % 7

        print(f"\n  Seg {seg_idx} ({len(seg)} bytes → {nevts} events, {trail} trail):")
        print(f"    Params: {seg[:6].hex()}")

        prev_tick = -1
        for i in range(nevts):
            evt = seg[6 + i * 7: 6 + (i + 1) * 7]
            r_val = i * 9  # unified formula
            note, vel, gate, tick, vc, f0, f1, f2 = decode(evt, r_val)
            name = GM_DRUMS.get(note, 'n' + str(note))
            valid = "✓" if note in XG_RANGE else "✗"

            total_events += 1
            if note in XG_RANGE:
                valid_events += 1

            if i > 0:
                mono_pairs += 1
                if tick >= prev_tick:
                    mono_ok += 1
            prev_tick = tick

            idx_label = f"H{i}" if i == 0 else f"e{i-1}"
            print(f"    {idx_label} R={r_val:>3}: note={note:>3}({name:>10}) {valid}"
                  f"  vel={vel:>3} gate={gate:>3} tick={tick:>5}")

        if trail > 0:
            print(f"    Trail: {seg[6 + nevts * 7:].hex()}")

    mono_pct = 100 * mono_ok / mono_pairs if mono_pairs > 0 else 0
    print(f"\n{'='*80}")
    print(f"  GLOBAL RESULTS (6-byte header, R=index*9)")
    print(f"{'='*80}")
    print(f"  Events: {total_events}")
    print(f"  Valid: {valid_events}/{total_events} ({100*valid_events/total_events:.0f}%)")
    print(f"  Monotonicity: {mono_ok}/{mono_pairs} ({mono_pct:.0f}%)")

    # ============================================================
    # 3. Compare: 6-byte header (R=i*9) vs 13-byte (R=9*(i+1))
    # ============================================================
    print(f"\n{'='*80}")
    print(f"  COMPARISON: 3 models (events after header only)")
    print(f"{'='*80}")

    for model_name, header_size, r_func in [
        ("13B header, const R=9", 13, lambda i: 9),
        ("13B header, cum R=9*(i+1)", 13, lambda i: 9 * (i + 1)),
        ("6B header, R=(i+1)*9", 6, lambda i: (i + 1) * 9),
        ("13B header, mixed", 13, None),
    ]:
        t_valid = 0
        t_total = 0

        for seg in segments:
            if len(seg) < header_size + 7:
                continue
            nevts = (len(seg) - header_size) // 7
            for i in range(nevts):
                evt = seg[header_size + i * 7: header_size + (i + 1) * 7]
                if len(evt) != 7:
                    continue
                t_total += 1

                if model_name == "13B header, mixed":
                    # Cumulative first, constant fallback
                    note_c, *_ = decode(evt, 9 * (i + 1))
                    if note_c in XG_RANGE:
                        t_valid += 1
                    else:
                        note_k, *_ = decode(evt, 9)
                        if note_k in XG_RANGE:
                            t_valid += 1
                else:
                    note, *_ = decode(evt, r_func(i))
                    if note in XG_RANGE:
                        t_valid += 1

        pct = 100 * t_valid / t_total if t_total > 0 else 0
        print(f"  {model_name}: {t_valid}/{t_total} ({pct:.0f}%)")

    # ============================================================
    # 4. 6-byte header params: are the first 6 bytes consistent?
    # ============================================================
    print(f"\n{'='*80}")
    print(f"  6-BYTE HEADER PARAMETERS")
    print(f"{'='*80}")

    print(f"\n  {'Seg':>4} | {'Byte0':>5} {'Byte1':>5} {'Byte2':>5}"
          f" {'Byte3':>5} {'Byte4':>5} {'Byte5':>5}")
    for seg_idx, seg in enumerate(segments):
        if len(seg) >= 6:
            params = [f"0x{b:02X}" for b in seg[:6]]
            print(f"  {seg_idx:>4} | {' '.join(params)}")


if __name__ == "__main__":
    main()
