#!/usr/bin/env python3
"""Compare R=9 vs R=34 for 2543 encoding, side by side."""

import sys, os
from collections import Counter, defaultdict
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from qymanager.formats.qy70.sysex_parser import SysExParser

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
}

def rot_right(val, shift, width=56):
    shift = shift % width
    return ((val >> shift) | (val << (width - shift))) & ((1 << width) - 1)

def f9(val, idx, total=56):
    shift = total - (idx + 1) * 9
    return (val >> shift) & 0x1FF if shift >= 0 else -1

def get_events(syx_path, section=0, track=0):
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

    events = []
    for seg_idx, seg in enumerate(segments):
        if len(seg) >= 20:
            header = seg[:13]
            for i in range((len(seg) - 13) // 7):
                evt = seg[13 + i * 7: 13 + (i + 1) * 7]
                if len(evt) == 7:
                    events.append((seg_idx, i, evt, header))
    return events


def main():
    base = os.path.dirname(os.path.abspath(__file__))
    events = get_events(os.path.join(base, "captured", "ground_truth_style.syx"), 0, 0)
    print(f"Events: {len(events)}\n")

    for R in [9, 34, 7, 53, 0]:
        print(f"\n{'='*80}")
        print(f"  R={R}")
        print(f"{'='*80}")

        f0_counter = Counter()
        beat_valid = 0
        total = len(events)

        print(f"\n  {'Seg':>3} {'#':>2} {'F0':>5} {'lo7':>4} {'Drum':>10} "
              f"{'F1':>4} {'F2':>4} {'F3':>4} {'lo4':>4} {'beat':>4} "
              f"{'F4':>4} {'F5':>4} {'rem':>3}")

        for seg_idx, evt_idx, evt, hdr in events[:20]:
            val = int.from_bytes(evt, "big")
            derot = rot_right(val, R)
            f0 = f9(derot, 0)
            f1 = f9(derot, 1)
            f2 = f9(derot, 2)
            f3 = f9(derot, 3)
            f4 = f9(derot, 4)
            f5 = f9(derot, 5)
            rem = derot & 0x3

            lo7 = f0 & 0x7F
            lo4 = f3 & 0xF
            beat_map = {0: 0, 1: 3, 2: 2, 4: 1, 8: 0}
            beat = beat_map.get(lo4, -1)
            if beat >= 0:
                beat_valid += 1
            name = GM_DRUMS.get(lo7, f"n{lo7}")[:10]

            f0_counter[lo7] += 1
            print(f"  {seg_idx:>3} {evt_idx:>2} {f0:>5} {lo7:>4} {name:>10} "
                  f"{f1:>4} {f2:>4} {f3:>4} {lo4:>4} {beat:>4} "
                  f"{f4:>4} {f5:>4} {rem:>3}")

        # Complete stats for all events
        all_f0 = Counter()
        all_beat = 0
        all_sim = defaultdict(list)
        for _, _, evt, _ in events:
            val = int.from_bytes(evt, "big")
            derot = rot_right(val, R)
            f0 = f9(derot, 0)
            f1 = f9(derot, 1)
            f2 = f9(derot, 2)
            f3 = f9(derot, 3)
            f4 = f9(derot, 4)
            f5 = f9(derot, 5)
            lo4 = f3 & 0xF
            if lo4 in (0, 1, 2, 4, 8):
                all_beat += 1
            all_f0[f0 & 0x7F] += 1
            all_sim[(f1, f2, f3, f4)].append(f0)

        gm = sum(v for k, v in all_f0.items() if 35 <= k <= 81)
        multi = sum(1 for v in all_sim.values() if len(v) > 1)
        print(f"\n  Summary: GM drums={gm}/{total} ({100*gm/total:.0f}%), "
              f"beat valid={all_beat}/{total} ({100*all_beat/total:.0f}%), "
              f"simultaneous groups={multi}")

        # F5 range check
        f5_vals = []
        for _, _, evt, _ in events:
            val = int.from_bytes(evt, "big")
            derot = rot_right(val, R)
            f5_vals.append(f9(derot, 5))
        print(f"  F5 range: {min(f5_vals)}-{max(f5_vals)}")

        # Show top F0 values
        print(f"\n  Top F0 lo7:")
        for lo7, cnt in sorted(all_f0.items(), key=lambda x: -x[1])[:10]:
            name = GM_DRUMS.get(lo7, f"n{lo7}")
            print(f"    {lo7:>3} ({name:>10}): ×{cnt}")

    # ============================================================
    # Test: what if 2543 events are NOT rotated, but BYTE-SHUFFLED?
    # ============================================================
    print(f"\n{'='*80}")
    print("  TEST: BYTE SHUFFLES")
    print(f"{'='*80}")

    # 7 bytes = ABCDEFG. Try all permutations of the first byte position
    # to find where the note number lives
    shuffles = [
        ("original", lambda b: b),
        ("reverse", lambda b: b[::-1]),
        ("swap01", lambda b: bytes([b[1],b[0]]) + b[2:]),
        ("rotate1", lambda b: b[1:] + b[:1]),
        ("rotate2", lambda b: b[2:] + b[:2]),
        ("rotate3", lambda b: b[3:] + b[:3]),
    ]

    for name, fn in shuffles:
        gm_count = 0
        for _, _, evt, _ in events:
            shuffled = fn(evt)
            # Check first byte as note
            if 35 <= shuffled[0] <= 81:
                gm_count += 1
        pct = 100 * gm_count / len(events)
        if pct > 30:
            print(f"  {name}: first byte in GM drum range = {gm_count}/{len(events)} ({pct:.0f}%)")

    # ============================================================
    # CRITICAL TEST: Do identical raw events ALWAYS appear in the data?
    # This proves constant rotation (regardless of R value)
    # ============================================================
    print(f"\n{'='*80}")
    print("  REPEATED RAW EVENTS (proving constant transformation)")
    print(f"{'='*80}")
    raw_counter = Counter()
    raw_positions = defaultdict(list)
    for seg_idx, evt_idx, evt, _ in events:
        raw_counter[evt] += 1
        raw_positions[evt].append((seg_idx, evt_idx))

    repeats = {k: v for k, v in raw_counter.items() if v > 1}
    print(f"\n  {len(repeats)} unique events appear more than once:")
    for evt, cnt in sorted(repeats.items(), key=lambda x: -x[1]):
        positions = raw_positions[evt]
        val = int.from_bytes(evt, "big")
        # Decode at R=9
        d9 = rot_right(val, 9)
        f0_9 = f9(d9, 0) & 0x7F
        # Decode at R=0 (no rotation)
        f0_0 = f9(val, 0) & 0x7F

        name9 = GM_DRUMS.get(f0_9, f"n{f0_9}")
        name0 = GM_DRUMS.get(f0_0, f"n{f0_0}")

        pos_str = ", ".join(f"s{s}e{e}" for s, e in positions[:6])
        print(f"  {evt.hex()} ×{cnt}  R9:F0={f0_9}({name9})  R0:F0={f0_0}({name0})  at: {pos_str}")


if __name__ == "__main__":
    main()
